import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

import app
import pandas as pd
from modules import league_workspace_ui


class TestLeagueWorkspaceUI(unittest.TestCase):
    def test_direct_league_helpers_are_exposed_through_app(self):
        self.assertIs(
            app._select_intelligence_row,
            league_workspace_ui._select_intelligence_row,
        )
        self.assertIs(
            app.render_team_rank_cards,
            league_workspace_ui.render_team_rank_cards,
        )
        self.assertIs(
            app.build_team_partner_context_tiles,
            league_workspace_ui.build_team_partner_context_tiles,
        )
        self.assertIs(
            app.render_archetype_summary,
            league_workspace_ui.render_archetype_summary,
        )
        self.assertIs(
            app.league_score_label,
            league_workspace_ui.league_score_label,
        )

    def test_intelligence_renderer_uses_injected_team_navigation(self):
        render_tap_grid = Mock(return_value={})
        open_team = Mock(return_value=False)
        with patch.object(league_workspace_ui.st, "rerun") as rerun:
            league_workspace_ui.render_league_intelligence_cards(
                [
                    {
                        "label": "Strongest Contender",
                        "roster_id": "12",
                        "team_name": "Test Team",
                        "owner_handle": "@owner",
                        "avatar_url": "",
                        "metric": "Starter score 100",
                        "note": "Best weekly lineup punch.",
                    }
                ],
                team_tap_markup=lambda row: (
                    " team-card-tappable",
                    " data-roster-id='12'",
                ),
                render_team_card_tap_grid=render_tap_grid,
                open_league_team_from_tap=open_team,
                team_logo_html=lambda *args, **kwargs: (
                    "<div class='intel-logo-wrap'>TT</div>"
                ),
            )

        html = render_tap_grid.call_args.kwargs["html"]
        self.assertIn("intelligence-grid", html)
        self.assertIn("team-card-tappable", html)
        self.assertIn("Strongest Contender", html)
        self.assertIn("Test Team", html)
        open_team.assert_called_once_with({})
        rerun.assert_not_called()

    def test_team_header_wrapper_preserves_html_rendering(self):
        with patch.object(league_workspace_ui.st, "markdown") as markdown:
            app.render_league_team_page_header(
                {
                    "team_name": "Test Team",
                    "owner_name": "Test Owner",
                    "username": "owner",
                    "avatar_url": "",
                },
                "Test League",
            )

        html = markdown.call_args.args[0]
        self.assertIn("league-team-page", html)
        self.assertIn("Test Team", html)
        self.assertIn("@owner", html)
        self.assertTrue(markdown.call_args.kwargs["unsafe_allow_html"])

    def test_prepared_team_workspace_preserves_own_team_handoff(self):
        handoff = Mock()
        player_cards = Mock()
        with (
            patch.object(league_workspace_ui, "render_league_team_page_header"),
            patch.object(league_workspace_ui, "render_team_rank_cards"),
            patch.object(league_workspace_ui, "render_archetype_summary"),
            patch.object(league_workspace_ui, "render_manager_tendencies_summary"),
            patch.object(league_workspace_ui.st, "expander", return_value=nullcontext()),
        ):
            league_workspace_ui.render_league_team_workspace(
                team_profile={"team_name": "My Team"},
                selected_league_name="Test League",
                selected_team_summary={},
                selected_draft_row={},
                team_metrics={},
                league_size=12,
                is_my_roster_page=True,
                selected_league_id="league-1",
                selected_roster_id="7",
                health_label="",
                injured_starters=0,
                key_injuries="",
                advice_items=[],
                starters=pd.DataFrame(),
                bench=pd.DataFrame(),
                starters_display=pd.DataFrame(),
                bench_display=pd.DataFrame(),
                team_pick_rows=[],
                team_players=pd.DataFrame(),
                roster_table=pd.DataFrame(),
                roster_score_field="value_score",
                team_logo_html=Mock(),
                format_score=str,
                format_rank=str,
                render_summary_tiles=Mock(),
                render_workspace_handoff=handoff,
                render_team_score_details=Mock(),
                render_advice_cards=Mock(),
                render_player_scan_cards=player_cards,
            )

        self.assertEqual(
            handoff.call_args.kwargs["key_prefix"],
            "league_team_my_team_league-1_7",
        )
        self.assertEqual(handoff.call_args.kwargs["route_key"], "my_team")
        player_cards.assert_not_called()

    def test_prepared_team_workspace_preserves_other_team_card_keys(self):
        handoff = Mock()
        player_cards = Mock()
        player_df = pd.DataFrame(
            [{"player_id": "p1", "name": "Player", "value_score": 80}]
        )
        with (
            patch.object(league_workspace_ui, "render_league_team_page_header"),
            patch.object(league_workspace_ui, "render_team_rank_cards"),
            patch.object(league_workspace_ui, "render_archetype_summary"),
            patch.object(league_workspace_ui, "render_manager_tendencies_summary"),
            patch.object(league_workspace_ui.st, "tabs", return_value=(nullcontext(), nullcontext())),
            patch.object(league_workspace_ui.st, "expander", return_value=nullcontext()),
            patch.object(league_workspace_ui.st, "markdown"),
            patch.object(league_workspace_ui.st, "dataframe"),
        ):
            league_workspace_ui.render_league_team_workspace(
                team_profile={"team_name": "Other Team"},
                selected_league_name="Test League",
                selected_team_summary={},
                selected_draft_row={},
                team_metrics={},
                league_size=12,
                is_my_roster_page=False,
                selected_league_id="league-1",
                selected_roster_id="9",
                health_label="",
                injured_starters=0,
                key_injuries="",
                advice_items=[],
                starters=player_df,
                bench=player_df,
                starters_display=player_df,
                bench_display=player_df,
                team_pick_rows=[],
                team_players=player_df,
                roster_table=player_df,
                roster_score_field="value_score",
                team_logo_html=Mock(),
                format_score=str,
                format_rank=str,
                render_summary_tiles=Mock(),
                render_workspace_handoff=handoff,
                render_team_score_details=Mock(),
                render_advice_cards=Mock(),
                render_player_scan_cards=player_cards,
            )

        self.assertEqual(
            handoff.call_args.kwargs["key_prefix"],
            "league_team_trade_hub_league-1_9",
        )
        calls_by_title = {
            call.kwargs["title"]: call.kwargs
            for call in player_cards.call_args_list
        }
        self.assertEqual(
            calls_by_title["Starting Lineup"]["quick_view_key_prefix"],
            "league_team_starters_league-1_9",
        )
        self.assertEqual(
            calls_by_title["Bench and Depth"]["quick_view_source_label"],
            "League Overview - Team Bench",
        )
        self.assertEqual(
            calls_by_title["Roster Scan"]["quick_view_key_prefix"],
            "league_team_roster_league-1_9",
        )


if __name__ == "__main__":
    unittest.main()
