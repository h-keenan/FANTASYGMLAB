"""modules.team_streaks: real per-roster current win/loss streak off actual
weekly Sleeper matchup results — the data half of the "Hot Streak"/"Cold
Streak" team badge. Same fake-fetcher pattern tests/test_manager_activity.py
uses: pins the pairing/streak algorithm against realistic raw Sleeper
matchup rows rather than the live Sleeper API.
"""

from __future__ import annotations

from unittest.mock import patch

from modules import team_streaks


def _matchups_for(by_week: dict[int, list[dict]]):
    def _fetch(league_id: str, week: int):
        return by_week.get(week, [])

    return _fetch


def test_three_straight_wins_produce_a_positive_streak_of_three():
    league = {"season": "2026", "settings": {"leg": 3, "playoff_week_start": 15}}
    by_week = {
        week: [
            {"roster_id": 1, "matchup_id": 100, "points": 120},
            {"roster_id": 2, "matchup_id": 100, "points": 100},
        ]
        for week in (1, 2, 3)
    }
    with patch("modules.sleeper.get_league", return_value=league):
        with patch("modules.sleeper.get_matchups", side_effect=_matchups_for(by_week)):
            streaks = team_streaks.league_current_streaks("L1")

    assert streaks[1] == {"current_streak": 3, "wins_last_three": 3, "losses_last_three": 0}
    assert streaks[2] == {"current_streak": -3, "wins_last_three": 0, "losses_last_three": 3}


def test_a_tie_resets_the_streak_rather_than_extending_or_starting_one():
    league = {"season": "2026", "settings": {"leg": 2, "playoff_week_start": 15}}
    by_week = {
        1: [
            {"roster_id": 1, "matchup_id": 100, "points": 120},
            {"roster_id": 2, "matchup_id": 100, "points": 100},
        ],
        2: [
            {"roster_id": 1, "matchup_id": 101, "points": 100},
            {"roster_id": 2, "matchup_id": 101, "points": 100},
        ],
    }
    with patch("modules.sleeper.get_league", return_value=league):
        with patch("modules.sleeper.get_matchups", side_effect=_matchups_for(by_week)):
            streaks = team_streaks.league_current_streaks("L1")

    assert streaks[1]["current_streak"] == 0


def test_empty_league_id_short_circuits():
    assert team_streaks.league_current_streaks("") == {}


def test_classify_streak_badge_hot_at_the_minimum_threshold():
    assert team_streaks.classify_streak_badge(team_streaks.MIN_STREAK_FOR_BADGE) == "Hot Streak"
    assert team_streaks.classify_streak_badge(team_streaks.MIN_STREAK_FOR_BADGE - 1) is None


def test_classify_streak_badge_cold_at_the_minimum_threshold():
    assert team_streaks.classify_streak_badge(-team_streaks.MIN_STREAK_FOR_BADGE) == "Cold Streak"
    assert team_streaks.classify_streak_badge(-(team_streaks.MIN_STREAK_FOR_BADGE - 1)) is None


def test_classify_streak_badge_none_for_a_single_result():
    assert team_streaks.classify_streak_badge(1) is None
    assert team_streaks.classify_streak_badge(-1) is None
    assert team_streaks.classify_streak_badge(0) is None
