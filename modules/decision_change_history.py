"""Session-scoped decision-change history — presentation only.

Consumes PR #149 lifecycle inventory diffs. Does not generate, score, order,
or Trust-filter recommendations. Does not call Sleeper/Supabase.
"""

from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, fields
from hashlib import sha256
from time import time
from typing import Any, Mapping, MutableMapping, Sequence

from modules import recommendation_lifecycle as lifecycle


DECISION_HISTORY_EVENTS_KEY = "_decision_change_history_events"
DECISION_HISTORY_PRIOR_SNAPSHOT_KEY = "_decision_change_history_prior_snapshot"
DECISION_HISTORY_ACCOUNT_SCOPE_KEY = "_decision_change_history_account_scope"
DECISION_HISTORY_LEAGUE_SCOPE_KEY = "_decision_change_history_league_scope"

MAX_HISTORY_EVENTS = 24
MAX_DASHBOARD_EVENTS = 3

CATEGORY_TRADE = "Trades"
CATEGORY_WAIVER = "Waivers"
CATEGORY_ROSTER = "Roster"
CATEGORY_LEAGUE = "League"
CATEGORY_INJURY = "Injuries"

WHY_LABELS: dict[str, str] = {
    lifecycle.MATERIAL_CHANGE_ROSTER: "Roster changed",
    lifecycle.MATERIAL_CHANGE_PLAYER_AVAILABILITY: "Player availability changed",
    lifecycle.MATERIAL_CHANGE_SCORING: "Scoring context changed",
    lifecycle.MATERIAL_CHANGE_VALUATION: "Strategy focus changed",
    lifecycle.MATERIAL_CHANGE_PRIORITY: "Recommendation priority changed",
    lifecycle.MATERIAL_CHANGE_RESOLVED: "Recommendation no longer active",
    lifecycle.MATERIAL_CHANGE_RECOMMENDATION: "Underlying recommendation context changed",
}

FALLBACK_WHY = "Underlying recommendation context changed."


@dataclass(frozen=True)
class DecisionStateSnapshot:
    """Slim prior/current canonical meaning — not rendered prose as truth."""

    recommendation_id: str = ""
    category: str = ""
    action: str = ""
    target_label: str = ""
    title: str = ""
    confidence_band: str = ""
    priority_rank: int | None = None
    destination: str = ""
    player_id: str = ""
    material_signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> DecisionStateSnapshot | None:
        if not isinstance(payload, Mapping):
            return None
        values: dict[str, Any] = {}
        for field in fields(cls):
            if field.name in payload:
                values[field.name] = payload[field.name]
            elif field.default is not MISSING:
                values[field.name] = field.default
        try:
            return cls(**values)
        except TypeError:
            return None


@dataclass(frozen=True)
class DecisionChangeEvent:
    """Material recommendation transition for Founder Beta session history."""

    event_id: str
    recommendation_id: str
    league_id: str
    roster_id: str
    timestamp: float
    lifecycle_transition: str
    reason: str
    category: str
    target_label: str
    player_id: str
    destination: str
    previous_state: Mapping[str, Any] | None
    current_state: Mapping[str, Any] | None
    previous_priority: int | None = None
    current_priority: int | None = None
    previous_confidence_band: str = ""
    current_confidence_band: str = ""
    scoring_format: str = ""
    valuation_lens: str = ""
    summary_headline: str = ""
    summary_detail: str = ""
    why_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> DecisionChangeEvent | None:
        if not isinstance(payload, Mapping):
            return None
        if not _text(payload.get("event_id")):
            return None
        values: dict[str, Any] = {}
        for field in fields(cls):
            if field.name in payload:
                values[field.name] = payload[field.name]
            elif field.default is not MISSING:
                values[field.name] = field.default
        try:
            return cls(**values)
        except TypeError:
            return None


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


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


def clear_decision_history(state: MutableMapping[str, Any]) -> None:
    """Drop session history on logout, account switch, or league switch."""

    state.pop(DECISION_HISTORY_EVENTS_KEY, None)
    state.pop(DECISION_HISTORY_PRIOR_SNAPSHOT_KEY, None)
    state.pop(DECISION_HISTORY_ACCOUNT_SCOPE_KEY, None)
    state.pop(DECISION_HISTORY_LEAGUE_SCOPE_KEY, None)


