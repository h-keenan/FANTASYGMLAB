"""Player outcome model: determinism, contract, scoring, realism and calibration guards.

Pure (no players.db, no network): the calibration tests run against the committed
real-history panel (``modules/sim/calibration/data/panel.json.gz``).
"""

from __future__ import annotations

import numpy as np
import pytest

from modules.sim import player_model as pm
from modules.sim.calibration import backtest, dataset

BASE = {"player_id": "p1", "pos": "WR", "age": 25.0, "years_exp": 3, "team": "KC",
        "projection_mean_ppg": 14.0, "projection_sd": 7.0, "adp": 30, "is_rookie": False}
HALF = {"rec": 0.5, "rec_yd": 0.1, "rec_td": 6.0, "rush_yd": 0.1, "rush_td": 6.0, "pass_yd": 0.04, "pass_td": 4.0,
        "pass_int": -1.0, "fum_lost": -2.0}
STD = {**HALF, "rec": 0.0}
BONUS = {**HALF, "rec": 1.0, "bonus_rec_te": 0.5, "bonus_pass_yd_300": 3.0, "bonus_rush_yd_100": 3.0, "bonus_rec_yd_100": 3.0}


def _player(pos="WR", ppg=14.0, **kw):
    return {**BASE, "pos": pos, "projection_mean_ppg": ppg, **kw}


def _no_events(profile, **kw):
    """A clean profile: healthy, no role changes, flat form, the given season mean."""
    d = profile.to_dict()
    d.update(injury_events=[], role_changes=[], games_available_mask=[True] * 17, unavailable_reason=[""] * 17,
             form=[1.0] * 17, slump_window=None, volatility=1.0, rookie=False, **kw)
    return pm.SeasonProfile.from_dict(d)


# ------------------------------------------------------------------ determinism and contract


def test_profile_and_week_are_deterministic_and_seed_sensitive():
    a = pm.draw_season_profile(BASE, pm.profile_rng(5, "p1"))
    b = pm.draw_season_profile(BASE, pm.profile_rng(5, "p1"))
    c = pm.draw_season_profile(BASE, pm.profile_rng(6, "p1"))
    assert a == b and a != c
    w1 = pm.draw_week_points(BASE, a, 3, pm.week_rng(5, "p1", 3), {})
    w2 = pm.draw_week_points(BASE, a, 3, pm.week_rng(5, "p1", 3), {})
    assert w1 == w2


def test_week_draws_are_order_independent():
    prof = pm.draw_season_profile(BASE, pm.profile_rng(1, "p1"))
    fwd = [pm.draw_week_points(BASE, prof, w, pm.week_rng(1, "p1", w), {}) for w in range(1, 18)]
    rev = [pm.draw_week_points(BASE, prof, w, pm.week_rng(1, "p1", w), {}) for w in range(17, 0, -1)][::-1]
    assert fwd == rev


def test_profile_json_round_trip():
    for seed in range(40):
        prof = pm.draw_season_profile(_player(age=31), pm.profile_rng(seed, "p1"))
        assert pm.SeasonProfile.from_dict(prof.to_dict()) == prof


def test_profile_shape_and_availability_invariants():
    for seed in range(300):
        pos = ("QB", "RB", "WR", "TE", "K")[seed % 5]
        prof = pm.draw_season_profile(_player(pos, 12.0, age=24 + seed % 9), pm.profile_rng(seed, "x"))
        assert len(prof.games_available_mask) == len(prof.form) == len(prof.unavailable_reason) == 17
        assert prof.archetype in pm.ARCHETYPES
        assert prof.games_available_mask[prof.bye_week - 1] is False
        assert prof.unavailable_reason[prof.bye_week - 1] == "bye"
        for ev in prof.injury_events:
            assert 1 <= ev.week <= 17 and ev.weeks_out >= 1
            assert prof.games_available_mask[ev.week - 1], "the injury game itself is played"
        out_weeks = [i for i, r in enumerate(prof.unavailable_reason) if r == "injury"]
        assert all(not prof.games_available_mask[i] for i in out_weeks)
        assert sum(e.weeks_out for e in prof.injury_events) >= len(out_weeks)
        assert prof.season_mean_ppg >= 0 and 0.6 <= prof.volatility <= 1.8


