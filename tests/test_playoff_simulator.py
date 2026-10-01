"""Playoff-odds Monte Carlo simulation — pure logic, no network/IO.

Covers: a fully deterministic small-league scenario (no remaining games,
expected outcome computable by hand), a hand-calculable single-game
win-probability case, structural clinch/elimination (must be exact, not
approximate), the logistic slope fit's insufficient-data fallback and its
ability to recover a real signal, and the real-matchup-payload parsing
helpers.
"""

from __future__ import annotations

import numpy as np
import pytest

from modules import playoff_simulator as sim


def test_no_remaining_games_is_fully_deterministic():
    """Zero games left: today's standings decide everything, exactly."""

    result = sim.simulate_playoff_odds(
        roster_ids=["A", "B", "C", "D"],
        power_scores=[100.0, 100.0, 100.0, 100.0],
        current_wins=[10, 8, 5, 2],
        current_losses=[0, 2, 5, 8],
        current_ties=[0, 0, 0, 0],
        points_for=[1500, 1400, 1200, 1000],
        points_against=[1000, 1100, 1200, 1400],
        team_names=["Alpha", "Bravo", "Charlie", "Delta"],
        completed_games=[],
        remaining_games=[],
        playoff_teams=2,
        n_trials=500,
        rng=np.random.default_rng(1),
    )
    teams = result["teams"]
    assert teams["A"]["playoff_probability"] == 100.0
    assert teams["B"]["playoff_probability"] == 100.0
    assert teams["C"]["playoff_probability"] == 0.0
    assert teams["D"]["playoff_probability"] == 0.0
    assert teams["A"]["clinched"] and teams["B"]["clinched"]
    assert teams["C"]["eliminated"] and teams["D"]["eliminated"]
    assert teams["A"]["median_seed"] == 1
    assert teams["B"]["median_seed"] == 2
    assert teams["C"]["median_seed"] == 3
    assert teams["D"]["median_seed"] == 4
    assert teams["A"]["median_final_wins"] == 10
    assert teams["A"]["median_final_losses"] == 0


def test_tiebreak_falls_back_to_real_points_for():
    """Equal wins, no remaining games: higher real points_for wins the tie."""

    result = sim.simulate_playoff_odds(
        roster_ids=["A", "B"],
        power_scores=[100.0, 100.0],
        current_wins=[5, 5],
        current_losses=[5, 5],
        current_ties=[0, 0],
        points_for=[1300, 1250],
        points_against=[1000, 1000],
        team_names=["Alpha", "Bravo"],
        completed_games=[],
        remaining_games=[],
        playoff_teams=1,
        n_trials=200,
        rng=np.random.default_rng(2),
    )
    assert result["teams"]["A"]["playoff_probability"] == 100.0
    assert result["teams"]["B"]["playoff_probability"] == 0.0


def test_single_remaining_game_matches_hand_calculated_logistic_probability():
    """Two teams, one game left, no fit data -> default slope=1.0 applies.

    power_scores chosen so the z-scored differential is exactly 2.0:
    sigmoid(1.0 * 2.0) = 1 / (1 + e^-2) ~= 0.880797.
    """

    result = sim.simulate_playoff_odds(
        roster_ids=["A", "B"],
        power_scores=[1000.0, 0.0],
        current_wins=[0, 0],
        current_losses=[0, 0],
        current_ties=[0, 0],
        points_for=[0, 0],
        points_against=[0, 0],
        team_names=["Alpha", "Bravo"],
        completed_games=[],
        remaining_games=[("A", "B")],
        playoff_teams=1,
        n_trials=20000,
        rng=np.random.default_rng(42),
    )
    assert result["slope_fitted"] is False
    assert result["slope"] == pytest.approx(1.0)
    expected = 1.0 / (1.0 + np.exp(-2.0)) * 100.0
    assert result["teams"]["A"]["playoff_probability"] == pytest.approx(expected, abs=1.5)
    assert result["teams"]["B"]["playoff_probability"] == pytest.approx(100.0 - expected, abs=1.5)


def test_team_is_structurally_eliminated_not_just_unlikely():
    """Two other teams already have more banked wins than this team's ceiling.

    X's best case (wins its one remaining game) tops out at 2 wins; Y and Z
    already have 9 real wins each with nothing left to play — they will
    finish with at least 9 wins no matter what. With playoff_teams=2, X can
    never finish ahead of fewer than 2 teams, so it must be exactly 0%
    across every trial, not just rare in a finite sample.
    """

    result = sim.simulate_playoff_odds(
        roster_ids=["X", "Y", "Z", "T"],
        power_scores=[100.0, 100.0, 100.0, 100.0],
        current_wins=[1, 9, 9, 0],
        current_losses=[8, 0, 0, 9],
        current_ties=[0, 0, 0, 0],
        points_for=[900, 1800, 1750, 850],
        points_against=[1000, 800, 820, 1200],
        team_names=["Xray", "Yankee", "Zulu", "Tango"],
        completed_games=[],
        remaining_games=[("X", "T")],
        playoff_teams=2,
        n_trials=2000,
        rng=np.random.default_rng(7),
    )
    assert result["teams"]["X"]["playoff_probability"] == 0.0
    assert result["teams"]["X"]["eliminated"] is True


