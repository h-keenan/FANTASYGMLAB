"""Canonical Notification Center — activity inbox composition and presentation.

Composes lightweight inbox records from existing canonical session inventory.
Does not generate football opinions, scores, rankings, or recommendation order.
Does not add push/email/SMS infrastructure.
"""

from __future__ import annotations
from dataclasses import MISSING, dataclass, fields
from typing import Any, Mapping, MutableMapping, Sequence
from modules import account_store
from modules import auth_supabase
from modules import brand_identity
from modules import canonical_recommendation_narrative

PRIORITY_ACTION = frozenset({"URGENT", "DECISIONS", "DRAFT"})


PRIORITY_PRODUCT = frozenset({"PRODUCT"})


ACTIVITY_INBOX_SNAPSHOT_KEY = "activity_inbox_snapshot"


ACTIVITY_INBOX_READY_KEY = "activity_inbox_ready_league"


NOTIFICATION_READ_IDS_KEY = "notification_center_read_ids"


NOTIFICATION_DISMISSED_IDS_KEY = "notification_center_dismissed_ids"


NOTIFICATION_ACCOUNT_SCOPE_KEY = "notification_center_account_scope"


NOTIFICATION_READ_STATE_TABLE = "notification_read_state"


NOTIFICATION_DURABLE_UNAVAILABLE_KEY = "notification_center_durable_unavailable"


URGENT_DELIVERY_STATE_KEY = "notification_center_urgent_delivery_state"


URGENT_DELIVERY_PENDING_KEY = "notification_center_urgent_delivery_pending"


MAX_INBOX_ITEMS = 6


PLAYER_EVENT_FOCUS_KEY_PREFIX = "my_team_player_event_focus_"


@dataclass(frozen=True)
class NotificationItem:
    """Canonical activity-inbox record. Summarizes existing state only."""

    id: str
    category: str
    title: str
    body: str
    unread: bool = True
    href_hint: str = ""
    age_label: str = "Just now"
    league_id: str = ""
    roster_id: str = ""
    player_id: str = ""
    recommendation_id: str = ""
    trade_package_id: str = ""
    destination_detail: str = ""
    provenance: str = ""
    entitlement_visibility: str = "all"
    stale: bool = False
    stale_reason: str = ""
    recommendation_narrative: Mapping[str, Any] | None = None
    source_kind: str = "canonical"  # canonical | product
    focus_mode: str = ""
    severity: str = ""
    roster_relationship: str = ""
    event_type: str = ""
    status_unconfirmed: bool = False
    player_name: str = ""
    significant_injury_event: bool = False
    source: str = ""
    source_url: str = ""
    event_time: float = 0.0
    event_identity: str = ""

    @property
    def notification_id(self) -> str:
        return self.id

    def to_dict(self) -> dict[str, Any]:
        payload = {field.name: getattr(self, field.name) for field in fields(self)}
        narrative = payload.get("recommendation_narrative")
        if hasattr(narrative, "to_dict"):
            payload["recommendation_narrative"] = narrative.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> NotificationItem | None:
        if not isinstance(payload, Mapping):
            return None
        if not _text(payload.get("id")):
            return None
        values: dict[str, Any] = {}
        for field in fields(cls):
            if field.name in payload:
                values[field.name] = payload[field.name]
            elif field.default is not MISSING:
                values[field.name] = field.default
            elif getattr(field, "default_factory", MISSING) is not MISSING:
                values[field.name] = field.default_factory()  # type: ignore[misc]
        narrative = values.get("recommendation_narrative")
        if narrative is not None and not isinstance(narrative, Mapping):
            if hasattr(narrative, "to_dict"):
                values["recommendation_narrative"] = narrative.to_dict()
            else:
                values["recommendation_narrative"] = None
        try:
            return cls(**values)
        except TypeError:
            return None


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def product_update_notification() -> NotificationItem:
    """Clearly labeled product news — not league activity."""

    return NotificationItem(
        id="product-founder-beta-inbox",
        category="PRODUCT",
        title=f"What's new in {brand_identity.PRODUCT_NAME}",
        body="Alerts, league, and account share one top bar. League activity appears here when your workspace produces it.",
        unread=False,
        href_hint="",
        age_label="Product",
        provenance="product_update",
        entitlement_visibility="all",
        source_kind="product",
    )


