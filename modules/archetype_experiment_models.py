"""Immutable contracts for offline valuation-archetype experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from typing import Any


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    FIXTURE_VALIDATED = "fixture_validated"
    SHADOW_VALIDATED = "shadow_validated"
    APPROVED_FOR_EXPERIMENT = "approved_for_experiment"
    APPROVED_FOR_PRODUCTION = "approved_for_production"
    REJECTED = "rejected"
    RETIRED = "retired"


_ALLOWED_TRANSITIONS = {
    ExperimentStatus.DRAFT: {
        ExperimentStatus.FIXTURE_VALIDATED,
        ExperimentStatus.REJECTED,
    },
    ExperimentStatus.FIXTURE_VALIDATED: {
        ExperimentStatus.SHADOW_VALIDATED,
        ExperimentStatus.REJECTED,
    },
    ExperimentStatus.SHADOW_VALIDATED: {
        ExperimentStatus.APPROVED_FOR_EXPERIMENT,
        ExperimentStatus.REJECTED,
    },
    ExperimentStatus.APPROVED_FOR_EXPERIMENT: {
        ExperimentStatus.APPROVED_FOR_PRODUCTION,
        ExperimentStatus.REJECTED,
    },
    ExperimentStatus.APPROVED_FOR_PRODUCTION: {ExperimentStatus.RETIRED},
    ExperimentStatus.REJECTED: {ExperimentStatus.DRAFT, ExperimentStatus.RETIRED},
    ExperimentStatus.RETIRED: set(),
}


def validate_status_transition(
    current: ExperimentStatus,
    target: ExperimentStatus,
) -> ExperimentStatus:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid experiment transition: {current.value} -> {target.value}")
    return target


@dataclass(frozen=True)
class AdjustmentBound:
    dimension: str
    maximum_absolute_delta: float
    maximum_percentage_delta: float | None = None


@dataclass(frozen=True)
class DirectionalExpectation:
    name: str
    selector_field: str
    selector_values: tuple[str, ...]
    direction: str
    minimum_matching_share: float = 1.0
    maximum_undeclared_absolute_delta: float = 0.0

    def __post_init__(self) -> None:
        if self.direction not in {"increase", "decrease", "unchanged"}:
            raise ValueError(f"Unsupported expectation direction: {self.direction}")
        if not 0 <= self.minimum_matching_share <= 1:
            raise ValueError("minimum_matching_share must be between 0 and 1")


@dataclass(frozen=True)
class ExperimentalArchetypeSpec:
    archetype_id: str
    display_name: str
    hypothesis: str
    intended_user: str
    intended_league_context: tuple[str, ...]
    supported_scoring_formats: tuple[str, ...]
    supported_roster_formats: tuple[str, ...]
    source_engine_version: str
    transformation_version: str
    affected_dimensions: tuple[str, ...]
    excluded_dimensions: tuple[str, ...]
    expected_directional_effects: tuple[DirectionalExpectation, ...]
    maximum_adjustment_bounds: tuple[AdjustmentBound, ...]
    explanation_template_version: str
    experiment_status: ExperimentStatus = ExperimentStatus.DRAFT
    owner: str = ""
    review_date: str = ""
    production_eligible: bool = False

    def __post_init__(self) -> None:
        normalized = self.archetype_id.strip().casefold()
        if not normalized or normalized != self.archetype_id:
            raise ValueError("Experimental archetype id must be normalized and non-empty")
        if set(self.affected_dimensions) & set(self.excluded_dimensions):
            raise ValueError("Affected and excluded dimensions must not overlap")
        if (
            self.production_eligible
            and self.experiment_status is not ExperimentStatus.APPROVED_FOR_PRODUCTION
        ):
            raise ValueError("Production eligibility requires approved_for_production status")


@dataclass(frozen=True)
class BaselineIdentity:
    archetype_id: str
    source_engine_version: str
    fixture_version: str
    league_settings: tuple[tuple[str, Any], ...]
    scoring_settings: tuple[tuple[str, Any], ...]
    roster_settings: tuple[tuple[str, Any], ...]
    frozen_at: str | None = None


@dataclass(frozen=True)
class AssetDelta:
    asset_id: str
    position: str
    age_band: str
    value_tier: str
    baseline_value: float | None
    candidate_value: float | None
    absolute_delta: float | None
    percentage_delta: float | None
    rank_delta: int | None
    position_rank_delta: int | None
    percentile_delta: float | None
    baseline_tier: str
    candidate_tier: str
    tier_changed: bool


@dataclass(frozen=True)
class RecommendationImpact:
    unchanged: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    reordered: tuple[str, ...] = ()
    composition_changed: tuple[str, ...] = ()
    classification_changed: tuple[str, ...] = ()
    strength_changed: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationReport:
    experiment_id: str
    baseline: BaselineIdentity
    fixture_labels: tuple[str, ...]
    schema_equal: bool
    dtypes_equal: bool
    ordering_equal: bool
    invariant_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    asset_deltas: tuple[AssetDelta, ...]
    draft_pick_deltas: tuple[AssetDelta, ...]
    unchanged_asset_count: int
    unchanged_asset_percentage: float
    largest_increases: tuple[str, ...]
    largest_decreases: tuple[str, ...]
    position_summaries: tuple[tuple[str, float], ...]
    age_band_summaries: tuple[tuple[str, float], ...]
    value_tier_summaries: tuple[tuple[str, float], ...]
    bound_violations: tuple[str, ...]
    directional_failures: tuple[str, ...]
    recommendation_impact: RecommendationImpact
    explanation_failures: tuple[str, ...]
    unsupported_scenarios: tuple[str, ...]
    product_review_complete: bool
    rollback_verified: bool
    promotion_eligible: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)
