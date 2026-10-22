"""Opt-in Community shared trades.

A user explicitly shares a Trade Analyzer result ("Share to community", off by
default). This module owns validation, sanitizing and the Supabase I/O for
docs/supabase_community_trades.sql. Every call uses the CALLER's own access
token, so RLS does the access control; nothing here uses service role.

Public output never contains user_id, league ids or team names. The display
name is whatever the user typed (or "Anonymous").
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import requests

from modules import auth_supabase

TRADES_TABLE = "community_shared_trades"
REPORTS_TABLE = "community_shared_trade_reports"
SETUP_DOC = "docs/supabase_community_trades.sql"

ANONYMOUS_NAME = "Anonymous"
DISPLAY_NAME_MAX = 24
WHY_MAX = 280
BAND_MAX = 32
REASON_MAX = 120
ASSET_MAX = 12
ASSET_NAME_MAX = 60
FEED_LIMIT_DEFAULT = 30
FEED_LIMIT_MAX = 50
# Per-user cap on new shares (counted in the table, so it holds across
# workers and restarts). The global per-IP mutation limiter still applies.
SHARES_PER_HOUR = 5
# Must match the trigger in docs/supabase_community_trades.sql.
HIDE_AFTER_REPORTS = 3
ALLOWED_GRADES = ("ACCEPT", "DECLINE", "COUNTER", "FAIR")

# Deliberately small: basic safety, not a moderation system. Matched per word
# on a de-leeted, letters-only copy ("sh1t", "f.u.c.k"). Short words must match
# a whole word so player names (Dickerson, Bucky) never trip it.
_BLOCKED_STEMS = (
    "fuck", "shit", "bitch", "cunt", "asshole", "pussy", "whore", "nigger", "nigga", "faggot",
)
_BLOCKED_WORDS = frozenset({"dick", "slut", "rape", "rapist", "nazi", "kys", "retard", "retarded"})
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
_CONTROL = re.compile(r"[\x00-\x1f\x7f<>]")
_URL = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)


class ShareError(ValueError):
    """Invalid share input; message is safe to show the user."""


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def clean_text(value: Any, max_len: int) -> str:
    """Strip control chars and angle brackets, collapse whitespace, cap length."""

    text = unicodedata.normalize("NFKC", _text(value))
    text = _CONTROL.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len].strip()


def contains_blocked_language(text: str) -> bool:
    folded = unicodedata.normalize("NFKD", text).casefold().translate(_LEET)
    for raw in re.split(r"\s+", folded):
        word = re.sub(r"[^a-z]", "", raw)
        if word and (word in _BLOCKED_WORDS or any(stem in word for stem in _BLOCKED_STEMS)):
            return True
    return False


def clean_display_name(value: Any) -> str:
    """"" means Anonymous. Raises ShareError for blocked language or links."""

    name = clean_text(value, DISPLAY_NAME_MAX)
    if not name or name.casefold() == ANONYMOUS_NAME.casefold():
        return ""
    if _URL.search(name) or "@" in name:
        raise ShareError("Display name can't include links or emails.")
    if contains_blocked_language(name):
        raise ShareError("Pick a different display name.")
    return name


def clean_why(value: Any) -> str:
    why = _URL.sub("", clean_text(value, WHY_MAX * 2))[:WHY_MAX].strip()
    if contains_blocked_language(why):
        return ""
    return why


def clean_assets(assets: Any) -> list[dict[str, Any]]:
    if not isinstance(assets, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for asset in assets[:ASSET_MAX]:
        if not isinstance(asset, Mapping):
            continue
        asset_type = "pick" if _text(asset.get("asset_type")) == "pick" else "player"
        name = clean_text(asset.get("name") or asset.get("label"), ASSET_NAME_MAX)
        if not name:
            continue
        entry: dict[str, Any] = {"asset_type": asset_type, "name": name}
        position = clean_text(asset.get("position"), 8)
        if position:
            entry["position"] = position
        player_id = clean_text(asset.get("player_id"), 32)
        if player_id and asset_type == "player":
            entry["player_id"] = player_id
        cleaned.append(entry)
    return cleaned


def build_share_row(user_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """Validated insert payload, or ShareError."""

    send = clean_assets(body.get("send"))
    receive = clean_assets(body.get("receive"))
    if not send or not receive:
        raise ShareError("A shared trade needs assets on both sides.")
    grade = _text(body.get("grade")).upper()
    if grade not in ALLOWED_GRADES:
        raise ShareError("Unknown trade grade.")
    return {
        "user_id": user_id,
        "display_name": clean_display_name(body.get("display_name")) or None,
        "send": send,
        "receive": receive,
        "grade": grade,
        "band": clean_text(body.get("band"), BAND_MAX),
        "why": clean_why(body.get("why")),
    }


def project_item(row: Mapping[str, Any], viewer_user_id: str) -> dict[str, Any]:
    """Public projection of a row. Never includes user_id."""

    return {
        "id": _text(row.get("id")),
        "display_name": _text(row.get("display_name")) or ANONYMOUS_NAME,
        "send": clean_assets(row.get("send")),
        "receive": clean_assets(row.get("receive")),
        "grade": _text(row.get("grade")),
        "band": _text(row.get("band")),
        "why": _text(row.get("why")),
        "created_at": row.get("created_at"),
        "mine": bool(viewer_user_id) and _text(row.get("user_id")) == viewer_user_id,
    }


def is_missing_table(response: requests.Response) -> bool:
    """True when PostgREST says the table isn't there (migration not applied)."""

    if response.status_code == 404:
        return True
    try:
        payload = response.json()
    except Exception:
        return False
    if not isinstance(payload, Mapping):
        return False
    code = _text(payload.get("code"))
    message = _text(payload.get("message")).casefold()
    return code in {"PGRST205", "42P01"} or "schema cache" in message or (
        "relation" in message and "does not exist" in message
    )


