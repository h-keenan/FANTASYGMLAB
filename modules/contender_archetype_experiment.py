"""Offline-only Contender valuation hypothesis.

This module is intentionally independent from the production archetype registry.
It transforms an isolated Balanced Dynasty result only when the caller supplies
an explicit contender fixture context.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import pandas as pd

from modules.archetype_experiment_models import (
    AdjustmentBound,
    DirectionalExpectation,
    ExperimentalArchetypeSpec,
    ExperimentStatus,
)
from modules.archetype_validation import AssetExplanation


CONTENDER_EXPERIMENT_ID = "contender"
CONTENDER_REFERENCE_YEAR = 2026
CONTENDER_PLAYER_CAP_PERCENT = 8.0
CONTENDER_ELITE_YOUNG_DOWNSIDE_CAP_PERCENT = 2.0
CONTENDER_PICK_CAP_PERCENT = 3.0
CONTENDER_CONTRIBUTION_CAP_PERCENT = 4.0

_AVAILABLE_STATUSES = {"active", "healthy"}
_UNCERTAIN_STATUSES = {
    "questionable", "doubtful", "out", "injured reserve", "ir",
    "suspended", "inactive",
}


CONTENDER_DRAFT_SPEC = ExperimentalArchetypeSpec(
    archetype_id=CONTENDER_EXPERIMENT_ID,
    display_name="Contender",
    hypothesis=(
        "For an explicitly identified dynasty contender, modestly emphasize "
        "reliable near-term production and time-to-realization without replacing "
        "Balanced Dynasty's long-term valuation."
    ),
    intended_user=(
        "A dynasty manager with an explicit current- or next-season contention "
        "window and sufficient lineup strength to prioritize near-term points."
    ),
    intended_league_context=("Dynasty",),
    supported_scoring_formats=("Standard", "TE Premium"),
    supported_roster_formats=("1QB", "Superflex"),
    source_engine_version="balanced-production-v1",
    transformation_version="contender-fixture-v1",
    affected_dimensions=(
        "near_term_production_reliability",
        "near_term_availability",
        "time_to_realization",
        "draft_pick_distance",
        "cap_adjustment",
    ),
    excluded_dimensions=(
        "player_identity",
        "news_narrative",
        "projection_inference",
        "independent_age_multiplier",
        "independent_positional_scarcity",
        "production_roster_classification",
    ),
    expected_directional_effects=(
        DirectionalExpectation(
            name="explicitly_available_assets",
            selector_field="status",
            selector_values=("Active",),
            direction="increase",
            minimum_matching_share=0.5,
            maximum_undeclared_absolute_delta=1_000.0,
        ),
        DirectionalExpectation(
            name="unavailable_assets_receive_no_bonus",
            selector_field="status",
            selector_values=("Injured Reserve",),
            direction="decrease",
            minimum_matching_share=1.0,
            maximum_undeclared_absolute_delta=1_000.0,
        ),
    ),
    maximum_adjustment_bounds=(
        AdjustmentBound("value", 800.0, CONTENDER_PLAYER_CAP_PERCENT),
    ),
    explanation_template_version="contender-explanation-v1",
    experiment_status=ExperimentStatus.DRAFT,
    owner="DynastyGM product and engineering",
    review_date="fixture review required",
    production_eligible=False,
)


def fixture_validated_spec() -> ExperimentalArchetypeSpec:
    """Return review metadata only; this does not register the experiment."""

    return replace(
        CONTENDER_DRAFT_SPEC,
        experiment_status=ExperimentStatus.FIXTURE_VALIDATED,
    )


@dataclass(frozen=True)
class CandidateResult:
    assets: pd.DataFrame
    picks: pd.DataFrame
    explanations: Mapping[str, AssetExplanation]
    applied: bool
    fallback_reason: str | None
    cap_hits: tuple[str, ...]


def classify_fixture_context(roster_profile: str) -> str:
    normalized = str(roster_profile or "").strip().casefold()
    if normalized == "contender":
        return "intended"
    if normalized == "rebuild":
        return "unsupported"
    return "neutral"


def _number(value: object) -> float | None:
    result = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(result) else float(result)


def _normalized_status(row: Mapping[str, object]) -> str:
    injury = str(row.get("injury_status") or "").strip().casefold()
    status = str(row.get("status") or "").strip().casefold()
    return injury or status


def _round_delta(baseline: float, percentage: float) -> float:
    return float(round(baseline * percentage / 100.0))


def _player_contributions(row: Mapping[str, object]) -> tuple[tuple[str, float], ...]:
    baseline = _number(row.get("dynasty_score"))
    current = _number(row.get("value_score"))
    if baseline is None or current is None or baseline <= 0:
        return ()

    status = _normalized_status(row)
    explicitly_available = status in _AVAILABLE_STATUSES
    uncertain = status in _UNCERTAIN_STATUSES or not status
    current_ratio = current / baseline

    production_percent = 0.0
    if explicitly_available and baseline >= 3_000:
        if current_ratio >= 0.97:
            production_percent = 4.0
        elif current_ratio >= 0.90:
            production_percent = 2.0
    elif current_ratio < 0.70:
        production_percent = -2.0

    # Balanced already incorporates injury risk. Availability gates bonuses but
    # deliberately adds no second injury penalty.
    availability_percent = 0.0 if uncertain else 0.0
    time_percent = 0.0
    if current_ratio < 0.75 and (
        row.get("rookie") is True
        or str(row.get("volatility") or "").strip().casefold() == "high"
    ):
        time_percent = -1.5

    production_percent = max(
        -CONTENDER_CONTRIBUTION_CAP_PERCENT,
        min(CONTENDER_CONTRIBUTION_CAP_PERCENT, production_percent),
    )
    time_percent = max(
        -CONTENDER_CONTRIBUTION_CAP_PERCENT,
        min(CONTENDER_CONTRIBUTION_CAP_PERCENT, time_percent),
    )
    return (
        ("near_term_production_reliability", _round_delta(baseline, production_percent)),
        ("near_term_availability", _round_delta(baseline, availability_percent)),
        ("time_to_realization", _round_delta(baseline, time_percent)),
    )


def apply_contender_candidate(
    baseline_assets: pd.DataFrame,
    baseline_picks: pd.DataFrame,
    *,
    league_settings: Mapping[str, object],
    roster_profile: str,
) -> CandidateResult:
    """Apply the candidate to isolated copies or fail closed to exact copies."""

    assets = baseline_assets.copy(deep=True)
    picks = baseline_picks.copy(deep=True)
    context = classify_fixture_context(roster_profile)
    scoring = "TE Premium" if league_settings.get("te_premium") else "Standard"
    supported = (
        str(league_settings.get("league_format") or "") == "Dynasty"
        and str(league_settings.get("qb_format") or "")
        in CONTENDER_DRAFT_SPEC.supported_roster_formats
        and scoring in CONTENDER_DRAFT_SPEC.supported_scoring_formats
    )
    if context != "intended" or not supported:
        reason = "unsupported_context" if context == "unsupported" else (
            "neutral_context" if context == "neutral" else "unsupported_format"
        )
        return CandidateResult(assets, picks, {}, False, reason, ())

    required = {"player_id", "dynasty_score", "value_score", "status", "injury_status"}
    if not required.issubset(assets.columns):
        return CandidateResult(
            baseline_assets.copy(deep=True), baseline_picks.copy(deep=True),
            {}, False, "missing_required_player_fields", (),
        )

    explanations: dict[str, AssetExplanation] = {}
    cap_hits: list[str] = []
    try:
        for index, row in assets.iterrows():
            baseline = _number(row.get("dynasty_score"))
            if baseline is None:
                continue
            contributions = list(_player_contributions(row))
            raw_delta = sum(value for _, value in contributions)
            downward_cap = CONTENDER_PLAYER_CAP_PERCENT
            age = _number(row.get("age"))
            if baseline >= 8_000 and age is not None and age <= 25:
                downward_cap = CONTENDER_ELITE_YOUNG_DOWNSIDE_CAP_PERCENT
            lower = -_round_delta(baseline, downward_cap)
            upper = _round_delta(baseline, CONTENDER_PLAYER_CAP_PERCENT)
            bounded = max(lower, min(upper, raw_delta))
            cap_adjustment = bounded - raw_delta
            contributions.append(("cap_adjustment", cap_adjustment))
            asset_id = str(row["player_id"])
            if cap_adjustment:
                cap_hits.append(asset_id)
            candidate_value = baseline + bounded
            assets.at[index, "dynasty_score"] = candidate_value
            if bounded:
                explanations[asset_id] = AssetExplanation(
                    asset_id=asset_id,
                    baseline_value=baseline,
                    candidate_value=candidate_value,
                    total_delta=bounded,
                    contributing_adjustments=tuple(contributions),
                    capped_adjustments=("total_player_adjustment",) if cap_adjustment else (),
                    rationale=(
                        "Contender fixture adjustment derived from explicit current "
                        "production evidence; availability only gates bonuses because "
                        "Balanced already incorporates injury risk. Experimental only."
                    ),
                    template_version=CONTENDER_DRAFT_SPEC.explanation_template_version,
                )

        required_picks = {"asset_id", "year", "round", "value_score"}
        if required_picks.issubset(picks.columns):
            for index, row in picks.iterrows():
                baseline = _number(row.get("value_score"))
                year = _number(row.get("year"))
                round_number = _number(row.get("round"))
                if baseline is None or year is None or round_number is None:
                    continue
                distance = max(1, int(year) - CONTENDER_REFERENCE_YEAR)
                percent = -min(float(distance), CONTENDER_PICK_CAP_PERCENT)
                delta = _round_delta(baseline, percent)
                candidate_value = baseline + delta
                picks.at[index, "value_score"] = candidate_value
                asset_id = str(row["asset_id"])
                explanations[asset_id] = AssetExplanation(
                    asset_id=asset_id,
                    baseline_value=baseline,
                    candidate_value=candidate_value,
                    total_delta=delta,
                    contributing_adjustments=(("draft_pick_distance", delta),),
                    capped_adjustments=(
                        ("draft_pick_distance",)
                        if distance > CONTENDER_PICK_CAP_PERCENT else ()
                    ),
                    rationale=(
                        "Contender fixture adjustment modestly discounts time to "
                        "realization while preserving pick chronology and round order. "
                        "Experimental only."
                    ),
                    template_version=CONTENDER_DRAFT_SPEC.explanation_template_version,
                )
        return CandidateResult(
            assets, picks, explanations, True, None, tuple(sorted(cap_hits))
        )
    except Exception:
        return CandidateResult(
            baseline_assets.copy(deep=True), baseline_picks.copy(deep=True),
            {}, False, "candidate_error", (),
        )
