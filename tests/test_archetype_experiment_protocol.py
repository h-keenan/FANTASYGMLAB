from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from modules import archetype_comparison
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
    DirectionalExpectation,
    ExperimentStatus,
    ExperimentalArchetypeSpec,
    validate_status_transition,
)
from modules.archetype_validation import (
    AssetExplanation,
    apply_candidate_fail_closed,
    pick_chronology_failures,
    validate_experiment,
)
from modules.valuation_archetypes import ARCHETYPE_REGISTRY, BALANCED_DYNASTY
from scripts.validate_archetype_experiment import (
    protocol_self_check_spec,
    run,
)


def _baseline_identity() -> BaselineIdentity:
    settings = fixture_matrix()[0].league_settings
    return BaselineIdentity(
        archetype_id="balanced_dynasty",
        source_engine_version="balanced-production-v1",
        fixture_version=FIXTURE_VERSION,
        league_settings=settings,
        scoring_settings=(("te_premium", False),),
        roster_settings=(("qb_format", "1QB"),),
    )


def _spec(**changes) -> ExperimentalArchetypeSpec:
    base = protocol_self_check_spec()
    return replace(base, **changes)


def _validate(
    candidate: pd.DataFrame,
    *,
    spec: ExperimentalArchetypeSpec | None = None,
    baseline: pd.DataFrame | None = None,
    explanations=None,
    product_review_complete=False,
):
    baseline = player_fixture() if baseline is None else baseline
    return validate_experiment(
        spec=spec or _spec(),
        baseline_identity=_baseline_identity(),
        fixture_labels=("standard-1qb",),
        baseline_assets=baseline,
        candidate_assets=candidate,
        baseline_picks=draft_pick_fixture(),
        candidate_picks=draft_pick_fixture(),
        baseline_recommendations=recommendation_fixture(),
        candidate_recommendations=recommendation_fixture(),
        explanations=explanations,
        product_review_complete=product_review_complete,
    )


def test_experimental_spec_is_frozen_and_nonproduction_by_default():
    spec = _spec()
    assert spec.experiment_status is ExperimentStatus.DRAFT
    assert spec.production_eligible is False
    with pytest.raises(FrozenInstanceError):
        spec.display_name = "Changed"


def test_contract_rejects_overlap_and_premature_production_eligibility():
    with pytest.raises(ValueError, match="overlap"):
        _spec(affected_dimensions=("age",), excluded_dimensions=("age",))
    with pytest.raises(ValueError, match="approved_for_production"):
        _spec(production_eligible=True)


def test_lifecycle_accepts_only_explicit_transitions():
    assert (
        validate_status_transition(
            ExperimentStatus.DRAFT,
            ExperimentStatus.FIXTURE_VALIDATED,
        )
        is ExperimentStatus.FIXTURE_VALIDATED
    )
    with pytest.raises(ValueError, match="Invalid"):
        validate_status_transition(
            ExperimentStatus.DRAFT,
            ExperimentStatus.APPROVED_FOR_PRODUCTION,
        )


def test_production_registry_is_separate_and_still_has_one_active_archetype():
    assert ARCHETYPE_REGISTRY.available() == (BALANCED_DYNASTY,)
    assert ARCHETYPE_REGISTRY.get("protocol_self_check") is None
    assert "archetype_experiment" not in Path(
        "modules/valuation_archetypes.py"
    ).read_text(encoding="utf-8")


def test_fixture_matrix_is_complete_deterministic_and_anonymous():
    first = fixture_matrix()
    second = fixture_matrix()
    assert first == second
    assert len(first) == 14
    assert {item.label for item in first} >= {
        "standard-1qb",
        "superflex",
        "tight-end-premium",
        "aging-roster",
        "strong-draft-capital",
    }
    assert player_fixture().equals(player_fixture())
    assert player_fixture()["player_id"].str.fullmatch(r"FX-\d{3}").all()


def test_baseline_identity_serializes_explicit_configuration():
    identity = _baseline_identity()
    assert identity.archetype_id == "balanced_dynasty"
    assert identity.fixture_version == FIXTURE_VERSION
    assert dict(identity.league_settings)["league_format"] == "Dynasty"
    assert identity.frozen_at is None


