"""Per-account acquisition record (Phase 1, 2026-11): who signed up, how, and from where.

Writes ONE row per Supabase auth user into ``public.account_acquisition`` (docs/supabase_account_acquisition_2026_11.sql)
the first time that account sends an analytics event, carrying:
  * the real account creation time and sign-up method (email | google | apple) read from the verified GoTrue user,
  * guest vs registered (``is_guest``; flips to registered when a guest upgrades -- same user id),
  * FIRST-touch (utm_*, referrer_host, click id) and LAST-touch (lt_*) attribution props the client sent.

Why a table: ``analytics_events`` holds only a KEYED HASH of the user id (privacy), so it can never be joined to
profiles/billing. This table keys on the raw ``user_id`` (service-role + owner-read RLS only, cascade-deleted with
the account), so signups, revenue and retention can be cut by acquisition source without exposing the hash.

Fail-soft by contract: never raises, never blocks the request (background thread), and a missing table (migration
not yet run) just disables writes for a few minutes. Dedupe: an in-process cache plus ``ignore-duplicates``.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Mapping

import requests

from modules import launch_analytics as la

TABLE = "account_acquisition"
_DISABLED_RETRY_S = 600.0
_CACHE_MAX = 50_000

_LOCK = threading.Lock()
_STATE: dict[str, str] = {}  # user_id -> "guest" | "registered" already recorded by this process
_disabled_until = 0.0

_FIRST_KEYS = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "referrer_host",
    "click_id",
    "click_id_value",
)
_LAST_KEYS = ("lt_utm_source", "lt_utm_medium", "lt_utm_campaign", "lt_referrer_host", "lt_click_id")
_METHODS = {"email", "google", "apple"}


def signup_method_for(user: Mapping[str, Any]) -> str:
    meta = user.get("app_metadata") if isinstance(user.get("app_metadata"), Mapping) else {}
    provider = str(meta.get("provider") or "").strip().casefold()
    if provider in _METHODS:
        return provider
    for ident in user.get("identities") or []:
        if isinstance(ident, Mapping):
            p = str(ident.get("provider") or "").strip().casefold()
            if p in _METHODS:
                return p
    return "other" if provider else "unknown"


def account_kind_for(user: Mapping[str, Any] | None) -> str:
    """visitor (no session) | guest (anonymous Supabase session) | registered."""

    if not user or not str(user.get("id") or "").strip():
        return "visitor"
    return "guest" if user.get("is_anonymous") is True else "registered"


def build_row(user: Mapping[str, Any], props: Mapping[str, Any]) -> dict[str, Any]:
    guest = user.get("is_anonymous") is True
    row: dict[str, Any] = {
        "user_id": str(user.get("id") or "").strip(),
        "is_guest": guest,
        "signup_method": "guest" if guest else signup_method_for(user),
        "platform": str(props.get("platform") or "")[:16],
    }
    created = str(user.get("created_at") or "").strip()
    if created:
        row["account_created_at"] = created
    for key in _FIRST_KEYS:
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            row[key] = value.strip()[:200]
    for key in _LAST_KEYS:
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            row[key] = value.strip()[:200]
    return row


def _headers(config: la.AnalyticsSupabaseConfig, prefer: str) -> dict[str, str]:
    return la._analytics_supabase_headers(config, prefer=prefer)


def _write(config: la.AnalyticsSupabaseConfig, row: dict[str, Any]) -> bool:
    global _disabled_until
    user_id = row["user_id"]
    try:
        resp = requests.post(
            f"{config.url}/rest/v1/{TABLE}",
            headers=_headers(config, "resolution=ignore-duplicates,return=minimal"),
            json=row,
            timeout=8,
        )
        if resp.status_code in (404, 400) and "account_acquisition" in (resp.text or ""):
            _disabled_until = time.time() + _DISABLED_RETRY_S
            return False
        if resp.status_code >= 400:
            return False
        if not row["is_guest"]:
            # Guest upgraded (or row pre-existed as guest): flip to registered once. No-op when already registered.
            patch = {
                "is_guest": False,
                "signup_method": row["signup_method"],
                "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                # Last touch at the moment of registration (first touch is kept from the first insert).
                **{k: v for k, v in row.items() if k.startswith("lt_")},
            }
            requests.patch(
                f"{config.url}/rest/v1/{TABLE}",
                headers=_headers(config, "return=minimal"),
                params={"user_id": f"eq.{user_id}", "is_guest": "eq.true"},
                json=patch,
                timeout=8,
            )
        return True
    except Exception:
        return False


def record_account_acquisition(user: Mapping[str, Any] | None, props: Mapping[str, Any]) -> bool:
    """Schedule the (at most once per process per state) background write. Returns True if scheduled."""

    try:
        if not user or not la.analytics_enabled():
            return False
        user_id = str(user.get("id") or "").strip()
        if not user_id or time.time() < _disabled_until:
            return False
        state = "guest" if user.get("is_anonymous") is True else "registered"
        with _LOCK:
            if _STATE.get(user_id) in (state, "registered"):
                return False
            if len(_STATE) >= _CACHE_MAX:
                _STATE.clear()
            _STATE[user_id] = state
        config = la.load_analytics_supabase_config()
        if not config.configured:
            return False
        row = build_row(user, props)
        la._spawn_background(lambda: _write(config, row))
        return True
    except Exception:
        return False


def reset_cache() -> None:
    """Test hook."""

    global _disabled_until
    with _LOCK:
        _STATE.clear()
    _disabled_until = 0.0


def fetch_accounts(since_ts: float | None, *, limit: int = 100_000) -> list[dict[str, Any]] | None:
    """Accounts created since ``since_ts`` (None = all). ``None`` = table unavailable; never raises."""

    try:
        config = la.load_analytics_supabase_config()
        if not config.configured:
            return None
        base: dict[str, str] = {
            "select": "is_guest,signup_method,account_created_at,first_seen_at,utm_source,utm_medium,utm_campaign,"
            "referrer_host,click_id,lt_utm_source,lt_utm_campaign,platform",
            "order": "first_seen_at.asc",
        }
        if since_ts is not None:
            from datetime import datetime, timezone

            base["first_seen_at"] = "gte." + datetime.fromtimestamp(since_ts, tz=timezone.utc).isoformat()
        out: list[dict[str, Any]] = []
        offset = 0
        while len(out) < limit:
            page = min(la.SUPABASE_PAGE_SIZE, limit - len(out))
            resp = requests.get(
                f"{config.url}/rest/v1/{TABLE}",
                headers=la._analytics_supabase_headers(config),
                params={**base, "limit": str(page), "offset": str(offset)},
                timeout=15,
            )
            if resp.status_code >= 400:
                return None
            parsed = resp.json()
            if not isinstance(parsed, list):
                return None
            out.extend(dict(r) for r in parsed if isinstance(r, Mapping))
            if len(parsed) < page:
                break
            offset += len(parsed)
        return out
    except Exception:
        return None
