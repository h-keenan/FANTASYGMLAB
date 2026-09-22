"""modules.nfl_schedule — real NFL schedule/market-line lookups.

Context-only data: these tests never assert anything about value_score,
rankings, or lineup logic — this module doesn't touch any of that.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd

from modules import nfl_schedule


def _games_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # Week 1: KC (home) vs BUF (away), played.
            {
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "home_team": "KC",
                "away_team": "BUF",
                "home_score": 24.0,
                "away_score": 20.0,
                "spread_line": -2.5,
                "total_line": 47.5,
            },
            # Week 2: BUF (home) vs LA (nflverse's Rams code), not yet played.
            {
                "season": 2026,
                "game_type": "REG",
                "week": 2,
                "home_team": "BUF",
                "away_team": "LA",
                "home_score": None,
                "away_score": None,
                "spread_line": -3.0,
                "total_line": 44.0,
            },
            # KC has a bye in week 3 — no row at all for KC.
            {
                "season": 2026,
                "game_type": "REG",
                "week": 3,
                "home_team": "BUF",
                "away_team": "NE",
                "home_score": None,
                "away_score": None,
                "spread_line": -6.0,
                "total_line": 41.0,
            },
            # A playoff row that must be excluded from the REG-only schedule.
            {
                "season": 2026,
                "game_type": "DIV",
                "week": 20,
                "home_team": "KC",
                "away_team": "BUF",
                "home_score": None,
                "away_score": None,
                "spread_line": -1.0,
                "total_line": 45.0,
            },
        ]
    )


def test_team_schedule_is_week_ordered_across_home_and_away_games():
    games = _games_frame()

    schedule = nfl_schedule.team_schedule("BUF", 2026, games=games)

    assert [row["week"] for row in schedule] == [1, 2, 3]
    assert schedule[0]["opponent"] == "KC"
    assert schedule[0]["is_home"] is False
    assert schedule[1]["opponent"] == "LAR"  # nflverse's "LA" remapped to this app's "LAR"
    assert schedule[1]["is_home"] is True


def test_spread_line_is_flipped_to_the_requested_teams_own_perspective():
    games = _games_frame()

    kc_schedule = nfl_schedule.team_schedule("KC", 2026, games=games)
    buf_schedule = nfl_schedule.team_schedule("BUF", 2026, games=games)

    kc_week1 = next(row for row in kc_schedule if row["week"] == 1)
    buf_week1 = next(row for row in buf_schedule if row["week"] == 1)
    # Published spread_line (-2.5) is from the home team's (KC's) perspective.
    assert kc_week1["spread_line"] == -2.5
    assert buf_week1["spread_line"] == 2.5


def test_unplayed_game_reports_no_scores_but_real_market_lines():
    games = _games_frame()

    schedule = nfl_schedule.team_schedule("BUF", 2026, games=games)
    week2 = next(row for row in schedule if row["week"] == 2)

    assert week2["played"] is False
    assert week2["team_score"] is None
    assert week2["opponent_score"] is None
    assert week2["total_line"] == 44.0


def test_app_team_code_lar_resolves_against_nflverses_la():
    games = _games_frame()

    schedule = nfl_schedule.team_schedule("LAR", 2026, games=games)

    assert len(schedule) == 1
    assert schedule[0]["opponent"] == "BUF"


def test_bye_week_has_no_matching_game():
    games = _games_frame()

    assert nfl_schedule.team_matchup_for_week("KC", 3, 2026, games=games) is None


def test_team_schedule_synthesizes_a_bye_row_for_a_gap_within_its_own_span():
    # NE has games in weeks 1 and 3 but nothing in week 2 — a real bye,
    # distinct from "this team has no game data past its last known week".
    games = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "home_team": "NE",
                "away_team": "KC",
                "home_score": 10.0,
                "away_score": 24.0,
                "spread_line": 3.0,
                "total_line": 40.0,
            },
            {
                "season": 2026,
                "game_type": "REG",
                "week": 3,
                "home_team": "BUF",
                "away_team": "NE",
                "home_score": None,
                "away_score": None,
                "spread_line": -6.0,
                "total_line": 41.0,
            },
        ]
    )

    schedule = nfl_schedule.team_schedule("NE", 2026, games=games)

    assert [row["week"] for row in schedule] == [1, 2, 3]
    bye_row = next(row for row in schedule if row["week"] == 2)
    assert bye_row["bye"] is True
    assert bye_row["opponent"] is None
    assert bye_row["played"] is False
    assert schedule[0]["bye"] is False
    assert schedule[2]["bye"] is False
    # The synthesized bye row doesn't fool the single-week lookup into
    # reporting a real opponent — it's still an explicit "this is a bye".
    matchup = nfl_schedule.team_matchup_for_week("NE", 2, 2026, games=games)
    assert matchup is not None
    assert matchup["bye"] is True
    assert matchup["opponent"] is None


def test_matchup_for_week_returns_the_one_real_game():
    games = _games_frame()

    matchup = nfl_schedule.team_matchup_for_week("KC", 1, 2026, games=games)

    assert matchup is not None
    assert matchup["opponent"] == "BUF"
    assert matchup["is_home"] is True


def test_playoff_rows_are_excluded_from_the_regular_season_schedule():
    games = _games_frame()

    kc_schedule = nfl_schedule.team_schedule("KC", 2026, games=games)

    assert all(row["week"] != 20 for row in kc_schedule)


def test_load_games_falls_back_to_disk_cache_on_fetch_failure(tmp_path):
    cache_path = tmp_path / "nfl_games.csv"
    _games_frame().to_csv(cache_path, index=False)

    with (
        patch.object(nfl_schedule, "GAMES_CACHE_PATH", str(cache_path)),
        patch.object(nfl_schedule, "requests") as mock_requests,
    ):
        mock_requests.get.side_effect = Exception("network down")
        result = nfl_schedule.load_games(refresh=True)

    assert not result.empty
    assert set(result["home_team"]) == {"KC", "BUF"}


def test_load_games_returns_empty_frame_with_no_cache_and_no_network(tmp_path):
    cache_path = tmp_path / "does_not_exist.csv"

    with (
        patch.object(nfl_schedule, "GAMES_CACHE_PATH", str(cache_path)),
        patch.object(nfl_schedule, "requests") as mock_requests,
    ):
        mock_requests.get.side_effect = Exception("network down")
        result = nfl_schedule.load_games(refresh=True)

    assert result.empty
