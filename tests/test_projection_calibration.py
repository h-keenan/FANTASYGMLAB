"""Projection calibration (league scoring, win-prob spread, top-tier shrink,
prior-season seeding, playoff slope prior). The fitted constants and their
held-out validation live in ``modules/projection_calibration.py``."""

import math

import numpy as np
import pytest

from modules import matchup_win_probability as mwp
from modules import player_projections as pp
from modules import projection_calibration as cal
from modules import trade_posture
from tests.test_player_projections import extended_schedule  # noqa: F401  (fixture)

PPR = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "rush_yd": 0.1, "rush_td": 6.0, "pass_yd": 0.04,
       "pass_td": 4.0, "pass_int": -1.0, "fum_lost": -2.0}


def scoring(**overrides):
    return {**PPR, **overrides}


# ---------------------------------------------------------------- scoring conversion
def test_numeric_scoring_settings_keeps_only_finite_numbers():
    out = cal.numeric_scoring_settings({"rec": 1, "pass_td": 6.0, "x": "no", "y": True, "z": float("nan"), "w": None})
    assert out == {"rec": 1.0, "pass_td": 6.0}
    assert cal.numeric_scoring_settings(None) == {}


def test_empty_or_non_scoring_blob_is_unknown_not_zero():
    assert cal.has_core_scoring({}) is False
    assert cal.has_core_scoring({"idp_tkl": 1.0}) is False
    assert cal.is_ppr_scoring({}) is True
    assert cal.game_scoring_delta({"receptions": 9}, "WR", {"idp_tkl": 1.0}) == 0.0


def test_ppr_scoring_is_recognised_and_changes_nothing():
    assert cal.is_ppr_scoring(PPR) is True
    row = {"receptions": 8, "receiving_yards": 90, "passing_tds": 3}
    assert cal.game_scoring_delta(row, "WR", PPR) == 0.0
    assert cal.is_ppr_scoring(scoring(pass_td=6.0)) is False


def test_game_scoring_delta_six_point_pass_td_is_two_per_td_for_qb():
    assert cal.game_scoring_delta({"passing_tds": 3}, "QB", scoring(pass_td=6.0)) == pytest.approx(6.0)


def test_game_scoring_delta_reception_value_and_te_premium():
    row = {"receptions": 7}
    assert cal.game_scoring_delta(row, "WR", scoring(rec=0.5)) == pytest.approx(-3.5)
    assert cal.game_scoring_delta(row, "TE", scoring(bonus_rec_te=0.5)) == pytest.approx(3.5)
    assert cal.game_scoring_delta(row, "WR", scoring(bonus_rec_te=0.5)) == 0.0
    assert cal.game_scoring_delta(row, "RB", scoring(bonus_rec_rb=0.25)) == pytest.approx(1.75)


def test_game_scoring_delta_interceptions_attempts_and_inc():
    row = {"passing_interceptions": 2, "pass_attempts": 40, "passing_completions": 25}
    assert cal.game_scoring_delta(row, "QB", scoring(pass_int=-2.0)) == pytest.approx(-2.0)
    assert cal.game_scoring_delta(row, "QB", scoring(pass_inc=-0.5)) == pytest.approx(-7.5)
    assert cal.game_scoring_delta(row, "QB", scoring(pass_cmp=0.1)) == pytest.approx(2.5)


def test_game_scoring_delta_threshold_bonuses():
    assert cal.game_scoring_delta({"passing_yards": 310}, "QB", scoring(bonus_pass_yd_300=3.0)) == 3.0
    assert cal.game_scoring_delta({"passing_yards": 299}, "QB", scoring(bonus_pass_yd_300=3.0)) == 0.0
    assert cal.game_scoring_delta({"rushing_yards": 104}, "RB", scoring(bonus_rush_yd_100=2.0)) == 2.0
    assert cal.game_scoring_delta({"receiving_yards": 120}, "WR", scoring(bonus_rec_yd_100=2.0)) == 2.0


def test_game_scoring_delta_skips_kickers_and_missing_fields():
    assert cal.game_scoring_delta({"receptions": 5}, "K", scoring(rec=0.5)) == 0.0
    assert cal.game_scoring_delta({}, "WR", scoring(rec=0.5)) == 0.0