class Unavailable(RuntimeError):
    """Storage missing or unreachable; callers degrade quietly."""


def _headers(config: dict, token: str, prefer: str = "") -> dict[str, str]:
    headers = auth_supabase.auth_headers(config, token)
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _check(response: requests.Response) -> None:
    if response.status_code >= 400:
        raise Unavailable(SETUP_DOC if is_missing_table(response) else "request_failed")


def fetch_feed(config: dict, token: str, viewer_user_id: str, limit: int = FEED_LIMIT_DEFAULT) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), FEED_LIMIT_MAX))
    query = f"select=*&hidden=eq.false&order=created_at.desc&limit={limit}"
    try:
        response = requests.get(
            auth_supabase.rest_api_url(config, TRADES_TABLE, query), headers=_headers(config, token), timeout=15
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)
    rows = response.json()
    if not isinstance(rows, list):
        return []
    return [project_item(r, viewer_user_id) for r in rows if isinstance(r, Mapping) and r.get("hidden") is not True]


def count_recent_shares(config: dict, token: str, user_id: str, *, now: datetime | None = None) -> int:
    since = ((now or datetime.now(timezone.utc)) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = f"select=id&user_id=eq.{user_id}&created_at=gte.{since}"
    try:
        response = requests.get(
            auth_supabase.rest_api_url(config, TRADES_TABLE, query), headers=_headers(config, token), timeout=15
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)
    rows = response.json()
    return len(rows) if isinstance(rows, list) else 0


def insert_share(config: dict, token: str, row: dict[str, Any], viewer_user_id: str) -> dict[str, Any]:
    try:
        response = requests.post(
            auth_supabase.rest_api_url(config, TRADES_TABLE),
            headers=_headers(config, token, "return=representation"),
            json=row,
            timeout=15,
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)
    rows = response.json()
    created = rows[0] if isinstance(rows, list) and rows else row
    return project_item(created, viewer_user_id)


def delete_share(config: dict, token: str, trade_id: str, user_id: str) -> None:
    query = f"id=eq.{trade_id}&user_id=eq.{user_id}"
    try:
        response = requests.delete(
            auth_supabase.rest_api_url(config, TRADES_TABLE, query),
            headers=_headers(config, token, "return=minimal"),
            timeout=15,
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)


def insert_report(config: dict, token: str, trade_id: str, reporter_id: str, reason: str) -> None:
    """One report per user per trade (unique constraint; duplicates ignored).
    The DB trigger hides the trade once HIDE_AFTER_REPORTS is reached."""

    try:
        response = requests.post(
            auth_supabase.rest_api_url(config, REPORTS_TABLE, "on_conflict=trade_id,reporter_id"),
            headers=_headers(config, token, "return=minimal,resolution=ignore-duplicates"),
            json={"trade_id": trade_id, "reporter_id": reporter_id, "reason": clean_text(reason, REASON_MAX)},
            timeout=15,
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)
