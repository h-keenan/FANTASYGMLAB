"""Live matchup win-probability — pure logic, no network/IO.

Covers: a hand-calculable two-player case, final real points overriding
projections, the no-starters/insufficient-coverage honesty gates, a
fully-tied matchup landing at exactly 50%, and in-progress games (points so
far plus the remaining share of the projection) staying continuous across
pre-game, kickoff, mid-game and final.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from modules.matchup_win_probability import (
    GAME_WALL_CLOCK,
    compute_live_win_probability,
    game_fraction_remaining,
)

KICKOFF = datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc)


def _projected_starter(
    point_estimate: float,
    low: float,
    high: float,
    *,
    started: bool = False,
    actual: float | None = None,
    final: bool | None = None,
    kickoff_at: str | None = None,
):
    return {
        "actual_points": actual,
        "game_started": started,
        "game_final": final,
        "game_kickoff_at": kickoff_at,
        "projection": {"status": "ok", "point_estimate": point_estimate, "low": low, "high": high},
    }


def _live(actual: float, *, kickoff: datetime = KICKOFF, started: bool = True):
    """15 +/- 7 projection; game kicked off at `kickoff`."""
    return _projected_starter(15.0, 8.0, 22.0, started=started, actual=actual, kickoff_at=kickoff.isoformat())


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


def test_real_points_override_projection_once_game_is_final():
    # Game final: real 30 points used (fixed, zero variance), the
    # pre-game projection (point_estimate 10) is ignored entirely.
    my_starters = [_projected_starter(10.0, 5.0, 15.0, started=True, actual=30.0, final=True)]
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
    my_starters = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=24.0, final=True)]
    opponent_starters = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=18.0, final=True)]

    result = compute_live_win_probability(my_starters, opponent_starters)

    assert result["available"] is True
    assert result["probability"] == 1.0


# --- in-progress games ---------------------------------------------------


def test_fraction_remaining_across_game_phases():
    pre = _live(0.0, started=False)
    assert game_fraction_remaining(pre, now=KICKOFF - timedelta(minutes=5)) == 1.0
    live = _live(3.0)
    assert game_fraction_remaining(live, now=KICKOFF) == 1.0
    assert math.isclose(game_fraction_remaining(live, now=KICKOFF + GAME_WALL_CLOCK / 2), 0.5)
    assert game_fraction_remaining(live, now=KICKOFF + GAME_WALL_CLOCK * 2) == 0.0
    final = {**live, "game_final": True}
    assert game_fraction_remaining(final, now=KICKOFF + timedelta(minutes=30)) == 0.0
    # Started but nothing to place it on the clock with.
    assert game_fraction_remaining({"game_started": True}, now=KICKOFF) is None


def test_identical_lineups_stay_near_even_just_after_kickoff():
    # The backtest repro: my 9 starters kicked off 5 minutes ago with 0.4
    # points each; the opponent's identical 9 haven't kicked off. The old
    # model froze my partial 3.6 points as final and read 0.0.
    now = KICKOFF + timedelta(minutes=5)
    mine = [_live(0.4) for _ in range(9)]
    opponent = [_live(0.0, kickoff=KICKOFF + timedelta(hours=7), started=False) for _ in range(9)]

    after = compute_live_win_probability(mine, opponent, now=now)
    mine_pre = [_live(0.0, started=False) for _ in range(9)]
    before = compute_live_win_probability(mine_pre, opponent, now=KICKOFF - timedelta(minutes=5))

    assert before["probability"] == 0.5
    assert 0.45 < after["probability"] < 0.55
    assert abs(after["probability"] - before["probability"]) < 0.05
    assert after["my_projected_total"] > 130.0


def test_no_jump_at_kickoff():
    opponent = [_projected_starter(14.0, 7.0, 21.0)]
    pre = compute_live_win_probability(
        [_live(0.0, started=False)], opponent, now=KICKOFF - timedelta(seconds=1)
    )
    at_kickoff = compute_live_win_probability([_live(0.0)], opponent, now=KICKOFF)
    one_minute = compute_live_win_probability([_live(0.0)], opponent, now=KICKOFF + timedelta(minutes=1))
    assert pre["probability"] == at_kickoff["probability"]
    assert abs(one_minute["probability"] - pre["probability"]) < 0.01


def test_mid_game_is_points_so_far_plus_remaining_projection_with_shrunk_variance():
    # Halfway through: mean = 10 + 0.5 * 15 = 17.5, variance = 0.5 * 7^2.
    # Opponent: a final 17.5, no variance. diff = 0, so exactly 50%.
    now = KICKOFF + GAME_WALL_CLOCK / 2
    mine = [_live(10.0)]
    opponent = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=17.5, final=True)]
    result = compute_live_win_probability(mine, opponent, now=now)
    assert result["my_projected_total"] == 17.5
    assert result["probability"] == 0.5

    # Same game state vs a final 20: P = Phi((17.5 - 20) / sqrt(0.5 * 49)).
    opponent = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=20.0, final=True)]
    result = compute_live_win_probability(mine, opponent, now=now)
    expected = 0.5 * (1.0 + math.erf(((17.5 - 20.0) / math.sqrt(0.5 * 49.0)) / math.sqrt(2.0)))
    assert result["probability"] == round(expected, 4)


def test_probability_firms_up_continuously_as_the_game_runs_out():
    # Up 5 real points with my game in progress, opponent final: the edge
    # gets more certain as the remaining variance shrinks, ending at 1.0.
    opponent = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=20.0, final=True)]
    probabilities = []
    for minutes in (0, 30, 60, 90, 120, 150, 180, 190):
        mine = [_projected_starter(0.0, -7.0, 7.0, started=True, actual=25.0, kickoff_at=KICKOFF.isoformat())]
        probabilities.append(
            compute_live_win_probability(mine, opponent, now=KICKOFF + timedelta(minutes=minutes))["probability"]
        )
    assert probabilities == sorted(probabilities)
    assert probabilities[0] < 0.8
    assert probabilities[-1] == 1.0
    steps = [b - a for a, b in zip(probabilities, probabilities[1:])]
    assert max(steps[:-1]) < 0.15


def test_final_game_ignores_wall_clock_and_uses_real_points():
    # nflverse already has a final score 2 hours in (a quick game): fixed.
    mine = [_projected_starter(15.0, 8.0, 22.0, started=True, actual=21.0, final=True, kickoff_at=KICKOFF.isoformat())]
    opponent = [_projected_starter(0.0, 0.0, 0.0, started=True, actual=20.0, final=True)]
    result = compute_live_win_probability(mine, opponent, now=KICKOFF + timedelta(hours=2))
    assert result["my_projected_total"] == 21.0
    assert result["probability"] == 1.0


def test_in_progress_starter_without_projection_counts_real_points_only():
    # Team DEF mid-game: no projection for the rest, real points so far only.
    defense = {
        "actual_points": 6.0,
        "game_started": True,
        "game_final": False,
        "game_kickoff_at": KICKOFF.isoformat(),
        "projection": {"status": "unsupported_position"},
    }
    mine = [_live(10.0), defense]
    opponent = [_projected_starter(15.0, 8.0, 22.0), _projected_starter(5.0, 0.0, 10.0)]
    result = compute_live_win_probability(mine, opponent, now=KICKOFF + GAME_WALL_CLOCK / 2)
    assert result["available"] is True
    assert result["my_projected_total"] == round(10.0 + 7.5 + 6.0, 1)
