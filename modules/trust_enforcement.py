"""Production enforcement for Trust Engine evidence.

The validator observes existing outputs.  It never repairs packages, replaces
assets, recalculates values, or changes pre-validation recommendation order.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

from modules.trust_engine import (
    ConfidenceLevel,
    Evidence,
    Freshness,
    recommendation_confidence,
    validate_pick,
    validate_player,
)


class EnforcementLevel(StrEnum):
    PASS = "pass"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class EnforcementResult:
    level: EnforcementLevel
    evidence: Evidence
    reasons: tuple[str, ...] = ()
    user_note: str = ""
    historical_only: bool = False

    @property
    def actionable(self) -> bool:
        return self.level is not EnforcementLevel.BLOCKED and not self.historical_only


@dataclass(frozen=True)
class BoardEnforcementResult:
    recommendations: tuple[dict[str, Any], ...]
    blocked_count: int
    degraded_count: int
    confidence_caps_applied: int
    blocked_reason_counts: tuple[tuple[str, int], ...]
    validation_failed: bool = False

    @property
    def diagnostics(self) -> dict[str, Any]:
        validated = len(self.recommendations) + self.blocked_count
        passed = validated - self.blocked_count - self.degraded_count
        return {
            "trades_validated": validated,
            "trades_passed": max(0, passed),
            "trades_degraded": self.degraded_count,
            "trades_blocked": self.blocked_count,
            "confidence_caps_applied": self.confidence_caps_applied,
            "blocked_reason_counts": dict(self.blocked_reason_counts),
        }


CONFIDENCE_LABELS = {
    "low": ConfidenceLevel.LOW,
    "medium": ConfidenceLevel.MEDIUM,
    "high": ConfidenceLevel.HIGH,
}

USER_EVIDENCE_NOTE = "Confidence limited by incomplete player-status evidence."
UNAVAILABLE_SECTION_MESSAGE = (
    "We couldn’t verify enough current data to produce a trustworthy "
    "recommendation for this section."
)

BLOCKED_PLAYER_REASONS = {
    "missing_player_id",
    "duplicate_player_identity",
    "ambiguous_player_identity",
    "retired_or_ineligible",
    "canonical_player_not_found",
    "contradictory_player_status",
}
BLOCKED_TRADE_REASONS = {
    "invalid_player_identity",
    "invalid_pick",
    "ownership_conflict",
    "duplicate_asset",
    "invalid_roster",
    "ambiguous_asset",
    "invalid_league_context",
    "protected_constraint",
    "validation_error",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).casefold()
    if text in {"1", "true", "yes", "active"}:
        return True
    if text in {"0", "false", "no", "inactive"}:
        return False
    return None


def _evidence(
    *,
    available: Iterable[str] = (),
    missing: Iterable[str] = (),
    freshness: Freshness = Freshness.CURRENT,
    uncertainty: Iterable[str] = (),
) -> Evidence:
    return Evidence(
        available=tuple(dict.fromkeys(value for value in available if value)),
        missing=tuple(dict.fromkeys(value for value in missing if value)),
        freshness=freshness,
        confidence_inputs=("canonical identity", "current eligibility signals"),
        uncertainty=tuple(dict.fromkeys(value for value in uncertainty if value)),
    )


def enforce_player_record(
    player: Mapping[str, Any],
    *,
    eligible: bool,
    eligibility_reason: str = "",
    duplicate_ids: frozenset[str] = frozenset(),
    canonical_player_ids: frozenset[str] | None = None,
    historical: bool = False,
) -> EnforcementResult:
    """Classify one normalized player without changing the underlying record."""

    if hasattr(player, "to_dict"):
        player = player.to_dict()
    player_id = _text(player.get("player_id"))
    reasons: list[str] = []
    if not player_id:
        reasons.append("missing_player_id")
    if player_id and player_id in duplicate_ids:
        reasons.append("duplicate_player_identity")
    if (
        canonical_player_ids is not None
        and player_id
        and player_id not in canonical_player_ids
    ):
        reasons.append("canonical_player_not_found")

    status = _text(player.get("status")).casefold()
    active = _optional_bool(player.get("active"))
    inactive_status = any(
        term in status
        for term in ("retired", "inactive", "historical", "deceased")
    )
    if active is True and inactive_status:
        reasons.append("contradictory_player_status")
    if not eligible:
        reasons.append("retired_or_ineligible")

    validation = validate_player(player)
    freshness = validation.evidence.freshness
    uncertainty: list[str] = []
    if validation.warnings or validation.stale_indicators:
        uncertainty.append("player_status_evidence")

    # Historical surfaces may show a blocked player, but the same object remains
    # explicitly non-actionable.
    if reasons:
        return EnforcementResult(
            EnforcementLevel.DEGRADED if historical else EnforcementLevel.BLOCKED,
            _evidence(
                available=("historical player identity",) if historical else (),
                missing=("safe actionable identity",),
                freshness=freshness,
                uncertainty=uncertainty,
            ),
            tuple(dict.fromkeys(reasons)),
            "Current player eligibility needs verification.",
            historical,
        )

    optional_missing = [
        name
        for name in ("age", "bye_week")
        if player.get(name) in (None, "")
    ]
    if (
        freshness in {Freshness.AGING, Freshness.STALE, Freshness.UNKNOWN}
        or optional_missing
        or uncertainty
    ):
        return EnforcementResult(
            EnforcementLevel.DEGRADED,
            _evidence(
                available=("canonical player identity", "current eligibility"),
                freshness=freshness,
                uncertainty=("incomplete_optional_metadata",) + tuple(uncertainty),
            ),
            ("incomplete_player_evidence",),
            USER_EVIDENCE_NOTE,
        )
    return EnforcementResult(
        EnforcementLevel.PASS,
        _evidence(
            available=("canonical player identity", "current eligibility"),
            freshness=freshness,
        ),
    )


def enforcement_from_player_annotations(
    player: Mapping[str, Any],
) -> EnforcementResult | None:
    """Rehydrate a normalized player's trust result without revalidating it."""

    try:
        level = EnforcementLevel(_text(player.get("trust_enforcement")).casefold())
        evidence_confidence = ConfidenceLevel(
            _text(player.get("trust_evidence_confidence")).casefold()
        )
    except ValueError:
        return None
    freshness = {
        ConfidenceLevel.HIGH: Freshness.CURRENT,
        ConfidenceLevel.MEDIUM: Freshness.UNKNOWN,
        ConfidenceLevel.LOW: Freshness.STALE,
    }[evidence_confidence]
    reason = _text(player.get("trust_block_reason"))
    return EnforcementResult(
        level,
        _evidence(
            available=("normalized player trust result",),
            missing=("safe actionable identity",)
            if level is EnforcementLevel.BLOCKED
            else (),
            freshness=freshness,
            uncertainty=("incomplete_player_status_evidence",)
            if level is EnforcementLevel.DEGRADED
            else (),
        ),
        (reason,) if reason else (),
        USER_EVIDENCE_NOTE if level is EnforcementLevel.DEGRADED else "",
    )


