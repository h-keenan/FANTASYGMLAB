import unittest
from unittest.mock import patch

import pandas as pd

import app
from modules import team_eval
from modules import trade_ideas


class FakeAdapter:
    platform = "sleeper"

    def __init__(self):
        self.get_rosters_calls = 0
        self.get_users_calls = 0
        self.get_traded_picks_calls = 0

    def get_rosters(self, league_id):
        self.get_rosters_calls += 1
        return [
            {"roster_id": 1, "owner_id": "u1", "players": ["p1", "missing"]},
            {"roster_id": 2, "owner_id": "u2", "players": ["p2"]},
        ]

    def get_users(self, league_id):
        self.get_users_calls += 1
        return [
            {"user_id": "u1", "display_name": "One"},
            {"user_id": "u2", "display_name": "Two"},
        ]

    def get_league(self, league_id):
        return {"season": 2026, "settings": {"draft_rounds": 4}}

    def get_traded_picks(self, league_id):
        self.get_traded_picks_calls += 1
        return [{"season": "2026", "round": 2, "roster_id": 1, "owner_id": 2}]

    def get_roster_player_ids(self, league_id, roster_id):
        for roster in self.get_rosters(league_id):
            if roster.get("roster_id") == roster_id:
                return list(roster.get("players") or [])
        return []


class TestPlatformAdapterMigration(unittest.TestCase):
    def test_team_eval_uses_adapter_canonical_roster_player_ids(self):
        adapter = FakeAdapter()
        df_players = pd.DataFrame(
            [
                {"player_id": "p1", "name": "Player One", "position": "QB", "age": 24, "dynasty_score": 100, "value_score": 100},
                {"player_id": "p2", "name": "Player Two", "position": "RB", "age": 25, "dynasty_score": 80, "value_score": 80},
            ]
        )

        with patch("modules.team_eval.get_league_roster_profiles", return_value={}):
            summary = team_eval.build_league_summary(
                df_players,
                "league",
                adapter=adapter,
            )

        self.assertEqual(adapter.get_rosters_calls, 1)
        self.assertEqual(adapter.get_users_calls, 1)
        self.assertEqual(set(summary["roster_id"]), {1, 2})
        self.assertGreater(float(summary.loc[summary["roster_id"].eq(1), "raw_roster_score"].iloc[0]), 0)

    def test_trade_ideas_uses_injected_adapter_for_roster_map(self):
        adapter = FakeAdapter()
        df_players = pd.DataFrame(
            [
                {"player_id": "p1", "name": "Player One", "position": "WR", "age": 24, "value_score": 100, "dynasty_score": 100},
                {"player_id": "p2", "name": "Player Two", "position": "RB", "age": 25, "value_score": 90, "dynasty_score": 90},
            ]
        )
        df_summary = pd.DataFrame(
            [
                {"roster_id": 1, "team_name": "One", "mode": "retool", "strategy": "retool"},
                {"roster_id": 2, "team_name": "Two", "mode": "retool", "strategy": "retool"},
            ]
        )

        with patch("modules.trade_ideas._build_roster_pick_assets", return_value={}), patch(
            "modules.trade_ideas.get_team_vs_league",
            return_value={},
        ):
            ideas = trade_ideas.build_trade_ideas(
                df_players=df_players,
                league_id="league",
                df_summary=df_summary,
                my_roster_id=1,
                trade_block_names=["Player One"],
                untouchable_names=[],
                role_map={},
                adapter=adapter,
            )

        self.assertEqual(ideas, [])
        self.assertEqual(adapter.get_rosters_calls, 1)

    def test_trade_roster_players_map_uses_canonical_player_ids(self):
        roster_map = trade_ideas._roster_players_map(
            [
                {"roster_id": 1, "players": ["canon-1", "canon-2"]},
                {"roster_id": 0, "players": ["ignored"]},
            ]
        )

        self.assertEqual(roster_map, {1: ["canon-1", "canon-2"]})

    def test_trade_pick_assets_use_adapter_traded_picks(self):
        adapter = FakeAdapter()
        df_summary = pd.DataFrame(
            [
                {"roster_id": 1, "team_name": "One", "total_score": 90},
                {"roster_id": 2, "team_name": "Two", "total_score": 80},
            ]
        )

        picks = trade_ideas.list_draft_pick_assets("league", df_summary, adapter=adapter)

        self.assertEqual(adapter.get_traded_picks_calls, 1)
        traded_second = [
            pick
            for pick in picks
            if pick.get("season") == 2026
            and pick.get("round") == 2
            and pick.get("original_roster_id") == 1
        ]
        self.assertEqual(traded_second[0]["owner_roster_id"], 2)

    def test_dashboard_waiver_preview_excludes_adapter_canonical_roster_ids(self):
        adapter = FakeAdapter()
        df_players = pd.DataFrame(
            [
                {"player_id": "p1", "name": "Rostered", "position": "WR", "team": "DAL", "active": True, "status": "Active", "fantasycalc_value": 90, "value_score": 90, "dynasty_score": 90},
                {"player_id": "p3", "name": "Free Agent", "position": "RB", "team": "NYG", "active": True, "status": "Active", "fantasycalc_value": 80, "value_score": 80, "dynasty_score": 80},
            ]
        )

        with patch("app.get_sleeper_adapter", return_value=adapter):
            free_agents, _, _ = app.build_home_dashboard_free_agent_preview(
                df_players,
                "league",
                my_roster_id=None,
                score_field="value_score",
                league_settings={},
            )

        self.assertEqual(free_agents["player_id"].tolist(), ["p3"])


if __name__ == "__main__":
    unittest.main()
