"""modules.player_projections — the first real per-game point projection.

Covers: defense-strength-by-position aggregation (recency weighting, low
sample handling, tier/rank), the weekly projection formula (normal vs
small-sample players, opponent-multiplier bounding), and the required edge
cases — bye week, no scheduled opponent, insufficient player data, and
unsupported positions. No test touches modules.rankings.load_players or
build_players_table (per this repo's safety rule, never against the real
data/players.db) and nothing here asserts anything about value_score or
rankings — this module doesn't feed either.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import nfl_schedule, player_projections as pp


# ---------------------------------------------------------------------------
# Schedule fixtures
# ---------------------------------------------------------------------------


def _round_robin_games() -> pd.DataFrame:
    """AAA/BBB/CCC/DDD across 6 weeks — deliberately gappy per team so real
    byes get synthesized by modules.nfl_schedule.team_schedule (AAA has no
    game in weeks 2 or 4; BBB none in 2/3/5; CCC none in 4/5; DDD none in 3).
    """

    rows = [
        {"season": 2099, "game_type": "REG", "week": 1, "home_team": "AAA", "away_team": "BBB", "home_score": 24.0, "away_score": 10.0},
        {"season": 2099, "game_type": "REG", "week": 2, "home_team": "CCC", "away_team": "DDD", "home_score": 20.0, "away_score": 14.0},
        {"season": 2099, "game_type": "REG", "week": 3, "home_team": "AAA", "away_team": "CCC", "home_score": 27.0, "away_score": 9.0},
        {"season": 2099, "game_type": "REG", "week": 4, "home_team": "BBB", "away_team": "DDD", "home_score": 17.0, "away_score": 20.0},
        {"season": 2099, "game_type": "REG", "week": 5, "home_team": "AAA", "away_team": "DDD", "home_score": 30.0, "away_score": 13.0},
        {"season": 2099, "game_type": "REG", "week": 6, "home_team": "BBB", "away_team": "CCC", "home_score": 21.0, "away_score": 24.0},
    ]
    return pd.DataFrame(rows)


def _tier_games() -> pd.DataFrame:
    """Three defenses (TOUGH/MID/WEAK) each play the same two opponents
    across weeks 1-2, plus a fourth defense (THIN) with a single sampled
    game — clean, unambiguous point totals so tier/rank math is easy to
    hand-verify."""

    rows = [
        {"season": 2098, "game_type": "REG", "week": 1, "home_team": "TOUGH", "away_team": "OFFA", "home_score": 10.0, "away_score": 3.0},
        {"season": 2098, "game_type": "REG", "week": 2, "home_team": "TOUGH", "away_team": "OFFA", "home_score": 12.0, "away_score": 3.0},
        {"season": 2098, "game_type": "REG", "week": 1, "home_team": "MID", "away_team": "OFFB", "home_score": 14.0, "away_score": 20.0},
        {"season": 2098, "game_type": "REG", "week": 2, "home_team": "MID", "away_team": "OFFB", "home_score": 10.0, "away_score": 22.0},
        {"season": 2098, "game_type": "REG", "week": 1, "home_team": "WEAK", "away_team": "OFFC", "home_score": 7.0, "away_score": 35.0},
        {"season": 2098, "game_type": "REG", "week": 2, "home_team": "WEAK", "away_team": "OFFC", "home_score": 3.0, "away_score": 33.0},
        {"season": 2098, "game_type": "REG", "week": 1, "home_team": "THIN", "away_team": "OFFD", "home_score": 9.0, "away_score": 1.0},
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def round_robin_schedule(monkeypatch):
    games = _round_robin_games()
    monkeypatch.setattr(nfl_schedule, "load_games", lambda **_: games)
    return games


@pytest.fixture
def tier_schedule(monkeypatch):
    games = _tier_games()
    monkeypatch.setattr(nfl_schedule, "load_games", lambda **_: games)
    return games


# ---------------------------------------------------------------------------
# Defense strength by position
# ---------------------------------------------------------------------------


def test_defense_strength_ranks_tough_mid_weak_by_position(tier_schedule):
    weekly_stats = {
        "rb_offa": {"weekly": [{"week": 1, "fantasy_points_ppr": 5.0}, {"week": 2, "fantasy_points_ppr": 7.0}]},
        "rb_offb": {"weekly": [{"week": 1, "fantasy_points_ppr": 20.0}, {"week": 2, "fantasy_points_ppr": 22.0}]},
        "rb_offc": {"weekly": [{"week": 1, "fantasy_points_ppr": 35.0}, {"week": 2, "fantasy_points_ppr": 33.0}]},
        "rb_offd": {"weekly": [{"week": 1, "fantasy_points_ppr": 1.0}]},
    }
    players = {
        "rb_offa": {"position": "RB", "team": "OFFA"},
        "rb_offb": {"position": "RB", "team": "OFFB"},
        "rb_offc": {"position": "RB", "team": "OFFC"},
        "rb_offd": {"position": "RB", "team": "OFFD"},
    }

    result = pp.team_defense_points_allowed_by_position(
        2098, upto_week=2, weekly_stats=weekly_stats, players=players
    )

    tough = result["TOUGH"]["RB"]
    mid = result["MID"]["RB"]
    weak = result["WEAK"]["RB"]
    thin = result["THIN"]["RB"]

    # Recency-weighted average (half-life 3 weeks): week2 gets full weight,
    # week1 gets 0.5**(1/3).
    week1_weight = 0.5 ** (1 / pp.DEFENSE_HALF_LIFE_WEEKS)
    assert tough["weighted_points_allowed_per_game"] == pytest.approx(
        (5.0 * week1_weight + 7.0) / (week1_weight + 1.0), abs=0.01
    )
    assert tough["games_sampled"] == 2
    assert tough["low_sample"] is False

    assert tough["weighted_points_allowed_per_game"] < mid["weighted_points_allowed_per_game"] < weak["weighted_points_allowed_per_game"]
    assert tough["tier"] == "tough"
    assert mid["tier"] == "average"
    assert weak["tier"] == "weak"
    assert tough["rank"] == 1
    assert mid["rank"] == 2
    assert weak["rank"] == 3

    # A single-game sample is flagged and excluded from ranking entirely.
    assert thin["games_sampled"] == 1
    assert thin["low_sample"] is True
    assert "rank" not in thin
    assert "tier" not in thin


def test_defense_strength_omits_positions_with_no_sampled_weeks(tier_schedule):
    weekly_stats = {
        "rb_offa": {"weekly": [{"week": 1, "fantasy_points_ppr": 5.0}]},
    }
    players = {"rb_offa": {"position": "RB", "team": "OFFA"}}

    result = pp.team_defense_points_allowed_by_position(
        2098, upto_week=2, weekly_stats=weekly_stats, players=players
    )

    assert "QB" not in result.get("TOUGH", {})
    assert "WR" not in result.get("TOUGH", {})


def test_defense_strength_ignores_non_offensive_positions(tier_schedule):
    weekly_stats = {
        "lb_offa": {"weekly": [{"week": 1, "fantasy_points_ppr": 9.0}]},
    }
    players = {"lb_offa": {"position": "LB", "team": "OFFA"}}

    result = pp.team_defense_points_allowed_by_position(
        2098, upto_week=2, weekly_stats=weekly_stats, players=players
    )

    assert result == {}


def test_defense_strength_respects_upto_week_and_lookback_window():
    games = pd.DataFrame(
        [
            {"season": 2097, "game_type": "REG", "week": w, "home_team": "TOUGH", "away_team": "OFFA", "home_score": 10.0, "away_score": 3.0}
            for w in range(1, 4)
        ]
    )

    weekly_stats = {
        "rb_offa": {
            "weekly": [
                {"week": 1, "fantasy_points_ppr": 100.0},  # far outside window / after cutoff
                {"week": 2, "fantasy_points_ppr": 5.0},
                {"week": 3, "fantasy_points_ppr": 7.0},
            ]
        }
    }
    players = {"rb_offa": {"position": "RB", "team": "OFFA"}}

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(nfl_schedule, "load_games", lambda **_: games)
        # upto_week=3 with a 2-week lookback should drop week 1 entirely.
        result = pp.team_defense_points_allowed_by_position(
            2097,
            upto_week=3,
            weekly_stats=weekly_stats,
            players=players,
            max_weeks_back=2,
        )

    assert result["TOUGH"]["RB"]["games_sampled"] == 2
    assert result["TOUGH"]["RB"]["weighted_points_allowed_per_game"] < 50.0


# ---------------------------------------------------------------------------
# Projection formula
# ---------------------------------------------------------------------------


def _players_fixture():
    return {
        "qb_a1": {"position": "QB", "team": "AAA"},
        "rb_b1": {"position": "RB", "team": "BBB"},
        "wr_c1": {"position": "WR", "team": "CCC"},
        "te_d1": {"position": "TE", "team": "DDD"},
        "k_a1": {"position": "K", "team": "AAA"},
        "fa_1": {"position": "RB", "team": None},
    }


def _weekly_stats_fixture():
    return {
        "qb_a1": {"weekly": [
            {"week": 1, "fantasy_points_ppr": 20.0},
            {"week": 3, "fantasy_points_ppr": 22.0},
            {"week": 5, "fantasy_points_ppr": 24.0},
        ]},
        "rb_b1": {"weekly": [
            {"week": 1, "fantasy_points_ppr": 15.0},
            {"week": 4, "fantasy_points_ppr": 18.0},
            {"week": 6, "fantasy_points_ppr": 10.0},
        ]},
        "wr_c1": {"weekly": [
            {"week": 2, "fantasy_points_ppr": 12.0},
            {"week": 3, "fantasy_points_ppr": 14.0},
            {"week": 6, "fantasy_points_ppr": 20.0},
        ]},
        "te_d1": {"weekly": [
            {"week": 2, "fantasy_points_ppr": 8.0},
            {"week": 4, "fantasy_points_ppr": 9.0},
            {"week": 5, "fantasy_points_ppr": 11.0},
        ]},
    }


def test_project_player_week_ok_for_normal_sample_player(round_robin_schedule):
    players = _players_fixture()
    weekly_stats = _weekly_stats_fixture()

    result = pp.project_player_week(
        "qb_a1",
        week=5,
        season=2099,
        players=players,
        player_weekly_rows=weekly_stats["qb_a1"]["weekly"],
        defense_strength=pp.team_defense_points_allowed_by_position(
            2099, upto_week=4, weekly_stats=weekly_stats, players=players
        ),
    )

    assert result["status"] == "ok"
    assert result["opponent"] == "DDD"  # AAA plays DDD in week 5
    assert result["low"] <= result["point_estimate"] <= result["high"]
    assert result["confidence"] in {"low", "medium", "high"}
    assert result["basis"]["recent_games_played"] == 2  # weeks 1 and 3, strictly before week 5
    assert result["point_estimate"] > 0


def test_project_player_week_small_sample_gets_wider_band_and_low_confidence(round_robin_schedule):
    players = dict(_players_fixture())
    players["qb_a1_rookie"] = {"position": "QB", "team": "AAA"}
    weekly_stats = dict(_weekly_stats_fixture())
    # Only one game played all season (e.g. just called up / returned from injury).
    weekly_stats["qb_a1_rookie"] = {"weekly": [{"week": 3, "fantasy_points_ppr": 22.0}]}

    defense_strength = pp.team_defense_points_allowed_by_position(
        2099, upto_week=4, weekly_stats=weekly_stats, players=players
    )

    normal = pp.project_player_week(
        "qb_a1", week=5, season=2099, players=players,
        player_weekly_rows=weekly_stats["qb_a1"]["weekly"], defense_strength=defense_strength,
    )
    rookie = pp.project_player_week(
        "qb_a1_rookie", week=5, season=2099, players=players,
        player_weekly_rows=weekly_stats["qb_a1_rookie"]["weekly"], defense_strength=defense_strength,
    )

    assert rookie["status"] == "ok"
    assert rookie["confidence"] == "low"
    rookie_band = rookie["high"] - rookie["low"]
    normal_band = normal["high"] - normal["low"]
    assert rookie_band > normal_band


def test_project_player_week_bye_week_returns_no_projection(round_robin_schedule):
    players = _players_fixture()
    weekly_stats = _weekly_stats_fixture()

    # AAA has a synthesized bye in week 2 (no game recorded that week).
    result = pp.project_player_week(
        "qb_a1", week=2, season=2099, players=players,
        player_weekly_rows=weekly_stats["qb_a1"]["weekly"],
    )

    assert result["status"] == "bye_week"
    assert "point_estimate" not in result


def test_project_player_week_beyond_schedule_returns_no_schedule_data(round_robin_schedule):
    players = _players_fixture()
    weekly_stats = _weekly_stats_fixture()

    result = pp.project_player_week(
        "qb_a1", week=99, season=2099, players=players,
        player_weekly_rows=weekly_stats["qb_a1"]["weekly"],
    )

    assert result["status"] == "no_schedule_data"
    assert "point_estimate" not in result


def test_project_player_week_insufficient_player_data(round_robin_schedule):
    players = _players_fixture()

    result = pp.project_player_week(
        "qb_a1", week=5, season=2099, players=players,
        player_weekly_rows=[],  # no recorded weeks at all (true rookie)
    )

    assert result["status"] == "insufficient_player_data"
    assert "point_estimate" not in result


def test_project_player_week_unsupported_position(round_robin_schedule):
    players = dict(_players_fixture())
    players["lb_a1"] = {"position": "LB", "team": "AAA"}

    result = pp.project_player_week("lb_a1", week=5, season=2099, players=players)

    assert result["status"] == "unsupported_position"
    assert result["position"] == "LB"


def test_project_player_week_ok_for_kicker_with_neutral_opponent_multiplier(round_robin_schedule):
    """Kickers (K) get a real projection from their own recent-scoring
    trend, same as every other position — see coridian_'s report that Cam
    Little (K) showed no projection at all. Unlike QB/RB/WR/TE, a kicker
    never gets an opponent-defense multiplier (no meaningful
    points-allowed-to-kickers signal exists), so the multiplier is always
    exactly neutral (1.0) and confidence can reach "medium" but not "high".
    """

    players = dict(_players_fixture())
    weekly_stats = dict(_weekly_stats_fixture())
    weekly_stats["k_a1"] = {"weekly": [
        {"week": 1, "fantasy_points_ppr": 9.0},
        {"week": 3, "fantasy_points_ppr": 11.0},
    ]}

    # Defense-strength-by-position map built from the normal (non-K) offensive
    # fixture data — deliberately has no "K" entry for any team, matching
    # real production behavior (team_defense_points_allowed_by_position never
    # tracks K).
    defense_strength = pp.team_defense_points_allowed_by_position(
        2099, upto_week=4, weekly_stats=weekly_stats, players=players
    )
    assert "K" not in defense_strength.get("DDD", {})

    result = pp.project_player_week(
        "k_a1",
        week=5,
        season=2099,
        players=players,
        player_weekly_rows=weekly_stats["k_a1"]["weekly"],
        defense_strength=defense_strength,
    )

    assert result["status"] == "ok"
    assert result["position"] == "K"
    assert result["opponent"] == "DDD"  # AAA plays DDD in week 5
    assert result["point_estimate"] is not None
    assert result["point_estimate"] > 0
    assert result["low"] <= result["point_estimate"] <= result["high"]
    assert result["basis"]["opponent_multiplier"] == 1.0
    assert result["basis"]["opponent_defense_has_signal"] is False
    assert result["confidence"] in {"low", "medium"}


def test_project_player_week_kicker_insufficient_data_is_honest_not_zero(round_robin_schedule):
    players = _players_fixture()

    result = pp.project_player_week(
        "k_a1", week=5, season=2099, players=players, player_weekly_rows=[],
    )

    assert result["status"] == "insufficient_player_data"
    assert "point_estimate" not in result


def test_project_player_week_no_team_is_not_a_zero(round_robin_schedule):
    players = _players_fixture()

    result = pp.project_player_week("fa_1", week=5, season=2099, players=players)

    assert result["status"] == "no_team"
    assert "point_estimate" not in result


def test_project_player_week_unknown_player(round_robin_schedule):
    result = pp.project_player_week("does_not_exist", week=5, season=2099, players={})

    assert result["status"] == "unknown_player"


def test_opponent_multiplier_is_bounded():
    # A wildly weak defense relative to league average should still only
    # nudge the projection within the documented bounds, not blow it up.
    defense_strength = {
        "WEAK": {"RB": {"weighted_points_allowed_per_game": 100.0, "games_sampled": 5, "low_sample": False}},
        "AVG1": {"RB": {"weighted_points_allowed_per_game": 10.0, "games_sampled": 5, "low_sample": False}},
        "AVG2": {"RB": {"weighted_points_allowed_per_game": 10.0, "games_sampled": 5, "low_sample": False}},
    }

    multiplier, has_signal = pp._opponent_multiplier(defense_strength, "WEAK", "RB")

    assert has_signal is True
    low, high = pp._OPPONENT_MULTIPLIER_BOUNDS
    assert low <= multiplier <= high
    assert multiplier == pytest.approx(high)


def test_opponent_multiplier_neutral_when_no_signal():
    multiplier, has_signal = pp._opponent_multiplier({}, "GHOST", "RB")

    assert multiplier == 1.0
    assert has_signal is False
