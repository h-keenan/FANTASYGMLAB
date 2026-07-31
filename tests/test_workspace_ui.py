import unittest
import os
from pathlib import Path
from unittest.mock import Mock, patch

import app
from modules import workspace_ui


class TestWorkspaceUI(unittest.TestCase):
    def test_dashboard_hero_avoids_duplicate_league_identity(self):
        source = Path("modules/workspace_ui.py").read_text(encoding="utf-8")
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn("Dashboard Command", source)
        self.assertIn("Next Moves", source)
        self.assertIn("Priority roster, trade, waiver, and draft signals", source)
        self.assertIn("Power Rank", source)
        self.assertIn("Franchise Rank", source)
        self.assertIn("Team Direction", source)
        self.assertIn("Health Status", source)
        self.assertIn(".home-hero-logo-command", css)
        self.assertIn("display: none !important", css)
        self.assertIn("grid-template-columns: 1fr !important", css)
        self.assertNotIn("DynastyGM Command Center", source)

    def test_debug_renderers_are_hidden_without_debug_flag(self):
        with (
            patch.dict(os.environ, {}, clear=False),
            patch.object(workspace_ui.st, "expander") as expander,
        ):
            os.environ.pop("DYNASTYGM_DEBUG_UI", None)
            workspace_ui.render_roster_utility_debug(
                [{"player_name": "Hidden Player"}]
            )

        expander.assert_not_called()

    def test_debug_renderers_are_available_with_debug_flag(self):
        class Context:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with (
            patch.dict(os.environ, {"DYNASTYGM_DEBUG_UI": "1"}),
            patch.object(
                workspace_ui.st,
                "expander",
                return_value=Context(),
            ) as expander,
            patch.object(workspace_ui.st, "dataframe"),
        ):
            workspace_ui.render_roster_utility_debug(
                [{"player_name": "Visible Player"}]
            )

        expander.assert_called_once()

    def test_direct_workspace_helpers_are_exposed_through_app(self):
        self.assertIs(app.render_section_header, workspace_ui.render_section_header)
        self.assertIs(app.render_summary_tiles, workspace_ui.render_summary_tiles)
        self.assertIs(app.render_analysis_cards, workspace_ui.render_analysis_cards)
        self.assertIs(
            app.render_roster_utility_debug,
            workspace_ui.render_roster_utility_debug,
        )

    def test_summary_tiles_preserve_html_rendering(self):
        with (
            patch.object(
                workspace_ui,
                "SUMMARY_TILE_TAP_COMPONENT",
                side_effect=ValueError("Component 'summary_tile_tap_grid' is not registered"),
            ),
            patch.object(workspace_ui.st, "markdown") as markdown,
        ):
            workspace_ui.render_summary_tiles(
                [
                    {
                        "label": "Power Rank",
                        "value": "#2",
                        "note": "Strong contender",
                        "tone": "power",
                    }
                ]
            )

        html = markdown.call_args.args[0]
        self.assertIn("summary-tile-grid", html)
        self.assertIn("summary-tile-power", html)
        self.assertIn("summary-tile-tappable", html)
        self.assertIn("summary-tile-affordance", html)
        self.assertIn("Power Rank", html)
        self.assertTrue(markdown.call_args.kwargs["unsafe_allow_html"])

    def test_summary_tile_tap_opens_detail_dialog(self):
        with (
            patch.object(
                workspace_ui,
                "SUMMARY_TILE_TAP_COMPONENT",
                return_value=type("Result", (), {"clicked": {"index": "0"}})(),
            ),
            patch.object(workspace_ui, "_render_summary_tile_detail_dialog") as dialog,
        ):
            workspace_ui.render_summary_tiles(
                [
                    {
                        "label": "Franchise Rank",
                        "value": "#3",
                        "note": "Young roster with draft capital.",
                        "tone": "franchise",
                    }
                ]
            )
        dialog.assert_called_once()
        self.assertEqual(dialog.call_args.args[0]["label"], "Franchise Rank")

    def test_summary_tile_component_key_uses_stable_digest_and_explicit_context(self):
        component = Mock(return_value=Mock(clicked=None))
        with patch.object(workspace_ui, "SUMMARY_TILE_TAP_COMPONENT", component):
            workspace_ui.render_summary_tiles(
                [{"label": "Same", "value": "Value", "note": "Note"}],
                key_prefix="dashboard_primary",
            )
            workspace_ui.render_summary_tiles(
                [{"label": "Same", "value": "Value", "note": "Note"}],
                key_prefix="trade_hub_primary",
            )

        keys = [call.kwargs["key"] for call in component.call_args_list]
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2)
        self.assertTrue(all(key.startswith("summary_tile_tap_") for key in keys))

    def test_summary_tile_detail_helper_renders_explanation(self):
        html = workspace_ui.summary_tile_detail_html(
            {
                "label": "Health Outlook",
                "value": "Monitor",
                "note": "Two injured starters.",
            }
        )

        self.assertIn("summary-detail-panel", html)
        self.assertIn("Health Outlook", html)
        self.assertIn("Monitor", html)
        self.assertIn("Availability outlook", html)

    def test_summary_tile_detail_helper_renders_rank_context_and_current_marker(self):
        html = workspace_ui.summary_tile_detail_html(
            {
                "label": "Power Rank",
                "value": "#4",
                "note": "Current strength.",
                "detail_items_title": "Current Power Board",
                "detail_items": [
                    {"title": "Team A", "value": "#1", "note": "Score 101"},
                    {"title": "Diddy's Lube Crew", "value": "#4", "note": "Score 88", "current": True},
                    {"title": "Team E", "value": "#5", "note": "Score 84"},
                ],
            }
        )

        self.assertIn("Current Power Board", html)
        self.assertIn("Team A", html)
        self.assertIn("Diddy&#x27;s Lube Crew", html)
        self.assertIn("summary-detail-list-row-current", html)
        self.assertIn("#4", html)

    def test_summary_tile_detail_fallback_adds_useful_context(self):
        html = workspace_ui.summary_tile_detail_html(
            {
                "label": "Unknown Metric",
                "value": "Summary",
            }
        )

        self.assertIn("What It Means", html)
        self.assertIn("existing analysis", html)

    def test_structured_decision_wrapper_keeps_player_card_dependency_in_app(self):
        with (
            patch.object(
                app,
                "_player_scan_card_html",
                return_value="<div class='scan-card'>Player</div>",
            ) as player_card,
            patch.object(
                app,
                "_compact_player_row_html",
                return_value="<div class='compact-player-row'>Player</div>",
            ) as compact_row,
            patch.object(workspace_ui.st, "markdown") as markdown,
        ):
            app.render_structured_decision_cards(
                [
                    {
                        "title": "Best Drop Candidates",
                        "label": "Roster Pressure",
                        "tone": "risk",
                        "candidates": [
                            {
                                "name": "Test Player",
                                "bucket": "drop",
                                "reason": "Lowest utility roster spot.",
                                "score": 12,
                            }
                        ],
                    }
                ]
            )

        player_card.assert_not_called()
        self.assertEqual(compact_row.call_count, 1)
        self.assertEqual(compact_row.call_args.kwargs["status_label"], "Drop Candidate")
        html = markdown.call_args.args[0]
        self.assertIn("decision-panel-grid", html)
        self.assertIn("compact-player-row", html)
        self.assertTrue(markdown.call_args.kwargs["unsafe_allow_html"])

    def test_home_command_player_tiles_use_compact_row_builder(self):
        player_row = {
            "player_id": "player-1",
            "name": "Test Player",
            "position": "WR",
            "team": "DAL",
            "age": 24,
            "value_score": 71,
        }
        scan_card = Mock(return_value="<div class='scan-card'>Old</div>")
        compact_row = Mock(return_value="<div class='compact-player-row' data-player-id='player-1'>Row</div>")
        with patch.object(workspace_ui.st, "markdown") as markdown:
            workspace_ui.render_home_command_tiles(
                [
                    {
                        "label": "Top Waiver Opportunity",
                        "note": "Best fit.",
                        "tone": "waiver",
                        "player_row": player_row,
                        "recommendation_label": "Priority Add",
                        "score_field": "value_score",
                    }
                ],
                player_scan_card_html=scan_card,
                compact_player_row_html=compact_row,
            )

        compact_row.assert_called_once()
        scan_card.assert_not_called()
        html = markdown.call_args.args[0]
        self.assertIn("home-command-player-card", html)
        self.assertIn("compact-player-row", html)
        self.assertTrue(markdown.call_args.kwargs["unsafe_allow_html"])

    def test_home_trade_opportunity_card_exposes_trade_hub_route(self):
        player_row = {
            "player_id": "target-1",
            "name": "Trade Target",
            "position": "WR",
            "team": "DAL",
            "age": 24,
            "value_score": 81,
        }
        compact_row = Mock(return_value="<div class='compact-player-row' data-player-id='target-1'>Target</div>")
        with patch.object(workspace_ui.st, "markdown") as markdown:
            workspace_ui.render_home_command_tiles(
                [
                    {
                        "label": "Top Trade Opportunity",
                        "note": "Best path.",
                        "tone": "trade",
                        "player_row": player_row,
                        "recommendation_label": "Trade Target",
                        "score_field": "value_score",
                        "route_key": "trade_hub",
                        "route_player_id": "target-1",
                        "route_focus_mode": "target_player",
                    }
                ],
                player_scan_card_html=Mock(return_value=""),
                compact_player_row_html=compact_row,
            )

        html = markdown.call_args.args[0]
        self.assertIn("home-command-route-card", html)
        self.assertIn("data-route='trade_hub'", html)
        self.assertIn("data-route-player-id='target-1'", html)
        self.assertIn("data-route-focus-mode='target_player'", html)
        self.assertIn("Open in Trade Hub", html)

    def test_home_trade_route_click_calls_route_callback(self):
        route_callback = Mock()
        with patch.object(
            workspace_ui,
            "st",
        ):
            workspace_ui.render_home_command_tiles(
                [
                    {
                        "label": "Top Trade Opportunity",
                        "note": "Best path.",
                        "tone": "trade",
                        "player_row": {"player_id": "target-1", "name": "Trade Target"},
                        "recommendation_label": "Trade Target",
                        "route_key": "trade_hub",
                        "route_player_id": "target-1",
                        "route_focus_mode": "target_player",
                    }
                ],
                player_scan_card_html=Mock(return_value=""),
                compact_player_row_html=Mock(return_value="<div class='compact-player-row' data-player-id='target-1'>Target</div>"),
                render_interactive_html=Mock(
                    return_value={
                        "route": "trade_hub",
                        "player_id": "target-1",
                        "focus_mode": "target_player",
                    }
                ),
                open_route_action=route_callback,
            )

        route_callback.assert_called_once_with(
            "trade_hub",
            player_id="target-1",
            focus_mode="target_player",
            source_label="Top Trade Opportunity",
            source_note="Best path.",
        )

    def test_dashboard_mobile_hierarchy_collapses_secondary_league_pulse(self):
        source = Path("app.py").read_text(encoding="utf-8")

        next_moves_idx = source.index('"Next Moves"')
        command_tiles_idx = source.index("render_home_command_tiles(visible_action_items)")
        quick_actions_idx = source.index("render_home_quick_actions", command_tiles_idx)
        league_pulse_idx = source.index('with st.expander("League Pulse"', quick_actions_idx)

        self.assertLess(next_moves_idx, command_tiles_idx)
        self.assertLess(command_tiles_idx, quick_actions_idx)
        self.assertLess(quick_actions_idx, league_pulse_idx)
        self.assertIn("visible_action_items = action_center_items if is_premium else action_center_items[:4]", source)
        self.assertIn("Full Next Moves", source)
        self.assertIn("render_summary_tiles(", source)
        self.assertIn("league_pulse_items,", source)
        self.assertIn(
            "workspace_ui.render_canonical_summary_tile_detail_dialog",
            source,
        )
        self.assertIn("Expanded League Pulse", source)

    def test_dashboard_labels_do_not_use_stale_action_center_copy(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('"Next Moves"', source)
        self.assertNotIn(">Action Center<", source)

    def test_mobile_gm_nav_has_overlap_safe_padding_and_bottom_left_anchor(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn("padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 13.8rem)", css)
        self.assertIn("bottom: max(16px, env(safe-area-inset-bottom))", css)
        self.assertIn("left: max(16px, env(safe-area-inset-left))", css)
        self.assertIn("min-height: 34px", css)
        self.assertIn("min-width: 44px", css)
        self.assertIn("height: auto !important", css)
        self.assertIn("overflow: visible !important", css)
        self.assertIn("border-radius: 0 2px 2px 0", css)

    def test_dashboard_espn_limited_mode_has_degraded_state(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('"ESPN limited review mode"', source)
        self.assertIn("st.session_state.get(\"active_platform\") == \"espn\"", source)
        self.assertIn("st.session_state.get(\"espn_limited_mode\")", source)
        self.assertIn("app-degraded-state", source)
        self.assertIn("Sleeper remains the full Dashboard path", source)


if __name__ == "__main__":
    unittest.main()
