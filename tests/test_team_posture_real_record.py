"""Regression tests for the THIRD instance of coridian_'s draft-pick "real
record isn't being taken into account" bug class.

`modules.team_eval._classify_team_strategy` auto-computes each team's roster
"posture" (contender / fringe_contender / retool / rebuild / tank) purely
from a roster-VALUE percentile + age vs. league median -- zero win-loss
input anywhere. That posture feeds `_assign_team_archetype`, which produces
the user-facing "Juggernaut" / "Aging Contender" / "Full Rebuild" / etc.
archetype labels shown on the My Team screen (mobile TeamAnalysisPanel /
MyTeamScreen, web `modules.my_team_ui`). A team with a strong roster on
paper but a real bad start (e.g. 0-2) still read as "Contender" -- exactly
the bug class already fixed once for draft-pick projections in
`modules.trade_ideas._pick_team_context` (PR #737).

Fixed the same way: a real win-loss record is now blended into the
percentile, weighted by how much of the season has been played, via
`modules.record_signal` -- the SAME shared helper `trade_ideas` uses, so the
two call sites can't drift apart. See that module's docstring for the
floor/ceiling/slope rationale.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from modules import record_signal
from modules import team_eval
from modules import trade_ideas


def test_shared_blend_lives_in_one_place_for_both_callers():
    """`trade_ideas` re-exports `record_signal`'s weight/season-progress
    functions under their old names -- pin that they are literally the same
    objects, not two copies that could silently drift apart."""

    assert trade_ideas._record_signal_weight is record_signal.record_signal_weight
    assert trade_ideas._season_progress_fraction is record_signal.season_progress_fraction


def test_classify_ignores_record_with_no_games_played():
    """Preseason / a 0-0-0 record must not change anything -- win_percentage
    returns None with no games, so the blend safely no-ops back to the pure
    roster-value + age baseline."""

    baseline = team_eval._classify_team_strategy(0.9, 25, 25)
    with_zero_games = team_eval._classify_team_strategy(
        0.9, 25, 25, roster_record={"wins": 0, "losses": 0, "ties": 0}, season_progress=0.5
    )
    assert baseline == "contender"
    assert with_zero_games == baseline


def test_bad_record_pulls_a_pure_value_contender_off_its_baseline_mid_season():
    """A team that reads as a roster-value 'Contender' but has an actually
    poor real record should no longer classify as a pure Contender once real
    games have been played and enough of the season has passed."""

    strong_roster_pct = 0.90
    mid_season_progress = 0.5

    baseline = team_eval._classify_team_strategy(strong_roster_pct, 25, 25)
    assert baseline == "contender"

    with_bad_record = team_eval._classify_team_strategy(
        strong_roster_pct,
        25,
        25,
        roster_record={"wins": 0, "losses": 5, "ties": 0},
        season_progress=mid_season_progress,
    )
    assert with_bad_record != "contender"


def test_identical_roster_value_diverges_on_real_record_mid_season():
    """Two teams with the IDENTICAL roster-value percentile (so any
    difference in outcome is purely the win-loss signal) but opposite real
    records classify into different postures once enough of the season has
    passed."""

    score_percentile = 0.70
    season_progress = 0.6

    hot_start = team_eval._classify_team_strategy(
        score_percentile,
        25,
        25,
        roster_record={"wins": 6, "losses": 0, "ties": 0},
        season_progress=season_progress,
    )
    cold_start = team_eval._classify_team_strategy(
        score_percentile,
        25,
        25,
        roster_record={"wins": 0, "losses": 6, "ties": 0},
        season_progress=season_progress,
    )
    assert hot_start != cold_start


def test_early_season_single_game_weighs_roster_value_more_than_late_season():
    """Same doesn't-overreact-to-small-samples guarantee as the pick fix:
    the record weight right after game 1 must be meaningfully smaller than
    the weight late in the season, both computed off the one shared
    floor/ceiling/slope formula."""

    game_one_progress = 1 / 14
    late_season_progress = 13 / 14
    early_weight = record_signal.record_signal_weight(game_one_progress)
    late_weight = record_signal.record_signal_weight(late_season_progress)

    assert 0.0 < early_weight < late_weight < 1.0
    # The floor guarantees a real (non-negligible) signal even after game 1
    # -- that's what actually fixes "nothing's being taken into account" --
    # but it stays far below the late-season weight, so roster value still
    # leads early.
    assert early_weight == pytest.approx(record_signal.RECORD_SIGNAL_WEIGHT_FLOOR, abs=0.05)
    assert late_weight == pytest.approx(record_signal.RECORD_SIGNAL_WEIGHT_CEILING, abs=0.05)


def _identical_two_team_players() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "p1",
                "name": "Player One",
                "position": "QB",
                "age": 25,
                "dynasty_score": 100,
                "value_score": 100,
            },
            {
                "player_id": "p2",
                "name": "Player Two",
                "position": "QB",
                "age": 25,
                "dynasty_score": 100,
                "value_score": 100,
            },
        ]
    )


def _two_roster_adapter(*, struggling_settings: dict, undefeated_settings: dict, leg: int) -> SimpleNamespace:
    rosters = [
        {"roster_id": 1, "owner_id": "u1", "players": ["p1"], "settings": struggling_settings},
        {"roster_id": 2, "owner_id": "u2", "players": ["p2"], "settings": undefeated_settings},
    ]
    return SimpleNamespace(
        get_rosters=lambda _league: rosters,
        get_users=lambda _league: [
            {"user_id": "u1", "display_name": "Struggling"},
            {"user_id": "u2", "display_name": "Undefeated"},
        ],
        get_league=lambda _league: {
            "season": 2026,
            "settings": {"leg": leg, "playoff_week_start": 15},
        },
    )


def test_build_league_summary_diverges_on_real_record_end_to_end():
    """Full-plumbing check: `build_league_summary` (the function My Team's
    posture/archetype pipeline actually calls) must read each roster's REAL
    Sleeper wins/losses and the league's current week off the payloads it
    already fetches (get_rosters/get_league), not just accept them if
    hand-fed to `_classify_team_strategy` directly.

    Two rosters with an IDENTICAL roster (so an identical roster-value
    percentile) but a 0-2 vs. 2-0 record, mid-season, must end up with
    different `strategy` -- before this fix both landed on the same
    roster-value-only posture ("Fringe Contender") regardless of record."""

    df_players = _identical_two_team_players()
    # leg=7 of a 14-week regular season (playoff_week_start=15) -> exactly
    # mid-season, matching modules.record_signal's season_progress_fraction.
    adapter = _two_roster_adapter(
        struggling_settings={"wins": 0, "losses": 2, "ties": 0},
        undefeated_settings={"wins": 2, "losses": 0, "ties": 0},
        leg=7,
    )

    with patch("modules.team_eval.get_league_roster_profiles", return_value={}):
        summary = team_eval.build_league_summary(df_players, "league", adapter=adapter)

    struggling = summary.loc[summary["roster_id"] == 1].iloc[0]
    undefeated = summary.loc[summary["roster_id"] == 2].iloc[0]

    # Identical rosters -> identical roster-value percentile, so both would
    # have landed on the exact same pre-fix posture.
    assert struggling["strategy"] != undefeated["strategy"]
    assert undefeated["strategy"] == "contender"
    assert struggling["strategy"] in {"rebuild", "tank", "retool"}


def test_build_league_summary_ignores_record_before_any_games_played():
    """Preseason (0-0-0 for every roster, leg=0) must classify identically
    to the pure roster-value + age baseline -- no divide-by-zero, no
    invented signal, matching the pre-fix behavior exactly."""

    df_players = _identical_two_team_players()
    adapter = _two_roster_adapter(
        struggling_settings={"wins": 0, "losses": 0, "ties": 0},
        undefeated_settings={"wins": 0, "losses": 0, "ties": 0},
        leg=0,
    )

    with patch("modules.team_eval.get_league_roster_profiles", return_value={}):
        summary = team_eval.build_league_summary(df_players, "league", adapter=adapter)

    strategies = set(summary["strategy"])
    assert len(strategies) == 1, "identical rosters with no games played must classify identically"
