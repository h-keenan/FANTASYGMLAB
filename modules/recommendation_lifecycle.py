"""Recommendation lifecycle helpers — presentation and provenance only.

Does not generate, score, order, or Trust-filter recommendations.
Establishes canonical context fingerprinting, material-change detection,
and cross-surface invalidation semantics for Founder Beta.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, MutableMapping, Sequence

from modules import canonical_recommendation_narrative as crn

# Internal lifecycle states — not user-facing labels on every tile.
LIFECYCLE_CURRENT = "current"
LIFECYCLE_CHANGED = "changed"
LIFECYCLE_SUPERSEDED = "superseded"
LIFECYCLE_RESOLVED = "resolved"
LIFECYCLE_STALE = "stale"

# Machine-readable change reasons for explainability foundations.
MATERIAL_CHANGE_ROSTER = "roster_changed"
MATERIAL_CHANGE_PLAYER_AVAILABILITY = "player_availability_changed"
MATERIAL_CHANGE_VALUATION = "valuation_context_changed"
MATERIAL_CHANGE_SCORING = "scoring_context_changed"
MATERIAL_CHANGE_RECOMMENDATION = "recommendation_changed"
MATERIAL_CHANGE_RESOLVED = "recommendation_resolved"
MATERIAL_CHANGE_PRIORITY = "priority_changed"

MATERIAL_CHANGE_REASONS: tuple[str, ...] = (
    MATERIAL_CHANGE_ROSTER,
    MATERIAL_CHANGE_PLAYER_AVAILABILITY,
    MATERIAL_CHANGE_VALUATION,
    MATERIAL_CHANGE_SCORING,
    MATERIAL_CHANGE_RECOMMENDATION,
    MATERIAL_CHANGE_RESOLVED,
    MATERIAL_CHANGE_PRIORITY,
)

LIFECYCLE_CONTEXT_FINGERPRINT_KEY = "_canonical_lifecycle_context_fingerprint"
LIFECYCLE_INVENTORY_SIGNATURES_KEY = "_canonical_lifecycle_inventory_signatures"
LIFECYCLE_BRIEFING_SIGNATURE_KEY = "_canonical_lifecycle_briefing_signature"
LIFECYCLE_PRIOR_TOP_RECOMMENDATION_KEY = "_canonical_lifecycle_prior_top_recommendation"
ROSTER_STATE_VERSION_SESSION_KEY = "_canonical_roster_state_version"


@dataclass(frozen=True)
class RecommendationContext:
    league_id: str
    roster_id: str
    valuation_lens: str


@dataclass(frozen=True)
class CanonicalContextFingerprint:
    """Lightweight football-context identity for lifecycle comparison."""

    account_scope: str
    league_id: str
    roster_id: str
    season: str
    week: str
    scoring_format: str
    valuation_lens: str
    roster_state_version: str
    provider_data_version: str

    @property
    def digest(self) -> str:
        payload = {
            "account_scope": _text(self.account_scope, "anon"),
            "league_id": _text(self.league_id),
            "roster_id": _text(self.roster_id),
            "season": _text(self.season),
            "week": _text(self.week),
            "scoring_format": _text(self.scoring_format),
            "valuation_lens": _text(self.valuation_lens),
            "roster_state_version": _text(self.roster_state_version),
            "provider_data_version": _text(self.provider_data_version),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()[:32]

    @property
    def football_digest(self) -> str:
        """Lifecycle digest without account_scope (account owned separately in package keys).

        Prevents post-usable auth remounts that only stabilize account identity from
        invalidating Game Plan packages when ``account_user_id`` is already keyed.
        """

        payload = {
            "league_id": _text(self.league_id),
            "roster_id": _text(self.roster_id),
            "season": _text(self.season),
            "week": _text(self.week),
            "scoring_format": _text(self.scoring_format),
            "valuation_lens": _text(self.valuation_lens),
            "roster_state_version": _text(self.roster_state_version),
            "provider_data_version": _text(self.provider_data_version),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()[:32]

    def matches(
        self,
        *,
        league_id: str = "",
        roster_id: str = "",
        valuation_lens: str = "",
        scoring_format: str = "",
    ) -> bool:
        if league_id and _text(self.league_id) and _text(self.league_id) != _text(league_id):
            return False
        if roster_id and _text(self.roster_id) and _text(self.roster_id) != _text(roster_id):
            return False
        if (
            valuation_lens
            and _text(self.valuation_lens)
            and _text(self.valuation_lens) != _text(valuation_lens)
        ):
            return False
        if (
            scoring_format
            and _text(self.scoring_format)
            and _text(self.scoring_format) != _text(scoring_format)
        ):
            return False
        return True


@dataclass(frozen=True)
class InventoryChange:
    recommendation_id: str
    prior_state: str
    next_state: str
    reason: str


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


def build_context_fingerprint(
    *,
    session: Mapping[str, Any] | None = None,
    account_scope: str = "",
    league_id: str = "",
    roster_id: str = "",
    season: str = "",
    week: str = "",
    scoring_format: str = "",
    valuation_lens: str = "",
    roster_state_version: str = "",
    provider_data_version: str = "",
) -> CanonicalContextFingerprint:
    """Build one canonical context identity from existing inputs only."""

    scope = _text(account_scope) or _account_scope(session)
    return CanonicalContextFingerprint(
        account_scope=scope,
        league_id=_text(league_id),
        roster_id=_text(roster_id),
        season=_text(season),
        week=_text(week),
        scoring_format=_text(scoring_format),
        valuation_lens=_text(valuation_lens),
        roster_state_version=_text(roster_state_version),
        provider_data_version=_text(provider_data_version),
    )


def load_context_fingerprint(
    state: Mapping[str, Any] | None,
) -> CanonicalContextFingerprint | None:
    raw = (state or {}).get(LIFECYCLE_CONTEXT_FINGERPRINT_KEY)
    if not isinstance(raw, Mapping):
        return None
    try:
        return CanonicalContextFingerprint(
            account_scope=_text(raw.get("account_scope"), "anon"),
            league_id=_text(raw.get("league_id")),
            roster_id=_text(raw.get("roster_id")),
            season=_text(raw.get("season")),
            week=_text(raw.get("week")),
            scoring_format=_text(raw.get("scoring_format")),
            valuation_lens=_text(raw.get("valuation_lens")),
            roster_state_version=_text(raw.get("roster_state_version")),
            provider_data_version=_text(raw.get("provider_data_version")),
        )
    except TypeError:
        return None


def store_context_fingerprint(
    state: MutableMapping[str, Any],
    fingerprint: CanonicalContextFingerprint,
) -> None:
    state[LIFECYCLE_CONTEXT_FINGERPRINT_KEY] = {
        "account_scope": fingerprint.account_scope,
        "league_id": fingerprint.league_id,
        "roster_id": fingerprint.roster_id,
        "season": fingerprint.season,
        "week": fingerprint.week,
        "scoring_format": fingerprint.scoring_format,
        "valuation_lens": fingerprint.valuation_lens,
        "roster_state_version": fingerprint.roster_state_version,
        "provider_data_version": fingerprint.provider_data_version,
        "digest": fingerprint.digest,
    }


def roster_state_version_from_player_ids(player_ids: Sequence[object]) -> str:
    """Lightweight roster ownership fingerprint from player ids only."""

    cleaned = sorted({_text(player_id) for player_id in player_ids if _text(player_id)})
    if not cleaned:
        return ""
    return sha256("|".join(cleaned).encode("utf-8")).hexdigest()[:16]


def clear_lifecycle_session_state(state: MutableMapping[str, Any]) -> None:
    """Drop lifecycle comparison state on logout / account switch."""

    state.pop(LIFECYCLE_CONTEXT_FINGERPRINT_KEY, None)
    state.pop(LIFECYCLE_INVENTORY_SIGNATURES_KEY, None)
    state.pop(LIFECYCLE_BRIEFING_SIGNATURE_KEY, None)
    state.pop(LIFECYCLE_PRIOR_TOP_RECOMMENDATION_KEY, None)
    state.pop(ROSTER_STATE_VERSION_SESSION_KEY, None)
    try:
        from modules import decision_change_history as _decision_history

        _decision_history.clear_decision_history(state)
    except Exception:
        state.pop("_decision_change_history_events", None)
        state.pop("_decision_change_history_prior_snapshot", None)


def _normalized_confidence(value: object) -> str:
    text = _text(value).casefold()
    if not text:
        return ""
    for label in ("high", "medium", "low"):
        if label in text:
            return label
    if text.isdigit():
        number = int(text)
        if number >= 70:
            return "high"
        if number >= 40:
            return "medium"
        return "low"
    return text


def _narrative_material_fields(narrative: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(narrative, Mapping):
        return {}
    return {
        "kind": _text(narrative.get("kind")),
        "action": _text(narrative.get("action")),
        "target_label": _text(narrative.get("target_label")),
        "reason": _text(narrative.get("reason")),
        "confidence_label": _normalized_confidence(narrative.get("confidence_label")),
        "market_signal": _text(narrative.get("market_signal")),
        "fit_signal": _text(narrative.get("fit_signal")),
        "is_active": str(bool(narrative.get("is_active_recommendation", True))),
    }


def recommendation_material_signature(
    item: Mapping[str, Any] | None,
    *,
    priority_rank: int | None = None,
) -> str:
    """Hash canonical recommendation meaning — ignores timestamps and formatting."""

    if not isinstance(item, Mapping):
        return ""
    narrative = item.get("recommendation_narrative")
    if hasattr(narrative, "to_dict"):
        narrative = narrative.to_dict()
    payload = {
        "recommendation_id": item_recommendation_id(item),
        "label": _text(item.get("label")),
        "value": _text(item.get("value")),
        "note": _text(item.get("note")),
        "route_player_id": _text(item.get("route_player_id") or item.get("player_id")),
        "route_focus_mode": _text(item.get("route_focus_mode")),
        "narrative": _narrative_material_fields(
            narrative if isinstance(narrative, Mapping) else None
        ),
        "priority_rank": priority_rank,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()[:24]


def inventory_record_signature(record: Mapping[str, Any]) -> str:
    direct = _text(record.get("material_signature"))
    if direct:
        return direct
    return recommendation_material_signature(record)


def briefing_content_signature(
    items: Sequence[Mapping[str, Any]],
    *,
    quiet: bool = False,
) -> str:
    """Stable digest for Today's Game Plan content."""

    rows = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "recommendation_id": _text(item.get("recommendation_id")),
                "category": _text(item.get("category")),
                "headline": _text(item.get("headline")),
                "reason": _text(item.get("reason")),
                "destination": _text(item.get("destination")),
                "signature": recommendation_material_signature(item, priority_rank=index),
            }
        )
    payload = {"quiet": bool(quiet), "items": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()[:32]


def compare_inventory_signatures(
    prior: Mapping[str, str],
    current: Mapping[str, str],
    *,
    prior_top: str = "",
    current_top: str = "",
) -> tuple[InventoryChange, ...]:
    """Detect material inventory transitions between two signature maps."""

    changes: list[InventoryChange] = []
    prior_ids = set(prior)
    current_ids = set(current)

    if prior_top and current_top and prior_top != current_top:
        changes.append(
            InventoryChange(
                recommendation_id=current_top,
                prior_state=LIFECYCLE_CURRENT,
                next_state=LIFECYCLE_CHANGED,
                reason=MATERIAL_CHANGE_PRIORITY,
            )
        )

    for rec_id in sorted(prior_ids - current_ids):
        changes.append(
            InventoryChange(
                recommendation_id=rec_id,
                prior_state=LIFECYCLE_CURRENT,
                next_state=LIFECYCLE_RESOLVED,
                reason=MATERIAL_CHANGE_RESOLVED,
            )
        )

    for rec_id in sorted(current_ids - prior_ids):
        changes.append(
            InventoryChange(
                recommendation_id=rec_id,
                prior_state=LIFECYCLE_SUPERSEDED,
                next_state=LIFECYCLE_CURRENT,
                reason=MATERIAL_CHANGE_RECOMMENDATION,
            )
        )

    for rec_id in sorted(prior_ids & current_ids):
        if prior.get(rec_id) == current.get(rec_id):
            continue
        changes.append(
            InventoryChange(
                recommendation_id=rec_id,
                prior_state=LIFECYCLE_CURRENT,
                next_state=LIFECYCLE_CHANGED,
                reason=MATERIAL_CHANGE_RECOMMENDATION,
            )
        )
    return tuple(changes)


def context_change_reasons(
    prior: CanonicalContextFingerprint | None,
    current: CanonicalContextFingerprint,
) -> tuple[str, ...]:
    """Return machine-readable reasons when football context changed."""

    if prior is None:
        return ()
    reasons: list[str] = []
    if _text(prior.account_scope) != _text(current.account_scope):
        return (MATERIAL_CHANGE_VALUATION,)
    if _text(prior.league_id) != _text(current.league_id):
        return (MATERIAL_CHANGE_VALUATION,)
    if _text(prior.roster_id) != _text(current.roster_id):
        reasons.append(MATERIAL_CHANGE_ROSTER)
    if _text(prior.roster_state_version) != _text(current.roster_state_version):
        if MATERIAL_CHANGE_ROSTER not in reasons:
            reasons.append(MATERIAL_CHANGE_ROSTER)
    if _text(prior.valuation_lens) != _text(current.valuation_lens):
        reasons.append(MATERIAL_CHANGE_VALUATION)
    if _text(prior.scoring_format) != _text(current.scoring_format):
        reasons.append(MATERIAL_CHANGE_SCORING)
    if _text(prior.season) != _text(current.season) or _text(prior.week) != _text(current.week):
        reasons.append(MATERIAL_CHANGE_PLAYER_AVAILABILITY)
    if _text(prior.provider_data_version) != _text(current.provider_data_version):
        if MATERIAL_CHANGE_PLAYER_AVAILABILITY not in reasons:
            reasons.append(MATERIAL_CHANGE_PLAYER_AVAILABILITY)
    return tuple(reasons)


def sync_lifecycle_on_context_change(
    state: MutableMapping[str, Any],
    fingerprint: CanonicalContextFingerprint,
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    scoring_format: str = "",
) -> tuple[bool, tuple[str, ...]]:
    """Invalidate dependent surfaces when canonical football context changed.

    Returns (context_changed, change_reasons).
    """

    prior = load_context_fingerprint(state)
    reasons = context_change_reasons(prior, fingerprint)
    context_changed = bool(reasons) or prior is None or prior.digest != fingerprint.digest
    if not context_changed:
        return False, ()

    invalidate_stale_narrative(
        state,
        league_id=league_id or fingerprint.league_id,
        roster_id=roster_id or fingerprint.roster_id,
        valuation_lens=valuation_lens or fingerprint.valuation_lens,
        scoring_format=scoring_format or fingerprint.scoring_format,
    )
    if prior is not None and _text(prior.league_id) != _text(fingerprint.league_id):
        state.pop(LIFECYCLE_INVENTORY_SIGNATURES_KEY, None)
        state.pop(LIFECYCLE_BRIEFING_SIGNATURE_KEY, None)
        state.pop(LIFECYCLE_PRIOR_TOP_RECOMMENDATION_KEY, None)
        try:
            from modules import decision_change_history as _decision_history

            _decision_history.clear_decision_history(state)
        except Exception:
            state.pop("_decision_change_history_events", None)
        try:
            from modules import notification_center as _notification_center

            _notification_center.clear_notification_league_snapshot(state)
        except Exception:
            state.pop("activity_inbox_snapshot", None)
    elif reasons:
        state.pop(LIFECYCLE_BRIEFING_SIGNATURE_KEY, None)
        if any(
            reason in reasons
            for reason in (
                MATERIAL_CHANGE_VALUATION,
                MATERIAL_CHANGE_SCORING,
                MATERIAL_CHANGE_ROSTER,
            )
        ):
            state.pop(LIFECYCLE_INVENTORY_SIGNATURES_KEY, None)
            try:
                from modules import notification_center as _notification_center

                _notification_center.clear_notification_context_snapshot(state)
            except Exception:
                state.pop("activity_inbox_snapshot", None)

    store_context_fingerprint(state, fingerprint)
    return True, reasons


def item_recommendation_id(item: Mapping[str, Any] | None) -> str:
    if not isinstance(item, Mapping):
        return ""
    direct = _text(item.get("recommendation_id"))
    if direct:
        return direct
    payload = item.get("recommendation_narrative")
    if isinstance(payload, Mapping):
        return _text(payload.get("recommendation_id"))
    model = crn.CanonicalRecommendationNarrative.from_dict(payload)
    return _text(model.recommendation_id) if model is not None else ""


def narrative_matches_context(
    narrative: crn.CanonicalRecommendationNarrative | Mapping[str, Any] | None,
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    scoring_format: str = "",
) -> bool:
    model = (
        narrative
        if isinstance(narrative, crn.CanonicalRecommendationNarrative)
        else crn.CanonicalRecommendationNarrative.from_dict(narrative)
    )
    if model is None:
        return False
    league_key = _text(league_id)
    roster_key = _text(roster_id)
    lens_key = _text(valuation_lens)
    scoring_key = _text(scoring_format)
    if league_key and _text(model.league_id) and _text(model.league_id) != league_key:
        return False
    if roster_key and _text(model.roster_id) and _text(model.roster_id) != roster_key:
        return False
    if lens_key and _text(model.valuation_lens) and _text(model.valuation_lens) != lens_key:
        return False
    if scoring_key:
        narrative_scoring = _text(getattr(model, "scoring_format", ""))
        if narrative_scoring and narrative_scoring != scoring_key:
            return False
    return True


def invalidate_stale_narrative(
    state: MutableMapping[str, Any],
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    scoring_format: str = "",
) -> bool:
    """Clear bound narrative when league, roster, lens, or scoring no longer match."""

    narrative = crn.load_narrative(state)
    if narrative is None:
        return False
    stored = load_context_fingerprint(state)
    scoring_key = _text(scoring_format)
    if (
        stored is not None
        and scoring_key
        and _text(stored.scoring_format)
        and _text(stored.scoring_format) != scoring_key
    ):
        crn.clear_narrative(state)
        return True
    if narrative_matches_context(
        narrative,
        league_id=league_id,
        roster_id=roster_id,
        valuation_lens=valuation_lens,
        scoring_format=scoring_format,
    ):
        return False
    crn.clear_narrative(state)
    return True


def dedupe_executive_items(
    items: Sequence[Mapping[str, Any]],
    *,
    seen_ids: set[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Drop later tiles that repeat the same recommendation_id."""

    seen = set(seen_ids or ())
    deduped: list[dict[str, Any]] = []
    for item in items:
        copy = dict(item)
        rec_id = item_recommendation_id(copy)
        if rec_id and rec_id in seen:
            continue
        if rec_id:
            seen.add(rec_id)
        deduped.append(copy)
    return tuple(deduped)


def suppress_duplicate_intelligence(
    primary: Mapping[str, Any] | None,
    intelligence: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Hide intelligence tiles that restate the primary recommendation."""

    if primary is None:
        return tuple(intelligence)
    primary_id = item_recommendation_id(primary)
    if not primary_id:
        return tuple(intelligence)
    filtered = [
        item
        for item in intelligence
        if item_recommendation_id(item) != primary_id
    ]
    return tuple(filtered)