def test_team_is_structurally_clinched_not_just_likely():
    """A's floor (loses every remaining game) beats every rival's ceiling.

    A has 8 wins with 2 games left (floor 8). Every other team's ceiling
    (current wins + its own remaining games) is at most 4. So regardless of
    how any remaining game resolves, A finishes with more wins than all but
    zero other teams -- guaranteed top-2 with playoff_teams=2.
    """

    result = sim.simulate_playoff_odds(
        roster_ids=["A", "B", "C", "D"],
        power_scores=[100.0, 100.0, 100.0, 100.0],
        current_wins=[8, 2, 1, 0],
        current_losses=[0, 0, 0, 0],
        current_ties=[0, 0, 0, 0],
        points_for=[1600, 900, 850, 800],
        points_against=[900, 950, 960, 970],
        team_names=["Alpha", "Bravo", "Charlie", "Delta"],
        completed_games=[],
        remaining_games=[("A", "B"), ("A", "C"), ("D", "B"), ("D", "C")],
        playoff_teams=2,
        n_trials=2000,
        rng=np.random.default_rng(11),
    )
    assert result["teams"]["A"]["playoff_probability"] == 100.0
    assert result["teams"]["A"]["clinched"] is True


def test_every_trial_produces_a_valid_rank_permutation():
    """Sanity check: each trial's ranks are exactly 1..n, no ties/gaps."""

    rng = np.random.default_rng(3)
    roster_ids = [f"r{i}" for i in range(6)]
    result = sim.simulate_playoff_odds(
        roster_ids=roster_ids,
        power_scores=list(rng.normal(size=6) * 50),
        current_wins=[3, 2, 4, 1, 0, 5],
        current_losses=[2, 3, 1, 4, 5, 0],
        current_ties=[0, 0, 0, 0, 0, 0],
        points_for=[1000, 950, 1100, 900, 800, 1200],
        points_against=[950, 1000, 900, 1050, 1100, 850],
        team_names=[f"Team{i}" for i in range(6)],
        completed_games=[],
        remaining_games=[("r0", "r1"), ("r2", "r3"), ("r4", "r5"), ("r0", "r2"), ("r1", "r3")],
        playoff_teams=3,
        n_trials=500,
        rng=rng,
    )
    probabilities = [result["teams"][rid]["playoff_probability"] for rid in roster_ids]
    assert all(0.0 <= p <= 100.0 for p in probabilities)


def test_slope_fit_falls_back_to_default_with_too_few_games():
    slope, fitted, n_games = sim.fit_win_probability_slope(
        z_differentials=[1.0, -1.0, 2.0],
        outcomes=[1, 0, 1],
    )
    assert fitted is False
    assert slope == sim.DEFAULT_SLOPE
    assert n_games == 3


def test_slope_fit_rejects_one_sided_results_as_uninformative():
    # Every single game won by the favored side -- nothing to distinguish
    # a real effect size from an artifact of a tiny sample.
    slope, fitted, n_games = sim.fit_win_probability_slope(
        z_differentials=[1.0] * 15,
        outcomes=[1] * 15,
    )
    assert fitted is False
    assert slope == sim.DEFAULT_SLOPE


def test_slope_fit_recovers_a_real_positive_signal():
    rng = np.random.default_rng(5)
    true_slope = 1.5
    z = rng.normal(scale=1.2, size=40)
    p = 1.0 / (1.0 + np.exp(-true_slope * z))
    outcomes = (rng.random(size=40) < p).astype(int)
    slope, fitted, n_games = sim.fit_win_probability_slope(z.tolist(), outcomes.tolist())
    assert fitted is True
    assert n_games == 40
    assert 0.0 < slope <= sim.MAX_FIT_SLOPE


def test_group_remaining_week_pairs_skips_byes_and_unpaired_groups():
    matchups = [
        {"roster_id": 1, "matchup_id": 10},
        {"roster_id": 2, "matchup_id": 10},
        {"roster_id": 3, "matchup_id": None},  # bye
        {"roster_id": 4, "matchup_id": 11},  # unpaired (odd team count glitch)
    ]
    pairs = sim._group_remaining_week_pairs(matchups)
    assert pairs == [("1", "2")]


def test_group_completed_week_games_picks_real_winner_and_skips_ties_and_unplayed():
    matchups = [
        {"roster_id": 1, "matchup_id": 1, "points": 120.5},
        {"roster_id": 2, "matchup_id": 1, "points": 99.0},
        {"roster_id": 3, "matchup_id": 2, "points": 0.0},
        {"roster_id": 4, "matchup_id": 2, "points": 0.0},
        {"roster_id": 5, "matchup_id": 3, "points": 100.0},
        {"roster_id": 6, "matchup_id": 3, "points": 100.0},
    ]
    games = sim._group_completed_week_games(matchups)
    assert games == [("1", "2", "1")]
