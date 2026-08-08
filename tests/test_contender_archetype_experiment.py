from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

import modules.contender_archetype_experiment as contender_module
from modules.archetype_experiment_fixtures import draft_pick_fixture, player_fixture
from modules.archetype_experiment_models import ExperimentStatus
from modules.contender_archetype_experiment import (
    CONTENDER_DRAFT_SPEC,
    CONTENDER_SPEC,
    apply_contender_candidate,
    classify_fixture_context,
    fixture_validated_spec,
)
from modules.contender_archetype_validation import run_contender_validation
from modules.valuation_archetypes import ARCHETYPE_REGISTRY


ROOT = Path(__file__).resolve().parents[1]


def settings(**overrides):
    return {
        "league_format": "Dynasty",
        "qb_format": "1QB",
        "te_premium": False,
        **overrides,
    }


def identity_adapter(frame, _settings):
    return frame.copy(deep=True)


def result(profile="contender", **overrides):
    players = player_fixture()
    picks = draft_pick_fixture()
    return players, picks, apply_contender_candidate(
        players, picks, league_settings=settings(**overrides),
        roster_profile=profile,
    )


def test_spec_is_frozen_draft_and_never_production_eligible():
    assert CONTENDER_DRAFT_SPEC.experiment_status is ExperimentStatus.DRAFT
    assert not CONTENDER_DRAFT_SPEC.production_eligible
    with pytest.raises(FrozenInstanceError):
        CONTENDER_DRAFT_SPEC.display_name = "Changed"
    validated = fixture_validated_spec()
    assert validated.experiment_status is ExperimentStatus.FIXTURE_VALIDATED
    assert not validated.production_eligible
    assert CONTENDER_SPEC == validated


def test_registry_isolation_and_no_ui_selector():
    assert [item.id for item in ARCHETYPE_REGISTRY.available()] == ["balanced_dynasty"]
    production_files = [
        ROOT / "app.py",
        ROOT / "modules" / "valuation_archetypes.py",
        ROOT / "modules" / "valuation_archetype_service.py",
    ]
    assert all(
        "contender_archetype_experiment" not in path.read_text(encoding="utf-8")
        for path in production_files
    )


@pytest.mark.parametrize(
    ("profile", "classification"),
    [("contender", "intended"), ("rebuild", "unsupported"), ("balanced", "neutral")],
)
def test_explicit_fixture_classification(profile, classification):
    assert classify_fixture_context(profile) == classification


@pytest.mark.parametrize("profile", ["rebuild", "balanced", "aging", "strong_qb"])
def test_non_intended_context_is_exact_fallback(profile):
    players, picks, candidate = result(profile)
    pd.testing.assert_frame_equal(candidate.assets, players)
    pd.testing.assert_frame_equal(candidate.picks, picks)
    assert not candidate.applied


@pytest.mark.parametrize(
    "unsupported",
    [
        {"league_format": "Redraft"},
        {"qb_format": "Unsupported"},
    ],
)
def test_unsupported_format_fails_closed(unsupported):
    players, picks, candidate = result("contender", **unsupported)
    pd.testing.assert_frame_equal(candidate.assets, players)
    pd.testing.assert_frame_equal(candidate.picks, picks)
    assert candidate.fallback_reason == "unsupported_format"


def test_candidate_is_deterministic_and_does_not_mutate_baseline():
    players = player_fixture()
    picks = draft_pick_fixture()
    players_before = players.copy(deep=True)
    picks_before = picks.copy(deep=True)
    first = apply_contender_candidate(
        players, picks, league_settings=settings(), roster_profile="contender"
    )
    second = apply_contender_candidate(
        players, picks, league_settings=settings(), roster_profile="contender"
    )
    pd.testing.assert_frame_equal(players, players_before)
    pd.testing.assert_frame_equal(picks, picks_before)
    pd.testing.assert_frame_equal(first.assets, second.assets)
    pd.testing.assert_frame_equal(first.picks, second.picks)
    assert first.explanations == second.explanations


def test_candidate_exception_fails_closed(monkeypatch):
    players = player_fixture()
    picks = draft_pick_fixture()

    def fail(_row):
        raise RuntimeError("synthetic candidate failure")

    monkeypatch.setattr(contender_module, "_player_contributions", fail)
    candidate = apply_contender_candidate(
        players, picks, league_settings=settings(), roster_profile="contender"
    )
    pd.testing.assert_frame_equal(candidate.assets, players)
    pd.testing.assert_frame_equal(candidate.picks, picks)
    assert candidate.fallback_reason == "candidate_error"


def test_schema_dtype_order_and_missing_values_are_preserved():
    players = player_fixture()
    players.loc[3, "dynasty_score"] = pd.NA
    picks = draft_pick_fixture()
    candidate = apply_contender_candidate(
        players, picks, league_settings=settings(), roster_profile="contender"
    )
    assert tuple(candidate.assets.columns) == tuple(players.columns)
    assert tuple(map(str, candidate.assets.dtypes)) == tuple(map(str, players.dtypes))
    assert candidate.assets["player_id"].tolist() == players["player_id"].tolist()
    assert candidate.assets["dynasty_score"].isna().equals(
        players["dynasty_score"].isna()
    )


