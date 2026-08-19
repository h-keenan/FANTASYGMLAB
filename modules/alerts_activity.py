"""Alerts / Activity timeline composition.

Reuses notification inventory, news intelligence events, and recap notices.
Does not create a second History system or a parallel news fetch.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules import notification_center as nc
from modules import signal_freshness

FILTER_IMPORTANT = "Important"
FILTER_MY_PLAYERS = "My Players"
FILTER_NEWS = "News"
FILTER_LEAGUE = "League"
FILTER_DECISIONS = "Decisions"
FILTER_ALL = "All"

EMPTY_COPY = {
    FILTER_IMPORTANT: "You’re caught up.",
    FILTER_MY_PLAYERS: "No recent player-specific alerts.",
    FILTER_NEWS: "No recent mapped news.",
    FILTER_LEAGUE: "No notable league activity recently.",
    FILTER_DECISIONS: "No new recommendation changes.",
    FILTER_ALL: "No activity yet.",
}

ALERT_FILTERS: tuple[str, ...] = (
    FILTER_IMPORTANT,
    FILTER_MY_PLAYERS,
    FILTER_NEWS,
    FILTER_LEAGUE,
    FILTER_DECISIONS,
)

TIMELINE_SESSION_KEY = "_signal_intelligence_timeline"
MAX_TIMELINE_ITEMS = 40
MAX_HEADER_ALERTS = 6
MIN_HEADER_ALERTS = 3

GLYPH_BY_CATEGORY = {
    "URGENT": "OUT",
    "ROSTER": "ROSTER",
    "NEWS": "NEWS",
    "LEAGUE": "RECAP",
    "DECISIONS": "DECISION",
    "DRAFT": "DRAFT",
    "PRODUCT": "PRODUCT",
}

_MY_REL = frozenset({"MY_STARTER", "MY_BENCH", "MY_TAXI", "MY_IR"})


def header_glyph(item: nc.NotificationItem | Mapping[str, Any]) -> str:
    if isinstance(item, nc.NotificationItem):
        category = item.category
        title = item.title
        provenance = item.provenance
    else:
        category = str(item.get("category") or "")
        title = str(item.get("title") or "")
        provenance = str(item.get("provenance") or "")
    if "recap" in provenance.casefold() or "recap" in title.casefold():
        return "RECAP"
    if category == "URGENT" and "out" in title.casefold():
        return "OUT"
    return GLYPH_BY_CATEGORY.get(category, category or "NEWS")


def is_alert_worthy(item: nc.NotificationItem) -> bool:
    if item.source_kind == "product":
        return False
    if item.stale:
        return False
    band = nc.notification_priority_band(item)
    if band == "action":
        return True
    if item.category in {"URGENT", "DECISIONS", "DRAFT"}:
        return True
    if item.category == "NEWS" and item.unread:
        return False
    return item.unread and item.category in {"ROSTER", "LEAGUE"}


def compose_header_alerts(
    items: Sequence[nc.NotificationItem],
    *,
    max_items: int = MAX_HEADER_ALERTS,
) -> tuple[nc.NotificationItem, ...]:
    """3–6 highest-value header rows. Quiet product-only inbox stays valid."""

    ranked = nc.ranked_notifications(tuple(items))
    canonical = [item for item in ranked if item.source_kind != "product"]
    product = [item for item in ranked if item.source_kind == "product"]
    cap = max(1, min(int(max_items), MAX_HEADER_ALERTS))
    if not canonical:
        return tuple(product[:1])
    worthy = [item for item in canonical if is_alert_worthy(item)] or canonical
    selected = worthy[:cap]
    return tuple(selected)


def timeline_items_for_requested_league(payload: Any, requested_league_id: str) -> list[Mapping[str, Any]]:
    """Return stored timeline rows only when they belong to the requested league.

    Unkeyed/legacy lists and league mismatches are ignored so League A activity
    cannot render on League B before B's news refresh.
    """

    requested = str(requested_league_id or "").strip()
    if isinstance(payload, (list, tuple)):
        return [] if requested else [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    stored_league = str(payload.get("league_id") or "").strip()
    if requested and stored_league != requested:
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, Mapping)]


def load_timeline_events(session: Mapping[str, Any] | None, league_id: str = "") -> list[Mapping[str, Any]]:
    if not isinstance(session, Mapping):
        return []
    return timeline_items_for_requested_league(session.get(TIMELINE_SESSION_KEY), league_id)


def empty_copy(selected: str) -> str:
    needle = str(selected or FILTER_IMPORTANT).strip() or FILTER_IMPORTANT
    return EMPTY_COPY.get(needle, EMPTY_COPY[FILTER_IMPORTANT])


def humanize_headline(row: Mapping[str, Any]) -> str:
    headline = str(row.get("headline") or "").strip()
    lowered = headline.casefold()
    player_id = str(row.get("player_id") or "").strip()
    event_type = str(row.get("event_type") or "").strip().upper()
    category = str(row.get("category") or "").strip().upper()
    if lowered in {"player: other", "other: other"} or lowered.endswith(": other"):
        if not player_id:
            return "League-wide news" if category in {"NEWS", "LEAGUE"} else "Unmapped player update"
        return "Player mapping unavailable"
    if event_type in {"OTHER", "FT_OTHER"} and (
        lowered.startswith("player:") or lowered in {"other", "update", "news"}
    ):
        if not player_id:
            return "League-wide news"
        return "Player mapping unavailable"
    return headline or "Update"


def _decision_memory_rows(session: Mapping[str, Any] | None, league_id: str) -> list[dict[str, Any]]:
    if not isinstance(session, Mapping):
        return []
    raw = session.get("_decision_memory_cache_events")
    if not isinstance(raw, (list, tuple)):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        event_league = str(item.get("league_id") or "").strip()
        if league_id and event_league and event_league != league_id:
            continue
        title = str(item.get("title") or item.get("summary") or item.get("action") or "").strip()
        if not title:
            continue
        rows.append(
            {
                "id": str(item.get("event_id") or item.get("id") or title),
                "kind": "decision",
                "category": "DECISIONS",
                "glyph": "DECISION",
                "headline": title,
                "context": str(item.get("body") or item.get("reason") or "")[:120],
                "freshness": signal_freshness.humanize_age_label(
                    item.get("age_label") or "",
                    age_seconds=item.get("age_seconds"),
                ),
                "unread": True,
                "href_hint": "alerts",
                "player_id": str(item.get("player_id") or ""),
                "alert_worthy": True,
                "roster_relationship": "",
                "source_kind": "canonical",
                "provenance": "decision_memory",
            }
        )
    return rows


def _cached_news_events(session: Mapping[str, Any] | None, league_id: str) -> list[Mapping[str, Any]]:
    # Compose every already-available source. A single stale session row must
    # not suppress the richer disk-cached league news pool.
    extra = list(load_timeline_events(session, league_id))
    seen = {
        str(item.get("id") or item.get("event_identity") or item.get("link") or "")
        for item in extra
        if isinstance(item, Mapping)
    }
    candidates: list[Mapping[str, Any]] = []
    if isinstance(session, Mapping):
        from modules.news_intelligence import TIMELINE_EVENT_KEY

        payload = session.get(TIMELINE_EVENT_KEY)
        if isinstance(payload, list) and not league_id:
            candidates = [item for item in payload if isinstance(item, Mapping)]
        if isinstance(payload, Mapping):
            stored_league = str(payload.get("league_id") or "").strip()
            items = payload.get("items")
            if isinstance(items, list) and (not league_id or stored_league == league_id):
                candidates = [item for item in items if isinstance(item, Mapping)]
        for item in candidates:
            identity = str(item.get("id") or item.get("event_identity") or item.get("link") or "")
            if identity and identity in seen:
                continue
            extra.append(item)
            if identity:
                seen.add(identity)
    try:
        from modules.news import load_cached_news_pool
        from modules import news_intelligence as ni
        from modules import news_signal

        pool = load_cached_news_pool() or []
        events: list[Mapping[str, Any]] = list(extra)
        for raw in pool[:MAX_TIMELINE_ITEMS]:
            if not isinstance(raw, Mapping):
                continue
            enriched = news_signal.enrich_news_item(raw)
            signal_events = tuple(enriched.get("signal_events") or ())
            # Cached league-wide inventory can contain entertainment and broad
            # league stories. Keep football decisions/status/role/transaction
            # signals; do not manufacture relevance for unrelated headlines.
            raw_title = str(raw.get("title") or "League-wide NFL update").strip()
            entertainment_only = any(
                phrase in raw_title.casefold()
                for phrase in (
                    "wedding",
                    " marry",
                    "celebrit",
                    "taylor swift",
                    "adam sandler",
                    "murder",
                    " found dead",
                    "ice bucket",
                    "pope",
                    "hollywood",
                    "basketball",
                )
            )
            if entertainment_only:
                continue
            event = ni.football_event_from_article(enriched)
            alert = ni.build_news_alert(event)
            tile = alert.as_tile()
            if not str(tile.get("player_id") or "").strip():
                # Preserve an honest league-wide headline and a per-article
                # identity. The classifier's generic unknown-player ID otherwise
                # collapses the entire cached pool into one stale shell row.
                tile["title"] = raw_title
                tile["value"] = raw_title
                tile["context"] = str(raw.get("summary") or "League-wide NFL context.").strip()[:180]
                tile["event_identity"] = str(enriched.get("event_identity") or "")
                tile["id"] = f"news:{tile['event_identity']}"
                tile["category"] = "NEWS"
                tile["event_type"] = str(enriched.get("signal_primary_event") or "HEADLINE")
            tile["source_url"] = str(raw.get("link") or "").strip()
            identity = str(tile.get("id") or tile.get("event_identity") or raw.get("link") or "")
            if identity and identity in seen:
                continue
            events.append(tile)
            if identity:
                seen.add(identity)
            if len(events) >= MAX_TIMELINE_ITEMS:
                break
        return events
    except Exception:
        return []


def compose_activity_timeline(
    *,
    session: Mapping[str, Any] | None = None,
    league_id: str = "",
    entitlement: str = "free",
    news_events: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Deeper timeline for the Alerts route. General news is included here."""

    requested_league = str(league_id or "").strip()
    inbox = nc.compose_activity_inbox(
        session=session,
        league_id=requested_league,
        entitlement=entitlement,
        include_product_update=True,
        header_cap=False,
    )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in inbox:
        row = _row_from_notification(item)
        key = str(row.get("id") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    extra = list(news_events or ())
    if not extra:
        extra = _cached_news_events(session, requested_league)
    for raw in extra:
        if not isinstance(raw, Mapping):
            continue
        event_league = str(raw.get("league_id") or "").strip()
        if requested_league and event_league and event_league != requested_league:
            continue
        row = _row_from_news_event(raw)
        key = str(row.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(row)

    for row in _decision_memory_rows(session, requested_league):
        key = str(row.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(row)

    return tuple(rows[:MAX_TIMELINE_ITEMS])


def filter_timeline(
    rows: Sequence[Mapping[str, Any]],
    selected: str,
) -> tuple[dict[str, Any], ...]:
    needle = str(selected or FILTER_IMPORTANT).strip() or FILTER_IMPORTANT
    out: list[dict[str, Any]] = []
    for row in rows:
        category = str(row.get("category") or "")
        rel = str(row.get("roster_relationship") or "")
        alert_worthy = bool(row.get("alert_worthy"))
        if needle == FILTER_ALL:
            out.append(dict(row))
        elif needle == FILTER_IMPORTANT and (alert_worthy or category == "URGENT"):
            out.append(dict(row))
        elif needle == FILTER_MY_PLAYERS and (rel in _MY_REL or category == "ROSTER"):
            out.append(dict(row))
        elif needle == FILTER_NEWS and (
            str(row.get("kind") or "") == "news" or category in {"NEWS", "URGENT"}
        ):
            out.append(dict(row))
        elif needle == FILTER_LEAGUE and category == "LEAGUE":
            out.append(dict(row))
        elif needle == FILTER_DECISIONS and category == "DECISIONS":
            out.append(dict(row))
    return tuple(out)


def store_timeline_events(
    session: dict[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    league_id: str = "",
) -> None:
    scoped = str(league_id or "")
    items = []
    for item in events:
        if not isinstance(item, Mapping):
            continue
        payload = dict(item)
        if scoped and not str(payload.get("league_id") or "").strip():
            payload["league_id"] = scoped
        items.append(payload)
        if len(items) >= MAX_TIMELINE_ITEMS:
            break
    session[TIMELINE_SESSION_KEY] = {
        "league_id": scoped,
        "items": items,
    }


def clear_signal_intelligence_timeline(session: Mapping[str, Any] | None) -> None:
    if isinstance(session, dict):
        session.pop(TIMELINE_SESSION_KEY, None)


def _row_from_notification(item: nc.NotificationItem) -> dict[str, Any]:
    compact = nc.compact_inbox_presentation(item)
    row = {
        "id": item.id,
        "kind": "notification",
        "category": item.category,
        "glyph": header_glyph(item),
        "headline": compact["primary"],
        "context": compact["reason_line"] or compact["action_line"],
        "freshness": signal_freshness.humanize_age_label(item.age_label),
        "unread": bool(item.unread and not item.stale),
        "href_hint": item.href_hint,
        "player_id": item.player_id,
        "alert_worthy": is_alert_worthy(item),
        "roster_relationship": "",
        "source_kind": item.source_kind,
        "provenance": item.provenance,
    }
    row["headline"] = humanize_headline(row)
    return row


def _row_from_news_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    rel = str(raw.get("news_roster_relationship") or raw.get("roster_relationship") or "")
    severity = str(raw.get("news_event_severity") or raw.get("severity") or "")
    alert_worthy = bool(raw.get("should_alert")) or severity in {"CRITICAL", "HIGH"}
    category = str(raw.get("category") or ("URGENT" if alert_worthy and rel in _MY_REL else "NEWS"))
    freshness = signal_freshness.humanize_age_label(
        str(
            raw.get("news_age_label")
            or raw.get("age_label")
            or signal_freshness.format_human_age_label(raw.get("age_seconds") or raw.get("news_age_seconds"))
            or ""
        ),
        age_seconds=raw.get("news_age_seconds") if raw.get("news_age_seconds") is not None else raw.get("age_seconds"),
    )
    context = str(
        raw.get("news_corroboration_note")
        or raw.get("news_why_care")
        or raw.get("note")
        or ""
    )[:120]
    if context == "News only — structured status not compared.":
        context = "Player status has not yet been confirmed."
    row = {
        "id": str(raw.get("id") or raw.get("recommendation_id") or raw.get("event_identity") or ""),
        "kind": "news",
        "category": category,
        "glyph": "NEWS" if category == "NEWS" else header_glyph({"category": category, "title": raw.get("value") or raw.get("title") or ""}),
        "headline": str(raw.get("value") or raw.get("title") or raw.get("article_title") or "News"),
        "context": context,
        "freshness": freshness,
        "unread": bool(raw.get("unread", True)),
        "href_hint": str(raw.get("route_key") or "alerts"),
        "player_id": str(raw.get("player_id") or ""),
        "alert_worthy": alert_worthy,
        "roster_relationship": rel,
        "source_kind": "canonical",
        "provenance": "news_intelligence",
        "event_type": str(raw.get("news_event_type") or raw.get("event_type") or ""),
        "corroboration": str(raw.get("news_corroboration") or ""),
        "source": str(raw.get("news_source") or raw.get("source") or ""),
        "source_url": str(raw.get("source_url") or raw.get("link") or "").strip(),
    }
    row["headline"] = humanize_headline(row)
    return row
