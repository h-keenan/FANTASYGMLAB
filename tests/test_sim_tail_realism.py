"""player-model-4: bounded tails, additive team roles, robust projections (the 72-point, 70-projected depth WR bug)."""

from __future__ import annotations

import copy
from dataclasses import replace

import numpy as np

from modules.sim import game_scoring, player_model as pm
from modules.sim import team_roles as tr
from modules.sim.calibration import tail_report
from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSettings
from tests.test_sim_game_engine import BYES, ROWS

V4_ID = "player_model-player-model-4"


def wr(pid="x", ppg=1.2, **kw):
    return {"player_id": pid, "pos": "WR", "age": 25.0, "team": "SEA", "projection_mean_ppg": ppg, "is_rookie": False, **kw}


def test_soft_ceiling_is_identity_low_bounded_high_and_monotone():
    assert pm.soft_ceiling(8.0, 26.0) > 7.99
    assert pm.soft_ceiling(26.0, 26.0) < 26.0
    assert all(pm.soft_ceiling(x, 26.0) < 26.0 for x in (30, 80, 500))
    xs = np.linspace(0, 200, 400)
    ys = [pm.soft_ceiling(float(x), 26.0) for x in xs]
    assert all(b >= a - 1e-12 for a, b in zip(ys, ys[1:]))
    assert pm.soft_ceiling(5.0, None) == 5.0
    assert tr.soft_ceiling(7.0, tr.PROJ_CEIL["WR"]) == pm.soft_ceiling(7.0, 30.0)


def test_a_depth_receiver_cannot_have_a_star_season_or_a_70_point_game():
    means, weeks = [], []
    for seed in range(1500):
        prof = pm.draw_season_profile(wr(f"d{seed}"), pm.profile_rng(seed, f"d{seed}"))
        means.append(prof.season_mean_ppg)
        assert prof.season_mean_ppg < pm.SEASON_CEIL["WR"]
        for w in range(1, 18):
            if prof.games_available_mask[w - 1]:
                assert pm.expected_week_points(wr(), prof, w) < pm.WEEK_CEIL["WR"]
                if seed < 150:
                    weeks.append(pm.draw_week_points(wr(f"d{seed}"), prof, w, pm.week_rng(seed, f"d{seed}", w), {}).points)
    assert np.percentile(means, 99.9) < 14.0  # real depth (< 3 ppg preseason) seasons stay in single digits to low teens
    assert max(weeks) < 60.0 and np.mean(np.array(weeks) > 40) < 0.002


def test_natural_role_changes_cannot_compound_without_limit():
    prof = pm.draw_season_profile(wr("c", 4.0), pm.profile_rng(1, "c"))
    many = tuple(pm.RoleChange(week=3, kind="promotion", multiplier=2.5) for _ in range(8))
    big = replace(prof, role_changes=many, form=tuple([1.0] * 17), season_mean_ppg=4.0)
    assert pm.expected_week_points(wr("c", 4.0), big, 6) <= 4.0 * pm.ROLE_CUM[1] + 1e-6
    low = replace(big, role_changes=tuple(pm.RoleChange(week=3, kind="demotion", multiplier=0.3) for _ in range(8)))
    assert pm.expected_week_points(wr("c", 4.0), low, 6) >= 4.0 * pm.ROLE_CUM[0] - 1e-6


def test_team_role_is_additive_points_not_a_multiplier_on_the_hidden_season():
    prof = pm.draw_season_profile(wr("a", 0.6), pm.profile_rng(3, "a"))
    boomer = replace(prof, season_mean_ppg=3.0, form=tuple([1.0] * 17), role_changes=())
    base = pm.expected_week_points(wr("a", 0.6), boomer, 7)
    with_role = pm.expected_week_points(wr("a", 0.6), pm.with_role(boomer, 7, 1.0, 4.7), 7)
    assert abs((with_role - base) - 4.7) < 0.05  # exactly the added points, whatever his season turned out to be
    assert pm.expected_week_points(wr("a", 0.6), pm.with_role(boomer, 7, 1.0, 400.0), 7) < pm.WEEK_CEIL["WR"]
    assert pm.with_role(boomer, 7, 1.0, 0.0) is boomer
    other = pm.expected_week_points(wr("a", 0.6), pm.with_role(boomer, 7, 1.0, 4.7), 8)
    assert abs(other - pm.expected_week_points(wr("a", 0.6), boomer, 8)) < 1e-9  # only that week


def sea_rows(star_out=4):
    rows = copy.deepcopy(ROWS)
    sea = [r for r in rows if r["nfl_team"] == "ATL" and r["pos"] == "WR"]
    spec = [("jsn", 25.8, 95.0, star_out, 1), ("shaheed", 6.0, 60.0, 0, 2), ("kupp", 6.4, 58.0, 0, 3), ("horton", 3.7, 56.0, 0, 4),
            ("velus", 0.6, 50.0, 0, 6)]
    for r, (n, mean, market, weeks, order) in zip(sea, spec):
        r.update(name=n, mean=mean, market=market, injury_weeks=weeks, extra={"depth_chart_order": float(order)})
    return rows, {n: r["pid"] for n, r in zip(("jsn", "shaheed", "kupp", "horton", "velus"), sea)}


