"""Run the deterministic archetype admission protocol without production wiring."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
from modules import valuation_archetype_service
from modules.archetype_experiment_fixtures import (
    FIXTURE_VERSION,
    draft_pick_fixture,
    fixture_matrix,
    player_fixture,
    recommendation_fixture,
)
from modules.archetype_experiment_models import (
    AdjustmentBound,
    BaselineIdentity,
    ExperimentalArchetypeSpec,
)
from modules.archetype_validation import validate_experiment
from modules.valuation_archetypes import BALANCED_DYNASTY, BALANCED_DYNASTY_ID


def protocol_self_check_spec() -> ExperimentalArchetypeSpec:
    """Return validation metadata, not a production archetype registration."""

    return ExperimentalArchetypeSpec(
        archetype_id="protocol_self_check",
        display_name="Protocol Self Check",
        hypothesis="The comparison harness reports no change for identical adapters.",
        intended_user="DynastyGM engineering review",
        intended_league_context=("Dynasty",),
        supported_scoring_formats=("Standard", "TE Premium"),
        supported_roster_formats=("1QB", "Superflex"),
        source_engine_version="balanced-production-v1",
        transformation_version="identity-v1",
        affected_dimensions=(),
        excluded_dimensions=("all_production_dimensions",),
        expected_directional_effects=(),
        maximum_adjustment_bounds=(AdjustmentBound("value", 0.0, 0.0),),
        explanation_template_version="explanation-v1",
        owner="engineering",
        review_date="not-scheduled",
    )


def run(*, inject_failure: bool = False):
    frame = player_fixture()
    settings = dict(fixture_matrix()[0].league_settings)
    baseline = valuation_archetype_service.apply_active_valuation(
        BALANCED_DYNASTY,
        frame,
        "Dynasty",
        settings,
        engines={BALANCED_DYNASTY_ID: app.apply_valuation_lens},
    )
    candidate = valuation_archetype_service.apply_active_valuation(
        BALANCED_DYNASTY,
        frame,
        "Dynasty",
        settings,
        engines={BALANCED_DYNASTY_ID: app.apply_valuation_lens},
    )
    spec = protocol_self_check_spec()
    if inject_failure:
        candidate = candidate.copy()
        candidate.loc[candidate.index[0], "dynasty_score"] += 100_000
    baseline_identity = BaselineIdentity(
        archetype_id=BALANCED_DYNASTY_ID,
        source_engine_version=spec.source_engine_version,
        fixture_version=FIXTURE_VERSION,
        league_settings=tuple(sorted(settings.items())),
        scoring_settings=(("te_premium", settings["te_premium"]),),
        roster_settings=(
            ("qb_format", settings["qb_format"]),
            ("starter_count", settings["starter_count"]),
        ),
    )
    picks = draft_pick_fixture()
    recommendations = recommendation_fixture()
    return validate_experiment(
        spec=spec,
        baseline_identity=baseline_identity,
        fixture_labels=tuple(item.label for item in fixture_matrix()),
        baseline_assets=baseline,
        candidate_assets=candidate,
        baseline_picks=picks,
        candidate_picks=picks.copy(deep=True),
        baseline_recommendations=recommendations,
        candidate_recommendations=tuple(dict(item) for item in recommendations),
        product_review_complete=False,
        rollback_verified=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the offline valuation-archetype admission protocol."
    )
    parser.add_argument(
        "--inject-failure",
        action="store_true",
        help="Use a synthetic out-of-bounds change to verify nonzero failure behavior.",
    )
    args = parser.parse_args()
    report = run(inject_failure=args.inject_failure)
    print(report.to_json())
    hard_failures = (
        report.invariant_failures
        or report.bound_violations
        or report.directional_failures
        or report.explanation_failures
    )
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
