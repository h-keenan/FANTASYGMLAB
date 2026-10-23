"""Source-backed contract layer for ``GET /v1/external/players/{id}/news``.

Pure functions (no I/O). Everything here is additive on top of the existing
Phase 2 fields and is built ONLY from facts the server really holds: RSS
feed items (headline, feed summary, article URL, publisher timestamp) and
the player table. The server never fetches publisher article bodies, so
nothing here ever claims a checked document: ``content_sha256`` is always
``null`` today and every item is explicitly review-only. See
``docs/external-api-contract.md`` ("Source-backed news contract").
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

LEAGUE = "NFL"

# Publisher domains the server's own feed list (modules.news.NEWS_FEEDS) is
# built from. This is the documented allowlist; anything else is reported in
# `domain_review`, never silently trusted and never auto-added.
ALLOWLISTED_PUBLISHER_DOMAINS = frozenset(
    {
        "rotowire.com",
        "espn.com",
        "cbssports.com",
        "sports.yahoo.com",
        "nbcsports.com",
        "profootballrumors.com",
    }
)
# Official primary-source domains (league). RSS feeds do not carry these
# today; the set exists so a primary URL, if one ever appears, is typed.
OFFICIAL_PRIMARY_DOMAINS = frozenset({"nfl.com", "nflpa.com"})

# Primary document types the bot already understands + proposed typed,
# non-medical equivalents. `headline_only_feed_item` is what this server
# actually supplies today.
PRIMARY_DOCUMENT_TYPES = ("injury_report", "inactive_list", "transaction", "team_announcement")
PROPOSED_PRIMARY_DOCUMENT_TYPES = (
    "depth_chart",
    "roster_move_notice",
    "coach_press_conference",
    "game_status_designation",
)
DOCUMENT_TYPE_HEADLINE_ONLY = "headline_only_feed_item"

AVAILABILITY_EVENT_TYPES = frozenset(
    {"INJURY", "INJURY_SEVERITY_UPDATE", "IR_PUP_NFI", "RETURN_TO_PRACTICE", "RETURN_TO_PLAY", "INACTIVE", "ACTIVE"}
)

GENERAL_MAX_PUBLISHED_AGE_S = 24 * 3600
GENERAL_MAX_CHECKED_AGE_S = 3600
URGENT_MAX_PUBLISHED_AGE_S = 6 * 3600
URGENT_MAX_CHECKED_AGE_S = 15 * 60

STATUS_ENUM = ("confirmed", "reported", "speculative", "superseded", "retracted")
CLAIM_FIELD_ENUM = ("event_type", "availability_designation", "team_affiliation")
AVAILABILITY_DESIGNATIONS = ("out", "doubtful", "questionable", "inactive", "cleared_to_play", "active")
# Exact lower-cased matched phrases -> enum. Nothing is inferred beyond these.
_DESIGNATION_BY_PHRASE = {
    "ruled out": "out",
    "out": "out",
    "doubtful": "doubtful",
    "questionable": "questionable",
    "inactive": "inactive",
    "cleared to play": "cleared_to_play",
    "activated": "active",
}

_GSIS_RE = re.compile(r"^00-\d{7}$")
_AGGREGATOR_KEYS = ("news.google", "google news")


def _host(url: str) -> str:
    try:
        host = (urlparse(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _in_domains(host: str, domains: frozenset[str]) -> bool:
    return bool(host) and any(host == d or host.endswith("." + d) for d in domains)


def _short_hash(*parts: Any, n: int = 16) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:n]


def resolve_player_identity(players_df: Any, player_id: str, player_name: str) -> dict[str, Any]:
    """Canonical ids. GSIS only when the table carries a well-formed
    ``gsis_id`` for this exact row AND the (name, team) pair is unique among
    rows in the table. Otherwise null with a machine-readable reason. Today's
    player table has no ``gsis_id`` column, so this is null with
    ``no_gsis_crosswalk_available`` — never guessed."""

    def result(gsis: str | None, reason: str | None, team: str | None) -> dict[str, Any]:
        return {
            "player_ids": {"sleeper": str(player_id), "gsis": gsis, "gsis_unavailable_reason": reason},
            "player": {"name": player_name or None, "team": team or None},
        }

    try:
        rows = players_df[players_df["player_id"].astype(str) == str(player_id)]
    except Exception:
        rows = None
    if rows is None or len(rows) == 0:
        return result(None, "player_not_in_table", None)
    row = rows.iloc[0]
    team = str(row.get("team") or "").strip().upper()
    if "gsis_id" not in players_df.columns:
        return result(None, "no_gsis_crosswalk_available", team)
    candidate = str(row.get("gsis_id") or "").strip()
    if not candidate or candidate.lower() in ("nan", "none"):
        return result(None, "gsis_not_mapped_for_player", team)
    if not _GSIS_RE.match(candidate):
        return result(None, "gsis_malformed", team)
    same_name = players_df["name"].astype(str).str.casefold() == player_name.casefold()
    if "team" in players_df.columns:
        same_name = same_name & (players_df["team"].fillna("").astype(str).str.upper() == team)
    if not team or int(same_name.sum()) != 1:
        return result(None, "ambiguous_name_team_mapping", team)
    return result(candidate, None, team)


def build_provenance(members: Sequence[Mapping[str, Any]], *, retracted: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in members:
        link = str(m.get("link") or "")
        host = _host(link)
        key = str(m.get("source_key") or "")
        feed = str(m.get("feed") or "").casefold()
        aggregator = any(a in key or a in feed for a in _AGGREGATOR_KEYS)
        ts = float(m.get("published_ts") or 0.0)
        official = _in_domains(host, OFFICIAL_PRIMARY_DOMAINS)
        out.append(
            {
                "id": "prov_" + _short_hash(link),
                "publisher_domain": host or None,
                "original_url": None if aggregator else (link or None),
                "original_url_unavailable_reason": "aggregator_syndication_origin_unknown" if aggregator else None,
                "retrieved_url": link or None,
                "published_at": int(ts) if ts > 0 else None,
                # Nothing is fetched: no document was checked, so no checked_at/hash.
                "checked_at": None,
                "content_sha256": None,
                "content_sha256_unavailable_reason": "document_not_fetched_feed_headline_only",
                "excerpt": None,
                "excerpt_unavailable_reason": "no_licensed_excerpt_supplied",
                "document_type": DOCUMENT_TYPE_HEADLINE_ONLY,
                "is_official_primary": bool(official),
                "allowlist_status": "allowlisted"
                if (official or _in_domains(host, ALLOWLISTED_PUBLISHER_DOMAINS))
                else "not_allowlisted",
                "retracted": bool(retracted),
            }
        )
    return out


def build_claims(
    event: Any, *, team: str | None, source_ids: Sequence[str], superseded_by: str | None
) -> list[dict[str, Any]]:
    """Structured claims derived only from the classifier's output and exact
    matched phrases. No diagnoses, body parts, timelines or causes."""

    base = {
        "source_ids": list(source_ids),
        "unit": None,
        "team": team,
        "status": "superseded" if superseded_by else "active",
        "superseded_by": superseded_by or None,
        "corrects": None,
    }
    claims: list[dict[str, Any]] = []

    def add(field: str, value: Any) -> None:
        claims.append(
            {"id": "claim_" + _short_hash(event.event_identity, field, value), "field": field, "value": value, **base}
        )

    add("event_type", event.event_type)
    seen: set[str] = set()
    for phrase in event.matched_evidence:
        value = _DESIGNATION_BY_PHRASE.get(str(phrase).strip().casefold())
        if value and value not in seen:
            seen.add(value)
            add("availability_designation", value)
    if team:
        add("team_affiliation", team)
    return claims


def build_freshness(
    *, event_type: str, published_ts: int | None, checked_ts: int | None, now_ts: int
) -> dict[str, Any]:
    urgent = event_type in AVAILABILITY_EVENT_TYPES
    max_pub = URGENT_MAX_PUBLISHED_AGE_S if urgent else GENERAL_MAX_PUBLISHED_AGE_S
    max_chk = URGENT_MAX_CHECKED_AGE_S if urgent else GENERAL_MAX_CHECKED_AGE_S
    pub_age = now_ts - published_ts if published_ts else None
    chk_age = now_ts - checked_ts if checked_ts else None
    return {
        "class": "urgent_availability" if urgent else "general",
        "max_published_age_seconds": max_pub,
        "max_checked_age_seconds": max_chk,
        "published_age_seconds": pub_age,
        "checked_age_seconds": chk_age,
        "published_within_limit": None if pub_age is None else 0 <= pub_age <= max_pub,
        # null: no document was ever checked, so there is nothing to be fresh.
        "checked_within_limit": None if chk_age is None else 0 <= chk_age <= max_chk,
    }


def build_contract_fields(
    *,
    group: Mapping[str, Any],
    identity: Mapping[str, Any],
    superseded_by: str,
    now_ts: int,
) -> dict[str, Any]:
    event = group["event"]
    members = list(group.get("members") or [])
    superseded = bool(superseded_by)
    provenance = build_provenance(members, retracted=False)
    source_ids = [p["id"] for p in provenance]
    published_ts = int(event.article_time) if event.article_time and event.article_time > 0 else None

    official = any(p["is_official_primary"] for p in provenance)
    independent = sorted(
        {p["publisher_domain"] for p in provenance if p["publisher_domain"] and p["original_url"]}
    )
    if superseded:
        status = "superseded"
    elif event.speculative:
        status = "speculative"
    elif official:
        status = "confirmed"
    else:
        status = "reported"

    review_reasons = ["document_not_fetched_headline_only"]
    if status != "confirmed":
        review_reasons.append("no_official_primary_source")
    if status in ("speculative", "superseded"):
        review_reasons.append(f"status_{status}")
    if published_ts is None:
        review_reasons.append("published_ts_unavailable")
    if not identity["player_ids"]["gsis"]:
        review_reasons.append("gsis_unavailable")
    unlisted = sorted(
        {p["publisher_domain"] for p in provenance if p["allowlist_status"] == "not_allowlisted" and p["publisher_domain"]}
    )
    if unlisted:
        review_reasons.append("non_allowlisted_domain")

    claims = build_claims(event, team=identity["player"]["team"], source_ids=source_ids, superseded_by=superseded_by)
    revision_id = _short_hash(
        json.dumps(
            {
                "s": status,
                "sup": superseded_by or None,
                "p": sorted(source_ids),
                "c": sorted((c["field"], str(c["value"]), c["status"]) for c in claims),
            },
            sort_keys=True,
        )
    )
    return {
        "league": LEAGUE,
        "id": event.event_identity,
        "revision_id": revision_id,
        "previous_revision_id": None,
        **identity,
        "status": status,
        "speculative": bool(event.speculative),
        "retracted": False,
        "published_ts": published_ts,
        "content": {
            "kind": "headline_only",
            "headline": (event.article_title or None),
            "body": None,
            "body_unavailable_reason": "article_body_not_fetched_or_licensed",
        },
        "provenance": provenance,
        "claims": claims,
        "corroboration": {
            "independent_publisher_domains": independent,
            "independent_publisher_count": len(independent),
            "independence_verified": False,
            "note": "Distinct publisher hosts only; shared-origin syndication across different hosts cannot be ruled out without fetched documents.",
        },
        "evidence": {
            "status": "unavailable",
            "reason_codes": ["document_not_fetched", "no_licensed_excerpt"],
        },
        "freshness": build_freshness(
            event_type=event.event_type, published_ts=published_ts, checked_ts=None, now_ts=now_ts
        ),
        "domain_review": unlisted,
        "review_only": True,
        "review_only_reasons": review_reasons,
    }
