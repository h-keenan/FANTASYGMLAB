"""player-model-6: the single-game tail is bounded (no 62-point WR), normal weeks and season totals are untouched."""

from __future__ import annotations

import numpy as np
import pytest

from modules.sim import player_model as pm
from modules.sim import player_model_v5 as v5
from modules.sim.calibration import backtest, dataset, single_game_tail


def test_stat_caps_bound_every_component_and_leave_normal_lines_alone():
    wild = {"rec_tgt": 40.0, "rec": 30.0, "rec_yd": 448.0, "rec_td": 9.0, "rush_yd": 0.0, "rush_td": 0.0, "fum_lost": 0.0}
    out = pm.cap_stats("WR", dict(wild))
    assert out["rec_td"] == 5 and out["rec"] == 21 and out["rec_tgt"] == 28 and 190 < out["rec_yd"] < 320
    normal = {"rec_tgt": 9.0, "rec": 6.0, "rec_yd": 88.0, "rec_td": 1.0, "rush_yd": 0.0, "rush_td": 0.0, "fum_lost": 0.0}
    assert pm.cap_stats("WR", dict(normal)) == normal and pm.squeeze_tail("WR", dict(normal)) == normal


def test_squeeze_is_monotone_bounded_and_takes_points_out_of_yards_only():
    prev = 0.0
    for yd in range(100, 700, 25):
        st = pm.squeeze_tail("WR", {"rec": 12.0, "rec_tgt": 15.0, "rec_yd": float(yd), "rec_td": 3.0})
        pts = sum(pm.PPR_WEIGHTS.get(k, 0.0) * v for k, v in st.items())
        assert pts >= prev - 1e-9 and pts < sum(pm.TAIL_SQUEEZE["WR"]) + 1.0 and st["rec_td"] == 3.0 and st["rec"] == 12.0
        prev = pts


def _pts(mod, pos, ppg, n):
    out = []
    for s in range(n):
        prof = mod.draw_season_profile({"player_id": f"p{s}", "pos": pos, "age": 26, "team": "CLE", "projection_mean_ppg": ppg}, mod.profile_rng(s, f"p{s}"))
        out += [mod.draw_week_points({"pos": pos}, prof, w, mod.week_rng(s, f"p{s}", w), {}).points for w in range(1, 18)]
    return np.array(out)


@pytest.mark.parametrize("pos,ppg", [("WR", 17.0), ("RB", 17.0), ("TE", 11.0)])
def test_v6_removes_the_extreme_tail_but_not_the_body(pos, ppg):
    a, b = _pts(v5, pos, ppg, 300), _pts(pm, pos, ppg, 300)
    assert b.max() < 62.0 and np.percentile(b, 99.9) <= np.percentile(a, 99.9) + 1e-9
    # the body (mean, sd, p90) is the same up to the few capped games
    assert b.mean() == pytest.approx(a.mean(), rel=0.01) and b.std() == pytest.approx(a.std(), rel=0.03)
    assert np.percentile(b, 90) == pytest.approx(np.percentile(a, 90), rel=0.01)


def test_real_panel_extremes_are_the_target():
    rows = dataset.load_panel()
    real = single_game_tail.real_games(rows)
    assert real["WR"][0].max() < 57 and (real["WR"][0] >= 60).sum() == 0
    sim, _ = single_game_tail.sim_games([r for r in rows if r["pos"] == "WR"][:250], 2)
    g, n = sim["WR"]
    assert g.max() < 60 and 1000.0 * (g >= 60).sum() / n < 1.0


def test_recap_rows_carry_the_projection_shown_going_into_the_week():
    from tests import test_sim_game_engine as eng
    from tests.test_sim_game_engine import BYES, ROWS
    from modules.sim.game_eval import Evaluator

    snap = eng.build_snapshot(ROWS, BYES, eng.GameSettings.parse({"user_slot": 4}), 11)
    state = eng.GameState(snap)
    em = eng.Emitter(state, snap)
    ctx = eng.DraftContext(snap, state)
    eng.run_ai_picks(ctx, em, 11)
    eng.auto_for_user(ctx, em, 11)
    eng.finish_draft(em, snap, state, 11)
    week = state.week
    ev = Evaluator(snap, state)  # what the lineup page showed before advancing
    eng.advance(eng.Emitter(state, snap), snap, state, 11)
    game = state.recaps[str(week)]["your_game"]
    rows = [r for r in [*game["starters"], *game["bench"], *game["opp_starters"]] if r["player"]]
    assert rows and all(isinstance(r["proj"], float) for r in rows)
    # the evaluator the engine used is built after waivers / AI trades, so the number can move a little from a pre-advance one
    for r in rows:
        assert 0.0 <= r["proj"] <= 40.0
        if r["flag"] in ("bye", "out"):
            assert r["proj"] == 0.0
        else:
            assert abs(r["proj"] - ev.proj(r["player"]["id"], week)) <= 0.35 * max(5.0, ev.proj(r["player"]["id"], week))
    assert any(r["proj"] > 0 for r in game["starters"] if r["flag"] is None)
