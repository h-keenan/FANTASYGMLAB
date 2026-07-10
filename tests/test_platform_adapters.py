import unittest
from unittest.mock import patch

import pandas as pd

from modules import player_identity
from modules.platforms.sleeper import SleeperPlatformAdapter, get_sleeper_adapter


class TestSleeperPlatformAdapter(unittest.TestCase):
    def test_sleeper_adapter_platform_name(self):
        self.assertEqual(get_sleeper_adapter().platform, "sleeper")

    def test_normalized_roster_canonicalizes_player_ids(self):
        adapter = SleeperPlatformAdapter()

        roster = adapter.normalize_roster(
            {
                "roster_id": "7",
                "owner_id": 123,
                "players": [101, "202", None, ""],
            }
        )

        self.assertEqual(roster["platform"], "sleeper")
        self.assertEqual(roster["roster_id"], 7)
        self.assertEqual(roster["owner_id"], "123")
        self.assertEqual(roster["players"], ["101", "202"])
        self.assertEqual(roster["platform_player_ids"], ["101", "202"])

    def test_get_roster_player_ids_returns_canonical_ids(self):
        adapter = SleeperPlatformAdapter()
        with patch(
            "modules.platforms.sleeper.sleeper_api.get_roster_player_ids",
            return_value=[1, "2", None],
        ):
            self.assertEqual(adapter.get_roster_player_ids("league", 1), ["1", "2"])

    def test_normalized_draft_pick_canonicalizes_player_id(self):
        adapter = SleeperPlatformAdapter()

        pick = adapter.normalize_draft_pick(
            {
                "round": 1,
                "pick_no": 3,
                "metadata": {"player_id": 456},
            }
        )

        self.assertEqual(pick["platform"], "sleeper")
        self.assertEqual(pick["platform_player_id"], "456")
        self.assertEqual(pick["player_id"], "456")
        self.assertEqual(pick["round"], 1)
        self.assertEqual(pick["pick_no"], 3)

    def test_normalized_draft_pick_handles_empty_player_id(self):
        adapter = SleeperPlatformAdapter()

        pick = adapter.normalize_draft_pick({"round": 1, "pick_no": 1})

        self.assertEqual(pick["platform_player_id"], "")
        self.assertEqual(pick["player_id"], "")

    def test_get_draft_picks_returns_normalized_picks(self):
        adapter = SleeperPlatformAdapter()
        with patch(
            "modules.platforms.sleeper.sleeper_api.get_draft_picks",
            return_value=[
                {"player_id": 111, "pick_no": 1},
                {"metadata": {"picked_player_id": "222"}, "pick_no": 2},
            ],
        ):
            picks = adapter.get_draft_picks("draft")

        self.assertEqual([pick["player_id"] for pick in picks], ["111", "222"])
        self.assertEqual([pick["platform_player_id"] for pick in picks], ["111", "222"])

    def test_get_traded_picks_wraps_sleeper_client(self):
        adapter = SleeperPlatformAdapter()
        with patch(
            "modules.platforms.sleeper.sleeper_api.get_traded_picks",
            return_value=[{"season": "2026", "round": 2, "roster_id": 1, "owner_id": 2}],
        ) as traded_picks:
            picks = adapter.get_traded_picks("league")

        traded_picks.assert_called_once_with("league")
        self.assertEqual(picks[0]["owner_id"], 2)

    def test_adapter_output_compatible_with_player_id_join(self):
        adapter = SleeperPlatformAdapter()
        roster = adapter.normalize_roster({"players": ["10"]})
        df_players = player_identity.ensure_identity_columns(
            pd.DataFrame(
                [
                    {"player_id": "10", "name": "Rostered"},
                    {"player_id": "20", "name": "Other"},
                ]
            )
        )

        joined = df_players[df_players["player_id"].isin(roster["players"])]

        self.assertEqual(joined["name"].tolist(), ["Rostered"])

    def test_low_level_sleeper_client_can_still_be_used_directly(self):
        from modules import sleeper

        self.assertTrue(callable(sleeper.get_rosters))
        self.assertTrue(callable(sleeper.get_draft_picks))


if __name__ == "__main__":
    unittest.main()