def test_baseline_versus_baseline_produces_zero_deltas_and_identical_contracts():
    report = run()
    assert report.schema_equal
    assert report.dtypes_equal
    assert report.ordering_equal
    assert not report.invariant_failures
    assert not report.bound_violations
    assert not report.directional_failures
    assert all(delta.absolute_delta == 0 for delta in report.asset_deltas)
    assert report.unchanged_asset_count == len(report.asset_deltas)
    assert report.unchanged_asset_percentage == 100.0
    assert all(delta.absolute_delta == 0 for delta in report.draft_pick_deltas)
    assert report.recommendation_impact.unchanged == (
        "REC-001",
        "REC-002",
        "REC-003",
    )
    assert not report.promotion_eligible


def test_schema_dtype_order_and_missing_value_changes_are_detected():
    baseline = player_fixture()
    changed = baseline.copy()
    changed.loc[0, "dynasty_score"] = None
    changed = changed.iloc[::-1].reset_index(drop=True)
    changed["extra"] = "unexpected"

    report = _validate(changed, baseline=baseline)

    assert not report.schema_equal
    assert not report.dtypes_equal
    assert not report.ordering_equal
    assert "missing_value_mask_changed" in report.invariant_failures


def test_duplicate_identifier_and_nonfinite_value_are_detected():
    baseline = player_fixture()
    changed = baseline.copy()
    changed.loc[1, "player_id"] = changed.loc[0, "player_id"]
    changed["dynasty_score"] = changed["dynasty_score"].astype(float)
    changed.loc[2, "dynasty_score"] = np.inf

    report = _validate(changed, baseline=baseline)

    assert "candidate_duplicate_identifiers" in report.invariant_failures
    assert "candidate_nonfinite_values" in report.invariant_failures


def test_unsupported_format_falls_back_to_isolated_baseline_without_calling_candidate():
    baseline = player_fixture()
    called = False

    def candidate(_frame):
        nonlocal called
        called = True
        raise AssertionError("unsupported transformation must not run")

    result, fallback_reason = apply_candidate_fail_closed(
        spec=_spec(),
        baseline=baseline,
        league_settings={
            "league_format": "Unsupported",
            "qb_format": "1QB",
            "te_premium": False,
        },
        transformation=candidate,
    )

    assert fallback_reason == "unsupported_format"
    assert not called
    assert result.equals(baseline)
    assert result is not baseline


def test_supported_candidate_receives_copy_and_cannot_mutate_source():
    baseline = player_fixture()

    def candidate(frame):
        frame.loc[0, "dynasty_score"] += 10
        return frame

    result, fallback_reason = apply_candidate_fail_closed(
        spec=_spec(maximum_adjustment_bounds=(AdjustmentBound("value", 20, 1),)),
        baseline=baseline,
        league_settings=dict(fixture_matrix()[0].league_settings),
        transformation=candidate,
    )

    assert fallback_reason is None
    assert result.loc[0, "dynasty_score"] == baseline.loc[0, "dynasty_score"] + 10
    assert baseline.loc[0, "dynasty_score"] == player_fixture().loc[0, "dynasty_score"]


def test_candidate_exception_fails_closed_to_baseline():
    baseline = player_fixture()

    def broken(_frame):
        raise RuntimeError("controlled failure")

    result, fallback_reason = apply_candidate_fail_closed(
        spec=_spec(),
        baseline=baseline,
        league_settings=dict(fixture_matrix()[0].league_settings),
        transformation=broken,
    )
    assert fallback_reason == "candidate_error"
    assert result.equals(baseline)
    assert result is not baseline


def test_bounds_outliers_rank_and_group_summaries_are_reported():
    baseline = player_fixture()
    candidate = baseline.copy()
    candidate.loc[0, "dynasty_score"] -= 3000
    report = _validate(
        candidate,
        baseline=baseline,
        spec=_spec(maximum_adjustment_bounds=(AdjustmentBound("value", 100, 2),)),
        explanations={
            "FX-001": AssetExplanation(
                "FX-001",
                float(baseline.loc[0, "dynasty_score"]),
                float(candidate.loc[0, "dynasty_score"]),
                -3000,
                (("age", -3000),),
                (),
                "Synthetic bounded-change verification.",
                "explanation-v1",
            )
        },
    )

    assert "FX-001:absolute" in report.bound_violations
    assert "FX-001:percentage" in report.bound_violations
    moved = report.asset_deltas[0]
    assert moved.rank_delta != 0
    assert moved.position_rank_delta != 0
    assert moved.percentile_delta != 0
    assert report.largest_decreases == ("FX-001",)
    assert report.unchanged_asset_count == len(report.asset_deltas) - 1
    assert dict(report.position_summaries)["QB"] < 0
    assert dict(report.age_band_summaries)["21-23"] < 0
    assert dict(report.value_tier_summaries)["elite"] < 0


