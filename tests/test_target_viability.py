"""Availability + depth-role + posture check on automatic acquisition targets (DYNASTYGM_TARGET_VIABILITY_V1)."""

from __future__ import annotations

import pandas as pd
import pytest

from modules import experimental_graduation, target_viability, trade_grade, trade_ideas

WINDOW = trade_grade.season_window({"current_week": 11})
POSTURES = ("contender", "fringe_contender", "retool", "rebuild", "tank")

# Benson-like: young RB on IR, no return date, sixth on the chart, mid-priced.
IR_DEEP_YOUNG = {"position": "RB", "age": 24, "status": "Inactive", "injury_status": "IR", "injury_body_part": "Knee", "depth_chart_order": 6}
HEALTHY_STARTER = {"position": "RB", "age": 26, "status": "Active", "injury_status": "", "depth_chart_order": 1}
IR_STARTER = {"position": "WR", "age": 28, "status": "Inactive", "injury_status": "IR", "injury_body_part": "Knee", "depth_chart_order": 1}


def _assess(row, posture, value=2606):
    return target_viability.assess(row, strategy=posture, window=WINDOW, value=value, cheap_value=3500)


def test_flag_is_registered_off_with_owner_and_kill_switch(monkeypatch):
    entry = experimental_graduation.FLAG_REGISTRY[target_viability.ENV_KEY]
    assert entry["default"] == "off" and entry["owner"] == "coridian_"
    monkeypatch.delenv(target_viability.ENV_KEY, raising=False)
    assert target_viability.enabled() is False
    monkeypatch.setenv(target_viability.ENV_KEY, "1")
    assert target_viability.enabled() is True
    monkeypatch.setenv(target_viability.ENV_KEY, "0")
    assert target_viability.enabled() is False


@pytest.mark.parametrize("posture", ("contender", "fringe_contender"))
def test_ir_deep_player_is_not_recommended_to_a_contender(posture):
    verdict = _assess(IR_DEEP_YOUNG, posture)
    assert verdict.verdict == "avoid"
    assert "IR" in verdict.note and "RB6" in verdict.note


@pytest.mark.parametrize("posture", ("retool", "rebuild", "tank"))
def test_young_cheap_ir_player_is_framed_as_a_stash_that_says_why(posture):
    verdict = _assess(IR_DEEP_YOUNG, posture)
    assert verdict.is_stash
    assert verdict.note.startswith("Injured stash, buy-low only")
    assert "knee" in verdict.note and "no return date" in verdict.note and "RB6" in verdict.note


def test_stash_needs_a_cheap_price_and_a_young_age():
    assert _assess(IR_DEEP_YOUNG, "rebuild", value=6000).verdict == "avoid"
    assert _assess({**IR_DEEP_YOUNG, "age": 29}, "rebuild").verdict == "avoid"


@pytest.mark.parametrize("posture", POSTURES)
def test_healthy_starter_is_unchanged(posture):
    verdict = _assess(HEALTHY_STARTER, posture)
    assert verdict.verdict == "target" and verdict.viability == 1.0 and verdict.note == ""


def test_missing_depth_data_is_no_evidence_not_a_penalty():
    assert target_viability.role_factor({"position": "RB", "depth_chart_order": None})[0] == 1.0
    assert target_viability.role_factor({"position": "K", "depth_chart_order": 3})[0] == 1.0


def test_snap_share_corroborates_a_role_the_chart_understates():
    row = {"position": "RB", "depth_chart_order": 5, "snap_share": 0.6}
    assert target_viability.role_factor(row)[0] >= 0.8


def test_availability_follows_the_shared_injury_estimate_and_posture_weight():
    contender, _ = target_viability.availability_factor(IR_STARTER, strategy="contender", window=WINDOW)
    rebuild, _ = target_viability.availability_factor(IR_STARTER, strategy="rebuild", window=WINDOW)
    assert contender < rebuild < 1.0
    assert target_viability.availability_factor(HEALTHY_STARTER, strategy="contender", window=WINDOW)[0] == 1.0


def _team_df():
    return pd.DataFrame([
        {"player_id": "ir", **IR_DEEP_YOUNG, "name": "IR Deep"},
        {"player_id": "ok", **HEALTHY_STARTER, "name": "Healthy"},
    ])


def _assets():
    return [
        {"asset_type": "player", "player_id": "ir", "label": "IR Deep", "score": 2606, "position": "RB"},
        {"asset_type": "player", "player_id": "ok", "label": "Healthy", "score": 2606, "position": "RB"},
    ]


def test_picker_drops_the_player_for_a_contender_and_keeps_the_healthy_one():
    kept = trade_ideas._viable_target_assets(_assets(), _team_df(), strategy="contender", league_settings={"current_week": 11})
    assert [a["player_id"] for a in kept] == ["ok"]


def test_stash_never_outranks_a_healthy_fit():
    # The injured player listed FIRST (better on every other sort key) still comes after the healthy one.
    kept = trade_ideas._viable_target_assets(_assets(), _team_df(), strategy="rebuild", league_settings={"current_week": 11})
    assert [a["player_id"] for a in kept] == ["ok", "ir"]
    assert kept[1]["availability_framing"] == "injured_stash" and "no return date" in kept[1]["availability_note"]
    ideas = [{"receive_assets": [kept[1]], "id": "stash"}, {"receive_assets": [kept[0]], "id": "healthy"}]
    ideas.sort(key=lambda idea: 1 if trade_ideas._is_injured_stash_idea(idea) else 0)
    assert [i["id"] for i in ideas] == ["healthy", "stash"]


def test_flag_off_leaves_asset_list_untouched_by_the_hub(monkeypatch):
    monkeypatch.delenv(target_viability.ENV_KEY, raising=False)
    assert target_viability.enabled() is False
