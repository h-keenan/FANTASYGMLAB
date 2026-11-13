"""Player-card game context on real starters: opponent, home/away, final score."""

from __future__ import annotations

import pandas as pd

from services import mobile_api_service as svc


def _games(played: bool) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "2026_10_DAL_PHI",
                "season": 2026,
                "week": 10,
                "gameday": "2026-11-08",
                "gametime": "13:00",
                "away_team": "DAL",
                "home_team": "PHI",
                "away_score": 17.0 if played else None,
                "home_score": 24.0 if played else None,
                "spread_line": -3.0,
                "total_line": 47.0,
            }
        ]
    )


def _ctx(games: pd.DataFrame):
    return svc._ProjectionContext(
        week=10, season=2026, players_lookup={}, weekly_stats={}, defense_strength={}, games=games
    )


def test_final_game_exposes_opponent_home_and_score():
    state = svc._player_game_state("PHI", _ctx(_games(True)))
    assert state["game_opponent"] == "DAL"
    assert state["game_is_home"] is True
    assert state["game_team_score"] == 24.0
    assert state["game_opponent_score"] == 17.0


def test_unplayed_game_has_context_but_no_score():
    state = svc._player_game_state("DAL", _ctx(_games(False)))
    assert state["game_opponent"] == "PHI"
    assert state["game_is_home"] is False
    assert state["game_team_score"] is None


def test_no_context_is_all_none():
    state = svc._player_game_state("PHI", None)
    assert state["game_opponent"] is None and state["game_final"] is None