def test_bye_week_comes_from_the_player_or_a_stable_team_default():
    prof = pm.draw_season_profile(_player(bye_week=9), pm.profile_rng(1, "p1"))
    assert prof.bye_week == 9
    p2 = {k: v for k, v in BASE.items()}
    assert pm.draw_season_profile(p2, pm.profile_rng(1, "p1")).bye_week == pm.default_bye_week("KC")
    assert 5 <= pm.default_bye_week("KC") <= 14


def test_season_points_and_rookie_flag_inputs():
    p = {"player_id": "r", "pos": "RB", "age": 21, "years_exp": 0, "team": "DAL", "projection_season_points": 170.0}
    prof = pm.draw_season_profile(p, pm.profile_rng(2, "r"))
    assert prof.rookie and prof.projection_mean_ppg == pytest.approx(10.0)


@pytest.mark.parametrize("bad", [{"pos": "WR", "projection_mean_ppg": 5}, {"player_id": "a", "pos": "LB", "projection_mean_ppg": 5},
                                 {"player_id": "a", "pos": "WR"}])
def test_invalid_player_inputs_raise(bad):
    with pytest.raises(ValueError):
        pm.draw_season_profile(bad, np.random.default_rng(0))


def test_week_out_of_range_raises():
    prof = pm.draw_season_profile(BASE, pm.profile_rng(1, "p1"))
    for w in (0, 18):
        with pytest.raises(ValueError):
            pm.draw_week_points(BASE, prof, w, np.random.default_rng(0), {})


# ------------------------------------------------------------------ weekly results


def test_bye_and_injury_weeks_are_inactive_and_the_onset_game_is_flagged():
    seen_injury = seen_bye = 0
    for seed in range(200):
        prof = pm.draw_season_profile(_player(age=30), pm.profile_rng(seed, "p1"))
        for w in range(1, 18):
            res = pm.draw_week_points(BASE, prof, w, pm.week_rng(seed, "p1", w), {})
            if w == prof.bye_week:
                assert (res.status, res.active, res.points) == ("bye", False, 0.0)
                seen_bye += 1
            elif prof.unavailable_reason[w - 1] == "injury":
                assert (res.status, res.active, res.points, res.stats) == ("injured", False, 0.0, {})
                assert not res.injury_incurred
            else:
                onset = any(e.week == w for e in prof.injury_events)
                assert res.active and res.injury_incurred == onset
                assert (res.status == "partial") == onset
                assert 0.0 < res.game_fraction <= 1.0 and (res.game_fraction < 1.0 or not onset)
                seen_injury += onset
    assert seen_bye == 200 and seen_injury > 50


@pytest.mark.parametrize("pos,keys", [
    ("QB", {"pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int", "rush_att", "rush_yd", "rush_td", "fum_lost"}),
    ("RB", {"rush_att", "rush_yd", "rush_td", "rec_tgt", "rec", "rec_yd", "rec_td", "fum_lost"}),
    ("WR", {"rec_tgt", "rec", "rec_yd", "rec_td", "rush_att", "rush_yd", "rush_td", "fum_lost"}),
    ("TE", {"rec_tgt", "rec", "rec_yd", "rec_td", "fum_lost"}),
    ("K", {"fgm", "xpm"}),
])
def test_stat_line_is_position_appropriate_and_consistent(pos, keys):
    prof = _no_events(pm.draw_season_profile(_player(pos, 12.0), pm.profile_rng(1, "p1")), season_mean_ppg=12.0)
    for w in range(1, 18):
        if w == prof.bye_week:
            continue
        res = pm.draw_week_points(_player(pos, 12.0), prof, w, pm.week_rng(3, "p1", w), {})
        assert set(res.stats) == keys
        assert all(v >= 0 for v in res.stats.values())
        assert res.points == pytest.approx(pm.score_stat_line(res.stats, pos, {}), abs=0.01)
        s = res.stats
        if "rec" in s:
            assert s["rec"] <= s["rec_tgt"]
        if "pass_cmp" in s:
            assert s["pass_cmp"] <= s["pass_att"]