def test_unsupported_scoring_keys_names_the_gaps():
    assert cal.unsupported_scoring_keys(scoring(rec_fd=0.5, rec_5_9=0.2)) == ["rec_fd", "rec_5_9"]
    assert cal.unsupported_scoring_keys(PPR) == []
    assert cal.unsupported_scoring_keys(None) == []


def test_league_scoring_adjustment_is_recency_weighted_mean():
    rows = [{"week": 1, "passing_tds": 0}, {"week": 7, "passing_tds": 4}]
    adj = cal.league_scoring_adjustment(rows, "QB", scoring(pass_td=6.0), reference_week=7, half_life=6.0)
    # deltas 0 and 8, weights 0.5 and 1.0 -> 8 * 1 / 1.5
    assert adj == pytest.approx(8.0 / 1.5)
    flat = cal.league_scoring_adjustment(rows, "QB", scoring(pass_td=6.0), reference_week=7, half_life=0)
    assert flat == pytest.approx(4.0)


def test_league_scoring_adjustment_zero_for_ppr_empty_or_k():
    rows = [{"week": 1, "passing_tds": 4}]
    assert cal.league_scoring_adjustment(rows, "QB", PPR, reference_week=1) == 0.0
    assert cal.league_scoring_adjustment([], "QB", scoring(pass_td=6.0), reference_week=1) == 0.0
    assert cal.league_scoring_adjustment(rows, "K", scoring(pass_td=6.0), reference_week=1) == 0.0
    assert cal.league_scoring_adjustment(rows, "QB", None, reference_week=1) == 0.0


def test_league_scoring_adjustment_shrink_k_pulls_toward_zero():
    rows = [{"week": 1, "passing_tds": 2}]
    raw = cal.league_scoring_adjustment(rows, "QB", scoring(pass_td=6.0), reference_week=1)
    shrunk = cal.league_scoring_adjustment(rows, "QB", scoring(pass_td=6.0), reference_week=1, shrink_k=3.0)
    assert shrunk == pytest.approx(raw * 1 / 4)


def test_apply_scoring_to_projection_shifts_band_and_floors_at_zero():
    assert cal.apply_scoring_to_projection(10.0, 4.0, 18.0, 2.0) == (12.0, 6.0, 20.0)
    assert cal.apply_scoring_to_projection(1.0, 0.0, 3.0, -2.0) == (0.0, 0.0, 1.0)
    assert cal.apply_scoring_to_projection(10.0, 4.0, 18.0, 0.0) == (10.0, 4.0, 18.0)


# ---------------------------------------------------------------- win-probability spread
def test_calibrated_margin_stdev_scales_the_independent_sum():
    assert cal.calibrated_margin_stdev(100.0) == pytest.approx(cal.WIN_PROB_SPREAD_MULTIPLIER * 10.0)
    assert cal.calibrated_margin_stdev(-5.0) == 0.0


def test_win_probability_uses_the_widened_spread_and_stays_monotone():
    def starter(mean, half):
        return {"projection": {"status": "ok", "point_estimate": mean, "low": mean - half, "high": mean + half}}

    me, them = [starter(120.0, 20.0)], [starter(110.0, 20.0)]
    result = mwp.compute_live_win_probability(me, them)
    sd = cal.WIN_PROB_SPREAD_MULTIPLIER * math.sqrt(20.0**2 + 20.0**2)
    assert result["probability"] == pytest.approx(0.5 * (1 + math.erf(10.0 / sd / math.sqrt(2))), abs=1e-4)
    uncalibrated = 0.5 * (1 + math.erf(10.0 / math.sqrt(800.0) / math.sqrt(2)))
    assert 0.5 < result["probability"] < uncalibrated


def test_win_prob_per_point_derives_from_lineup_variance_with_flat_fallback():
    flat = cal.win_prob_per_point(None)
    assert flat == pytest.approx(0.3989422804014327 / (math.sqrt(2.0) * 22.0))
    assert cal.win_prob_per_point(0.0) == flat
    small = cal.win_prob_per_point(16.0**2)
    large = cal.win_prob_per_point(31.0**2)
    assert large < small  # bigger lineups are noisier, so a point is worth less
    assert large == pytest.approx(0.3989422804014327 / (cal.WIN_PROB_SPREAD_MULTIPLIER * math.sqrt(2.0) * 31.0))