def notification_priority_band(item: NotificationItem) -> str:
    """Return presentation band: action | routine | product."""

    category = str(item.category or "")
    if category in PRIORITY_PRODUCT or item.source_kind == "product":
        return "product"
    if category in PRIORITY_ACTION:
        return "action"
    return "routine"


def ranked_notifications(items: Sequence[NotificationItem]) -> tuple[NotificationItem, ...]:
    """Order for the executive inbox: unread action first, product last.

    Equal-priority items keep their relative source order. Does not invent
    football priority — presentation banding only.
    """

    band_rank = {"action": 0, "routine": 1, "product": 2}
    indexed = list(enumerate(items))

    def sort_key(pair: tuple[int, NotificationItem]) -> tuple[int, int, int]:
        index, item = pair
        return (
            0 if item.unread and not item.stale else 1,
            band_rank.get(notification_priority_band(item), 1),
            index,
        )

    return tuple(item for _, item in sorted(indexed, key=sort_key))


def _account_scope(session: Mapping[str, Any] | None) -> str:
    if not isinstance(session, Mapping):
        return "anon"
    for key in (
        "account_user_id",
        "supabase_user_id",
        "auth_user_id",
        "account_email",
        "account_label",
    ):
        value = _text(session.get(key))
        if value and value.casefold() != "guest":
            return value.casefold()
    return "anon"


def _read_scope(session: Mapping[str, Any] | None, *, league_id: str) -> str:
    return f"{_account_scope(session)}|{_text(league_id) or 'no-league'}"


def _read_id_store(session: MutableMapping[str, Any]) -> dict[str, list[str]]:
    raw = session.get(NOTIFICATION_READ_IDS_KEY)
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    for key, value in raw.items():
        if isinstance(value, (list, tuple, set)):
            cleaned[str(key)] = [str(item) for item in value if str(item).strip()]
    return cleaned