def test_directional_expectation_success_and_failure():
    baseline = player_fixture()
    expectation = DirectionalExpectation(
        "qb-direction",
        "position",
        ("QB",),
        "increase",
        minimum_matching_share=1.0,
        maximum_undeclared_absolute_delta=0,
    )
    spec = _spec(
        affected_dimensions=("position",),
        excluded_dimensions=(),
        expected_directional_effects=(expectation,),
        maximum_adjustment_bounds=(AdjustmentBound("value", 100, 10),),
    )
    success = baseline.copy()
    success.loc[success["position"].eq("QB"), "dynasty_score"] += 25
    explanations = {
        row.player_id: AssetExplanation(
            row.player_id,
            float(row.dynasty_score),
            float(row.dynasty_score + 25),
            25,
            (("position", 25),),
            (),
            "Declared fixture direction.",
            "explanation-v1",
        )
        for row in baseline[baseline["position"].eq("QB")].itertuples()
    }
    assert not _validate(
        success, baseline=baseline, spec=spec, explanations=explanations
    ).directional_failures

    failure = baseline.copy()
    failure.loc[failure["position"].eq("QB"), "dynasty_score"] -= 25
    failure_report = _validate(failure, baseline=baseline, spec=spec)
    assert "qb-direction:direction" in failure_report.directional_failures


def test_undeclared_side_effect_is_detected():
    baseline = player_fixture()
    expectation = DirectionalExpectation(
        "qb-only",
        "position",
        ("QB",),
        "increase",
        maximum_undeclared_absolute_delta=0,
    )
    candidate = baseline.copy()
    candidate.loc[candidate["position"].eq("QB"), "dynasty_score"] += 10
    candidate.loc[candidate["position"].eq("WR"), "dynasty_score"] += 10
    spec = _spec(
        affected_dimensions=("position",),
        excluded_dimensions=(),
        expected_directional_effects=(expectation,),
        maximum_adjustment_bounds=(AdjustmentBound("value", 20, 10),),
    )
    report = _validate(candidate, baseline=baseline, spec=spec)
    assert "qb-only:undeclared_side_effect" in report.directional_failures


def test_multiple_declared_directional_scopes_do_not_flag_each_other():
    baseline = player_fixture()
    candidate = baseline.copy()
    candidate.loc[candidate["position"].eq("QB"), "dynasty_score"] += 10
    candidate.loc[candidate["position"].eq("WR"), "dynasty_score"] -= 10
    expectations = (
        DirectionalExpectation(
            "qb-up",
            "position",
            ("QB",),
            "increase",
            maximum_undeclared_absolute_delta=0,
        ),
        DirectionalExpectation(
            "wr-down",
            "position",
            ("WR",),
            "decrease",
            maximum_undeclared_absolute_delta=0,
        ),
    )
    deltas = archetype_comparison.compare_asset_frames(
        baseline, candidate
    )[0]
    assert not archetype_comparison.validate_directional_expectations(
        baseline,
        deltas,
        expectations,
    )


def test_pick_chronology_accepts_fixture_and_rejects_incoherence():
    picks = draft_pick_fixture()
    assert not pick_chronology_failures(picks)
    changed = picks.copy()
    changed.loc[
        (changed["year"].eq(2027)) & changed["round"].eq(4),
        "value_score",
    ] = 9000
    assert "pick_round_order:2027" in pick_chronology_failures(changed)


