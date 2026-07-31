"""Pure comparisons for offline archetype validation."""

from __future__ import annotations

import math
from typing import Iterable, Mapping

import pandas as pd

from modules.archetype_experiment_models import (
    AssetDelta,
    DirectionalExpectation,
    ExperimentalArchetypeSpec,
    RecommendationImpact,
)


def _age_band(value: object) -> str:
    age = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(age):
        return "unknown"
    if age <= 23:
        return "21-23"
    if age <= 26:
        return "24-26"
    if age <= 29:
        return "27-29"
    return "30+"


def _value_tier(value: float | None) -> str:
    if value is None:
        return "missing"
    if value >= 8000:
        return "elite"
    if value >= 6000:
        return "high"
    if value >= 3000:
        return "middle"
    return "replacement"


def _numeric(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def compare_asset_frames(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    *,
    identifier: str = "player_id",
    value_column: str = "dynasty_score",
) -> tuple[
    tuple[AssetDelta, ...],
    tuple[str, ...],
    bool,
    bool,
    bool,
]:
    failures: list[str] = []
    schema_equal = tuple(baseline.columns) == tuple(candidate.columns)
    dtypes_equal = tuple(map(str, baseline.dtypes)) == tuple(map(str, candidate.dtypes))
    ordering_equal = (
        identifier in baseline
        and identifier in candidate
        and baseline[identifier].tolist() == candidate[identifier].tolist()
    )
    if not schema_equal:
        failures.append("output_schema_changed")
    if not dtypes_equal:
        failures.append("output_dtypes_changed")
    if not ordering_equal:
        failures.append("asset_order_changed")
    for label, frame in (("baseline", baseline), ("candidate", candidate)):
        if identifier not in frame or value_column not in frame:
            failures.append(f"{label}_required_column_missing")
            continue
        if frame[identifier].duplicated().any():
            failures.append(f"{label}_duplicate_identifiers")
        numeric = pd.to_numeric(frame[value_column], errors="coerce")
        unexpected_nonfinite = numeric.notna() & ~numeric.map(math.isfinite)
        if unexpected_nonfinite.any():
            failures.append(f"{label}_nonfinite_values")
        if (numeric.dropna() < 0).any():
            failures.append(f"{label}_negative_values")
    if (
        identifier not in baseline
        or identifier not in candidate
        or value_column not in baseline
        or value_column not in candidate
    ):
        return (), tuple(sorted(set(failures))), schema_equal, dtypes_equal, ordering_equal

    baseline_ids = baseline[identifier].astype(str)
    candidate_ids = candidate[identifier].astype(str)
    if set(baseline_ids) != set(candidate_ids):
        failures.append("asset_identity_set_changed")
    if baseline_ids.duplicated().any() or candidate_ids.duplicated().any():
        return (
            (),
            tuple(sorted(set(failures))),
            schema_equal,
            dtypes_equal,
            ordering_equal,
        )

    if value_column in baseline and value_column in candidate:
        baseline_missing = baseline.set_index(identifier)[value_column].isna()
        candidate_missing = candidate.set_index(identifier)[value_column].isna()
        if not baseline_missing.equals(candidate_missing.reindex(baseline_missing.index)):
            failures.append("missing_value_mask_changed")

    base = baseline.set_index(identifier, drop=False)
    cand = candidate.set_index(identifier, drop=False)
    common = [asset_id for asset_id in baseline_ids if asset_id in cand.index]
    base_values = pd.to_numeric(base.loc[common, value_column], errors="coerce")
    candidate_values = pd.to_numeric(cand.loc[common, value_column], errors="coerce")
    base_ranks = base_values.rank(method="first", ascending=False)
    candidate_ranks = candidate_values.rank(method="first", ascending=False)
    base_position_ranks: dict[str, float] = {}
    candidate_position_ranks: dict[str, float] = {}
    if "position" in base.columns and "position" in cand.columns:
        for position in sorted(set(base.loc[common, "position"].astype(str))):
            position_ids = [
                asset_id
                for asset_id in common
                if str(base.loc[asset_id].get("position", "")) == position
            ]
            left = base_values.loc[position_ids].rank(method="first", ascending=False)
            right = candidate_values.loc[position_ids].rank(method="first", ascending=False)
            base_position_ranks.update(left.to_dict())
            candidate_position_ranks.update(right.to_dict())
    count = max(1, len(common) - 1)
    deltas = []
    for asset_id in common:
        before = _numeric(base_values.loc[asset_id])
        after = _numeric(candidate_values.loc[asset_id])
        absolute = None if before is None or after is None else after - before
        percentage = (
            None
            if absolute is None or before == 0
            else (absolute / abs(before)) * 100
        )
        rank_delta = (
            None
            if before is None or after is None
            else int(base_ranks.loc[asset_id] - candidate_ranks.loc[asset_id])
        )
        position_rank_delta = (
            None
            if (
                before is None
                or after is None
                or asset_id not in base_position_ranks
                or pd.isna(base_position_ranks[asset_id])
                or pd.isna(candidate_position_ranks[asset_id])
            )
            else int(
                base_position_ranks[asset_id] - candidate_position_ranks[asset_id]
            )
        )
        percentile_delta = None if rank_delta is None else (rank_delta / count) * 100
        row = base.loc[asset_id]
        candidate_row = cand.loc[asset_id]
        baseline_tier = str(row.get("player_tier", ""))
        candidate_tier = str(candidate_row.get("player_tier", ""))
        deltas.append(
            AssetDelta(
                asset_id=str(asset_id),
                position=str(row.get("position", "")),
                age_band=_age_band(row.get("age")),
                value_tier=_value_tier(before),
                baseline_value=before,
                candidate_value=after,
                absolute_delta=absolute,
                percentage_delta=percentage,
                rank_delta=rank_delta,
                position_rank_delta=position_rank_delta,
                percentile_delta=percentile_delta,
                baseline_tier=baseline_tier,
                candidate_tier=candidate_tier,
                tier_changed=baseline_tier != candidate_tier,
            )
        )
    return (
        tuple(deltas),
        tuple(sorted(set(failures))),
        schema_equal,
        dtypes_equal,
        ordering_equal,
    )


def grouped_mean_deltas(
    deltas: Iterable[AssetDelta],
    field: str,
) -> tuple[tuple[str, float], ...]:
    groups: dict[str, list[float]] = {}
    for delta in deltas:
        value = delta.absolute_delta
        if value is not None:
            groups.setdefault(str(getattr(delta, field)), []).append(value)
    return tuple(
        (label, sum(values) / len(values))
        for label, values in sorted(groups.items())
    )


def bound_violations(
    deltas: Iterable[AssetDelta],
    spec: ExperimentalArchetypeSpec,
) -> tuple[str, ...]:
    bounds = {bound.dimension: bound for bound in spec.maximum_adjustment_bounds}
    value_bound = bounds.get("value")
    if value_bound is None:
        return ("missing_value_adjustment_bound",)
    failures = []
    for delta in deltas:
        if delta.absolute_delta is not None and abs(delta.absolute_delta) > value_bound.maximum_absolute_delta:
            failures.append(f"{delta.asset_id}:absolute")
        if (
            value_bound.maximum_percentage_delta is not None
            and delta.percentage_delta is not None
            and abs(delta.percentage_delta) > value_bound.maximum_percentage_delta
        ):
            failures.append(f"{delta.asset_id}:percentage")
    return tuple(failures)


def validate_directional_expectations(
    baseline: pd.DataFrame,
    deltas: tuple[AssetDelta, ...],
    expectations: tuple[DirectionalExpectation, ...],
    *,
    identifier: str = "player_id",
) -> tuple[str, ...]:
    by_id = {delta.asset_id: delta for delta in deltas}
    failures = []
    declared_ids: set[str] = set()
    for expectation in expectations:
        if expectation.selector_field not in baseline:
            failures.append(f"{expectation.name}:selector_missing")
            continue
        mask = baseline[expectation.selector_field].astype(str).isin(expectation.selector_values)
        selected = baseline.loc[mask, identifier].astype(str).tolist()
        declared_ids.update(selected)
        outcomes = []
        for asset_id in selected:
            delta = by_id.get(asset_id)
            value = delta.absolute_delta if delta is not None else None
            outcomes.append(
                value is not None
                and (
                    (expectation.direction == "increase" and value >= 0)
                    or (expectation.direction == "decrease" and value <= 0)
                    or (expectation.direction == "unchanged" and value == 0)
                )
            )
        share = (sum(outcomes) / len(outcomes)) if outcomes else 0.0
        if share < expectation.minimum_matching_share:
            failures.append(f"{expectation.name}:direction")
        outside = [
            delta.asset_id
            for delta in deltas
            if delta.asset_id not in declared_ids
            and delta.absolute_delta is not None
            and abs(delta.absolute_delta) > expectation.maximum_undeclared_absolute_delta
        ]
        if outside:
            failures.append(f"{expectation.name}:undeclared_side_effect")
    return tuple(sorted(set(failures)))


def compare_recommendations(
    baseline: Iterable[Mapping[str, object]],
    candidate: Iterable[Mapping[str, object]],
) -> RecommendationImpact:
    unsupported = []
    before = {}
    after = {}
    for label, items, destination in (
        ("baseline", baseline, before),
        ("candidate", candidate, after),
    ):
        for index, item in enumerate(items):
            recommendation_id = str(item.get("recommendation_id") or "").strip()
            if not recommendation_id:
                unsupported.append(f"{label}:missing_id:{index}")
                continue
            destination[recommendation_id] = item
    common = sorted(set(before) & set(after))
    unchanged = []
    reordered = []
    classifications = []
    strengths = []
    compositions = []
    for recommendation_id in common:
        left = before[recommendation_id]
        right = after[recommendation_id]
        if dict(left) == dict(right):
            unchanged.append(recommendation_id)
        if left.get("order") != right.get("order"):
            reordered.append(recommendation_id)
        if left.get("classification") != right.get("classification"):
            classifications.append(recommendation_id)
        if left.get("strength") != right.get("strength"):
            strengths.append(recommendation_id)
        if any(
            left.get(field) != right.get(field)
            for field in (
                "partner",
                "sent_assets",
                "received_assets",
                "estimated_value_difference",
                "team_needs_inputs",
                "trust_inputs",
            )
        ):
            compositions.append(recommendation_id)
    return RecommendationImpact(
        unchanged=tuple(unchanged),
        added=tuple(sorted(set(after) - set(before))),
        removed=tuple(sorted(set(before) - set(after))),
        reordered=tuple(reordered),
        composition_changed=tuple(compositions),
        classification_changed=tuple(classifications),
        strength_changed=tuple(strengths),
        unsupported=tuple(unsupported),
    )
