"""Fail-closed orchestration for offline archetype validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import pandas as pd

from modules.archetype_comparison import (
    bound_violations,
    compare_asset_frames,
    compare_recommendations,
    grouped_mean_deltas,
    validate_directional_expectations,
)
from modules.archetype_experiment_models import (
    BaselineIdentity,
    ExperimentalArchetypeSpec,
    ValidationReport,
)


@dataclass(frozen=True)
class AssetExplanation:
    asset_id: str
    baseline_value: float
    candidate_value: float
    total_delta: float
    contributing_adjustments: tuple[tuple[str, float], ...]
    capped_adjustments: tuple[str, ...]
    rationale: str
    template_version: str


def apply_candidate_fail_closed(
    *,
    spec: ExperimentalArchetypeSpec,
    baseline: pd.DataFrame,
    league_settings: Mapping[str, object],
    transformation: Callable[[pd.DataFrame], pd.DataFrame],
) -> tuple[pd.DataFrame, str | None]:
    """Run only in declared formats; otherwise return an isolated baseline copy."""

    league_format = str(league_settings.get("league_format") or "")
    qb_format = str(league_settings.get("qb_format") or "")
    scoring = "TE Premium" if league_settings.get("te_premium") else "Standard"
    supported = (
        league_format in spec.intended_league_context
        and qb_format in spec.supported_roster_formats
        and scoring in spec.supported_scoring_formats
    )
    if not supported:
        return baseline.copy(deep=True), "unsupported_format"
    source = baseline.copy(deep=True)
    try:
        result = transformation(source)
        if not isinstance(result, pd.DataFrame):
            raise TypeError("Candidate transformation must return a DataFrame")
    except Exception:
        return baseline.copy(deep=True), "candidate_error"
    return result, None


def pick_chronology_failures(picks: pd.DataFrame) -> tuple[str, ...]:
    """Check only deterministic year/round coherence, not subjective pick prices."""

    required = {"asset_id", "year", "round", "value_score"}
    if not required.issubset(picks.columns):
        return ("pick_schema_missing",)
    failures = []
    ordered = picks.sort_values(["year", "round"], kind="stable")
    for year, group in ordered.groupby("year", sort=True):
        values = pd.to_numeric(group["value_score"], errors="coerce")
        if not values.is_monotonic_decreasing:
            failures.append(f"pick_round_order:{year}")
    firsts = ordered[ordered["round"].eq(1)].sort_values("year")
    if not pd.to_numeric(firsts["value_score"], errors="coerce").is_monotonic_decreasing:
        failures.append("pick_year_order")
    return tuple(failures)


def explanation_failures(
    explanations: Mapping[str, AssetExplanation],
    changed_asset_ids: set[str],
    *,
    expected_template_version: str,
    declared_dimensions: tuple[str, ...] = (),
) -> tuple[str, ...]:
    failures = []
    for asset_id in sorted(changed_asset_ids):
        explanation = explanations.get(asset_id)
        if explanation is None:
            failures.append(f"{asset_id}:missing_explanation")
            continue
        if explanation.template_version != expected_template_version:
            failures.append(f"{asset_id}:template_version")
        if not explanation.contributing_adjustments or not explanation.rationale.strip():
            failures.append(f"{asset_id}:incomplete_explanation")
        contribution_dimensions = {
            dimension for dimension, _ in explanation.contributing_adjustments
        }
        if not contribution_dimensions.issubset(set(declared_dimensions)):
            failures.append(f"{asset_id}:undeclared_explanation_dimension")
        contribution_total = sum(value for _, value in explanation.contributing_adjustments)
        if round(contribution_total, 8) != round(explanation.total_delta, 8):
            failures.append(f"{asset_id}:contribution_mismatch")
        if round(explanation.candidate_value - explanation.baseline_value, 8) != round(
            explanation.total_delta, 8
        ):
            failures.append(f"{asset_id}:delta_mismatch")
    return tuple(failures)


def validate_experiment(
    *,
    spec: ExperimentalArchetypeSpec,
    baseline_identity: BaselineIdentity,
    fixture_labels: tuple[str, ...],
    baseline_assets: pd.DataFrame,
    candidate_assets: pd.DataFrame,
    baseline_picks: pd.DataFrame | None = None,
    candidate_picks: pd.DataFrame | None = None,
    baseline_recommendations: tuple[dict[str, object], ...] = (),
    candidate_recommendations: tuple[dict[str, object], ...] = (),
    explanations: Mapping[str, AssetExplanation] | None = None,
    unsupported_scenarios: tuple[str, ...] = (),
    product_review_complete: bool = False,
    rollback_verified: bool = True,
) -> ValidationReport:
    deltas, invariants, schema_equal, dtypes_equal, ordering_equal = compare_asset_frames(
        baseline_assets,
        candidate_assets,
    )
    invariant_list = list(invariants)
    pick_deltas = ()
    if baseline_picks is not None and candidate_picks is not None:
        pick_deltas, pick_invariants, pick_schema, pick_dtypes, pick_order = compare_asset_frames(
            baseline_picks.rename(columns={"asset_id": "player_id"}),
            candidate_picks.rename(columns={"asset_id": "player_id"}),
            value_column="value_score",
        )
        invariant_list.extend(f"picks:{item}" for item in pick_invariants)
        invariant_list.extend(pick_chronology_failures(candidate_picks))
        schema_equal = schema_equal and pick_schema
        dtypes_equal = dtypes_equal and pick_dtypes
        ordering_equal = ordering_equal and pick_order
    invariants = tuple(sorted(set(invariant_list)))
    bounds = bound_violations(deltas, spec)
    directional = validate_directional_expectations(
        baseline_assets,
        deltas,
        spec.expected_directional_effects,
    )
    changed = {
        delta.asset_id
        for delta in deltas
        if delta.absolute_delta not in {None, 0}
    }
    explanation_issues = explanation_failures(
        explanations or {},
        changed,
        expected_template_version=spec.explanation_template_version,
        declared_dimensions=spec.affected_dimensions,
    )
    impact = compare_recommendations(
        baseline_recommendations,
        candidate_recommendations,
    )
    warnings = []
    if (
        impact.added
        or impact.removed
        or impact.reordered
        or impact.composition_changed
        or impact.classification_changed
        or impact.strength_changed
    ):
        warnings.append("recommendation_review_required")
    if impact.unsupported:
        warnings.append("recommendation_comparison_unsupported")
    if unsupported_scenarios:
        warnings.append("unsupported_scenarios_present")

    hard_pass = not (
        invariants
        or bounds
        or directional
        or explanation_issues
        or unsupported_scenarios
        or impact.unsupported
    )
    promotion_eligible = bool(
        hard_pass
        and product_review_complete
        and rollback_verified
        and spec.production_eligible
    )
    unchanged_count = sum(delta.absolute_delta == 0 for delta in deltas)
    unchanged_percentage = (
        (unchanged_count / len(deltas)) * 100 if deltas else 0.0
    )
    changed_with_values = [
        delta for delta in deltas if delta.absolute_delta not in {None, 0}
    ]
    largest_increases = tuple(
        delta.asset_id
        for delta in sorted(
            changed_with_values,
            key=lambda item: item.absolute_delta or 0,
            reverse=True,
        )[:10]
        if (delta.absolute_delta or 0) > 0
    )
    largest_decreases = tuple(
        delta.asset_id
        for delta in sorted(
            changed_with_values,
            key=lambda item: item.absolute_delta or 0,
        )[:10]
        if (delta.absolute_delta or 0) < 0
    )
    return ValidationReport(
        experiment_id=spec.archetype_id,
        baseline=baseline_identity,
        fixture_labels=fixture_labels,
        schema_equal=schema_equal,
        dtypes_equal=dtypes_equal,
        ordering_equal=ordering_equal,
        invariant_failures=invariants,
        warnings=tuple(warnings),
        asset_deltas=deltas,
        draft_pick_deltas=pick_deltas,
        unchanged_asset_count=unchanged_count,
        unchanged_asset_percentage=unchanged_percentage,
        largest_increases=largest_increases,
        largest_decreases=largest_decreases,
        position_summaries=grouped_mean_deltas(deltas, "position"),
        age_band_summaries=grouped_mean_deltas(deltas, "age_band"),
        value_tier_summaries=grouped_mean_deltas(deltas, "value_tier"),
        bound_violations=bounds,
        directional_failures=directional,
        recommendation_impact=impact,
        explanation_failures=explanation_issues,
        unsupported_scenarios=unsupported_scenarios,
        product_review_complete=product_review_complete,
        rollback_verified=rollback_verified,
        promotion_eligible=promotion_eligible,
    )
