"""Canonical Notification Center — activity inbox composition and presentation.

Composes lightweight inbox records from existing canonical session inventory.
Does not generate football opinions, scores, rankings, or recommendation order.
Does not add push/email/SMS infrastructure.
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, fields
from html import escape
from typing import Any, Callable, Mapping, MutableMapping, Sequence

import streamlit as st

from modules import brand_identity
from modules import canonical_recommendation_narrative
from modules import decision_change_history as decision_history
from modules import decision_memory
from modules import interaction_latency
from modules import recommendation_lifecycle
from modules.html_rendering import render_html_fragment


NOTIFICATION_CATEGORIES: tuple[str, ...] = (
    "Trades",
    "Waivers",
    "League",
    "Injuries",
    "Live Draft",
    "Product updates",
)

PRIORITY_ACTION = frozenset({"Trades", "Waivers", "Injuries"})
PRIORITY_PRODUCT = frozenset({"Product updates"})

DESTINATION_LABELS: dict[str, str] = {
    "trade_hub": "Open Trade Hub",
    "waivers": "Open Waivers",
    "my_team": "Open My Team",
    "dashboard": "Open Dashboard",
    "live_draft": "Open Live Draft",
    "league_overview": "Open League Overview",
    "rankings": "Open League Overview",
    "player_quick_view": "Open Player",
}

ACTIVITY_INBOX_SNAPSHOT_KEY = "activity_inbox_snapshot"
NOTIFICATION_READ_IDS_KEY = "notification_center_read_ids"
NOTIFICATION_ACCOUNT_SCOPE_KEY = "notification_center_account_scope"
MAX_INBOX_ITEMS = 8

_LABEL_CATEGORY = {
    "Top Trade Opportunity": "Trades",
    "Top Waiver Opportunity": "Waivers",
    "Injury Alert": "Injuries",
    "Roster Pressure": "League",
    "Biggest Team Need": "League",
    "Roster Quality": "League",
    "Lineup Construction": "League",
    "Startup Observation": "League",
}

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
        category="Product updates",
        title=f"What's new in {brand_identity.PRODUCT_NAME}",
        body="Alerts, league, and account share one top bar. League activity appears here when your workspace produces it.",
        unread=False,
        href_hint="",
        age_label="Product",
        provenance="product_update",
        entitlement_visibility="all",
        source_kind="product",
    )


# Retained name for fixtures/tests that still reference the product seed.
FOUNDER_BETA_DEMO_NOTIFICATIONS: tuple[NotificationItem, ...] = (
    product_update_notification(),
)


def unread_count(items: Sequence[NotificationItem]) -> int:
    return sum(1 for item in items if item.unread and not item.stale)


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


def destination_label(href_hint: str) -> str:
    hint = str(href_hint or "").strip()
    if not hint:
        return ""
    return DESTINATION_LABELS.get(hint, "Open")


def summary_from_recommendation_narrative(narrative) -> str:
    """Build a notification body from a canonical narrative when data exists."""

    model = (
        narrative
        if isinstance(
            narrative,
            canonical_recommendation_narrative.CanonicalRecommendationNarrative,
        )
        else canonical_recommendation_narrative.CanonicalRecommendationNarrative.from_dict(
            narrative
        )
    )
    if model is None or not model.is_active_recommendation:
        return ""
    return model.notification_summary(limit=96)


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
    state.pop(NOTIFICATION_READ_IDS_KEY, None)
    state.pop(NOTIFICATION_ACCOUNT_SCOPE_KEY, None)
    state.pop("_notification_open_notice", None)
    state.pop("_notification_return_ack", None)


def clear_notification_league_snapshot(state: MutableMapping[str, Any]) -> None:
    """League switch: drop prior-league inventory so it cannot flash."""

    state.pop(ACTIVITY_INBOX_SNAPSHOT_KEY, None)
    state.pop("_notification_open_notice", None)


def clear_notification_context_snapshot(state: MutableMapping[str, Any]) -> None:
    """Lens/scoring/roster context change: drop stale inbox inventory."""

    state.pop(ACTIVITY_INBOX_SNAPSHOT_KEY, None)
    state.pop("_notification_open_notice", None)


def _player_id_from_tile(tile: Mapping[str, Any]) -> str:
    direct = _text(tile.get("route_player_id") or tile.get("player_id"))
    if direct:
        return direct
    row = tile.get("player_row")
    if isinstance(row, Mapping):
        return _text(row.get("player_id"))
    if hasattr(row, "get"):
        try:
            return _text(row.get("player_id"))
        except Exception:
            return ""
    return ""


def _destination_for_tile(tile: Mapping[str, Any], *, category: str) -> str:
    route = _text(tile.get("route_key"))
    if route:
        return route
    label = _text(tile.get("label"))
    if label == "Top Waiver Opportunity" or category == "Waivers":
        return "waivers"
    if label in {"Injury Alert", "Roster Pressure", "Biggest Team Need"}:
        player_id = _player_id_from_tile(tile)
        return "player_quick_view" if player_id else "my_team"
    if label == "Top Trade Opportunity" or category == "Trades":
        return "trade_hub"
    if category == "League":
        return "rankings"
    return "dashboard"


def _stable_notification_id(tile: Mapping[str, Any], *, category: str) -> str:
    rec_id = recommendation_lifecycle.item_recommendation_id(tile)
    if rec_id:
        return f"rec:{rec_id}"
    label = _text(tile.get("label"))
    player_id = _player_id_from_tile(tile)
    value = _text(tile.get("value"))
    return f"tile:{category}:{label}:{player_id}:{value}"[:120]


def inventory_record_from_tile(
    tile: Mapping[str, Any],
    *,
    league_id: str = "",
    roster_id: str = "",
) -> dict[str, Any] | None:
    """Serialize a Dashboard tile into a lightweight inbox inventory record."""

    if not isinstance(tile, Mapping):
        return None
    label = _text(tile.get("label"))
    value = _text(tile.get("value"))
    note = _text(tile.get("note"))
    if not label:
        return None
    # Skip empty / placeholder tiles that do not represent a real action.
    if value.casefold() in {"", "open trade hub", "open waivers", "within limit"}:
        if not recommendation_lifecycle.item_recommendation_id(tile):
            if label in {"Top Trade Opportunity", "Top Waiver Opportunity"}:
                return None
    if label == "Roster Pressure" and "over" not in value.casefold():
        return None
    if label == "Injury Alert" and value.casefold() in {"", "none", "stable", "0 injured starters"}:
        return None

    category = _LABEL_CATEGORY.get(label, "League")
    narrative = tile.get("recommendation_narrative")
    if hasattr(narrative, "to_dict"):
        narrative = narrative.to_dict()
    if not isinstance(narrative, Mapping):
        narrative = None
    rec_id = recommendation_lifecycle.item_recommendation_id(tile)
    player_id = _player_id_from_tile(tile)
    destination = _destination_for_tile(tile, category=category)
    body = note
    if narrative is not None:
        summary = summary_from_recommendation_narrative(narrative)
        if summary:
            body = summary
    material_signature = recommendation_lifecycle.recommendation_material_signature(tile)
    return {
        "id": _stable_notification_id(tile, category=category),
        "category": category,
        "title": value or label,
        "body": body or label,
        "href_hint": destination,
        "age_label": "Now",
        "league_id": _text(league_id),
        "roster_id": _text(roster_id),
        "player_id": player_id,
        "recommendation_id": rec_id,
        "trade_package_id": _text(
            (narrative or {}).get("recommendation_id") if narrative else ""
        ),
        "destination_detail": _text(tile.get("route_focus_mode")),
        "provenance": f"dashboard_inventory|{label}",
        "entitlement_visibility": "all",
        "recommendation_narrative": narrative,
        "source_kind": "canonical",
        "focus_mode": _text(tile.get("route_focus_mode")),
        "material_signature": material_signature,
    }


def publish_activity_inventory(
    session: MutableMapping[str, Any],
    tiles: Sequence[Mapping[str, Any]],
    *,
    league_id: str,
    roster_id: str = "",
    entitlement: str = "free",
    live_draft_active: bool = False,
    context_fingerprint: str = "",
    scoring_format: str = "",
    valuation_lens: str = "",
    supabase_config: Mapping[str, Any] | None = None,
) -> None:
    """Cache a lightweight inbox inventory from already-built Dashboard tiles.

    Call after Dashboard computation — never on the cold-start critical path
    as a generator of new football work. Identical reruns preserve read state
    and do not manufacture new activity when material signatures are unchanged.
    """

    # Cross-session Decision Memory: hydrate durable baseline before compare.
    try:
        decision_memory.hydrate_session_from_durable(
            session,
            league_id=league_id,
            config=supabase_config,
        )
    except Exception:
        pass

    records: list[dict[str, Any]] = []
    signatures: dict[str, str] = {}
    seen: set[str] = set()
    for index, tile in enumerate(tiles):
        record = inventory_record_from_tile(
            tile,
            league_id=league_id,
            roster_id=roster_id,
        )
        if record is None:
            continue
        note_id = _text(record.get("id"))
        rec_id = _text(record.get("recommendation_id"))
        dedupe_key = rec_id or note_id
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        signature = _text(record.get("material_signature"))
        if rec_id and signature:
            signatures[rec_id] = signature
        records.append(record)
        if len(records) >= MAX_INBOX_ITEMS:
            break

    fingerprint_key = _text(context_fingerprint)
    prior_snapshot = session.get(ACTIVITY_INBOX_SNAPSHOT_KEY)
    prior_signatures: dict[str, str] = {}
    prior_top = ""
    if isinstance(prior_snapshot, Mapping):
        prior_signatures = dict(prior_snapshot.get("material_signatures") or {})
        prior_top = _text(prior_snapshot.get("top_recommendation_id"))

    top_recommendation_id = ""
    for record in records:
        top_recommendation_id = _text(record.get("recommendation_id"))
        if top_recommendation_id:
            break

    prior_store = session.get(recommendation_lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY)
    if isinstance(prior_store, Mapping):
        prior_signatures = {str(k): str(v) for k, v in prior_store.items()}

    changes = recommendation_lifecycle.compare_inventory_signatures(
        prior_signatures,
        signatures,
        prior_top=prior_top,
        current_top=top_recommendation_id,
    )
    prior_history_snapshots = decision_history.load_prior_snapshots(session)
    if not prior_history_snapshots and prior_signatures:
        # First history-capable publish after signatures already exist: seed
        # prior snapshots without inventing transitions from an empty board.
        if isinstance(prior_snapshot, Mapping):
            prior_history_snapshots = decision_history.build_prior_snapshot_map(
                tuple(prior_snapshot.get("records") or ())
            )
    had_prior_inventory = bool(prior_signatures) or bool(prior_history_snapshots)
    if (
        isinstance(prior_snapshot, Mapping)
        and _text(prior_snapshot.get("context_fingerprint")) == fingerprint_key
        and not changes
        and _text(prior_snapshot.get("league_id")) == _text(league_id)
    ):
        session[ACTIVITY_INBOX_SNAPSHOT_KEY] = {
            **prior_snapshot,
            "live_draft_active": bool(live_draft_active),
            "entitlement": _text(entitlement, "free"),
        }
        session[recommendation_lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY] = signatures
        session[recommendation_lifecycle.LIFECYCLE_PRIOR_TOP_RECOMMENDATION_KEY] = (
            top_recommendation_id
        )
        # Identical inventory — refresh prior snapshot index, emit zero events.
        new_events = decision_history.record_inventory_transition(
            session,
            (),
            prior_snapshots=prior_history_snapshots,
            current_records=records,
            league_id=league_id,
            roster_id=roster_id,
            scoring_format=scoring_format,
            valuation_lens=valuation_lens,
            prior_top_id=prior_top,
        )
        _persist_decision_memory(
            session,
            new_events=new_events,
            signatures=signatures,
            league_id=league_id,
            roster_id=roster_id,
            context_fingerprint=fingerprint_key,
            scoring_format=scoring_format,
            valuation_lens=valuation_lens,
            top_recommendation_id=top_recommendation_id,
            supabase_config=supabase_config,
        )
        return

    # First observation of an inventory seeds baselines only — no history spam.
    history_changes = changes if had_prior_inventory else ()
    new_events = decision_history.record_inventory_transition(
        session,
        history_changes,
        prior_snapshots=prior_history_snapshots,
        current_records=records,
        league_id=league_id,
        roster_id=roster_id,
        scoring_format=scoring_format,
        valuation_lens=valuation_lens,
        prior_top_id=prior_top,
    )
    _persist_decision_memory(
        session,
        new_events=new_events,
        signatures=signatures,
        league_id=league_id,
        roster_id=roster_id,
        context_fingerprint=fingerprint_key,
        scoring_format=scoring_format,
        valuation_lens=valuation_lens,
        top_recommendation_id=top_recommendation_id,
        supabase_config=supabase_config,
    )

    session[ACTIVITY_INBOX_SNAPSHOT_KEY] = {
        "league_id": _text(league_id),
        "roster_id": _text(roster_id),
        "entitlement": _text(entitlement, "free"),
        "live_draft_active": bool(live_draft_active),
        "context_fingerprint": fingerprint_key,
        "material_signatures": signatures,
        "top_recommendation_id": top_recommendation_id,
        "records": records,
    }
    session[recommendation_lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY] = signatures
    session[recommendation_lifecycle.LIFECYCLE_PRIOR_TOP_RECOMMENDATION_KEY] = (
        top_recommendation_id
    )


def _persist_decision_memory(
    session: MutableMapping[str, Any],
    *,
    new_events: Sequence[Any],
    signatures: Mapping[str, str],
    league_id: str,
    roster_id: str,
    context_fingerprint: str,
    scoring_format: str,
    valuation_lens: str,
    top_recommendation_id: str,
    supabase_config: Mapping[str, Any] | None,
) -> None:
    """Best-effort durable sync — never raises into Dashboard publish."""

    try:
        snapshots = decision_history.load_prior_snapshots(session)
        decision_memory.persist_after_transition(
            session,
            new_events=tuple(new_events or ()),
            signatures=signatures,
            snapshots=snapshots,
            league_id=league_id,
            roster_id=roster_id,
            context_fingerprint=context_fingerprint,
            scoring_format=scoring_format,
            valuation_lens=valuation_lens,
            top_recommendation_id=top_recommendation_id,
            config=supabase_config,
        )
    except Exception:
        return


def _live_draft_notification(*, league_id: str) -> NotificationItem:
    return NotificationItem(
        id=f"live-draft:{_text(league_id) or 'active'}",
        category="Live Draft",
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
    return NotificationItem(
        id=note_id,
        category=_text(record.get("category"), "League"),
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
    )


def compose_activity_inbox(
    *,
    session: Mapping[str, Any] | None = None,
    league_id: str = "",
    roster_id: str = "",
    entitlement: str = "free",
    include_product_update: bool = True,
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

    if include_product_update:
        product = product_update_notification()
        if is_notification_read(session_map, product.id, league_id=league_key):
            product = NotificationItem(**{**product.to_dict(), "unread": False})
        items.append(product)

    return ranked_notifications(tuple(items[:MAX_INBOX_ITEMS]))


def list_founder_beta_notifications(
    *,
    session: dict | None = None,
) -> tuple[NotificationItem, ...]:
    """Return the composed activity inbox for the current session."""

    entitlement = "free"
    if isinstance(session, Mapping):
        entitlement = _text(session.get("_effective_entitlement"), "free")
    return compose_activity_inbox(session=session, entitlement=entitlement)


def mark_stale(
    item: NotificationItem,
    *,
    reason: str,
) -> NotificationItem:
    return NotificationItem(
        **{
            **item.to_dict(),
            "stale": True,
            "stale_reason": _text(reason, "No longer active"),
            "href_hint": "",
            "unread": False,
        }
    )


def validate_notification_for_open(
    item: NotificationItem,
    *,
    session: Mapping[str, Any] | None,
    current_league_id: str,
) -> NotificationItem:
    """Fail closed when underlying canonical context is gone or mismatched."""

    league_key = _text(current_league_id)
    item_league = _text(item.league_id)
    if item.source_kind == "product":
        return item
    if item_league and league_key and item_league != league_key:
        return mark_stale(
            item,
            reason="This alert belongs to another league. Switch leagues to open it.",
        )
    if item.category == "Live Draft":
        if not bool((session or {}).get("_cached_live_draft_active")):
            snap = (session or {}).get(ACTIVITY_INBOX_SNAPSHOT_KEY)
            if not (isinstance(snap, Mapping) and snap.get("live_draft_active")):
                return mark_stale(item, reason="Draft has ended")
        return item

    snapshot = (session or {}).get(ACTIVITY_INBOX_SNAPSHOT_KEY) if session else None
    if item.recommendation_id and isinstance(snapshot, Mapping):
        active_ids = {
            _text(record.get("recommendation_id"))
            for record in (snapshot.get("records") or ())
            if isinstance(record, Mapping)
        }
        if item.recommendation_id not in active_ids:
            return mark_stale(item, reason="Recommendation updated")
    if item.player_id and item.href_hint == "player_quick_view":
        # Player-specific opens still route when inventory exists; without snapshot
        # treat as unavailable rather than inventing a dossier.
        if not isinstance(snapshot, Mapping):
            return mark_stale(item, reason="Player is no longer available")
    if item.href_hint and item.provenance.startswith("dashboard_inventory"):
        if not isinstance(snapshot, Mapping):
            return mark_stale(item, reason="No longer active")
        active_ids = {
            _text(record.get("id"))
            for record in (snapshot.get("records") or ())
            if isinstance(record, Mapping)
        }
        if item.id not in active_ids and not item.recommendation_id:
            return mark_stale(item, reason="No longer active")
    return item


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
    meta = f"{_text(item.category)} · {_text(item.age_label, 'Now')}"
    primary = _text(item.title)
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
    }


def notification_item_html(item: NotificationItem) -> str:
    state = "is-unread" if item.unread and not item.stale else "is-read"
    if item.stale:
        state = "is-stale is-read"
    band = notification_priority_band(item)
    hint = escape(item.href_hint) if item.href_hint and not item.stale else ""
    compact = compact_inbox_presentation(item)
    stale_html = (
        f"<div class='dg-notification-item__stale'>{escape(item.stale_reason or 'No longer active')}</div>"
        if item.stale
        else ""
    )
    action_html = (
        f"<div class='dg-notification-item__action-line'>{escape(compact['action_line'])}</div>"
        if compact["action_line"]
        else ""
    )
    reason_html = (
        f"<p class='dg-notification-item__body'>{escape(compact['reason_line'])}</p>"
        if compact["reason_line"]
        else ""
    )
    source_attr = escape(item.source_kind)
    return (
        f"<article class='dg-notification-item {state} dg-notification-item--{band}' "
        f"data-notification-id='{escape(item.id)}' "
        f"data-source-kind='{source_attr}'"
        f"{f' data-href-hint={chr(34)}{hint}{chr(34)}' if hint else ''}"
        f"{f' data-recommendation-id={chr(34)}{escape(item.recommendation_id)}{chr(34)}' if item.recommendation_id else ''}"
        f"{f' data-player-id={chr(34)}{escape(item.player_id)}{chr(34)}' if item.player_id else ''}>"
        f"<div class='dg-notification-item__meta'>"
        f"<span class='dg-notification-item__category'>{escape(compact['meta'])}</span>"
        "</div>"
        f"<div class='dg-notification-item__title'>{escape(compact['primary'])}</div>"
        f"{action_html}"
        f"{reason_html}"
        f"{stale_html}"
        "</article>"
    )


def _close_inbox(key_prefix: str) -> None:
    st.session_state[f"{key_prefix}_inbox_open"] = False


def _inbox_header_html(*, unread: int, status_note: str = "") -> str:
    """Compact Alerts chrome — single title matching the command-bar trigger."""

    status = (
        f"<div class='dg-notification-panel__status'>"
        f"{escape(str(unread))} unread"
        f"</div>"
        if unread > 0
        else "<div class='dg-notification-panel__status'>All caught up</div>"
    )
    note_html = (
        f"<div class='dg-notification-panel__note'>{escape(status_note)}</div>"
        if status_note
        else ""
    )
    return (
        "<div class='dg-notification-panel' role='region' "
        "aria-label='Alerts'>"
        "<div class='dg-notification-panel__header'>"
        "<div class='dg-notification-panel__title-row'>"
        "<div class='dg-notification-panel__title'>Alerts</div>"
        f"{status}"
        "</div>"
        f"{note_html}"
        "</div>"
    )


def _render_inbox_panel(
    *,
    resolved: Sequence[NotificationItem],
    key_prefix: str,
    action_key_prefix: str,
    status_note: str,
    on_open_item: Callable[[NotificationItem], None] | None,
    on_open_destination: Callable[[str], None] | None,
    empty_copy: str,
) -> None:
    """Render inbox body with each card immediately followed by its real CTA."""

    unread = unread_count(resolved)
    render_html_fragment(_inbox_header_html(unread=unread, status_note=status_note))
    if not resolved:
        render_html_fragment(
            f"<p class='dg-notification-panel__empty'>{escape(empty_copy)}</p>"
        )
    for item in resolved:
        render_html_fragment(notification_item_html(item))
        if item.stale:
            continue
        hint = str(item.href_hint or "").strip()
        cta = destination_label(hint)
        if not hint or not cta:
            continue
        with st.container(key=f"dg_notify_action_{action_key_prefix}_{item.id}"):

            def _handle_item_open(
                _item: NotificationItem = item,
                _prefix: str = key_prefix,
                _callback=on_open_item,
            ) -> None:
                _close_inbox(_prefix)
                if _callback is not None:
                    _callback(_item)

            def _handle_destination_open(
                _destination: str = hint,
                _prefix: str = key_prefix,
                _callback=on_open_destination,
            ) -> None:
                _close_inbox(_prefix)
                if _callback is not None:
                    _callback(_destination)

            if on_open_item is not None:
                st.button(
                    f"{cta} →",
                    key=f"{action_key_prefix}_go_{item.id}",
                    use_container_width=True,
                    on_click=_handle_item_open,
                )
            elif on_open_destination is not None:
                if key_prefix.startswith("fixture"):
                    st.link_button(
                        f"{cta} →",
                        url=(
                            f"?surface=dashboard&notify=populated&inbox=open"
                            f"&fixture_nav={hint}"
                        ),
                        use_container_width=True,
                        key=f"{action_key_prefix}_go_{item.id}",
                    )
                else:
                    st.button(
                        f"{cta} →",
                        key=f"{action_key_prefix}_go_{item.id}",
                        use_container_width=True,
                        on_click=_handle_destination_open,
                    )
    render_html_fragment("</div>")
    notice = st.session_state.pop("_notification_open_notice", None)
    if notice:
        st.caption(str(notice))


def render_notification_center(
    *,
    items: Sequence[NotificationItem] | None = None,
    on_open_item: Callable[[NotificationItem], None] | None = None,
    on_open_destination: Callable[[str], None] | None = None,
    key_prefix: str = "executive_notifications",
) -> None:
    """Render Alerts as an anchored command-bar dropdown (not a centered modal).

    Interaction integrity from #150 is preserved: every actionable card is
    immediately followed by its real Streamlit CTA control. Decorative HTML
    never acts as the click target.
    """

    resolved = (
        list_founder_beta_notifications(session=st.session_state)
        if items is None
        else ranked_notifications(tuple(items))
    )
    count = unread_count(resolved)
    label = f"Alerts ({count})" if count else "Alerts"
    has_canonical = any(item.source_kind == "canonical" for item in resolved)
    # Compact chrome only — product updates stay subordinate via item styling.
    # Avoid introductory copy that pushes the first notification below the fold.
    status_note = ""
    empty_copy = (
        "No league activity yet."
        if not has_canonical
        else "You're all caught up."
    )
    open_key = f"{key_prefix}_inbox_open"
    force_open = bool(st.session_state.get(open_key)) and key_prefix.startswith("fixture")

    with st.container(key=f"executive_command_cell_alerts_{key_prefix}"):
        with st.popover(label, key=f"{key_prefix}_alerts_popover"):
            interaction_latency.mark_interaction_milestone("alerts_compose_only")
            # When the Chromium harness force-opens the panel, skip the popover
            # body so we never paint a duplicate Inbox title stack.
            if not force_open:
                _render_inbox_panel(
                    resolved=resolved,
                    key_prefix=key_prefix,
                    action_key_prefix=key_prefix,
                    status_note=status_note,
                    on_open_item=on_open_item,
                    on_open_destination=on_open_destination,
                    empty_copy=empty_copy,
                )

        # Deterministic harness open path when ?inbox=open — same body/CTA
        # contract without relying on a giant dialog or popover portal quirks.
        if force_open:
            with st.container(key=f"{key_prefix}_inbox_harness_open"):
                render_html_fragment(
                    "<div class='dg-notification-harness-open' data-inbox-open='1'></div>"
                )
                _render_inbox_panel(
                    resolved=resolved,
                    key_prefix=key_prefix,
                    action_key_prefix=f"{key_prefix}_harness",
                    status_note=status_note,
                    on_open_item=on_open_item,
                    on_open_destination=on_open_destination,
                    empty_copy=empty_copy,
                )