@pytest.mark.parametrize("pos,ppg", [("QB", 20.0), ("RB", 13.0), ("WR", 14.0), ("TE", 9.0), ("K", 8.0), ("WR", 4.0), ("RB", 22.0)])
@pytest.mark.parametrize("scoring", [{}, HALF, STD, BONUS], ids=["ppr", "half", "std", "te-premium-and-bonuses"])
def test_weekly_mean_matches_the_target_in_the_leagues_own_scoring(pos, ppg, scoring):
    """The model's expected stat line is solved so mean points equal the target mean in
    the scoring the caller supplies (projection_mean_ppg is in league points)."""

    prof = _no_events(pm.draw_season_profile(_player(pos, ppg), pm.profile_rng(1, "p1")), season_mean_ppg=ppg)
    pts = []
    for s in range(900):
        for w in (1, 2, 3):
            pts.append(pm.draw_week_points(_player(pos, ppg), prof, w if w != prof.bye_week else 1, pm.week_rng(s, "m", w), scoring).points)
    assert np.mean(pts) == pytest.approx(ppg, rel=0.05)


def test_scoring_is_respected_and_te_premium_adds_points():
    prof = _no_events(pm.draw_season_profile(_player("TE", 9.0), pm.profile_rng(1, "p1")), season_mean_ppg=9.0)
    res = pm.draw_week_points(_player("TE", 9.0), prof, 1 if prof.bye_week != 1 else 2, pm.week_rng(2, "t", 1), {})
    ppr = pm.score_stat_line(res.stats, "TE", {})
    assert pm.score_stat_line(res.stats, "TE", STD) == pytest.approx(ppr - res.stats["rec"])
    prem = pm.score_stat_line(res.stats, "TE", {**HALF, "rec": 1.0, "bonus_rec_te": 0.5})
    assert prem == pytest.approx(ppr + 0.5 * res.stats["rec"])
    big = {"rec_yd": 0.1, "rec": 1.0, "bonus_rec_yd_100": 3.0, "rec_td": 6.0}
    assert pm.score_stat_line({"rec_yd": 120, "rec": 5}, "WR", big) == pytest.approx(12 + 5 + 3)


def test_weekly_points_are_skewed_and_td_driven_like_real_ones():
    prof = _no_events(pm.draw_season_profile(_player("WR", 12.0), pm.profile_rng(1, "p1")), season_mean_ppg=12.0)
    pts = np.array([pm.draw_week_points(_player("WR", 12.0), prof, 1 if prof.bye_week != 1 else 2, pm.week_rng(s, "w", 1), {}).points
                    for s in range(3000)])
    assert np.median(pts) < pts.mean()                 # right skew
    assert 0.5 < pts.std() / pts.mean() < 0.85         # real WR weekly CV is about 0.6
    assert (pts > 1.6 * pts.mean()).mean() > 0.08      # boom weeks exist
    assert (pts < 0.4 * pts.mean()).mean() > 0.08      # so do duds


def test_team_shock_correlates_teammates():
    prof = _no_events(pm.draw_season_profile(_player("WR", 12.0), pm.profile_rng(1, "p1")), season_mean_ppg=12.0)
    w = 1 if prof.bye_week != 1 else 2
    hi = [pm.draw_week_points({**_player("WR", 12.0), "team_shock": 2.0}, prof, w, pm.week_rng(s, "a", w), {}).points for s in range(1500)]
    lo = [pm.draw_week_points({**_player("WR", 12.0), "team_shock": -2.0}, prof, w, pm.week_rng(s, "a", w), {}).points for s in range(1500)]
    assert np.mean(hi) > np.mean(lo) + 1.0


# ------------------------------------------------------------------ season-level realism


def _profiles(n, **kw):
    return [pm.draw_season_profile(_player(**kw), pm.profile_rng(s, f"p{s}")) for s in range(n)]


def test_archetype_mix_is_varied_and_rookies_are_riskier():
    vets = _profiles(1500, age=27)
    rooks = _profiles(1500, age=21, years_exp=0, is_rookie=True)
    arch = {a: sum(p.archetype == a for p in vets) / 1500 for a in pm.ARCHETYPES}
    assert all(v > 0.03 for v in arch.values()), arch
    assert arch["solid"] > 0.3
    assert np.std([p.season_multiplier for p in rooks]) > np.std([p.season_multiplier for p in vets])
    assert sum(p.archetype == "breakout" for p in rooks) > sum(p.archetype == "breakout" for p in vets)


def test_stars_slump_and_older_players_miss_more_time():
    stars = _profiles(1500, ppg=22.0, pos="WR", age=27)
    assert sum(p.archetype == "slump" for p in stars) / 1500 > 0.04
    assert all(p.slump_window for p in stars if p.archetype == "slump")
    young = _profiles(1500, age=22)
    old = _profiles(1500, age=33)
    missed = lambda ps: np.mean([sum(1 for r in p.unavailable_reason if r == "injury") for p in ps])  # noqa: E731
    assert missed(old) > missed(young)