def confidence_from_label(label: Any) -> ConfidenceLevel:
    return CONFIDENCE_LABELS.get(_text(label).casefold(), ConfidenceLevel.LOW)


def confidence_label(level: ConfidenceLevel) -> str:
    return {
        ConfidenceLevel.HIGH: "High",
        ConfidenceLevel.MEDIUM: "Medium",
        ConfidenceLevel.LOW: "Low",
    }[level]


def _asset_key(asset: Mapping[str, Any]) -> str:
    asset_type = _text(asset.get("asset_type")).casefold()
    if asset_type == "player":
        player_id = _text(asset.get("player_id"))
        return f"player:{player_id}" if player_id else ""
    if asset_type == "pick":
        season = _text(asset.get("season"))
        round_value = _text(asset.get("round"))
        original = _text(asset.get("original_roster_id"))
        return f"pick:{season}:{round_value}:{original}" if all((season, round_value, original)) else ""
    return ""


def _partner_roster_id(
    idea: Mapping[str, Any],
    team_name_to_roster: Mapping[str, int],
) -> int:
    try:
        direct = int(idea.get("partner_roster_id") or 0)
    except (TypeError, ValueError):
        direct = 0
    if direct:
        return direct
    return int(team_name_to_roster.get(_text(idea.get("partner_team_name")).casefold(), 0) or 0)


