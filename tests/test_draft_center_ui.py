import unittest
from unittest.mock import patch

import pandas as pd

from modules import draft_center_cards


class TestDraftCenterUI(unittest.TestCase):

    def test_pick_rich_rebuilder_posture_is_preserved(self):
        posture = draft_center_cards._draft_posture_profile(
            {
                "mode": "rebuild",
                "draft_capital_rank": 1,
                "future_draft_capital_rank": 1,
                "power_rank": 10,
                "first_rounders": 3,
            },
            12,
        )

        self.assertEqual(posture["label"], "Pick-Rich Rebuilder")
        self.assertEqual(posture["tone"], "opportunity")
        self.assertIn("3 tracked first-rounders", posture["note"])

    def test_draft_decision_cards_keep_expected_sections(self):
        draft_workspace = pd.DataFrame(
            [
                {
                    "roster_id": 1,
                    "team_name": "Contender",
                    "mode": "contender",
                    "strategy_display": "Contender",
                    "power_rank": 1,
                    "franchise_rank": 2,
                    "draft_capital_rank": 2,
                    "future_draft_capital_rank": 2,
                    "draft_capital": 4000,
                    "future_draft_capital": 3000,
                    "pick_count": 5,
                    "age_rank": 3,
                    "first_rounders": 2,
                },
                {
                    "roster_id": 2,
                    "team_name": "Rebuilder",
                    "mode": "rebuild",
                    "strategy_display": "Rebuild",
                    "power_rank": 12,
                    "franchise_rank": 8,
                    "draft_capital_rank": 11,
                    "future_draft_capital_rank": 10,
                    "draft_capital": 500,
                    "future_draft_capital": 400,
                    "pick_count": 1,
                    "age_rank": 9,
                    "first_rounders": 0,
                },
            ]
        )

        cards = draft_center_cards.build_draft_decision_cards(draft_workspace)

        self.assertEqual(
            [card["label"] for card in cards],
            [
                "Best Pick Buyers",
                "Best Pick Sellers",
                "Pivot Candidates",
                "Pick-Rich Teams",
                "Pick-Poor Teams",
            ],
        )
        self.assertTrue(all(card["items"] for card in cards))

    def _workspace(self):
        return pd.DataFrame(
            [
                {
                    "roster_id": 1,
                    "team_name": "Contender | Crew",
                    "mode": "contender",
                    "strategy_display": "Contender",
                    "power_rank": 1,
                    "franchise_rank": 2,
                    "draft_capital_rank": 2,
                    "future_draft_capital_rank": 2,
                    "draft_capital": 4000,
                    "future_draft_capital": 3000,
                    "pick_count": 5,
                    "age_rank": 3,
                    "first_rounders": 2,
                },
                {
                    "roster_id": 2,
                    "team_name": "Retooler",
                    "mode": "retool",
                    "strategy_display": "Retool",
                    "power_rank": 9,
                    "franchise_rank": 8,
                    "draft_capital_rank": 10,
                    "future_draft_capital_rank": 10,
                    "draft_capital": 500,
                    "future_draft_capital": 400,
                    "pick_count": 1,
                    "age_rank": 9,
                    "first_rounders": 0,
                    "avatar_url": "https://example.com/a.png",
                },
            ]
        )

    def test_cards_carry_structured_rows_and_keep_legacy_items(self):
        cards = draft_center_cards.build_draft_decision_cards(self._workspace())
        for card in cards:
            self.assertEqual(card["schema"], 2)
            # Legacy strings stay for the clients that still render them.
            self.assertTrue(all(isinstance(item, str) for item in card["items"]))
            self.assertGreaterEqual(len(card["rows"]), len(card["items"]))
            for item, row in zip(card["items"], card["rows"]):
                self.assertTrue(item.startswith(row["team_name"]))
                self.assertLessEqual(len(row["reason_short"]), 60)
                # The long sentence is exactly what the legacy string ends with.
                self.assertTrue(item.endswith(row["reason_long"]))
                self.assertNotIn(" | ", row["reason_short"])
                self.assertTrue(row["evidence"])

    def test_rows_expose_fields_instead_of_a_joined_string(self):
        cards = draft_center_cards.build_draft_decision_cards(self._workspace())
        buyers = next(card for card in cards if card["label"] == "Best Pick Buyers")
        retool = next(row for row in buyers["rows"] if row["team_name"] == "Retooler")
        self.assertEqual(retool["team_id"], "2")
        self.assertEqual(retool["strategy"], "retool")
        self.assertEqual(retool["strategy_display"], "Retool")
        self.assertEqual(retool["draft_rank"], 10)
        self.assertEqual(retool["future_rank"], 10)
        self.assertEqual(retool["reason_code"], "too_few_picks")
        self.assertEqual(retool["reason_short"], "Too few picks for a retool")
        self.assertEqual(retool["avatar_url"], "https://example.com/a.png")
        by_key = {entry["key"]: entry["value"] for entry in retool["evidence"]}
        self.assertEqual(by_key["draft_rank"], "#10")
        # A team name containing the old delimiter survives untouched.
        sellers = next(card for card in cards if card["label"] == "Best Pick Sellers")
        self.assertIn("Contender | Crew", [row["team_name"] for row in sellers["rows"]])

    def test_rows_keep_more_teams_than_the_legacy_top_three(self):
        teams = []
        for index in range(1, 9):
            teams.append(
                {
                    "roster_id": index,
                    "team_name": f"Team {index}",
                    "mode": "rebuild",
                    "strategy_display": "Rebuild",
                    "power_rank": 9 + index % 3,
                    "franchise_rank": 8,
                    "draft_capital_rank": 20 - index,
                    "future_draft_capital_rank": 20 - index,
                    "draft_capital": 100 * index,
                    "future_draft_capital": 90 * index,
                    "pick_count": index,
                    "age_rank": 5,
                    "first_rounders": index % 3,
                }
            )
        cards = draft_center_cards.build_draft_decision_cards(pd.DataFrame(teams))
        buyers = next(card for card in cards if card["label"] == "Best Pick Buyers")
        self.assertEqual(len(buyers["items"]), 3)
        self.assertGreater(len(buyers["rows"]), 3)
        for card in cards:
            self.assertLessEqual(len(card["items"]), 3)
            self.assertLessEqual(len(card["rows"]), draft_center_cards.CARD_ROW_POOL)
            # The first three rows are the same teams, in the same order, as the legacy strings.
            for item, row in zip(card["items"], card["rows"]):
                self.assertTrue(item.startswith(row["team_name"]))

    def test_partner_cards_also_carry_rows(self):
        cards = draft_center_cards.build_draft_partner_cards(self._workspace())
        self.assertTrue(cards)
        for card in cards:
            self.assertEqual(card["schema"], 2)
            self.assertGreaterEqual(len(card["rows"]), len(card["items"]))


if __name__ == "__main__":
    unittest.main()
