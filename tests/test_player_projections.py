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


def _extended_two_team_games(weeks: int = 10) -> pd.DataFrame:
    """AAA vs BBB, every week from 1 through ``weeks`` with no bye — long
    enough to project several weeks past a player's last real game (see
    the "far out" trend-invariance regression test below)."""

    rows = []
    for week in range(1, weeks + 1):
        if week % 2 == 1:
            rows.append({"season": 2099, "game_type": "REG", "week": week, "home_team": "AAA", "away_team": "BBB", "home_score": 20.0, "away_score": 17.0})
        else:
            rows.append({"season": 2099, "game_type": "REG", "week": week, "home_team": "BBB", "away_team": "AAA", "home_score": 17.0, "away_score": 20.0})
    return pd.DataFrame(rows)


@pytest.fixture
def extended_schedule(monkeypatch):
    games = _extended_two_team_games()
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


def test_project_player_week_trend_is_invariant_to_target_week_distance(extended_schedule):
    """Regression for the Juwan-Johnson-style bug: a player's recency-
    weighted trend must be identical whether he's being projected for next
    week or several weeks further out, as long as no new games have been
    played in between. Before the fix, the lookback window was anchored on
    ``week - 1`` (the TARGET week), not the real as-of week — so a player
    whose last real game was week 3 got his full 3-game trend when
    projected for week 4, but only his single best game (week 3) when
    projected for week 9 (weeks 1-2 aged out of the window purely because
    a later target week was being projected, not because any real time
    passed), and lost the trend entirely (``insufficient_player_data``) for
    weeks far enough out that even week 3 aged out.
    """

    players = {"wr_a1": {"position": "WR", "team": "AAA"}}
    weekly_rows = [
        {"week": 1, "fantasy_points_ppr": 14.4},
        {"week": 2, "fantasy_points_ppr": 10.6},
        {"week": 3, "fantasy_points_ppr": 23.3},
    ]

    near = pp.project_player_week(
        "wr_a1", week=4, season=2099, players=players,
        player_weekly_rows=weekly_rows, defense_strength={},
        team_qb_quality={}, weekly_stats={},
    )
    far = pp.project_player_week(
        "wr_a1", week=9, season=2099, players=players,
        player_weekly_rows=weekly_rows, defense_strength={},
        team_qb_quality={}, weekly_stats={},
    )
    way_far = pp.project_player_week(
        "wr_a1", week=10, season=2099, players=players,
        player_weekly_rows=weekly_rows, defense_strength={},
        team_qb_quality={}, weekly_stats={},
    )

    for result in (near, far, way_far):
        assert result["status"] == "ok"
        assert result["basis"]["recent_weeks_used"] == [1, 2, 3]
        assert result["basis"]["recent_games_played"] == 3

    assert near["basis"]["recent_weighted_avg_ppr"] == pytest.approx(far["basis"]["recent_weighted_avg_ppr"])
    assert near["basis"]["recent_weighted_avg_ppr"] == pytest.approx(way_far["basis"]["recent_weighted_avg_ppr"])
    # No defense signal was injected (neutral 1.0 multiplier throughout),
    # so the point estimates themselves must match too.
    assert near["point_estimate"] == pytest.approx(far["point_estimate"])
    assert near["point_estimate"] == pytest.approx(way_far["point_estimate"])


def test_project_player_week_recent_trend_still_drops_old_games_for_actively_playing_player(extended_schedule):
    """Guards against overcorrecting the fix above into "every game ever
    counts forever": a player who HAS played recently must still get a
    trend built from his actual recent games — weeks far enough before his
    real last-played week must still fall out of the ``PLAYER_MAX_WEEKS_BACK``
    lookback window, exactly as before the fix.
    """

    players = {"wr_a1": {"position": "WR", "team": "AAA"}}
    weekly_rows = [
        {"week": 1, "fantasy_points_ppr": 1.0},
        {"week": 2, "fantasy_points_ppr": 2.0},
        {"week": 3, "fantasy_points_ppr": 9.0},
        {"week": 4, "fantasy_points_ppr": 10.0},
        {"week": 5, "fantasy_points_ppr": 11.0},
        {"week": 6, "fantasy_points_ppr": 12.0},
        {"week": 7, "fantasy_points_ppr": 13.0},
        {"week": 8, "fantasy_points_ppr": 14.0},
    ]

    result = pp.project_player_week(
        "wr_a1", week=9, season=2099, players=players,
        player_weekly_rows=weekly_rows, defense_strength={},
        team_qb_quality={}, weekly_stats={},
    )

    assert result["status"] == "ok"
    # Real as-of week is 8 (his last played week). With a 6-week lookback,
    # weeks 1 and 2 (7 and 6 weeks before week 8) must still be excluded.
    assert result["basis"]["recent_weeks_used"] == [3, 4, 5, 6, 7, 8]
    assert result["basis"]["recent_games_played"] == 6


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


# ---------------------------------------------------------------------------
# Team starting-QB-quality signal (WR/TE only)
# ---------------------------------------------------------------------------