def test_recommendation_impact_reports_set_order_classification_strength_and_composition():
    baseline = list(recommendation_fixture())
    candidate = [dict(item) for item in baseline]
    candidate[0]["order"] = 2
    candidate[0]["partner"] = "TEAM-03"
    candidate[1]["classification"] = "Watch"
    candidate[1]["strength"] = 0.5
    candidate.pop(2)
    candidate.append(
        {
            "recommendation_id": "REC-004",
            "order": 3,
            "classification": "Add",
            "strength": 0.6,
        }
    )
    impact = archetype_comparison.compare_recommendations(baseline, candidate)
    assert impact.added == ("REC-004",)
    assert impact.removed == ("REC-003",)
    assert impact.reordered == ("REC-001",)
    assert impact.composition_changed == ("REC-001",)
    assert impact.classification_changed == ("REC-002",)
    assert impact.strength_changed == ("REC-002",)


def test_malformed_recommendation_snapshot_is_reported_as_unsupported():
    impact = archetype_comparison.compare_recommendations(
        recommendation_fixture(),
        ({"classification": "Add"},),
    )
    assert impact.unsupported == ("candidate:missing_id:0",)

    duplicate = archetype_comparison.compare_recommendations(
        recommendation_fixture(),
        (
            recommendation_fixture()[0],
            recommendation_fixture()[0],
        ),
    )
    assert duplicate.unsupported == ("candidate:duplicate_id:REC-001",)


def test_explanation_must_reconcile_and_use_declared_dimensions():
    baseline = player_fixture()
    candidate = baseline.copy()
    candidate.loc[0, "dynasty_score"] += 20
    spec = _spec(
        affected_dimensions=("age",),
        excluded_dimensions=(),
        maximum_adjustment_bounds=(AdjustmentBound("value", 50, 10),),
    )
    bad = AssetExplanation(
        "FX-001",
        float(baseline.loc[0, "dynasty_score"]),
        float(candidate.loc[0, "dynasty_score"]),
        20,
        (("position", 10),),
        (),
        "",
        "wrong-template",
    )
    failures = _validate(
        candidate,
        baseline=baseline,
        spec=spec,
        explanations={"FX-001": bad},
    ).explanation_failures
    assert "FX-001:template_version" in failures
    assert "FX-001:incomplete_explanation" in failures
    assert "FX-001:undeclared_explanation_dimension" in failures
    assert "FX-001:contribution_mismatch" in failures


def test_promotion_requires_explicit_status_eligibility_product_review_and_rollback():
    approved = _spec(
        experiment_status=ExperimentStatus.APPROVED_FOR_PRODUCTION,
        production_eligible=True,
    )
    baseline = player_fixture()
    report = _validate(
        baseline.copy(deep=True),
        baseline=baseline,
        spec=approved,
        product_review_complete=True,
    )
    assert report.promotion_eligible

    draft_report = _validate(
        baseline.copy(deep=True),
        baseline=baseline,
        product_review_complete=True,
    )
    assert not draft_report.promotion_eligible


def test_report_serialization_is_deterministic_and_contains_no_customer_fields():
    first = run().to_json()
    second = run().to_json()
    assert first == second
    payload = json.loads(first)
    assert payload["baseline"]["archetype_id"] == "balanced_dynasty"
    for forbidden in ("email", "token", "cookie", "sleeper_username"):
        assert forbidden not in first.casefold()


def test_cli_success_and_failure_exit_codes():
    command = [
        sys.executable,
        "scripts/validate_archetype_experiment.py",
    ]
    success = subprocess.run(command, capture_output=True, text=True, check=False)
    failure = subprocess.run(
        [*command, "--inject-failure"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert success.returncode == 0
    assert json.loads(success.stdout)["bound_violations"] == []
    assert failure.returncode != 0
    assert json.loads(failure.stdout)["bound_violations"]


def test_application_remains_unmodified_and_exposes_no_archetype_selector():
    app_source = Path("app.py").read_text(encoding="utf-8")
    ui_source = Path("modules/valuation_archetype_ui.py").read_text(encoding="utf-8")
    assert "experimental_archetype" not in app_source
    # The canonical format lens is public; experimental archetypes are not.
    assert "experimental_archetype" not in ui_source
    assert "SUPPORTED_VALUATION_LENSES," in ui_source
    assert "key=CANONICAL_LENS_SESSION_KEY" in ui_source
    assert "radio(" not in ui_source