def test_trade_posture_slope_uses_team_sd_when_known():
    assert trade_posture.win_prob_per_point_for(None) == trade_posture.WIN_PROB_PER_POINT
    assert trade_posture.win_prob_per_point_for(0.0) == trade_posture.WIN_PROB_PER_POINT
    assert trade_posture.win_prob_per_point_for(35.0) < trade_posture.win_prob_per_point_for(20.0)


def test_trade_posture_assess_reads_the_lineup_derived_slope():
    def model(team_sd):
        points = {"ros_delta": -100.0, "ros_before": 1500.0}
        if team_sd is not None:
            points["team_weekly_sd"] = team_sd
        return {"available": True, "points": points, "value_per_point": 40.0, "win_now_delta": 0, "future_delta": 0}

    posture = {"key": "contender", "group": trade_posture.GROUP_BY_KEY["contender"]}
    base = trade_posture.assess(posture, model(None))
    wide = trade_posture.assess(posture, model(40.0))
    assert wide["wins_delta"] == pytest.approx(-100.0 * trade_posture.win_prob_per_point_for(40.0), abs=0.01)
    assert abs(wide["wins_delta"]) < abs(base["wins_delta"])
    # The window cost is wins * (price per win): the slope cancels, so it is unchanged.
    assert wide["window_term"] == pytest.approx(base["window_term"], rel=0.01)


# ---------------------------------------------------------------- top-tier shrink
@pytest.mark.parametrize("pos", ["QB", "RB", "WR", "TE"])
def test_shrink_is_identity_at_or_below_anchor_and_continuous(pos):
    anchor, slope = cal.TOP_SHRINK[pos]
    assert cal.shrink_top_tier(anchor - 3.0, pos) == anchor - 3.0
    assert cal.shrink_top_tier(anchor, pos) == anchor
    assert cal.shrink_top_tier(anchor + 1e-9, pos) == pytest.approx(anchor, abs=1e-6)
    assert 0.0 < slope < 1.0


@pytest.mark.parametrize("pos", ["QB", "RB", "WR", "TE"])
def test_shrink_is_strictly_order_preserving_above_anchor(pos):
    anchor, _ = cal.TOP_SHRINK[pos]
    values = [anchor + x for x in (0.5, 2.0, 5.0, 9.0)]
    out = [cal.shrink_top_tier(v, pos) for v in values]
    assert out == sorted(out) and len(set(out)) == len(out)
    assert all(o < v for o, v in zip(out, values))


def test_shrink_leaves_kickers_and_unknown_positions_alone():
    assert cal.shrink_top_tier(25.0, "K") == 25.0
    assert cal.shrink_top_tier(25.0, "DEF") == 25.0
    assert cal.shrink_top_tier(25.0, None) == 25.0


def test_calibrated_baseline_applies_shrink_in_the_estimator():
    anchor, slope = cal.TOP_SHRINK["RB"]
    assert pp._calibrated_baseline(anchor + 6.0, "RB") == pytest.approx(anchor + 6.0 * slope)
    assert pp._calibrated_baseline(4.0, "RB") == 4.0


# ---------------------------------------------------------------- prior-season seeding
def test_seed_with_prior_season_shifts_prior_weeks_into_the_past_and_keeps_current():
    prior = [{"week": 17, "fantasy_points_ppr": 9.0}, {"week": 18, "fantasy_points_ppr": 11.0}]
    current = [{"week": 1, "fantasy_points_ppr": 20.0}]
    out = cal.seed_with_prior_season(current, prior)
    shift = cal.PRIOR_SEASON_WEEKS + cal.PRIOR_SEASON_AGE_OFFSET_WEEKS
    assert [r["week"] for r in out] == [17 - shift, 18 - shift, 1]
    assert prior[0]["week"] == 17 and current[0]["week"] == 1  # inputs untouched
    assert all(r["week"] <= 0 for r in out[:2])


