"""Thursday lock: Sleeper locks a player at his own kickoff, so weekly lineup
advice must keep started players where they are (see
modules.team_eval.suggest_optimal_lineup started_player_ids/locked_starter_ids).
"""

from __future__ import annotations

import pandas as pd

from modules.team_eval import suggest_optimal_lineup

_SETTINGS = {"qb_count": 1, "rb_count": 2, "wr_count": 2, "te_count": 1, "regular_flex_count": 1, "k_count": 0}


def _roster():
    rows = [
        ("qb1", "QB", 8000), ("rb1", "RB", 9000), ("rb2", "RB", 7000), ("rb3", "RB", 3000),
        ("wr1", "WR", 8500), ("wr2", "WR", 6000), ("wr3", "WR", 2500), ("te1", "TE", 5000),
    ]
    return pd.DataFrame(
        [{"player_id": p, "name": p, "position": pos, "team": "KC", "value_score": s,
          "status": "Active", "injury_status": ""} for p, pos, s in rows]
    )


def _by_id(frame):
    return {row["player_id"]: row for _, row in frame.iterrows()}


def test_started_game_locks_the_lineup_both_ways():
    points = {"qb1": 18.0, "rb1": 20.0, "rb2": 5.0, "rb3": 9.0, "wr1": 15.0, "wr2": 12.0, "wr3": 11.0, "te1": 8.0}
    lineup = _by_id(
        suggest_optimal_lineup(
            _roster(), _SETTINGS, score_field="value_score", weekly_points=points,
            bye_player_ids=set(), started_player_ids={"rb1", "rb2"}, locked_starter_ids={"rb2"},
        )
    )
    # rb2 already played and is in the lineup: he stays despite a low projection.
    assert lineup["rb2"]["suggested_starter"]
    # rb1's game started while he sat on the bench: he cannot be started now.
    assert lineup["rb1"]["slot"] == "BENCH"
    assert lineup["rb1"]["start_ineligible_reason"] == "Game started"
    assert bool(lineup["rb1"]["game_locked"]) is True
    assert lineup["rb3"]["suggested_starter"]


def test_started_player_ids_follow_each_teams_kickoff():
    from types import SimpleNamespace
    from unittest.mock import patch

    from services import mobile_api_service as svc

    roster = pd.DataFrame(
        [{"player_id": "a", "team": "KC"}, {"player_id": "b", "team": "BUF"}, {"player_id": "c", "team": ""}]
    )
    ctx = SimpleNamespace(games=pd.DataFrame(), week=5, season=2026)
    with patch.object(
        svc, "_player_game_state", side_effect=lambda team, _ctx: {"game_started": team == "KC"}
    ):
        assert svc._started_game_player_ids(roster, ctx) == {"a"}
    assert svc._started_game_player_ids(roster, SimpleNamespace(games=None, week=5, season=2026)) == set()


def test_no_started_games_changes_nothing():
    points = {"rb1": 20.0, "rb2": 5.0, "rb3": 9.0}
    a = suggest_optimal_lineup(_roster(), _SETTINGS, score_field="value_score", weekly_points=points, bye_player_ids=set())
    b = suggest_optimal_lineup(
        _roster(), _SETTINGS, score_field="value_score", weekly_points=points, bye_player_ids=set(),
        started_player_ids=set(), locked_starter_ids=set(),
    )
    assert list(a["slot"]) == list(b["slot"])