def snapshot_from_record(
    record: Mapping[str, Any] | None,
    *,
    priority_rank: int | None = None,
) -> DecisionStateSnapshot | None:
    if not isinstance(record, Mapping):
        return None
    rec_id = _text(record.get("recommendation_id"))
    if not rec_id:
        return None
    narrative = record.get("recommendation_narrative")
    if hasattr(narrative, "to_dict"):
        narrative = narrative.to_dict()
    if not isinstance(narrative, Mapping):
        narrative = {}
    return DecisionStateSnapshot(
        recommendation_id=rec_id,
        category=_text(record.get("category"), CATEGORY_LEAGUE),
        action=_text(narrative.get("action")),
        target_label=_text(narrative.get("target_label")) or _text(record.get("title")),
        title=_text(record.get("title")),
        confidence_band=lifecycle._normalized_confidence(narrative.get("confidence_label")),
        priority_rank=priority_rank,
        destination=_text(record.get("href_hint")),
        player_id=_text(record.get("player_id")),
        material_signature=_text(record.get("material_signature")),
    )


def build_prior_snapshot_map(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index slim prior states by recommendation id for the next publish cycle."""

    snapshot: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        model = snapshot_from_record(record, priority_rank=index)
        if model is None:
            continue
        snapshot[model.recommendation_id] = model.to_dict()
    return snapshot


def why_label_for_reason(reason: str, *, context_reasons: Sequence[str] = ()) -> str:
    for candidate in context_reasons:
        label = WHY_LABELS.get(_text(candidate))
        if label:
            return label
    return WHY_LABELS.get(_text(reason), FALLBACK_WHY)


def _event_id(
    *,
    recommendation_id: str,
    reason: str,
    next_state: str,
    signature: str,
    league_id: str,
) -> str:
    raw = "|".join(
        (
            _text(league_id),
            _text(recommendation_id),
            _text(reason),
            _text(next_state),
            _text(signature),
        )
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def deterministic_summary(
    change: lifecycle.InventoryChange,
    *,
    prior: DecisionStateSnapshot | None,
    current: DecisionStateSnapshot | None,
    prior_top_label: str = "",
) -> tuple[str, str]:
    """Return (headline, detail) from structured differences only."""

    target = _text(
        (current.target_label if current else "")
        or (prior.target_label if prior else "")
        or change.recommendation_id
    )
    category = _text(
        (current.category if current else "")
        or (prior.category if prior else "")
        or CATEGORY_LEAGUE
    )

    if change.reason == lifecycle.MATERIAL_CHANGE_PRIORITY:
        prior_name = _text(prior_top_label) or _text(prior.target_label if prior else "")
        if target and prior_name and prior_name.casefold() != target.casefold():
            return (
                "Top priority changed",
                f"{target} replaced {prior_name} as your leading trade target."
                if category == CATEGORY_TRADE
                else f"{target} replaced {prior_name} as your leading priority.",
            )
        if target:
            return (
                "Top priority changed",
                f"{target} is now your leading trade target."
                if category == CATEGORY_TRADE
                else f"{target} is now your leading priority.",
            )
        return ("Top priority changed", "Your leading recommendation changed.")

    if change.next_state == lifecycle.LIFECYCLE_RESOLVED:
        if category == CATEGORY_WAIVER and target:
            return (
                "Waiver opportunity resolved",
                f"{target} is no longer available in this league.",
            )
        if category == CATEGORY_ROSTER or "need" in _text(prior.action if prior else "").casefold():
            label = target or "This roster need"
            return (
                "Roster need resolved",
                f"{label} is no longer identified as an immediate roster need.",
            )
        if target:
            return (
                "Recommendation resolved",
                f"{target} is no longer an active recommendation.",
            )
        return ("Recommendation resolved", "A prior recommendation is no longer active.")

    if change.reason == lifecycle.MATERIAL_CHANGE_RECOMMENDATION:
        prior_action = _text(prior.action if prior else "")
        current_action = _text(current.action if current else "")
        prior_band = _text(prior.confidence_band if prior else "")
        current_band = _text(current.confidence_band if current else "")
        if prior is None and current is not None:
            if category == CATEGORY_WAIVER and target:
                return (
                    "New waiver opportunity",
                    f"{target} is now an active waiver priority.",
                )
            if category == CATEGORY_TRADE and target:
                return (
                    "New trade opportunity",
                    f"{target} is now an active trade target.",
                )
            if target:
                return ("New recommendation", f"{target} entered your decision board.")
            return ("New recommendation", "A new recommendation became active.")

        if prior_action and current_action and prior_action.casefold() != current_action.casefold():
            return (
                "Recommendation action changed",
                f"Your recommendation on {target or 'this player'} moved from {prior_action} to {current_action}.",
            )
        if prior_band and current_band and prior_band != current_band:
            prior_label = prior_band.title()
            current_label = current_band.title()
            verb = "strengthened" if _band_rank(current_band) > _band_rank(prior_band) else "softened"
            return (
                f"Recommendation {verb}",
                f"Your recommendation on {target or 'this player'} moved from {prior_label} to {current_label}.",
            )
        prior_priority = prior.priority_rank if prior else None
        current_priority = current.priority_rank if current else None
        if (
            prior_priority is not None
            and current_priority is not None
            and prior_priority != current_priority
        ):
            direction = "increased" if current_priority < prior_priority else "decreased"
            return (
                f"Priority {direction}",
                f"{target or 'This recommendation'} moved from priority #{prior_priority} to #{current_priority}.",
            )
        if target:
            return (
                "Recommendation changed",
                f"Your recommendation on {target} changed in a material way.",
            )
        return ("Recommendation changed", "A recommendation changed in a material way.")

    return ("Decision context changed", FALLBACK_WHY)


def _band_rank(band: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(_text(band).casefold(), 1)


def events_from_inventory_changes(
    changes: Sequence[lifecycle.InventoryChange],
    *,
    prior_snapshots: Mapping[str, Mapping[str, Any]],
    current_snapshots: Mapping[str, Mapping[str, Any]],
    league_id: str,
    roster_id: str = "",
    scoring_format: str = "",
    valuation_lens: str = "",
    context_reasons: Sequence[str] = (),
    prior_top_id: str = "",
    timestamp: float | None = None,
) -> tuple[DecisionChangeEvent, ...]:
    """Map lifecycle InventoryChange rows into founder-facing history events."""

    if not changes:
        return ()

    stamped = float(timestamp if timestamp is not None else time())
    prior_top_label = ""
    if prior_top_id and prior_top_id in prior_snapshots:
        prior_top_label = _text(prior_snapshots[prior_top_id].get("target_label"))

    # Prefer one priority event when multiple changes accompany a new #1.
    priority_ids = {
        change.recommendation_id
        for change in changes
        if change.reason == lifecycle.MATERIAL_CHANGE_PRIORITY
    }

    events: list[DecisionChangeEvent] = []
    seen_ids: set[str] = set()
    for change in changes:
        # Suppress redundant "new recommendation" for the same id that already
        # produced a top-priority event in this sync.
        if (
            change.reason == lifecycle.MATERIAL_CHANGE_RECOMMENDATION
            and change.next_state == lifecycle.LIFECYCLE_CURRENT
            and change.recommendation_id in priority_ids
        ):
            continue

        prior = DecisionStateSnapshot.from_dict(prior_snapshots.get(change.recommendation_id))
        current = DecisionStateSnapshot.from_dict(current_snapshots.get(change.recommendation_id))
        if change.reason == lifecycle.MATERIAL_CHANGE_PRIORITY and prior is None and prior_top_id:
            prior = DecisionStateSnapshot.from_dict(prior_snapshots.get(prior_top_id))

        signature = _text(
            (current.material_signature if current else "")
            or (prior.material_signature if prior else "")
            or change.recommendation_id
        )
        event_id = _event_id(
            recommendation_id=change.recommendation_id,
            reason=change.reason,
            next_state=change.next_state,
            signature=signature,
            league_id=league_id,
        )
        if event_id in seen_ids:
            continue
        seen_ids.add(event_id)

        headline, detail = deterministic_summary(
            change,
            prior=prior,
            current=current,
            prior_top_label=prior_top_label,
        )
        category = _text(
            (current.category if current else "")
            or (prior.category if prior else "")
            or CATEGORY_LEAGUE
        )
        target = _text(
            (current.target_label if current else "")
            or (prior.target_label if prior else "")
        )
        destination = _text(
            (current.destination if current else "")
            or (prior.destination if prior else "")
        )
        player_id = _text(
            (current.player_id if current else "")
            or (prior.player_id if prior else "")
        )
        events.append(
            DecisionChangeEvent(
                event_id=event_id,
                recommendation_id=_text(change.recommendation_id),
                league_id=_text(league_id),
                roster_id=_text(roster_id),
                timestamp=stamped,
                lifecycle_transition=f"{change.prior_state}->{change.next_state}",
                reason=_text(change.reason),
                category=category,
                target_label=target,
                player_id=player_id,
                destination=destination,
                previous_state=prior.to_dict() if prior else None,
                current_state=current.to_dict() if current else None,
                previous_priority=prior.priority_rank if prior else None,
                current_priority=current.priority_rank if current else None,
                previous_confidence_band=_text(prior.confidence_band if prior else ""),
                current_confidence_band=_text(current.confidence_band if current else ""),
                scoring_format=_text(scoring_format),
                valuation_lens=_text(valuation_lens),
                summary_headline=headline,
                summary_detail=detail,
                why_label=why_label_for_reason(
                    change.reason,
                    context_reasons=context_reasons,
                ),
            )
        )
    return tuple(events)


def record_inventory_transition(
    session: MutableMapping[str, Any],
    changes: Sequence[lifecycle.InventoryChange],
    *,
    prior_snapshots: Mapping[str, Mapping[str, Any]],
    current_records: Sequence[Mapping[str, Any]],
    league_id: str,
    roster_id: str = "",
    scoring_format: str = "",
    valuation_lens: str = "",
    context_reasons: Sequence[str] = (),
    prior_top_id: str = "",
) -> tuple[DecisionChangeEvent, ...]:
    """Append material events and refresh the prior-snapshot index.

    Identical inventories (empty changes) produce zero events.
    """

    account = _account_scope(session)
    league_key = _text(league_id)
    stored_account = _text(session.get(DECISION_HISTORY_ACCOUNT_SCOPE_KEY))
    stored_league = _text(session.get(DECISION_HISTORY_LEAGUE_SCOPE_KEY))
    if stored_account and stored_account != account:
        clear_decision_history(session)
    elif stored_league and league_key and stored_league != league_key:
        clear_decision_history(session)

    current_snapshots = build_prior_snapshot_map(current_records)
    new_events = events_from_inventory_changes(
        changes,
        prior_snapshots=prior_snapshots,
        current_snapshots=current_snapshots,
        league_id=league_key,
        roster_id=roster_id,
        scoring_format=scoring_format,
        valuation_lens=valuation_lens,
        context_reasons=context_reasons,
        prior_top_id=prior_top_id,
    )

    existing_raw = session.get(DECISION_HISTORY_EVENTS_KEY)
    existing: list[DecisionChangeEvent] = []
    if isinstance(existing_raw, Sequence):
        for row in existing_raw:
            event = DecisionChangeEvent.from_dict(row if isinstance(row, Mapping) else None)
            if event is not None:
                existing.append(event)

    existing_ids = {event.event_id for event in existing}
    merged = list(existing)
    for event in new_events:
        if event.event_id in existing_ids:
            continue
        merged.append(event)
        existing_ids.add(event.event_id)

    merged.sort(key=lambda event: event.timestamp, reverse=True)
    session[DECISION_HISTORY_EVENTS_KEY] = [
        event.to_dict() for event in merged[:MAX_HISTORY_EVENTS]
    ]
    session[DECISION_HISTORY_PRIOR_SNAPSHOT_KEY] = current_snapshots
    session[DECISION_HISTORY_ACCOUNT_SCOPE_KEY] = account
    session[DECISION_HISTORY_LEAGUE_SCOPE_KEY] = league_key
    return new_events


def list_decision_events(
    session: Mapping[str, Any] | None,
    *,
    league_id: str = "",
    limit: int | None = None,
) -> tuple[DecisionChangeEvent, ...]:
    if not isinstance(session, Mapping):
        return ()
    league_key = _text(league_id)
    account = _account_scope(session)
    if _text(session.get(DECISION_HISTORY_ACCOUNT_SCOPE_KEY)) not in {"", account}:
        return ()
    if league_key and _text(session.get(DECISION_HISTORY_LEAGUE_SCOPE_KEY)) not in {
        "",
        league_key,
    }:
        return ()
    raw = session.get(DECISION_HISTORY_EVENTS_KEY)
    if not isinstance(raw, Sequence):
        return ()
    events: list[DecisionChangeEvent] = []
    for row in raw:
        event = DecisionChangeEvent.from_dict(row if isinstance(row, Mapping) else None)
        if event is None:
            continue
        if league_key and _text(event.league_id) and _text(event.league_id) != league_key:
            continue
        events.append(event)
    events.sort(key=lambda event: event.timestamp, reverse=True)
    if limit is not None:
        return tuple(events[: max(0, int(limit))])
    return tuple(events)


def dashboard_events(
    session: Mapping[str, Any] | None,
    *,
    league_id: str = "",
) -> tuple[DecisionChangeEvent, ...]:
    return list_decision_events(session, league_id=league_id, limit=MAX_DASHBOARD_EVENTS)


def age_label(timestamp: float, *, now: float | None = None) -> str:
    current = float(now if now is not None else time())
    delta = max(0, int(current - float(timestamp)))
    if delta < 60:
        return "Just now"
    if delta < 3600:
        minutes = delta // 60
        return f"{minutes}m"
    if delta < 86400:
        hours = delta // 3600
        return f"{hours}h"
    days = delta // 86400
    return f"{days}d"


def destination_is_current(event: DecisionChangeEvent) -> bool:
    """Historical destinations reopen current truth — never resurrect stale advice."""

    return bool(_text(event.destination))


def load_prior_snapshots(session: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = (session or {}).get(DECISION_HISTORY_PRIOR_SNAPSHOT_KEY) if session else None
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): dict(value)
        for key, value in raw.items()
        if isinstance(value, Mapping) and _text(key)
    }