def enforce_trade_recommendation(
    idea: Mapping[str, Any],
    *,
    canonical_players: Mapping[str, Mapping[str, Any]],
    player_enforcement: Mapping[str, EnforcementResult],
    ownership_by_player: Mapping[str, int],
    valid_roster_ids: frozenset[int],
    my_roster_id: int,
    team_name_to_roster: Mapping[str, int],
    league_context_valid: bool,
    untouchable_names: frozenset[str] = frozenset(),
    explicit_player_focus: bool = False,
    focused_player_ids: Sequence[str] | frozenset[str] = (),
) -> tuple[EnforcementResult, dict[str, Any] | None, bool]:
    """Validate one generated trade and return a display-only copy.

    The original mapping and all package lists remain untouched.
    """

    focused_ids = {
        _text(player_id)
        for player_id in (focused_player_ids or ())
        if _text(player_id)
    }

    try:
        send = idea.get("send_assets")
        receive = idea.get("receive_assets")
        if (
            not isinstance(send, Sequence)
            or isinstance(send, (str, bytes))
            or not isinstance(receive, Sequence)
            or isinstance(receive, (str, bytes))
            or not send
            or not receive
        ):
            raise ValueError("malformed package")

        reasons: list[str] = []
        if not league_context_valid:
            reasons.append("invalid_league_context")
        partner_roster_id = _partner_roster_id(idea, team_name_to_roster)
        if (
            my_roster_id not in valid_roster_ids
            or partner_roster_id not in valid_roster_ids
            or partner_roster_id == my_roster_id
        ):
            reasons.append("invalid_roster")

        send_keys = [_asset_key(asset) if isinstance(asset, Mapping) else "" for asset in send]
        receive_keys = [_asset_key(asset) if isinstance(asset, Mapping) else "" for asset in receive]
        if any(not key for key in send_keys + receive_keys):
            reasons.append("ambiguous_asset")
        if len(send_keys) != len(set(send_keys)) or len(receive_keys) != len(set(receive_keys)):
            reasons.append("duplicate_asset")
        if set(send_keys) & set(receive_keys):
            reasons.append("duplicate_asset")

        evidence_levels: list[ConfidenceLevel] = []
        for side, assets, expected_owner in (
            ("send", send, my_roster_id),
            ("receive", receive, partner_roster_id),
        ):
            for asset in assets:
                if not isinstance(asset, Mapping):
                    reasons.append("ambiguous_asset")
                    continue
                asset_type = _text(asset.get("asset_type")).casefold()
                if asset_type == "player":
                    player_id = _text(asset.get("player_id"))
                    player_result = player_enforcement.get(player_id)
                    if not player_id or player_id not in canonical_players or player_result is None:
                        reasons.append("invalid_player_identity")
                    elif player_result.level is EnforcementLevel.BLOCKED:
                        reasons.append("invalid_player_identity")
                    else:
                        evidence_levels.append(player_result.evidence.confidence)
                    if int(ownership_by_player.get(player_id, 0) or 0) != int(expected_owner or 0):
                        reasons.append("ownership_conflict")
                    if side == "send":
                        is_focused_send = bool(
                            explicit_player_focus and player_id and player_id in focused_ids
                        )
                        if (
                            bool(asset.get("is_protected"))
                            and not is_focused_send
                        ) or (
                            _text(asset.get("label")).casefold() in untouchable_names
                            and not is_focused_send
                        ):
                            reasons.append("protected_constraint")
                elif asset_type == "pick":
                    pick_result = validate_pick(asset)
                    if (
                        not pick_result.valid
                        or not _text(asset.get("original_roster_id"))
                        or not _text(asset.get("owner_roster_id"))
                    ):
                        reasons.append("invalid_pick")
                    try:
                        pick_owner = int(asset.get("owner_roster_id") or 0)
                    except (TypeError, ValueError):
                        pick_owner = 0
                    if pick_owner != int(expected_owner or 0):
                        reasons.append("ownership_conflict")
                    evidence_levels.append(pick_result.confidence)
                else:
                    reasons.append("ambiguous_asset")

        reasons = list(dict.fromkeys(reasons))
        if reasons:
            return (
                EnforcementResult(
                    EnforcementLevel.BLOCKED,
                    _evidence(missing=("safe actionable trade assets",)),
                    tuple(reason for reason in reasons if reason in BLOCKED_TRADE_REASONS),
                ),
                None,
                False,
            )

        evidence_confidence = min(
            evidence_levels or [ConfidenceLevel.MEDIUM],
            key={ConfidenceLevel.LOW: 0, ConfidenceLevel.MEDIUM: 1, ConfidenceLevel.HIGH: 2}.__getitem__,
        )
        model_label = _text(idea.get("trade_confidence_label")) or "Low"
        model = confidence_from_label(model_label)
        effective = recommendation_confidence(model, evidence_confidence)
        display = dict(idea)
        display["model_confidence_label"] = confidence_label(model)
        display["evidence_confidence_label"] = confidence_label(evidence_confidence)
        display["effective_confidence_label"] = confidence_label(
            effective.effective_confidence
        )
        display["trade_confidence_label"] = display["effective_confidence_label"]
        display["trust_enforcement"] = (
            EnforcementLevel.DEGRADED.value
            if evidence_confidence is not ConfidenceLevel.HIGH
            else EnforcementLevel.PASS.value
        )
        capped = effective.effective_confidence is not model
        if capped:
            display["trust_evidence_note"] = USER_EVIDENCE_NOTE
        level = (
            EnforcementLevel.DEGRADED
            if evidence_confidence is not ConfidenceLevel.HIGH
            else EnforcementLevel.PASS
        )
        return (
            EnforcementResult(
                level,
                _evidence(
                    available=("canonical trade assets", "ownership"),
                    freshness=(
                        Freshness.CURRENT
                        if level is EnforcementLevel.PASS
                        else Freshness.UNKNOWN
                    ),
                    uncertainty=(
                        ("incomplete_player_status_evidence",)
                        if level is EnforcementLevel.DEGRADED
                        else ()
                    ),
                ),
                ("incomplete_player_evidence",)
                if level is EnforcementLevel.DEGRADED
                else (),
                USER_EVIDENCE_NOTE if capped else "",
            ),
            display,
            capped,
        )
    except Exception:
        return (
            EnforcementResult(
                EnforcementLevel.BLOCKED,
                _evidence(missing=("safe actionable trade validation",)),
                ("validation_error",),
            ),
            None,
            False,
        )


def enforce_trade_board(
    ideas: Iterable[Mapping[str, Any]],
    **context: Any,
) -> BoardEnforcementResult:
    visible: list[dict[str, Any]] = []
    blocked = 0
    degraded = 0
    caps = 0
    reasons: Counter[str] = Counter()
    validation_failed = False
    for idea in ideas:
        result, display, capped = enforce_trade_recommendation(idea, **context)
        if result.level is EnforcementLevel.BLOCKED or display is None:
            blocked += 1
            reasons.update(result.reasons or ("validation_error",))
            validation_failed = validation_failed or "validation_error" in result.reasons
            continue
        if result.level is EnforcementLevel.DEGRADED:
            degraded += 1
        caps += int(capped)
        visible.append(display)
    return BoardEnforcementResult(
        tuple(visible),
        blocked,
        degraded,
        caps,
        tuple(sorted(reasons.items())),
        validation_failed,
    )


def canonical_input_fingerprint(*objects: Any) -> str:
    """Sanitized cache/version fingerprint for evaluated recommendation inputs."""

    encoded = json.dumps(objects, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]