def test_deeper_players_have_more_upside_in_ppg_terms():
    depth = _profiles(1500, ppg=4.0, pos="WR", age=24)
    assert np.percentile([p.season_mean_ppg for p in depth], 95) > 7.0     # a role grab: 4 ppg becomes 7+
    assert np.mean([p.season_multiplier > 1.5 for p in depth]) > 0.1


def test_projection_sd_nudges_volatility():
    lo = np.mean([pm.draw_season_profile(_player(projection_sd=4.0), pm.profile_rng(s, "v")).volatility for s in range(200)])
    hi = np.mean([pm.draw_season_profile(_player(projection_sd=11.0), pm.profile_rng(s, "v")).volatility for s in range(200)])
    assert hi > lo


# ------------------------------------------------------------------ calibration against real history


@pytest.fixture(scope="module")
def panel():
    return dataset.load_panel()


def test_panel_is_real_multi_season_history(panel):
    assert {r["season"] for r in panel} == {2021, 2022, 2023, 2024, 2025}
    assert len(panel) > 1500
    r = next(r for r in panel if r["pos"] == "WR" and r["adp"] and r["adp"] < 30)
    assert len(r["weeks"]) == 17 and sum(w is None for w in r["weeks"]) == 1   # one bye


@pytest.fixture(scope="module")
def replay(panel):
    """Replay every other real player-season (all five seasons) through the model.
    The shipped constants were fit on all five seasons, so this is an in-sample
    regression guard; the true held-out 2024-25 numbers are in
    docs/fantasy-sim-player-model.md (produced by ``fit.py --train 2021 2022 2023``)."""

    rows = panel[::2]
    return rows, backtest.run(rows, copies=14)


def test_season_ppg_percentiles_are_calibrated_against_real_history(replay):
    _rows, res = replay
    p = res["pit"]["all"]
    assert p["n"] > 700
    assert p["ks"] < 0.12
    assert 0.38 < p["cov50"] < 0.62 and 0.66 < p["cov80"] < 0.90 and 0.80 < p["cov90"] < 0.97
    assert abs(p["mean_pit"] - 0.5) < 0.06
    for key in ("QB", "RB", "WR", "TE"):
        assert abs(res["pit"][key]["mean_pit"] - 0.5) < 0.09, key


def test_tier_hit_rates_match_real_outcomes_against_real_history(replay):
    _rows, res = replay
    assert res["tier_hit_mae"]["overall"] < 0.06
    for name, mae in res["tier_hit_mae"].items():
        assert mae < 0.09, name


def test_weekly_variance_matches_real_games_against_real_history(replay):
    _rows, res = replay
    for pos, row in res["weekly"].items():
        assert 0.88 < row["cv_ratio"] < 1.12, (pos, row["cv_ratio"])
        assert abs(row["sim_boom"] - row["real_boom"]) < 0.04, pos
        assert abs(row["sim_bust"] - row["real_bust"]) < 0.05, pos


def test_games_missed_match_real_rates_against_real_history(replay):
    _rows, res = replay
    a = res["availability"]["all core"]
    assert abs(a["sim"]["mean"] - a["real"]["mean"]) < 0.5
    assert abs(a["sim"]["p0"] - a["real"]["p0"]) < 0.07
    assert abs(a["sim"]["p6"] - a["real"]["p6"]) < 0.06


def test_in_season_drift_is_neither_too_wild_nor_too_flat(replay):
    _rows, res = replay
    assert abs(res["half_split"]["sim_sd"] - res["half_split"]["real_sd"]) < 0.07
    assert abs(res["lag1"]["sim"] - res["lag1"]["real"]) < 0.06


# ------------------------------------------------------------------ depth-chart coupling (starter injury -> backup role)


def _team(pos="RB", ppgs=(15.0, 6.0, 2.0), team="KC"):
    players, profs = {}, {}
    for i, ppg in enumerate(ppgs):
        pid = f"{pos}{i}"
        players[pid] = _player(pos, ppg, player_id=pid, team=team)
        profs[pid] = _no_events(pm.draw_season_profile(players[pid], pm.profile_rng(1, pid)), season_mean_ppg=ppg)
    return players, profs


