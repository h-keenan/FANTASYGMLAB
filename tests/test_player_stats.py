import unittest

import pandas as pd

from modules.rankings import attach_player_stats
from modules.sleeper import _aggregate_player_week_stats


class TestPlayerStatsPipeline(unittest.TestCase):
    def test_weekly_sleeper_stats_aggregate_to_canonical_fields(self):
        weekly_payloads = [
            {
                "player-1": {
                    "gp": 1,
                    "rec_tgt": 8,
                    "rec": 5,
                    "rec_yd": 70,
                    "rec_td": 1,
                    "pts_std": 13,
                    "pts_half_ppr": 15.5,
                    "pts_ppr": 18,
                    "off_snp": 48,
                    "tm_off_snp": 60,
                }
            },
            {
                "player-1": {
                    "gp": 1,
                    "rec_tgt": 6,
                    "rec": 4,
                    "rec_yd": 50,
                    "pts_std": 5,
                    "pts_half_ppr": 7,
                    "pts_ppr": 9,
                    "off_snp": 42,
                    "tm_off_snp": 60,
                }
            },
        ]

        stats = _aggregate_player_week_stats(weekly_payloads, 2025)["player-1"]

        self.assertEqual(stats["games_played"], 2)
        self.assertEqual(stats["targets"], 14)
        self.assertEqual(stats["receptions"], 9)
        self.assertEqual(stats["receiving_yards"], 120.0)
        self.assertEqual(stats["receiving_tds"], 1)
        self.assertEqual(stats["fantasy_points_ppr"], 27.0)
        self.assertAlmostEqual(stats["ppg"], 13.5)
        self.assertAlmostEqual(stats["snap_share"], 0.75)
        self.assertNotIn("passing_yards", stats)
        self.assertNotIn("target_share", stats)

    def test_stats_join_uses_player_id_and_preserves_missing_values(self):
        players = pd.DataFrame(
            [
                {"player_id": "player-1", "name": "Player One"},
                {"player_id": "player-2", "name": "Player Two"},
            ]
        )
        stats = {
            "player-1": {
                "stats_season": 2025,
                "games_played": 17,
                "targets": 0,
                "fantasy_points_ppr": 100.0,
            }
        }

        joined = attach_player_stats(players, stats).set_index("player_id")

        self.assertEqual(joined.loc["player-1", "games_played"], 17)
        self.assertEqual(joined.loc["player-1", "targets"], 0)
        self.assertEqual(joined.loc["player-1", "fantasy_points_ppr"], 100.0)
        self.assertTrue(pd.isna(joined.loc["player-2", "games_played"]))
        self.assertTrue(pd.isna(joined.loc["player-2", "targets"]))


if __name__ == "__main__":
    unittest.main()
