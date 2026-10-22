"""Projections v2: usage-based empirical-Bayes baseline, availability, ranges.

Backtest evidence for every constant lives in docs/projections-v2-backtest.md.
"""

import pytest

from modules import player_projections as pp
from tests.test_player_projections import extended_schedule  # noqa: F401  (fixture)


def _rows(points, targets=None, start=1):
    return [
        {"week": start + i, "games_played": 1, "fantasy_points_ppr": p, "targets": (targets or [8] * len(points))[i]}
        for i, p in enumerate(points)
    ]


def test_usage_trend_shrinks_single_hot_game_toward_volume():
    # Same volume (8 targets) every week; one blow-up game on top of it.
    steady = pp._player_usage_trend(_rows([12, 12, 12, 12, 12]), position="WR", upto_week=5)
    spike = pp._player_usage_trend(_rows([12, 12, 12, 12, 40]), position="WR", upto_week=5)
    # The 28-point outlier moves the baseline by far less than 28 / n.
    assert spike["baseline_ppr"] - steady["baseline_ppr"] < 28 / 5
    assert spike["baseline_ppr"] > steady["baseline_ppr"]


def test_usage_trend_one_game_is_pulled_to_volume_implied_points():
    one = pp._player_usage_trend(_rows([30.0]), position="WR", upto_week=1)
    # 8 targets implies ~14 PPR for a WR; one 30-point game only keeps k-share of the surplus.
    assert one["usage_implied_ppr"] < one["baseline_ppr"] < 30.0
    assert one["efficiency_weight"] == pytest.approx(1 / (1 + pp._V2_SHRINKAGE["WR"][2]))


def test_usage_trend_ignores_games_after_as_of_week():
    rows = _rows([10, 10, 10, 10, 10, 99])
    capped = pp._player_usage_trend(rows, position="WR", upto_week=5)
    assert capped["games_played"] == 5
    assert capped["baseline_ppr"] == pp._player_usage_trend(rows[:5], position="WR", upto_week=5)["baseline_ppr"]


def test_range_is_ordered_around_the_estimate():
    for confidence in ("high", "medium", "low"):
        low, high = pp._v2_range(10.0, "WR", confidence)
        assert low <= 10.0 <= high


@pytest.mark.parametrize(
    "status,injury,ahead,mult",
    [
        ("Active", "", 0, 1.0),
        ("Active", "Out", 0, 0.0),
        ("Inactive", "IR", 0, 0.0),
        ("Inactive", "IR", 3, 0.0),
        ("Inactive", "IR", 4, 1.0),
        ("Active", "Sus", 0, 0.0),
        ("Active", "Doubtful", 0, pp._V2_DOUBTFUL_MULTIPLIER),
        ("Active", "Questionable", 0, pp._V2_QUESTIONABLE_MULTIPLIER),
        ("Active", "Questionable", 2, 1.0),
        ("Active", "NA", 0, 1.0),
    ],
)
def test_availability_multiplier(status, injury, ahead, mult):
    out = pp._availability_adjustment({"status": status, "injury_status": injury}, ahead)
    assert out["multiplier"] == mult
    assert out["applied"] is (mult != 1.0)


def test_project_player_week_ruled_out_player_projects_zero(extended_schedule):  # noqa: F811
    players = {"wr_a1": {"position": "WR", "team": "AAA", "status": "Inactive", "injury_status": "IR"}}
    result = pp.project_player_week(
        "wr_a1", week=5, season=2099, players=players,
        player_weekly_rows=_rows([12, 14, 11]), defense_strength={}, team_qb_quality={}, weekly_stats={},
    )
    assert result["status"] == "ok"
    assert result["point_estimate"] == 0.0 and result["high"] == 0.0
    assert result["basis"]["availability"]["reason"] == "reserve_list"
    assert result["basis"]["model_version"] == pp.PROJECTION_MODEL_VERSION


def test_project_player_week_reports_opponent_signal_as_context_only(extended_schedule):  # noqa: F811
    players = {"wr_a1": {"position": "WR", "team": "AAA"}}
    result = pp.project_player_week(
        "wr_a1", week=5, season=2099, players=players,
        player_weekly_rows=_rows([12, 14, 11]), defense_strength={}, team_qb_quality={}, weekly_stats={},
    )
    assert result["basis"]["opponent_multiplier_applied"] is False
    assert result["low"] <= result["point_estimate"] <= result["high"]
