from __future__ import annotations

import pandas as pd

from modules import waivers_logic


def _fa(pid: str, score: int) -> dict:
    return {
        "player_id": pid, "name": pid, "position": "WR", "team": "NYG", "status": "Active", "active": True,
        "value_score": score, "dynasty_score": score, "stale_free_agent": False, "workload_trend": "",
        "waiver_actionable": True,
    }


def test_players_with_games_needs_a_recorded_game():
    stats = {
        "a": {"weekly": [{"week": 1, "games_played": 1}]},
        "b": {"weekly": [{"week": 1, "games_played": 0}]},
        "c": {"games_played": 3},
        "d": {"games_played": 0},
    }
    assert waivers_logic.players_with_games(stats) == {"a", "c"}


def test_priority_adds_skip_players_with_no_game_this_season():
    free_agents = pd.DataFrame([_fa("played", 2000), _fa("benched", 9000)])
    kwargs = dict(
        score_field="value_score", needed_positions=["WR"], league_settings={}, roster_df=pd.DataFrame(), max_items=6
    )
    ungated = waivers_logic.rank_priority_add_candidates(free_agents, **kwargs)
    assert "benched" in set(ungated["player_id"])
    gated = waivers_logic.rank_priority_add_candidates(free_agents, played_ids={"played"}, **kwargs)
    assert "benched" not in set(gated["player_id"])
    assert "played" in set(gated["player_id"])