def _team_qb_quality_entry(quality: float, *, player_id: str = "qb") -> dict:
    return {
        "quality": quality,
        "qb_count": 1,
        "selected_player_id": player_id,
        "selection_method": "depth_chart",
        "pass_att_pg": 30.0,
        "quality_detail": "QB pass_att/g=30.0",
    }


def test_team_qb_quality_multiplier_is_bounded_above():
    team_qb_quality = {
        "ELITE": _team_qb_quality_entry(0.95),
        "AVG1": _team_qb_quality_entry(0.5),
        "AVG2": _team_qb_quality_entry(0.5),
    }

    multiplier, has_signal = pp._team_qb_quality_multiplier(team_qb_quality, "ELITE")

    assert has_signal is True
    low, high = pp._TEAM_QB_QUALITY_MULTIPLIER_BOUNDS
    assert low <= multiplier <= high
    assert multiplier == pytest.approx(high)


def test_team_qb_quality_multiplier_is_bounded_below():
    team_qb_quality = {
        "WEAK": _team_qb_quality_entry(0.05),
        "AVG1": _team_qb_quality_entry(0.5),
        "AVG2": _team_qb_quality_entry(0.5),
    }

    multiplier, has_signal = pp._team_qb_quality_multiplier(team_qb_quality, "WEAK")

    assert has_signal is True
    low, high = pp._TEAM_QB_QUALITY_MULTIPLIER_BOUNDS
    assert low <= multiplier <= high
    assert multiplier == pytest.approx(low)


def test_team_qb_quality_multiplier_neutral_when_no_signal():
    multiplier, has_signal = pp._team_qb_quality_multiplier({}, "GHOST")

    assert multiplier == 1.0
    assert has_signal is False


def test_team_qb_quality_multiplier_neutral_with_single_team_sample():
    # A single team's quality score can't be compared to a "league
    # average" of just itself — that would always normalize to a false 1.0
    # ratio, so this must stay neutral/no-signal instead.
    team_qb_quality = {"LONE": _team_qb_quality_entry(0.9)}

    multiplier, has_signal = pp._team_qb_quality_multiplier(team_qb_quality, "LONE")

    assert multiplier == 1.0
    assert has_signal is False


def test_project_player_week_wr_projection_moves_both_directions_with_team_qb_quality(round_robin_schedule):
    players = _players_fixture()
    weekly_stats = _weekly_stats_fixture()
    defense_strength = pp.team_defense_points_allowed_by_position(
        2099, upto_week=5, weekly_stats=weekly_stats, players=players
    )

    neutral_quality = {
        "CCC": _team_qb_quality_entry(0.5, player_id="qb_c1"),
        "ZZZ": _team_qb_quality_entry(0.5, player_id="qb_z1"),
    }
    better_quality = {
        "CCC": _team_qb_quality_entry(0.9, player_id="qb_c1"),
        "ZZZ": _team_qb_quality_entry(0.5, player_id="qb_z1"),
    }
    worse_quality = {
        "CCC": _team_qb_quality_entry(0.2, player_id="qb_c1"),
        "ZZZ": _team_qb_quality_entry(0.5, player_id="qb_z1"),
    }

    def _project(team_qb_quality):
        return pp.project_player_week(
            "wr_c1",
            week=6,
            season=2099,
            players=players,
            player_weekly_rows=weekly_stats["wr_c1"]["weekly"],
            defense_strength=defense_strength,
            team_qb_quality=team_qb_quality,
            weekly_stats={},
        )

    neutral = _project(neutral_quality)
    better = _project(better_quality)
    worse = _project(worse_quality)

    assert neutral["status"] == "ok"
    assert neutral["basis"]["team_qb_quality_multiplier"] == pytest.approx(1.0)
    assert neutral["basis"]["team_qb_quality_has_signal"] is True

    low, high = pp._TEAM_QB_QUALITY_MULTIPLIER_BOUNDS
    assert better["basis"]["team_qb_quality_multiplier"] == pytest.approx(high)
    assert worse["basis"]["team_qb_quality_multiplier"] == pytest.approx(low)
    assert low <= better["basis"]["team_qb_quality_multiplier"] <= high
    assert low <= worse["basis"]["team_qb_quality_multiplier"] <= high

    # Both directions of the audit's ask: a better team QB situation must
    # raise the point estimate above neutral, a worse one must lower it.
    assert better["point_estimate"] > neutral["point_estimate"] > worse["point_estimate"]
    assert better["basis"]["team_starting_qb_player_id"] == "qb_c1"


