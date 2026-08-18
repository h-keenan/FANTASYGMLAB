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


def compose_activity_timeline(
    *,
    session: Mapping[str, Any] | None = None,
    league_id: str = "",
    entitlement: str = "free",
    news_events: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Deeper timeline for the Alerts route. General news is included here."""

    inbox = nc.compose_activity_inbox(
        session=session,
        league_id=league_id,
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
    if not extra and isinstance(session, Mapping):
        stored = session.get(TIMELINE_SESSION_KEY)
        if isinstance(stored, Mapping):
            extra = list(stored.get("items") or ())
        elif isinstance(stored, (list, tuple)):
            extra = list(stored)
    for raw in extra:
        if not isinstance(raw, Mapping):
            continue
        row = _row_from_news_event(raw)
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
    session[TIMELINE_SESSION_KEY] = {
        "league_id": str(league_id or ""),
        "items": [dict(item) for item in events if isinstance(item, Mapping)][:MAX_TIMELINE_ITEMS],
    }


def _row_from_notification(item: nc.NotificationItem) -> dict[str, Any]:
    compact = nc.compact_inbox_presentation(item)
    return {
        "id": item.id,
        "kind": "notification",
        "category": item.category,
        "glyph": header_glyph(item),
        "headline": compact["primary"],
        "context": compact["reason_line"] or compact["action_line"],
        "freshness": item.age_label,
        "unread": bool(item.unread and not item.stale),
        "href_hint": item.href_hint,
        "player_id": item.player_id,
        "alert_worthy": is_alert_worthy(item),
        "roster_relationship": "",
        "source_kind": item.source_kind,
        "provenance": item.provenance,
    }


def _row_from_news_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    rel = str(raw.get("news_roster_relationship") or raw.get("roster_relationship") or "")
    severity = str(raw.get("news_event_severity") or raw.get("severity") or "")
    alert_worthy = bool(raw.get("should_alert")) or severity in {"CRITICAL", "HIGH"}
    category = str(raw.get("category") or ("URGENT" if alert_worthy and rel in _MY_REL else "NEWS"))
    freshness = str(
        raw.get("news_age_label")
        or raw.get("age_label")
        or signal_freshness.format_age_short(raw.get("age_seconds"))
        or ""
    )
    return {
        "id": str(raw.get("id") or raw.get("recommendation_id") or raw.get("event_identity") or ""),
        "kind": "news",
        "category": category,
        "glyph": "NEWS" if category == "NEWS" else header_glyph({"category": category, "title": raw.get("value") or raw.get("title") or ""}),
        "headline": str(raw.get("value") or raw.get("title") or raw.get("article_title") or "News"),
        "context": str(
            raw.get("news_corroboration_note")
            or raw.get("news_why_care")
            or raw.get("note")
            or ""
        )[:120],
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
    }
