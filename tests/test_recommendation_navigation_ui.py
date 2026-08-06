import unittest
from unittest.mock import patch

import pandas as pd

import app


class TestRecommendationNavigationUI(unittest.TestCase):
    def test_team_tap_markup_requires_stable_roster_id(self):
        self.assertEqual(app._team_tap_markup({"team_name": "No ID"}), ("", ""))

        class_name, attributes = app._team_tap_markup(
            {"roster_id": "12", "team_name": "O'Brien's Team"}
        )

        self.assertEqual(class_name, " team-card-tappable")
        self.assertIn("data-roster-id='12'", attributes)
        self.assertIn("data-team-name='O&#x27;Brien&#x27;s Team'", attributes)

    def test_structured_candidate_retains_player_card_fields(self):
        candidate = app._build_structured_decision_candidate(
            pd.Series(
                {
                    "player_id": "player-1",
                    "name": "Test Player",
                    "position": "WR",
                    "team": "DAL",
                    "age": 24,
                    "player_tier": "Starter",
                    "value_score": 72,
                }
            ),
            bucket="drop",
            reason="Lowest utility roster spot.",
            priority=1,
        )

        self.assertEqual(candidate["player_id"], "player-1")
        self.assertEqual(candidate["age"], 24)
        self.assertEqual(candidate["player_tier"], "Starter")
        self.assertEqual(candidate["reason"], "Lowest utility roster spot.")

    def test_compact_recommendation_card_renders_reason_once(self):
        html = app._player_scan_card_html(
            {
                "player_id": "player-1",
                "name": "Test Player",
                "position": "WR",
                "team": "DAL",
                "age": 24,
                "value_score": 72,
                "player_tier": "Starter",
            },
            score_field="value_score",
            score_label="Value",
            status_label="Hold",
            note_text="Hold because opportunity is rising.",
            compact=True,
            show_inline_reason=True,
        )

        self.assertIn("scan-card-recommendation", html)
        self.assertEqual(html.count("Hold because opportunity is rising."), 1)

    def test_noncompact_scan_card_can_be_full_surface_tappable(self):
        html = app._player_scan_card_html(
            {
                "player_id": "player-2",
                "name": "League Player",
                "position": "RB",
                "team": "DAL",
                "age": 25,
                "value_score": 80,
                "player_tier": "Starter",
            },
            score_field="value_score",
            score_label="Value",
            status_label="Starter",
            interactive=True,
        )

        self.assertIn("scan-card-tappable", html)
        self.assertIn("data-player-id='player-2'", html)
        self.assertIn("role='button'", html)

    def test_other_team_scan_routes_tap_to_quick_view(self):
        player_df = pd.DataFrame(
            [
                {
                    "player_id": "player-3",
                    "name": "Other Team Player",
                    "position": "WR",
                    "team": "NYG",
                    "age": 24,
                    "value_score": 77,
                    "player_tier": "Starter",
                }
            ]
        )
        with (
            patch.object(
                app,
                "_render_tappable_player_html",
                return_value="player-3",
            ),
            patch.object(app, "open_player_quick_view") as open_quick_view,
        ):
            app.render_player_scan_cards(
                player_df,
                score_field="value_score",
                title="Roster Scan",
                note="Another team's roster.",
                enable_quick_view=True,
                quick_view_source_label="League Overview - Team Roster",
                quick_view_key_prefix="other_team_roster",
            )

        open_quick_view.assert_called_once_with(
            "player-3",
            source_label="League Overview - Team Roster",
            source_note="",
            status_label="",
            recommendation_narrative=None,
        )


if __name__ == "__main__":
    unittest.main()
