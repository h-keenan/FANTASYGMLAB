"""Cursor feed for ``GET /v1/external/news`` (content bot).

Pure read side over the ingest store (``modules.news_ingest``): no network
fetching, no file writes. Every field is either something we really hold or
``null`` with a reason; nothing here claims a document was checked.

Honest defaults:
* ``retracted`` is always ``false`` and ``retraction_detection`` says it is
  not performed (never inferred);
* ``superseded`` is true only when a newer stored revision of the same URL
  exists;
* ``speculative`` comes from the deterministic classifier over the feed
  headline/summary;
* ``provenance[].content_sha256`` / ``checked_at`` / ``excerpt`` are null:
  only the publisher RSS feed was read, never the article;
* ``claims`` come only from Sleeper's structured status for a matched
  player, scoped ``player_current_state`` (not asserted by the article).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from modules import external_news_contract as enc
from modules import news_identity, news_ingest, news_signal

LEAGUE = enc.LEAGUE
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
DEFAULT_LOOKBACK_SECONDS = 24 * 3600
CURSOR_PREFIX = "c1."

_STRUCTURED_DESIGNATIONS = {"out": "out", "doubtful": "doubtful", "questionable": "questionable"}


class CursorError(ValueError):
    pass


def encode_cursor(seq: int) -> str:
    return f"{CURSOR_PREFIX}{int(seq)}"


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    text = str(cursor).strip()
    if not text.startswith(CURSOR_PREFIX) or not text[len(CURSOR_PREFIX) :].isdigit():
        raise CursorError("cursor is not a value returned by this endpoint")
    return int(text[len(CURSOR_PREFIX) :])


def parse_since(since: str | None) -> float:
    """ISO-8601 timestamp or epoch seconds -> epoch seconds."""

    if since is None or str(since).strip() == "":
        return 0.0
    text = str(since).strip()
    try:
        if text.replace(".", "", 1).isdigit():
            return float(text)
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise CursorError("since must be an ISO-8601 timestamp or epoch seconds") from exc


def _structured_claims(player: news_identity.PlayerMatch, row: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    base = {
        "source": "sleeper_api",
        "scope": "player_current_state",
        "article_supported": False,
        "as_of": None,
        "as_of_unavailable_reason": "players_db_snapshot_time_not_recorded",
    }
    claims: list[dict[str, Any]] = []

    def add(field: str, value: str) -> None:
        claims.append({"id": "claim_" + enc._short_hash(player.player_id, field, value), "field": field, "value": value,
                        "player_id": player.player_id, **base})

    if row is not None:
        injury = str(row.get("injury_status") or "").strip().lower()
        if injury in _STRUCTURED_DESIGNATIONS:
            add("availability_designation", _STRUCTURED_DESIGNATIONS[injury])
        status = str(row.get("status") or "").strip()
        if status and status.lower() not in ("nan", "none"):
            add("roster_status", status)
    if player.team:
        add("team_affiliation", player.team)
    return claims


def _player_payload(match: news_identity.PlayerMatch, index: news_identity.IdentityIndex) -> dict[str, Any]:
    gsis, reason = index.gsis(match.player_id)
    return {
        "sleeper": match.player_id,
        "gsis": gsis,
        "gsis_unavailable_reason": reason,
        "name": match.name,
        "team": match.team or None,
        "position": match.position or None,
        "match_method": match.method,
    }


def _provenance(rev: Mapping[str, Any], dups: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    members = [
        {"link": rev.get("link"), "source_key": rev.get("source_key"), "feed": rev.get("feed_url"),
         "published_ts": rev.get("published_ts")}
    ] + [
        {"link": d.get("link"), "source_key": d.get("source_key"), "feed": d.get("feed_url"),
         "published_ts": d.get("published_ts")}
        for d in dups
    ]
    out = enc.build_provenance(members, retracted=False)
    firsts = [rev.get("first_seen_at")] + [d.get("first_seen_at") for d in dups]
    feeds = [rev.get("feed_url")] + [d.get("feed_url") for d in dups]
    for entry, first_seen, feed_url in zip(out, firsts, feeds):
        entry["feed_url"] = feed_url
        entry["first_seen_at"] = first_seen
        entry["retrieval"] = "publisher_rss_feed_only"
        entry["checked_at_unavailable_reason"] = "article_document_not_fetched_only_rss_feed_read"
    return out


def build_feed(
    store: news_ingest.NewsStore,
    *,
    players_df: pd.DataFrame | None,
    index: news_identity.IdentityIndex | None,
    cursor: str | None = None,
    since: str | None = None,
    limit: int = DEFAULT_LIMIT,
    now: float | None = None,
) -> dict[str, Any]:
    now = time.time() if now is None else now
    limit = max(1, min(int(limit), MAX_LIMIT))
    after_seq = decode_cursor(cursor)
    since_ts = parse_since(since)
    since_given = since is not None and str(since).strip() != ""
    if not cursor and not since_given:
        since_ts = now - DEFAULT_LOOKBACK_SECONDS

    unavailable: list[dict[str, str]] = []
    try:
        revisions = store.read_revisions(after_seq, 0.0 if cursor else since_ts, limit + 1)
        health = store.read_health()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True, "league": LEAGUE, "items": [], "next_cursor": cursor or None, "has_more": False,
            "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "ingest": {"backend": store.backend, "durable": store.durable, "fallback_reason": store.fallback_reason, "sources": []},
            "unavailable": [{"reason": "ingest_store_unavailable", "detail": str(exc)[:160]}],
        }

    has_more = len(revisions) > limit
    revisions = revisions[:limit]
    ids = sorted({r["item_id"] for r in revisions})
    latest = store.latest_revisions(ids) if ids else {}
    dups = store.duplicates_of(ids) if ids else {}
    item_rows = store.get_items(ids) if ids else {}

    if store.fallback_reason:
        unavailable.append({"reason": "durable_store_unavailable_using_local_file", "detail": store.fallback_reason})
    if index is None or not index.by_id:
        unavailable.append({"reason": "players_table_unavailable", "detail": "player ids are null for every item"})
    if not health:
        unavailable.append({"reason": "no_ingest_data_yet", "detail": "the scheduled ingest has not recorded any source run"})
    elif not revisions and not cursor:
        unavailable.append({"reason": "no_items_in_window", "detail": "no stored revisions at or after the requested since"})

    rows_by_id = {}
    if players_df is not None and not getattr(players_df, "empty", True) and "player_id" in players_df.columns:
        rows_by_id = {str(r["player_id"]): r for r in players_df.to_dict("records")}

    items: list[dict[str, Any]] = []
    for rev in revisions:
        item_row = item_rows.get(rev["item_id"], {})
        # Duplicate copies ride inside their canonical item's provenance.
        if item_row.get("duplicate_of"):
            continue
        rev = {**rev, "first_seen_at": item_row.get("first_seen_at") or rev.get("created_at")}
        text_item = {"title": rev.get("title"), "summary": rev.get("summary"), "link": rev.get("link"),
                     "source": rev.get("feed_url"), "published_ts": rev.get("published_ts") or 0}
        enriched = news_signal.enrich_news_item(text_item)
        speculative = bool(enriched.get("signal_speculative"))
        superseded = latest.get(rev["item_id"]) not in (None, rev["revision_id"])

        matches: list[news_identity.PlayerMatch] = []
        ambiguous: list[str] = []
        reason = None
        if index is not None and index.by_id:
            matches, ambiguous = news_identity.match_article_players(text_item, index)
            if not matches:
                reason = "ambiguous_player_name" if ambiguous else "no_unambiguous_player_named"
        else:
            reason = "players_table_unavailable"

        claims: list[dict[str, Any]] = []
        for m in matches:
            claims.extend(_structured_claims(m, rows_by_id.get(m.player_id)))

        published_ts = int(rev["published_ts"]) if rev.get("published_ts") else None
        event_type = enriched.get("signal_primary_event")
        items.append(
            {
                "league": LEAGUE,
                "id": rev["item_id"],
                "revision_id": rev["revision_id"],
                "previous_revision_id": rev.get("previous_revision_id"),
                "cursor": encode_cursor(rev["seq"]),
                "player_ids": [_player_payload(m, index) for m in matches],
                "player_match_unavailable_reason": reason,
                "unmatched": not matches,
                "event_type": event_type,
                "status": "superseded" if superseded else ("speculative" if speculative else "reported"),
                "speculative": speculative,
                "superseded": superseded,
                "superseded_by_revision_id": latest.get(rev["item_id"]) if superseded else None,
                "retracted": False,
                "retraction_detection": "not_performed",
                "published_ts": published_ts,
                "first_seen_at": rev["first_seen_at"],
                "revision_created_at": rev.get("created_at"),
                "content": {
                    "kind": "headline_only",
                    "headline": rev.get("title") or None,
                    "body": None,
                    "body_unavailable_reason": "article_body_not_fetched_or_licensed",
                },
                "provenance": _provenance(rev, dups.get(rev["item_id"], [])),
                "claims": claims,
                "claims_unavailable_reason": None if claims else "no_structured_sleeper_status_for_matched_player",
                "evidence": {"status": "unavailable", "reason_codes": ["document_not_fetched", "no_licensed_excerpt"]},
                "review_only": True,
            }
        )

    next_cursor = encode_cursor(revisions[-1]["seq"]) if revisions else (cursor or None)
    return {
        "ok": True,
        "league": LEAGUE,
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "ingest": {
            "backend": store.backend,
            "durable": store.durable,
            "fallback_reason": store.fallback_reason,
            "last_success_at": max((h.get("last_success_at") or "" for h in health), default="") or None,
            "sources": [
                {
                    "source": h.get("source_key"),
                    "last_attempt_at": h.get("last_attempt_at"),
                    "last_success_at": h.get("last_success_at"),
                    "consecutive_failures": h.get("consecutive_failures"),
                    "last_error": h.get("last_error"),
                    "last_item_count": h.get("last_item_count"),
                }
                for h in sorted(health, key=lambda h: str(h.get("source_key")))
            ],
        },
        "unavailable": unavailable,
    }