def test_seed_with_prior_season_without_prior_returns_current_copy():
    current = [{"week": 3, "fantasy_points_ppr": 7.0}]
    out = cal.seed_with_prior_season(current, None)
    assert out == current and out[0] is not current[0]
    assert cal.seed_with_prior_season(None, [{"week": None}]) == []


def _rows(points, start=1):
    return [{"week": start + i, "games_played": 1, "fantasy_points_ppr": p, "targets": 8} for i, p in enumerate(points)]


def test_seeded_history_gives_a_week_one_estimate_and_older_games_weigh_less():
    prior = _rows([14.0] * 12, start=1)
    seeded = cal.seed_with_prior_season([], prior)
    as_of = pp._most_recent_played_week(seeded, before_week=1)
    trend = pp._player_usage_trend(seeded, position="WR", upto_week=as_of)
    assert trend is not None and trend["games_played"] == 12
    # A hot current-season game outweighs an equally recent prior-season one.
    mixed = cal.seed_with_prior_season(_rows([30.0], start=1), prior)
    hot = pp._player_usage_trend(mixed, position="WR", upto_week=1)
    cold = pp._player_usage_trend(seeded, position="WR", upto_week=as_of)
    assert hot["baseline_ppr"] > cold["baseline_ppr"]


def test_project_player_week_week_one_uses_prior_rows_and_flags_them(extended_schedule):  # noqa: F811
    players = {"wr_a1": {"position": "WR", "team": "AAA"}}
    kwargs = dict(players=players, defense_strength={}, team_qb_quality={}, weekly_stats={})
    none = pp.project_player_week("wr_a1", week=1, season=2099, player_weekly_rows=[], **kwargs)
    assert none["status"] == "insufficient_player_data"
    seeded = pp.project_player_week(
        "wr_a1", week=1, season=2099, player_weekly_rows=[], prior_weekly_rows=_rows([13, 15, 12, 14, 16]), **kwargs
    )
    assert seeded["status"] == "ok"
    assert seeded["basis"]["prior_season_seeded"] is True
    assert seeded["basis"]["recent_weeks_used"] == []  # prior weeks are not shown as this season's
    assert seeded["confidence"] == "medium"  # 5 prior games, none this season: capped below "high"
    assert seeded["low"] <= seeded["point_estimate"] <= seeded["high"]


def test_project_player_week_with_current_games_is_not_capped_and_shows_only_current_weeks(extended_schedule):  # noqa: F811
    players = {"wr_a1": {"position": "WR", "team": "AAA"}}
    kwargs = dict(players=players, defense_strength={}, team_qb_quality={}, weekly_stats={})
    prior = [dict(r, targets=2) for r in _rows([3.0] * 14)]  # a low-usage prior season
    cur = _rows([22.0, 24.0, 21.0, 23.0], start=1)
    with_prior = pp.project_player_week("wr_a1", week=5, season=2099, player_weekly_rows=cur,
                                        prior_weekly_rows=prior, **kwargs)
    without = pp.project_player_week("wr_a1", week=5, season=2099, player_weekly_rows=cur, **kwargs)
    assert without["basis"]["prior_season_seeded"] is False
    assert with_prior["basis"]["season_games_played"] == 18  # 14 prior + 4 current
    assert with_prior["basis"]["recent_weeks_used"] == [1, 2, 3, 4]
    assert abs(with_prior["point_estimate"] - without["point_estimate"]) < 3.0
    assert with_prior["confidence"] == "high"  # four current games


def test_prior_season_weekly_map_is_cached_and_fails_soft(monkeypatch):
    calls = []

    def fake(season):
        calls.append(season)
        return {"1": [{"week": 1}]}

    monkeypatch.setattr(pp.sleeper, "cached_season_weekly_map", fake)
    pp._prior_season_map_cache.clear()
    assert pp.prior_season_weekly_map(2026) == {"1": [{"week": 1}]}
    assert pp.prior_season_weekly_map(2026) == {"1": [{"week": 1}]}
    assert calls == [2025]
    pp._prior_season_map_cache.clear()
    monkeypatch.setattr(pp.sleeper, "cached_season_weekly_map", lambda s: (_ for _ in ()).throw(OSError("x")))
    assert pp.prior_season_weekly_map(2026) == {}
    pp._prior_season_map_cache.clear()