def test_project_player_week_qb_and_rb_unaffected_by_team_qb_quality_signal(round_robin_schedule):
    """QB/RB projections must be completely untouched by this new signal —
    even when a deliberately extreme team_qb_quality map is injected (one
    that would swing a WR/TE projection to the bound), the QB/RB point
    estimate and basis must be identical to the no-signal-at-all case."""

    players = _players_fixture()
    weekly_stats = _weekly_stats_fixture()
    defense_strength = pp.team_defense_points_allowed_by_position(
        2099, upto_week=4, weekly_stats=weekly_stats, players=players
    )
    extreme_team_qb_quality = {
        "AAA": _team_qb_quality_entry(1.0, player_id="qb_a1"),
        "BBB": _team_qb_quality_entry(0.01, player_id="qb_b1"),
    }

    # AAA (qb_a1) plays in week 5; BBB (rb_b1) has a bye in week 5 (see
    # round_robin_schedule's docstring), so each player is projected for a
    # week its own team actually plays.
    for player_id, week in (("qb_a1", 5), ("rb_b1", 4)):
        with_signal = pp.project_player_week(
            player_id,
            week=week,
            season=2099,
            players=players,
            player_weekly_rows=weekly_stats[player_id]["weekly"],
            defense_strength=defense_strength,
            team_qb_quality=extreme_team_qb_quality,
            weekly_stats=weekly_stats,
        )
        without_signal = pp.project_player_week(
            player_id,
            week=week,
            season=2099,
            players=players,
            player_weekly_rows=weekly_stats[player_id]["weekly"],
            defense_strength=defense_strength,
        )

        assert with_signal["point_estimate"] == pytest.approx(without_signal["point_estimate"])
        assert with_signal["basis"]["team_qb_quality_multiplier"] == 1.0
        assert with_signal["basis"]["team_qb_quality_has_signal"] is False
        assert with_signal["basis"]["team_qb_quality_score"] is None
        assert with_signal["basis"] == without_signal["basis"]


def test_project_player_week_floors_negative_real_trend_but_preserves_it_in_basis(extended_schedule):
    """Regression for the Chimere Dike bug report: a near-zero-usage
    player's real weekly PPR rows can genuinely be negative (a catch
    behind the line of scrimmage, a lost fumble is a real, bounded-floor-
    stat-exception game, not a data error), so the recency-weighted trend
    feeding the projection can legitimately compute to a negative number.
    That negative *trend* is honest and must stay visible in
    ``basis.recent_weighted_avg_ppr`` — but the *displayed* projection
    (``point_estimate``/``low``/``high``) must never show a misleadingly
    precise negative number like "-0.7": every mainstream fantasy platform
    floors a forward-looking projection at 0, since "less than zero points
    expected" isn't a meaningfully different forecast from "approximately
    zero points expected."
    """

    players = {"wr_a1": {"position": "WR", "team": "AAA"}}
    # Real shape of the bug report: 2 usable games, both genuinely negative
    # PPR (a negative-yardage catch each week) out of a 3-game season.
    weekly_rows = [
        {"week": 1, "fantasy_points_ppr": -0.3, "games_played": 1},
        {"week": 3, "fantasy_points_ppr": -0.7, "games_played": 1},
    ]

    result = pp.project_player_week(
        "wr_a1", week=6, season=2099, players=players,
        player_weekly_rows=weekly_rows, defense_strength={},
        team_qb_quality={}, weekly_stats={},
    )

    assert result["status"] == "ok"
    # The real recency-weighted trend is negative — honestly preserved.
    assert result["basis"]["recent_weighted_avg_ppr"] < 0.0
    assert result["basis"]["point_estimate_floored"] is True
    # But nothing shown to a user is ever negative.
    assert result["point_estimate"] == 0.0
    assert result["low"] == 0.0
    assert result["high"] >= 0.0


def test_project_player_week_floored_estimate_repeats_across_weeks_for_sidelined_player(extended_schedule):
    """A near-identical small (floored-to-zero) estimate repeating across
    several consecutive future weeks for a player who hasn't played a new
    game is NOT a recurrence of the PR #868 recency-window-anchoring bug —
    it's the correctly-fixed behavior working as intended. Per
    ``_most_recent_played_week``'s "as-of" anchoring, the lookback window
    stays anchored on his real last game for every future week projected
    (no new games played => no new information => same baseline trend),
    so weeks far apart must agree on the underlying (pre-floor) trend.
    """

    players = {"wr_a1": {"position": "WR", "team": "AAA"}}
    weekly_rows = [
        {"week": 1, "fantasy_points_ppr": -0.3, "games_played": 1},
        {"week": 3, "fantasy_points_ppr": -0.7, "games_played": 1},
    ]

    results = [
        pp.project_player_week(
            "wr_a1", week=week, season=2099, players=players,
            player_weekly_rows=weekly_rows, defense_strength={},
            team_qb_quality={}, weekly_stats={},
        )
        for week in (4, 6, 8, 10)
    ]

    for result in results:
        assert result["status"] == "ok"
        assert result["point_estimate"] == 0.0

    # Same underlying trend every time — no defense signal injected, so the
    # (pre-floor) weighted average must be identical across every future
    # week, exactly like the existing trend-invariance regression test
    # above for a positive-production player.
    first = results[0]["basis"]["recent_weighted_avg_ppr"]
    for result in results[1:]:
        assert result["basis"]["recent_weighted_avg_ppr"] == pytest.approx(first)