def attention_aliases(row: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Stable ids used for read/dismiss — unique per event, plus rec: aliases."""

    from modules import alert_presentation

    return alert_presentation.attention_aliases(row)


def _resolve_durable_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(config, Mapping) and config:
        return dict(config)
    try:
        return auth_supabase.get_supabase_config()
    except Exception:
        return {}


def _mark_durable_unavailable(session: MutableMapping[str, Any]) -> None:
    session[NOTIFICATION_DURABLE_UNAVAILABLE_KEY] = True


def _persist_notification_read_state(
    session: Mapping[str, Any],
    notification_id: str,
    *,
    league_id: str,
    dismissed: bool | None = None,
    config: Mapping[str, Any] | None = None,
) -> None:
    """Best-effort durable write-through — never raises, never blocks a UI action.

    `dismissed=None` (the mark-read path) omits that column from the upsert
    payload entirely, so it can't regress an already-dismissed row back to
    false; dismiss_notification passes dismissed=True explicitly.
    """

    if bool(session.get(NOTIFICATION_DURABLE_UNAVAILABLE_KEY)):
        return
    league_key = _text(league_id)
    if not league_key:
        return
    try:
        user_id = auth_supabase.current_user_id(dict(session))
        access_token = auth_supabase.current_access_token(dict(session))
    except Exception:
        return
    if not user_id or not access_token:
        return
    resolved = _resolve_durable_config(config)
    if not auth_supabase.is_configured(resolved):
        return
    payload: dict[str, Any] = {
        "user_id": user_id,
        "league_id": league_key,
        "notification_id": notification_id,
    }
    if dismissed is not None:
        payload["dismissed"] = bool(dismissed)
    try:
        ok, error = account_store.upsert_row(
            resolved,
            access_token,
            NOTIFICATION_READ_STATE_TABLE,
            payload,
            on_conflict="user_id,league_id,notification_id",
        )
    except Exception:
        return
    if not ok and isinstance(session, MutableMapping):
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_durable_unavailable(session)


def mark_alert_read(
    session: MutableMapping[str, Any],
    row: Mapping[str, Any] | str,
    *,
    league_id: str = "",
) -> None:
    payload = row if isinstance(row, Mapping) else {"id": row, "recommendation_id": row}
    for note_id in attention_aliases(payload):
        mark_notification_read(session, note_id, league_id=league_id)


def dismiss_alert(
    session: MutableMapping[str, Any],
    row: Mapping[str, Any] | str,
    *,
    league_id: str = "",
) -> None:
    payload = row if isinstance(row, Mapping) else {"id": row, "recommendation_id": row}
    for note_id in attention_aliases(payload):
        dismiss_notification(session, note_id, league_id=league_id)


def mark_notification_read(
    session: MutableMapping[str, Any],
    notification_id: str,
    *,
    league_id: str = "",
) -> None:
    """Persist in-session read state for one notification id."""

    note_id = _text(notification_id)
    if not note_id:
        return
    scope = _read_scope(session, league_id=league_id or _text(session.get("selected_league_id")))
    store = _read_id_store(session)
    existing = list(store.get(scope) or [])
    if note_id not in existing:
        existing.append(note_id)
    store[scope] = existing
    session[NOTIFICATION_READ_IDS_KEY] = store
    session[NOTIFICATION_ACCOUNT_SCOPE_KEY] = _account_scope(session)
    _persist_notification_read_state(session, note_id, league_id=league_id or _text(session.get("selected_league_id")))


def dismiss_notification(
    session: MutableMapping[str, Any],
    notification_id: str,
    *,
    league_id: str = "",
) -> None:
    """Remove from active toast/header presentation without deleting history."""

    note_id = _text(notification_id)
    if not note_id:
        return
    scope = _read_scope(session, league_id=league_id or _text(session.get("selected_league_id")))
    raw = session.get(NOTIFICATION_DISMISSED_IDS_KEY)
    store = dict(raw) if isinstance(raw, Mapping) else {}
    existing = list(store.get(scope) or [])
    if note_id not in existing:
        existing.append(note_id)
    store[scope] = existing[-200:]
    session[NOTIFICATION_DISMISSED_IDS_KEY] = store
    _persist_notification_read_state(
        session, note_id, league_id=league_id or _text(session.get("selected_league_id")), dismissed=True
    )
    mark_notification_read(session, note_id, league_id=league_id)


def is_notification_dismissed(
    session: Mapping[str, Any] | None,
    notification_id: str,
    *,
    league_id: str = "",
) -> bool:
    note_id = _text(notification_id)
    if not note_id or not isinstance(session, Mapping):
        return False
    scope = _read_scope(session, league_id=league_id or _text(session.get("selected_league_id")))
    raw = session.get(NOTIFICATION_DISMISSED_IDS_KEY)
    if not isinstance(raw, Mapping):
        return False
    return note_id in {str(item) for item in (raw.get(scope) or ())}


def is_notification_read(
    session: Mapping[str, Any] | None,
    notification_id: str,
    *,
    league_id: str = "",
) -> bool:
    if not isinstance(session, Mapping):
        return False
    scope = _read_scope(session, league_id=league_id)
    store = session.get(NOTIFICATION_READ_IDS_KEY)
    if not isinstance(store, dict):
        return False
    ids = store.get(scope) or []
    return _text(notification_id) in {str(item) for item in ids}


def clear_notification_session_state(state: MutableMapping[str, Any]) -> None:
    """Drop inbox snapshot and read maps (account / logout hygiene)."""

    state.pop(ACTIVITY_INBOX_SNAPSHOT_KEY, None)
    state.pop(ACTIVITY_INBOX_READY_KEY, None)
    state.pop(NOTIFICATION_READ_IDS_KEY, None)
    state.pop(NOTIFICATION_DISMISSED_IDS_KEY, None)
    state.pop(NOTIFICATION_ACCOUNT_SCOPE_KEY, None)
    state.pop(URGENT_DELIVERY_STATE_KEY, None)
    state.pop(URGENT_DELIVERY_PENDING_KEY, None)
    state.pop("_notification_open_notice", None)
    state.pop("_notification_return_ack", None)


def clear_notification_league_snapshot(state: MutableMapping[str, Any]) -> None:
    """League switch: drop prior-league inventory so it cannot flash."""

    state.pop(ACTIVITY_INBOX_SNAPSHOT_KEY, None)
    state.pop(ACTIVITY_INBOX_READY_KEY, None)
    state.pop(URGENT_DELIVERY_PENDING_KEY, None)
    state.pop("_notification_open_notice", None)
    for key in tuple(state):
        if str(key).startswith(PLAYER_EVENT_FOCUS_KEY_PREFIX):
            state.pop(key, None)


def clear_notification_context_snapshot(state: MutableMapping[str, Any]) -> None:
    """Lens/scoring/roster context change: drop stale inbox inventory."""

    state.pop(ACTIVITY_INBOX_SNAPSHOT_KEY, None)
    state.pop(ACTIVITY_INBOX_READY_KEY, None)
    state.pop("_notification_open_notice", None)


def _live_draft_notification(*, league_id: str) -> NotificationItem:
    return NotificationItem(
        id=f"live-draft:{_text(league_id) or 'active'}",
        category="DRAFT",
        title="Live Draft is active",
        body="Your league has an active draft context. Open Live Draft to continue.",
        unread=True,
        href_hint="live_draft",
        age_label="Live",
        league_id=_text(league_id),
        provenance="live_draft_cache",
        entitlement_visibility="all",
        source_kind="canonical",
    )


def _item_from_record(
    record: Mapping[str, Any],
    *,
    session: Mapping[str, Any] | None,
    league_id: str,
) -> NotificationItem:
    note_id = _text(record.get("id"))
    unread = not is_notification_read(session, note_id, league_id=league_id)
    narrative = record.get("recommendation_narrative")
    if not isinstance(narrative, Mapping):
        narrative = None
    try:
        event_time = float(record.get("news_event_time") or 0.0)
    except (TypeError, ValueError):
        event_time = 0.0
    return NotificationItem(
        id=note_id,
        category=_text(record.get("category"), "LEAGUE"),
        title=_text(record.get("title")),
        body=_text(record.get("body")),
        unread=unread,
        href_hint=_text(record.get("href_hint")),
        age_label=_text(record.get("age_label"), "Now"),
        league_id=_text(record.get("league_id"), league_id),
        roster_id=_text(record.get("roster_id")),
        player_id=_text(record.get("player_id")),
        recommendation_id=_text(record.get("recommendation_id")),
        trade_package_id=_text(record.get("trade_package_id")),
        destination_detail=_text(record.get("destination_detail")),
        provenance=_text(record.get("provenance"), "dashboard_inventory"),
        entitlement_visibility=_text(record.get("entitlement_visibility"), "all"),
        recommendation_narrative=narrative,
        source_kind=_text(record.get("source_kind"), "canonical"),
        focus_mode=_text(record.get("focus_mode")),
        severity=_text(record.get("news_event_severity")),
        roster_relationship=_text(record.get("news_roster_relationship")),
        event_type=_text(record.get("news_event_type")),
        status_unconfirmed=bool(record.get("news_status_unconfirmed")),
        player_name=_text(record.get("news_player_name")),
        significant_injury_event=bool(record.get("news_significant_injury_event")),
        source=_text(record.get("news_source") or record.get("source")),
        source_url=_text(record.get("source_url")),
        event_time=event_time,
        event_identity=_text(record.get("event_identity")),
    )


def compose_activity_inbox(
    *,
    session: Mapping[str, Any] | None = None,
    league_id: str = "",
    roster_id: str = "",
    entitlement: str = "free",
    include_product_update: bool = True,
    header_cap: bool = True,
) -> tuple[NotificationItem, ...]:
    """Compose the activity inbox from cached inventory + product/live-draft signals.

    Never invents league events. Quiet inbox is valid when nothing is active.
    """

    session_map = session if isinstance(session, Mapping) else {}
    league_key = _text(league_id) or _text(session_map.get("selected_league_id"))
    snapshot = session_map.get(ACTIVITY_INBOX_SNAPSHOT_KEY)
    items: list[NotificationItem] = []
    seen_rec: set[str] = set()

    if isinstance(snapshot, Mapping):
        snap_league = _text(snapshot.get("league_id"))
        # Never flash another league's inbox.
        if snap_league and league_key and snap_league != league_key:
            snapshot = None
        else:
            for record in snapshot.get("records") or ():
                if not isinstance(record, Mapping):
                    continue
                visibility = _text(record.get("entitlement_visibility"), "all")
                ent = _text(entitlement or snapshot.get("entitlement"), "free").casefold()
                if visibility == "premium" and ent != "premium":
                    continue
                item = _item_from_record(record, session=session_map, league_id=league_key)
                if not item.title:
                    continue
                if item.recommendation_id and item.recommendation_id in seen_rec:
                    continue
                if item.recommendation_id:
                    seen_rec.add(item.recommendation_id)
                items.append(item)

    live_draft = False
    if isinstance(snapshot, Mapping):
        live_draft = bool(snapshot.get("live_draft_active"))
    if not live_draft:
        live_draft = bool(session_map.get("_cached_live_draft_active"))
    if live_draft and league_key:
        draft_item = _live_draft_notification(league_id=league_key)
        if not is_notification_read(session_map, draft_item.id, league_id=league_key):
            draft_item = NotificationItem(**{**draft_item.to_dict(), "unread": True})
        else:
            draft_item = NotificationItem(**{**draft_item.to_dict(), "unread": False})
        items.append(draft_item)

    recap_notice = session_map.get("_league_recap_notice")
    if isinstance(recap_notice, Mapping) and _text(recap_notice.get("id")):
        notice_id = _text(recap_notice.get("id"))
        unread = not is_notification_read(session_map, notice_id, league_id=league_key)
        items.append(
            NotificationItem(
                id=notice_id,
                category="LEAGUE",
                title=_text(recap_notice.get("title"), "League Recap is ready."),
                body=_text(recap_notice.get("body")),
                unread=unread,
                href_hint=_text(recap_notice.get("href_hint"), "league_recaps"),
                age_label="This week",
                league_id=_text(recap_notice.get("league_id"), league_key),
                provenance="league_recap_cache",
                entitlement_visibility="all",
                source_kind="canonical",
            )
        )

    if include_product_update:
        product = product_update_notification()
        if is_notification_read(session_map, product.id, league_id=league_key):
            product = NotificationItem(**{**product.to_dict(), "unread": False})
        items.append(product)

    ranked = ranked_notifications(tuple(items))
    ranked = tuple(
        item
        for item in ranked
        if not is_notification_dismissed(session_map, item.id, league_id=league_key)
    )
    if not header_cap:
        return ranked
    from modules import alerts_activity

    return alerts_activity.compose_header_alerts(ranked, max_items=MAX_INBOX_ITEMS)


def compact_inbox_presentation(item: NotificationItem) -> dict[str, str]:
    """Shortest canonical inbox fields — presentation only, meaning unchanged."""

    narrative = item.recommendation_narrative
    if hasattr(narrative, "to_dict"):
        narrative = narrative.to_dict()
    model = (
        canonical_recommendation_narrative.CanonicalRecommendationNarrative.from_dict(narrative)
        if isinstance(narrative, Mapping)
        else None
    )
    meta = f"{_text(item.severity or item.category)} · {_text(item.event_type or item.category)} · {_text(item.age_label, 'Now')}"
    from modules import alerts_activity

    glyph = alerts_activity.header_glyph(item)
    primary = _text(item.title)
    if primary.casefold() in {"player: other", "other: other"} or primary.casefold().endswith(": other"):
        if not _text(item.player_id):
            primary = "League-wide news" if item.category == "NEWS" else "Unmapped player update"
        else:
            primary = "Player mapping unavailable"
    action_line = ""
    reason_line = ""

    if model is not None:
        if _text(model.target_label):
            primary = _text(model.target_label)
        action_candidate = _text(model.action)
        if action_candidate and action_candidate.casefold() != primary.casefold():
            action_line = canonical_recommendation_narrative.shorten_narrative_text(
                action_candidate, 56
            )
        for candidate in (model.reason, model.evidence, model.risk):
            text = _text(candidate)
            if not text:
                continue
            lowered = text.casefold()
            if primary and primary.casefold() in lowered and len(text) <= len(primary) + 8:
                continue
            reason_line = canonical_recommendation_narrative.shorten_narrative_text(text, 72)
            break
    if not reason_line:
        body = _text(item.body)
        if body and body.casefold() != primary.casefold():
            reason_line = canonical_recommendation_narrative.shorten_narrative_text(body, 72)

    if item.source_kind == "product":
        primary = _text(item.title)
        action_line = ""
        reason_line = canonical_recommendation_narrative.shorten_narrative_text(item.body, 80)

    return {
        "meta": meta,
        "primary": primary,
        "action_line": action_line,
        "reason_line": reason_line,
        "glyph": glyph,
    }