def test_unavailable_player_gets_no_availability_bonus():
    players, _, candidate = result()
    unavailable = players["status"].eq("Injured Reserve")
    deltas = candidate.assets["dynasty_score"] - players["dynasty_score"]
    assert (deltas.loc[unavailable] <= 0).all()
    for asset_id in players.loc[unavailable, "player_id"].astype(str):
        explanation = candidate.explanations.get(asset_id)
        if explanation:
            assert dict(explanation.contributing_adjustments)[
                "near_term_availability"
            ] == 0


def test_replacement_veterans_are_not_broadly_boosted():
    players, _, candidate = result()
    replacements = players["dynasty_score"].lt(3_000)
    deltas = candidate.assets["dynasty_score"] - players["dynasty_score"]
    assert not (deltas.loc[replacements] > 0).any()


def test_productive_rookie_is_not_penalized_for_youth_alone():
    players = player_fixture()
    players.loc[0, ["dynasty_score", "value_score", "status", "injury_status"]] = [
        9_000, 9_000, "Active", "",
    ]
    candidate = apply_contender_candidate(
        players, draft_pick_fixture(), league_settings=settings(),
        roster_profile="contender",
    )
    assert candidate.assets.loc[0, "dynasty_score"] >= players.loc[0, "dynasty_score"]


def test_explanations_reconcile_and_are_structured():
    _, _, candidate = result()
    assert candidate.explanations
    for explanation in candidate.explanations.values():
        assert sum(value for _, value in explanation.contributing_adjustments) == (
            explanation.total_delta
        )
        assert explanation.candidate_value - explanation.baseline_value == (
            explanation.total_delta
        )
        assert "Experimental" in explanation.rationale


def test_pick_adjustments_preserve_chronology_and_round_order():
    _, _, candidate = result()
    firsts = candidate.picks[candidate.picks["round"].eq(1)].sort_values("year")
    assert firsts["value_score"].is_monotonic_decreasing
    for _, group in candidate.picks.groupby("year"):
        assert group.sort_values("round")["value_score"].is_monotonic_decreasing
    assert (candidate.picks["value_score"] > 0).all()


@pytest.mark.parametrize(
    "overrides",
    [{"qb_format": "Superflex"}, {"te_premium": True}],
)
def test_supported_settings_do_not_add_position_only_multiplier(overrides):
    players, picks, baseline_result = result()
    contender = apply_contender_candidate(
        players, picks, league_settings=settings(**overrides),
        roster_profile="contender",
    )
    pd.testing.assert_series_equal(
        contender.assets["dynasty_score"],
        baseline_result.assets["dynasty_score"],
    )


def test_validation_runs_all_fixtures_and_promotes_report_only():
    artifact = run_contender_validation(balanced_adapter=identity_adapter)
    assert len(artifact.fixture_summaries) == 14
    assert artifact.hard_gates_passed
    assert artifact.lifecycle_decision == "fixture_validated"
    assert not artifact.production_eligible
    assert artifact.recommendation_changes == ()
    assert artifact.recommendation_churn_percentage == 0
    assert len(artifact.golden_scenarios) == 8


def test_validation_detects_injected_failure():
    artifact = run_contender_validation(
        balanced_adapter=identity_adapter, inject_failure=True
    )
    assert not artifact.hard_gates_passed
    assert artifact.lifecycle_decision == "draft"


def test_validation_serialization_is_deterministic_and_sanitized():
    first = run_contender_validation(balanced_adapter=identity_adapter).to_json()
    second = run_contender_validation(balanced_adapter=identity_adapter).to_json()
    assert first == second
    parsed = json.loads(first)
    assert "token" not in first.casefold()
    assert parsed["experiment_id"] == "contender"


def test_committed_artifact_matches_deterministic_validation():
    expected = json.loads(
        (ROOT / "tests" / "fixtures" / "archetype_experiments"
         / "contender_fixture_validation.json").read_text(encoding="utf-8")
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_archetype_experiment.py",
            "--experiment",
            "contender",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    actual = json.loads(completed.stdout)
    assert expected == actual


def test_cli_success_and_injected_failure():
    command = [
        sys.executable, "scripts/validate_archetype_experiment.py",
        "--experiment", "contender",
    ]
    success = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    failure = subprocess.run(
        [*command, "--inject-failure"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert success.returncode == 0
    assert json.loads(success.stdout)["hard_gates_passed"]
    assert failure.returncode != 0
    assert not json.loads(failure.stdout)["hard_gates_passed"]


def test_app_py_does_not_expose_contender_experiment():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "contender_archetype_experiment" not in source
    assert "contender_archetype_validation" not in source
    assert "--experiment contender" not in source