def v4_eval(rows, week=2):
    settings = replace(GameSettings.parse({"user_slot": 4}), reserve_v=0, ir_slots=0)
    snap = build_snapshot(rows, BYES, settings, 11, scoring_model=V4_ID)
    state = GameState(snap)
    state.week = week
    return snap, state, Evaluator(snap, state)


def test_the_velus_case_fill_in_projection_is_additive_bounded_and_robust_to_one_freak_game():
    rows, ids = sea_rows()
    snap, state, ev = v4_eval(rows, 1)
    assert ev.additive
    v = ids["velus"]
    r = ev.role(ids["horton"], 1)
    assert r.kind == "fill_in" and ev.role(v, 1).kind == "bench"  # one inheritor, the next WR on the chart stays baseline
    # the inheritor: own mean + 0.23 x 0.8 of the star's level, never above the star
    exp = 3.7 + tr.ABSORB["WR"] * tr.FIRST_BACKUP_SHARE * 25.8
    assert abs(ev.week_mean(ids["horton"], 1) - exp) < 0.1 and ev.week_mean(ids["horton"], 1) < 25.8
    # the bench receiver is projected near his baseline, not as a starter
    assert ev.week_mean(v, 1) < 1.5
    # one 72-point game, then three big ones: his level and projection stay modest (winsorised, shrunk toward 0.6)
    state.points[v] = [72.0, 40.0, 30.0, 25.0]
    state.history = [{}] * 4
    state.week = 5
    ev = Evaluator(snap, state)
    assert ev.level(v) <= tr.LEVEL_PRIOR_GAMES * 0.6 / 6 + 4 * tr.LEVEL_WIN_MULT * 3.0 / 6 and ev.level(v) < 8.0
    assert ev.next_proj(v, 5) < 12.0 and ev.ros_mean(v) < 12.0
    assert max(ev.week_mean(p, 5) for p in snap.pids) < tr.PROJ_CEIL["QB"]


def test_role_normalised_level_does_not_double_count_a_fill_in_stretch():
    rows, ids = sea_rows(star_out=0)
    snap, state, _ = v4_eval(rows, 5)
    h = ids["horton"]
    state.points[h] = [9.0, 9.0, 9.0, 9.0]  # 9 a game as a fill-in worth 3.7 + 4.7 = 8.4: no evidence he is better than 3.7
    state.role_hist[h] = {str(w): [1.0, 4.7] for w in range(1, 5)}
    state.history = [{}] * 4
    ev = Evaluator(snap, state)
    assert ev.level(h) < 5.0
    state.role_hist = {}  # the same scores with no role recorded would read as a real improvement
    assert Evaluator(snap, state).level(h) > ev.level(h)


def test_a_bench_qb_weighted_by_his_role_share():
    ev_rows = copy.deepcopy(ROWS)
    qbs = [r for r in ev_rows if r["nfl_team"] == "ATL" and r["pos"] == "QB"]
    for r, (n, m, mk, o) in zip(qbs, (("q1", 20.0, 90.0, 1), ("q2", 14.0, 60.0, 2), ("q3", 10.0, 55.0, 3))):
        r.update(name=n, mean=m, market=mk, injury_weeks=0, extra={"depth_chart_order": float(o)})
    snap, state, _ = v4_eval(ev_rows, 5)
    q2 = qbs[1]["pid"]
    state.points[q2] = [1.0, 2.0, 0.0, 1.0]  # bench QB scoring nothing says little about his level
    state.role_hist[q2] = {str(w): [tr.BACKUP_QB_SHARE, 0.0] for w in range(1, 5)}
    state.history = [{}] * 4
    assert Evaluator(snap, state).level(q2) > 8.0


def test_whole_game_tails_projections_and_team_scores_are_realistic():
    rows = tail_report.dataset.load_panel()
    res = tail_report.game_layer(rows, V4_ID, games=2)
    w = res["weekly"]
    assert w["depth(<6)"]["gt40"] < 0.002 and w["depth(<6)"]["max"] < 75
    for pos in ("QB", "RB", "WR", "TE"):
        assert w[pos]["gt40"] < 0.012 and w[pos]["max"] < 80, (pos, w[pos])
    assert 85 < res["team_scores"]["mean"] < 135 and res["team_scores"]["max"] < 230
    pe = res["projection_error"]
    assert pe["max_shown"] < max(tr.PROJ_CEIL.values()) and pe["shown_gt_30"] == 0 and pe["mae"] < 5.0


def test_summarize_reports_shares_and_percentiles():
    s = tail_report.summarize([1.0] * 98 + [45.0, 55.0])
    assert s["n"] == 100 and s["max"] == 55.0 and s["gt40"] == 0.02 and s["gt50"] == 0.01