def _hurt(profile, week=5, weeks_out=3):
    d = profile.to_dict()
    mask, reason = list(d["games_available_mask"]), list(d["unavailable_reason"])
    for w in range(week + 1, week + 1 + weeks_out):
        mask[w - 1], reason[w - 1] = False, "injury"
    d.update(games_available_mask=mask, unavailable_reason=reason, injury_events=[{"week": week, "weeks_out": weeks_out, "kind": "multi"}])
    return pm.SeasonProfile.from_dict(d)


def test_starter_injury_promotes_the_backup_for_exactly_the_games_missed():
    players, profs = _team()
    profs["RB0"] = _hurt(profs["RB0"], week=5, weeks_out=3)
    out = pm.apply_depth_coupling(players, profs)
    assert out["RB0"] == profs["RB0"]
    cover = out["RB1"].role_changes
    assert len(cover) == 1 and (cover[0].week, cover[0].end_week) == (6, 8) and cover[0].multiplier > 1.0
    before = [pm.expected_week_points(players["RB1"], profs["RB1"], w) for w in range(1, 18)]
    after = [pm.expected_week_points(players["RB1"], out["RB1"], w) for w in range(1, 18)]
    assert [round(a, 6) for a in after[:5]] == [round(b, 6) for b in before[:5]]          # before the injury: unchanged
    assert all(a > b for a, b in zip(after[5:8], before[5:8]))                              # covered games: lifted
    assert [round(a, 6) for a in after[8:]] == [round(b, 6) for b in before[8:]]            # starter back: unchanged
    assert out["RB2"].role_changes and out["RB2"].role_changes[0].multiplier < cover[0].multiplier * 1.5
    lift = after[5] - before[5]
    assert 0.0 < lift <= pm.INSEASON.absorb[1] * profs["RB0"].season_mean_ppg   # never more than the absorbed share


def test_coupling_is_pure_deterministic_and_scoped_to_team_and_position():
    players, profs = _team()
    profs["RB0"] = _hurt(profs["RB0"])
    other_team, other_profs = _team(team="BUF")
    wr, wr_profs = _team("WR", team="KC")
    allp = {**players, **{f"b{k}": {**v, "player_id": f"b{k}"} for k, v in other_team.items()}, **wr}
    allprof = {**profs, **{f"b{k}": v for k, v in other_profs.items()}, **wr_profs}
    snapshot = dict(allprof)
    a = pm.apply_depth_coupling(allp, allprof)
    b = pm.apply_depth_coupling(allp, allprof)
    assert a == b and allprof == snapshot                       # pure
    assert a["RB1"].role_changes                                # same team and position: covered
    for pid in ("bRB0", "bRB1", "bRB2", "WR0", "WR1", "WR2"):   # other team / other position: untouched
        assert a[pid] == allprof[pid], pid
    assert pm.apply_depth_coupling(allp, allprof, absorb=0.0) == allprof


def test_role_change_end_week_round_trips_and_defaults_to_the_rest_of_the_season():
    players, profs = _team()
    profs["RB0"] = _hurt(profs["RB0"])
    out = pm.apply_depth_coupling(players, profs)["RB1"]
    assert pm.SeasonProfile.from_dict(out.to_dict()) == out
    legacy = out.to_dict()
    for rc in legacy["role_changes"]:
        rc.pop("end_week", None)
    assert pm.SeasonProfile.from_dict(legacy).role_changes[0].end_week == 0


def test_season_spread_is_not_too_thin_and_qbs_are_not_too_loose_against_real_history(replay):
    """The v1 weak spots (five-season in-sample variance ratio 0.78 overall / 0.56 rookies / 1.76 QB, now 0.90 / 0.70 / 1.28), guarded with margin
    against the noisier half-panel replay."""

    _rows, res = replay
    sv = res["season_variance"]
    assert sv["all"]["var_ratio"] > 0.74
    assert sv["rookies"]["var_ratio"] > 0.50
    assert sv["QB"]["var_ratio"] < 1.55
    assert sv["proj < 8"]["var_ratio"] > 0.74
    wr = res["finish"]["WR:top12"]
    assert wr["real_top12"] - wr["sim_top12"] < 0.18   # five-season panel: v1 0.396 vs 0.521 real, v2 0.452; half-panel replay is noisy