# ---------------------------------------------------------------- scoring through the estimator
def _box_rows(passing_tds, n=5):
    return [
        {"week": 1 + i, "games_played": 1, "fantasy_points_ppr": 20.0, "pass_attempts": 34.0, "rush_attempts": 3.0,
         "passing_tds": passing_tds, "passing_yards": 250.0}
        for i in range(n)
    ]


def test_scoring_adjustment_helper_uses_games_up_to_as_of_week():
    rows = _box_rows(2)
    six = {**PPR, "pass_td": 6.0}
    assert pp._scoring_adjustment(rows, "QB", six, 5) == pytest.approx(4.0)
    assert pp._scoring_adjustment(rows, "QB", PPR, 5) == 0.0
    assert pp._scoring_adjustment(rows, "QB", None, 5) == 0.0
    assert pp._scoring_adjustment(rows, "QB", six, None) == 0.0


def test_project_player_week_converts_to_league_scoring_at_the_source(extended_schedule):  # noqa: F811
    players = {"qb_a1": {"position": "QB", "team": "AAA"}}
    kwargs = dict(players=players, player_weekly_rows=_box_rows(2), defense_strength={}, team_qb_quality={},
                  weekly_stats={})
    ppr = pp.project_player_week("qb_a1", week=6, season=2099, **kwargs)
    six = pp.project_player_week("qb_a1", week=6, season=2099, scoring_settings={**PPR, "pass_td": 6.0}, **kwargs)
    assert ppr["basis"]["league_scoring_applied"] is False
    assert six["basis"]["league_scoring_applied"] is True
    assert six["basis"]["league_scoring_adjustment"] == pytest.approx(4.0)
    assert six["point_estimate"] == pytest.approx(ppr["point_estimate"] + 4.0, abs=0.11)
    assert six["low"] == pytest.approx(ppr["low"] + 4.0, abs=0.11)
    assert six["high"] == pytest.approx(ppr["high"] + 4.0, abs=0.11)
    same = pp.project_player_week("qb_a1", week=6, season=2099, scoring_settings=PPR, **kwargs)
    assert same["point_estimate"] == ppr["point_estimate"]


def test_baseline_weekly_points_scores_in_league_scoring_and_flags_it():
    rows = [{"player_id": "q", "position": "QB"}]
    weekly = {"q": _box_rows(2)}
    ppr = pp.baseline_weekly_points(rows, weekly_by_player=weekly, as_of_week=6)["q"]
    six = pp.baseline_weekly_points(rows, weekly_by_player=weekly, as_of_week=6,
                                    scoring_settings={**PPR, "pass_td": 6.0})["q"]
    assert six["ppg"] == pytest.approx(ppr["ppg"] + 4.0, abs=0.02)
    assert six["scoring_applied"] is True
    assert pp.baseline_weekly_points(rows, weekly_by_player=weekly, as_of_week=6)["q"]["scoring_applied"] is False


def test_baseline_weekly_points_seeds_from_prior_rows_when_no_current_games():
    rows = [{"player_id": "w", "position": "WR"}]
    out = pp.baseline_weekly_points(rows, weekly_by_player={}, prior_weekly_by_player={"w": _rows([12.0] * 8)}, as_of_week=1)
    assert out["w"]["ppg"] > 0 and out["w"]["games"] == 8
    assert pp.baseline_weekly_points(rows, weekly_by_player={}, as_of_week=1) == {}


# ---------------------------------------------------------------- playoff slope prior
def test_playoff_constants_are_the_calibration_module_values():
    from modules import playoff_simulator as sim

    assert sim.DEFAULT_SLOPE == cal.PLAYOFF_SLOPE_PRIOR
    assert sim.MAX_FIT_SLOPE == cal.PLAYOFF_MAX_SLOPE
    assert sim.PRIOR_GAMES == cal.PLAYOFF_SLOPE_PRIOR_GAMES
    assert 0.3 < cal.PLAYOFF_SLOPE_PRIOR < 0.6


