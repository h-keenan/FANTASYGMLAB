import unittest
from unittest.mock import patch

import pandas as pd

import app
from modules import draft_center_ui


class TestDraftCenterUI(unittest.TestCase):
    def test_direct_draft_helpers_are_exposed_through_app(self):
        self.assertIs(
            app._draft_rank_cutoffs,
            draft_center_ui._draft_rank_cutoffs,
        )
        self.assertIs(
            app._draft_posture_profile,
            draft_center_ui._draft_posture_profile,
        )
        self.assertIs(
            app.build_draft_decision_cards,
            draft_center_ui.build_draft_decision_cards,
        )
        self.assertIs(
            app.build_draft_partner_cards,
            draft_center_ui.build_draft_partner_cards,
        )

    def test_pick_rich_rebuilder_posture_is_preserved(self):
        posture = draft_center_ui._draft_posture_profile(
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
                    "first_rounders": 0,
                },
            ]
        )

        cards = draft_center_ui.build_draft_decision_cards(draft_workspace)

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

    def test_draft_dashboard_wrapper_forwards_app_owned_callbacks(self):
        with patch.object(
            draft_center_ui,
            "render_draft_capital_dashboard",
        ) as render_dashboard:
            app.render_draft_capital_dashboard(pd.DataFrame(), [])

        kwargs = render_dashboard.call_args.kwargs
        self.assertIs(kwargs["draft_year_columns"], app.draft_year_columns)
        self.assertIs(
            kwargs["render_draft_team_cards"],
            app.render_draft_team_cards,
        )
        self.assertIs(kwargs["team_tap_markup"], app._team_tap_markup)
        self.assertIs(
            kwargs["render_team_card_tap_grid"],
            app._render_team_card_tap_grid,
        )
        self.assertIs(
            kwargs["open_league_team_from_tap"],
            app._open_league_team_from_tap,
        )
        self.assertIs(kwargs["team_logo_html"], app.team_logo_html)


if __name__ == "__main__":
    unittest.main()
