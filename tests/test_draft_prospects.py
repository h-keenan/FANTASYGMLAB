import unittest

import pandas as pd

from modules.draft_prospects import draft_watch_positions, prospects_for_positions


class TestDraftProspects(unittest.TestCase):
    def test_covered_future_asset_injury_does_not_drive_top_draft_need(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "future-te",
                    "position": "TE",
                    "value_score": 90,
                    "player_tier": "Core Starter",
                    "age": 21,
                    "years_exp": 0,
                    "status": "IR",
                    "injury_status": "out",
                },
                {
                    "player_id": "healthy-te",
                    "position": "TE",
                    "value_score": 62,
                    "player_tier": "Contributor",
                    "age": 27,
                    "years_exp": 5,
                    "status": "Active",
                    "injury_status": "",
                },
                {
                    "player_id": "qb-1",
                    "position": "QB",
                    "value_score": 70,
                    "player_tier": "Core Starter",
                    "age": 25,
                    "years_exp": 3,
                    "status": "Active",
                    "injury_status": "",
                },
                {
                    "player_id": "rb-1",
                    "position": "RB",
                    "value_score": 25,
                    "age": 28,
                    "years_exp": 6,
                    "status": "Active",
                    "injury_status": "",
                },
                {
                    "player_id": "wr-1",
                    "position": "WR",
                    "value_score": 45,
                    "age": 26,
                    "years_exp": 4,
                    "status": "Active",
                    "injury_status": "",
                },
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [False, True, True, True, True]
        injury_context = {
            "active_injury_positions": [],
            "future_injury_positions": ["TE"],
            "covered_future_injury_positions": ["TE"],
            "injury_need_positions": [],
        }

        positions = draft_watch_positions(
            ["TE", "QB"],
            roster,
            lineup,
            injury_context=injury_context,
            league_settings={
                "qb_count": 1,
                "rb_count": 2,
                "wr_count": 3,
                "te_count": 1,
            },
            team_strategy="rebuild",
        )

        self.assertNotIn("TE", positions)
        self.assertIn("QB", positions)

    def test_prospect_selection_round_robins_across_positions(self):
        prospects = prospects_for_positions(["QB", "RB", "WR", "TE"], limit=6)
        first_four_positions = [prospect["position"] for prospect in prospects[:4]]

        self.assertEqual(first_four_positions, ["QB", "RB", "WR", "TE"])
        self.assertGreaterEqual(len(set(prospect["position"] for prospect in prospects)), 4)


if __name__ == "__main__":
    unittest.main()