def test_playoff_map_slope_is_shrunk_toward_prior_relative_to_the_mle():
    from modules import playoff_simulator as sim

    rng = np.random.default_rng(3)
    z = rng.normal(scale=1.3, size=30)
    y = (rng.random(30) < 1.0 / (1.0 + np.exp(-1.2 * z))).astype(int)
    mle, _, _ = sim.fit_win_probability_slope(z.tolist(), y.tolist(), prior_games=0.0)
    map_, fitted, _ = sim.fit_win_probability_slope(z.tolist(), y.tolist())
    assert fitted is True
    assert abs(map_ - cal.PLAYOFF_SLOPE_PRIOR) < abs(mle - cal.PLAYOFF_SLOPE_PRIOR)


# ---------------------------------------------------------------- plumbing
def test_league_value_settings_expose_the_leagues_numeric_scoring():
    from modules import league_value_settings as lvs

    league = {"scoring_settings": {"rec": 0.5, "pass_td": 6, "label": "x"}, "settings": {}, "roster_positions": []}
    detected = lvs.detect_league_value_settings_from_payload(league)
    assert detected["_scoring_settings"] == {"rec": 0.5, "pass_td": 6.0}
    assert lvs.detect_league_value_settings_from_payload({})["_scoring_settings"] == {}
    assert lvs.detect_league_value_settings(None)["_scoring_settings"] == {}


def test_attach_projection_baselines_forwards_league_scoring_and_flags_rows(monkeypatch):
    import pandas as pd

    from modules import trade_grade

    seen = {}

    def fake(rows, **kwargs):
        seen.update(kwargs)
        return {"a": {"ppg": 12.5, "sd": 3.0, "games": 5, "confidence": "high", "scoring_applied": True}}

    monkeypatch.setattr(pp, "baseline_weekly_points", fake)
    valued = pd.DataFrame([{"player_id": "a", "position": "WR", "dynasty_score": 50},
                           {"player_id": "b", "position": "WR", "dynasty_score": 40}])
    out, _ = trade_grade.attach_projection_baselines(
        valued, None, {"a", "b"}, "dynasty_score", lineup_settings={"_scoring_settings": {"rec": 0.5}}
    )
    assert seen["scoring_settings"] == {"rec": 0.5}
    flags = dict(zip(out["player_id"], out["proj_scoring_applied"]))
    assert flags == {"a": True, "b": False}
    trade_grade.attach_projection_baselines(valued, None, {"a"}, "dynasty_score")
    assert seen["scoring_settings"] is None


def test_weekly_projection_for_player_passes_league_scoring_and_prior_rows(monkeypatch):
    from services import mobile_api_service as svc

    captured = {}

    def fake_project(player_id, week, season, **kwargs):
        captured.update(kwargs)
        return {"status": "ok", "point_estimate": 10.0, "low": 5.0, "high": 15.0, "confidence": "high",
                "opponent": "BBB", "position": "WR"}

    monkeypatch.setattr(svc.player_projections, "project_player_week", fake_project)
    monkeypatch.setattr(svc, "_with_game_weather", lambda summary, result: summary)
    svc._weekly_projection_for_player(
        "p1", 3, 2026, players_lookup={}, weekly_stats={"p1": {"weekly": [{"week": 1}]}}, defense_strength={},
        scoring_settings={"rec": 0.5}, prior_weekly_by_player={"p1": [{"week": 18}]},
    )
    assert captured["scoring_settings"] == {"rec": 0.5}
    assert captured["prior_weekly_rows"] == [{"week": 18}]
    assert captured["player_weekly_rows"] == [{"week": 1}]


def test_baseline_scoring_applied_is_false_for_non_ppr_leagues_without_box_stats():
    rows = [{"player_id": "w", "position": "WR"}]
    bare = [{"week": i, "games_played": 1, "fantasy_points_ppr": 12.0, "targets": 8} for i in range(1, 5)]
    half = {**PPR, "rec": 0.5}
    out = pp.baseline_weekly_points(rows, weekly_by_player={"w": bare}, as_of_week=5, scoring_settings=half)["w"]
    # no receptions on the rows -> no conversion possible -> the lineup model must convert it
    assert out["scoring_applied"] is False
    ppr = pp.baseline_weekly_points(rows, weekly_by_player={"w": bare}, as_of_week=5, scoring_settings=PPR)["w"]
    assert ppr["scoring_applied"] is True
