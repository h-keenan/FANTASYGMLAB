"""Live matchup win-probability — pure logic, no network/IO.

Covers: a hand-calculable two-player case, real (already-started) points
overriding projections, the no-starters/insufficient-coverage honesty
gates, and a fully-tied matchup landing at exactly 50%.
"""

from __future__ import annotations

import math

from modules.matchup_win_probability import compute_live_win_probability


def _projected_starter(point_estimate: float, low: float, high: float, *, started: bool = False, actual: float | None = None):
    return {
        "actual_points": actual,
        "game_started": started,
        "projection": {"status": "ok", "point_estimate": point_estimate, "low": low, "high": high},
    }


def _unmodeled_starter():
    return {"actual_points": None, "game_started": False, "projection": {"status": "unsupported_position"}}


def test_hand_calculable_two_starter_case():
    # My side: one starter, mean 20, stdev 5 (low=15, high=25).
    # Opponent: one starter, mean 15, stdev 5 (low=10, high=20).
    # diff_mean = 5, diff_stdev = sqrt(25 + 25) = sqrt(50).
    my_starters = [_projected_starter(20.0, 15.0, 25.0)]
    opponent_starters = [_projected_starter(15.0, 10.0, 20.0)]

    result = compute_live_win_probability(my_starters, opponent_starters)

    assert result["available"] is True
    expected = 0.5 * (1.0 + math.erf((5.0 / math.sqrt(50.0)) / math.sqrt(2.0)))
    assert result["probability"] == round(expected, 4)
    assert result["my_projected_total"] == 20.0
    assert result["opponent_projected_total"] == 15.0


def test_real_points_override_projection_once_game_has_started():
    # Game started: real 30 points used (fixed, zero variance), the
    # pre-game projection (point_estimate 10) is ignored entirely.
    my_starters = [_projected_starter(10.0, 5.0, 15.0, started=True, actual=30.0)]
    opponent_starters = [_projected_starter(10.0, 5.0, 15.0)]

    result = compute_live_win_probability(my_starters, opponent_starters)

    assert result["available"] is True
    assert result["my_projected_total"] == 30.0
    # My side is now a fixed 30 (zero variance) vs. opponent's Normal(10, 2.5^2)
    # — any positive gap with finite opponent variance clears >50%.
    assert result["probability"] > 0.5


def test_exactly_tied_distributions_land_at_fifty_percent():
    my_starters = [_projected_starter(20.0, 15.0, 25.0)]
    opponent_starters = [_projected_starter(20.0, 15.0, 25.0)]

    result = compute_live_win_probability(my_starters, opponent_starters)

    assert result["available"] is True
    assert result["probability"] == 0.5


def test_no_starters_is_honestly_unavailable():
    assert compute_live_win_probability([], [])["available"] is False
    assert compute_live_win_probability([], [])["reason"] == "no_starters"


def test_insufficient_modeled_coverage_is_honestly_unavailable():
    # Every starter on my side is unmodeled (e.g. all DEF/IDP or no-data
    # skill players) — coverage is 0%, well under the 60% floor.
    my_starters = [_unmodeled_starter(), _unmodeled_starter()]
    opponent_starters = [_projected_starter(20.0, 15.0, 25.0)]

    result = compute_live_win_probability(my_starters, opponent_starters)

    assert result["available"] is False
    assert result["reason"] == "insufficient_coverage"
    assert result["coverage"]["my"] == 0.0
    assert result["coverage"]["opponent"] == 1.0


def test_zero_variance_both_sides_is_fully_deterministic():
    # Both sides fully resolved by real points (game over) — no variance
    # left at all, so the outcome is exact, not approximate.
    my_starters = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=24.0)]
    opponent_starters = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=18.0)]

    result = compute_live_win_probability(my_starters, opponent_starters)

    assert result["available"] is True
    assert result["probability"] == 1.0
