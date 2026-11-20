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


def test_flag_is_registered_with_owner_and_follows_its_default(monkeypatch):
    entry = experimental_graduation.FLAG_REGISTRY[target_viability.ENV_KEY]
    assert entry["owner"] == "coridian_" and entry["default"] in {"on", "off"}
    monkeypatch.delenv(target_viability.ENV_KEY, raising=False)
    assert target_viability.enabled() is (entry["default"] == "on")
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


def test_env_switches_it_both_ways(monkeypatch):
    monkeypatch.setenv(target_viability.ENV_KEY, "1")
    assert target_viability.enabled() is True
    monkeypatch.setenv(target_viability.ENV_KEY, "0")
    assert target_viability.enabled() is False


# --- gate 4: no contender target is IR-no-return or buried on the chart (RB5+/WR6+/TE4+/QB3+) -----------------------------------

BURIED = (("RB", 5), ("RB", 8), ("WR", 6), ("WR", 10), ("TE", 4), ("TE", 6), ("QB", 3), ("QB", 4))
USABLE = (("RB", 1), ("RB", 4), ("WR", 1), ("WR", 5), ("TE", 1), ("TE", 3), ("QB", 1), ("QB", 2))


def _row(pos, order, **extra):
    return {"position": pos, "age": 26, "status": "Active", "injury_status": "", "depth_chart_order": order, **extra}


@pytest.mark.parametrize("posture", ("contender", "fringe_contender"))
@pytest.mark.parametrize("pos,order", BURIED)
def test_golden_buried_depth_is_never_a_contender_target(posture, pos, order):
    assert _assess(_row(pos, order), posture, value=1500).verdict == "avoid"


@pytest.mark.parametrize("posture", POSTURES)
@pytest.mark.parametrize("pos,order", USABLE)
def test_golden_usable_depth_stays_a_target(posture, pos, order):
    assert _assess(_row(pos, order), posture).verdict == "target"


@pytest.mark.parametrize("posture", ("contender", "fringe_contender"))
@pytest.mark.parametrize("pos", ("QB", "RB", "WR", "TE"))
@pytest.mark.parametrize("injury", ("IR", "PUP", "NFI"))
def test_golden_ir_without_a_return_date_is_never_a_contender_target(posture, pos, injury):
    row = _row(pos, 1, status="Inactive", injury_status=injury, injury_body_part="Knee")
    assert _assess(row, posture, value=6000).verdict == "avoid"


@pytest.mark.parametrize("posture", ("contender", "fringe_contender"))
def test_short_term_out_is_allowed_but_labelled(posture):
    verdict = _assess(_row("WR", 1, injury_status="Out", injury_body_part="Hamstring"), posture)
    assert verdict.verdict == "target" and verdict.note.startswith("Availability:") and "hamstring" in verdict.note


def test_wr_sub_slot_orders_are_read_per_slot():
    # Sleeper numbers WRs within LWR / RWR / SWR: RWR 4 is the third man in that slot, RWR 1-2 are starter and backup.
    assert target_viability.role_factor({"position": "WR", "depth_chart_position": "RWR", "depth_chart_order": 2})[0] == 1.0
    assert target_viability.role_factor({"position": "WR", "depth_chart_position": "RWR", "depth_chart_order": 4})[0] < 0.5


# --- gate 2: the stash path triggers for a rebuilder on a real-shaped row, with the reason shown ------------------------------------

# Field-for-field the shape of a players.db row (NaN / None where the table has none).
REAL_SHAPED_BENSON = {
    "player_id": "11629", "name": "Trey Benson", "position": "RB", "team": "ARI", "age": 24.0, "status": "Inactive",
    "injury_status": "IR", "injury_body_part": "Knee", "injury_notes": None, "depth_chart_position": "RB",
    "depth_chart_order": 6.0, "snap_share": None, "value_score": 2040,
}


@pytest.mark.parametrize("posture", ("retool", "rebuild", "tank"))
def test_real_shaped_benson_is_a_stash_for_non_contenders_with_the_reason(posture):
    team = pd.DataFrame([REAL_SHAPED_BENSON, {"player_id": "ok", **HEALTHY_STARTER, "name": "Healthy"}])
    assets = [
        {"asset_type": "player", "player_id": "11629", "label": "Trey Benson", "score": 2040, "position": "RB"},
        {"asset_type": "player", "player_id": "ok", "label": "Healthy", "score": 3000, "position": "RB"},
    ]
    out = trade_ideas._viable_target_assets(assets, team, strategy=posture, league_settings={"current_week": 11})
    assert [a["player_id"] for a in out] == ["ok", "11629"]
    benson = out[1]
    assert benson["availability_framing"] == "injured_stash"
    assert benson["availability_note"] == (
        "Injured stash, buy-low only: IR, knee, no return date; RB6 on the depth chart; cheap now, value if he returns and the role opens."
    )
