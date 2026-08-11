import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import app
from modules import waivers_ui


class TestWaiversUI(unittest.TestCase):
    @staticmethod
    def _render_card(row):
        tap_renderer = Mock(return_value="")
        quick_view = Mock()
        waivers_ui.render_free_agent_cards(
            pd.DataFrame([row]),
            "value_score",
            recommendation_reason_text=lambda value, _limit: str(value),
            player_display_name=lambda value: value.get("name"),
            cached_headshot_data_url=lambda _player_id: "",
            asset_initials=lambda _name: "P",
            player_status_style=lambda label: {
                "label": label,
                "tone": "neutral",
            },
            canonical_player_status=lambda value: str(value),
            tier_chip_html=lambda _value: "",
            player_support_chip_html=lambda _value, _tone: "",
            player_status_pill_html=lambda value: f"<span>{value}</span>",
            render_tappable_player_html=tap_renderer,
            open_player_quick_view=quick_view,
            render_recommendation_feedback=Mock(),
        )
        return tap_renderer.call_args.kwargs["html"], tap_renderer, quick_view

    def test_waiver_cards_use_one_section_level_feedback_control(self):
        free_agents = pd.DataFrame(
            [
                {
                    "player_id": f"player-{index}",
                    "name": f"Player {index}",
                    "position": "RB",
                    "team": "DAL",
                    "age": 24,
                    "value_score": 70 - index,
                    "market_score": 60,
                    "opportunity_score": 55,
                    "position_rank": index + 1,
                    "stale_free_agent": False,
                }
                for index in range(3)
            ]
        )
        feedback = Mock()

        tap_renderer = Mock(return_value="")
        waivers_ui.render_free_agent_cards(
            free_agents,
            "value_score",
            recommendation_reason_text=lambda value, _limit: str(value),
            player_display_name=lambda row: row.get("name"),
            cached_headshot_data_url=lambda _player_id: "",
            asset_initials=lambda _name: "P",
            player_status_style=lambda label: {
                "label": label,
                "tone": "neutral",
            },
            canonical_player_status=lambda value: str(value),
            tier_chip_html=lambda _value: "",
            player_support_chip_html=lambda _value, _tone: "",
            player_status_pill_html=lambda value: f"<span>{value}</span>",
            render_tappable_player_html=tap_renderer,
            open_player_quick_view=Mock(),
            render_recommendation_feedback=feedback,
        )

        html = tap_renderer.call_args.kwargs["html"]
        self.assertIn("player-position-badge", html)
        self.assertIn(">RB<", html)
        self.assertIn("DAL · Age 24", html)
        self.assertNotIn("RB | DAL | Age 24", html)
        feedback.assert_called_once()
        self.assertEqual(
            feedback.call_args.kwargs["recommendation_title"],
            "Waiver recommendation board",
        )

    def test_top_waiver_suppresses_kicker_when_roster_has_viable_kicker(self):
        free_agents = pd.DataFrame(
            [
                {"player_id": "k-2", "name": "Top Kicker", "position": "K", "value_score": 90},
                {"player_id": "rb-1", "name": "Upside Back", "position": "RB", "value_score": 60},
            ]
        )
        roster = pd.DataFrame(
            [
                {
                    "player_id": "k-1",
                    "name": "Roster Kicker",
                    "position": "K",
                    "team": "DAL",
                    "status": "Active",
                    "injury_status": "",
                }
            ]
        )

        selected = waivers_ui.select_top_waiver_opportunity(
            free_agents,
            roster,
            {"k_count": 1},
            "value_score",
        )

        self.assertEqual(selected["player_id"], "rb-1")

    def test_top_waiver_allows_kicker_for_clear_required_lineup_need(self):
        free_agents = pd.DataFrame(
            [
                {"player_id": "k-2", "name": "Top Kicker", "position": "K", "value_score": 90},
                {"player_id": "rb-1", "name": "Upside Back", "position": "RB", "value_score": 60},
            ]
        )

        selected = waivers_ui.select_top_waiver_opportunity(
            free_agents,
            pd.DataFrame(
                [{"player_id": "rb-0", "position": "RB", "team": "DAL"}]
            ),
            {"k_count": 1},
            "value_score",
        )

        self.assertEqual(selected["player_id"], "k-2")
        self.assertTrue(selected["kicker_need_fit"])
        self.assertIn("requires a kicker", selected["injury_replacement_note"])

    def test_top_waiver_does_not_choose_qb_or_te_without_true_need(self):
        free_agents = pd.DataFrame(
            [
                {"player_id": "te-1", "name": "Tight End", "position": "TE", "value_score": 90},
                {"player_id": "qb-1", "name": "Quarterback", "position": "QB", "value_score": 85},
                {"player_id": "rb-1", "name": "Running Back", "position": "RB", "value_score": 60},
            ]
        )

        selected = waivers_ui.select_top_waiver_opportunity(
            free_agents,
            pd.DataFrame(),
            {"k_count": 0},
            "value_score",
            needed_positions=["RB"],
        )

        self.assertEqual(selected["player_id"], "rb-1")

    def test_priority_badge_is_exposed_through_app(self):
        self.assertIs(
            app.free_agent_priority_badge,
            waivers_ui.free_agent_priority_badge,
        )
        self.assertEqual(
            app.free_agent_priority_badge(
                {"score": 80, "stale_free_agent": False},
                1,
            )[0],
            "Best Available",
        )
        self.assertEqual(
            app.free_agent_priority_badge(
                {"score": 0, "stale_free_agent": True},
                1,
            )[0],
            "Deprioritized",
        )

    def test_reason_wrapper_preserves_roster_need_context(self):
        reason = app.free_agent_reason_text(
            {
                "position": "WR",
                "score": 70,
                "age": 25,
                "stale_free_agent": False,
            },
            4,
            "Value Score",
            needed_positions=["WR"],
        )

        self.assertIn("Matches your current WR need", reason)

    def test_summary_cards_render_html(self):
        free_agents = pd.DataFrame(
            [
                {
                    "player_id": "player-1",
                    "name": "Test Player",
                    "position": "WR",
                    "age": 24,
                    "value_score": 75,
                    "stale_free_agent": False,
                }
            ]
        )
        with patch.object(waivers_ui.st, "markdown") as markdown:
            waivers_ui.render_free_agent_summary_cards(
                free_agents,
                "value_score",
                player_display_name=lambda row: row.get("name"),
            )

        html = markdown.call_args.args[0]
        self.assertIn("free-agent-summary-grid", html)
        self.assertIn("Test Player", html)
        self.assertIn("Value Score: 75", html)
        self.assertIn("waiver-snapshot-avatar", html)
        self.assertTrue(markdown.call_args.kwargs["unsafe_allow_html"])

    def test_free_agent_card_wrapper_injects_app_callbacks(self):
        with patch.object(
            waivers_ui,
            "render_free_agent_cards",
        ) as render_cards:
            app.render_free_agent_cards(
                pd.DataFrame(),
                "value_score",
                key_prefix="test",
            )

        kwargs = render_cards.call_args.kwargs
        self.assertIs(
            kwargs["open_player_quick_view"],
            app.open_player_quick_view,
        )
        self.assertIs(
            kwargs["render_recommendation_feedback"],
            app.render_recommendation_feedback,
        )
        self.assertIs(
            kwargs["cached_headshot_data_url"],
            app.cached_headshot_data_url,
        )
        self.assertIs(
            kwargs["render_tappable_player_html"],
            app._render_tappable_player_html,
        )
        self.assertEqual(kwargs["key_prefix"], "test")

    def test_waiver_workspace_collapses_secondary_mobile_sections(self):
        source = Path("modules/waivers_ui.py").read_text(encoding="utf-8")

        priority_idx = source.index("Priority Adds")
        secondary_idx = source.index('with st.expander("Secondary waiver board", expanded=False):')
        detailed_idx = source.index('with st.expander("Detailed Table View", expanded=False):')

        self.assertLess(priority_idx, secondary_idx)
        self.assertLess(secondary_idx, detailed_idx)
        self.assertIn("Waiver Snapshot", source)
        self.assertIn("FAAB Shortlist", source)
        self.assertIn("waiver_section_header_html", source)
        self.assertNotIn("<span class='dg-semantic-icon' aria-hidden='true'>+</span>Waiver Snapshot", source)
        self.assertNotIn("<span class='dg-semantic-icon' aria-hidden='true'>+</span>Priority Adds", source)
        self.assertIn("Open this after checking the priority adds.", source)

        header_html = waivers_ui.waiver_section_header_html(
            "Priority Adds",
            kicker="Next Add",
            note="Start here.",
            preset="opportunity-list",
        )
        self.assertIn("dg-section-opportunity-list", header_html)
        self.assertIn("dg-ui-section-title", header_html)
        self.assertIn("<h2", header_html)

    def test_waiver_copy_and_avatar_polish_markers_are_present(self):
        rankings_source = Path("modules/rankings.py").read_text(encoding="utf-8")
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn("_append_display_sentence", rankings_source)
        self.assertNotIn("alive Player", rankings_source)
        self.assertNotIn("role Player", rankings_source)
        self.assertIn(".free-agent-avatar", css)
        self.assertIn("--avatar-size: 56px !important", css)
        self.assertIn("--avatar-size: 48px !important", css)
        self.assertIn("border-radius: var(--radius-pill) !important", css)
        self.assertIn("object-position: center 42% !important", css)

    def test_recommendation_card_uses_canonical_decision_hierarchy(self):
        html, _, _ = self._render_card(
            {
                "player_id": "player-1",
                "name": "A Very Long Waiver Target Name",
                "position": "WR",
                "team": "DAL",
                "age": 23,
                "value_score": 71,
                "position_rank": 4,
                "opportunity_label": "Backup With Upside",
                "opportunity_explanation": "Role could expand after a depth-chart change.",
                "opportunity_confidence": "Medium",
                "stale_free_agent": False,
            }
        )

        self.assertIn("dg-ui-card dg-ui-card--elevated", html)
        self.assertIn(">Stash<", html)
        self.assertIn("Role could expand after a depth-chart change.", html)
        self.assertIn("Medium confidence", html)
        self.assertIn("Review add →", html)
        self.assertNotIn("View Details", html)
        self.assertNotIn("Why now?", html)
        self.assertNotIn("Dynasty context", html)
        self.assertNotIn("waiver-context-grid", html)

    def test_recommendation_labels_do_not_mutate_or_reorder_input(self):
        frame = pd.DataFrame(
            [
                {
                    "player_id": "add",
                    "name": "Add Player",
                    "position": "RB",
                    "age": 27,
                    "position_rank": 1,
                    "value_score": 80,
                    "stale_free_agent": False,
                },
                {
                    "player_id": "watch",
                    "name": "Watch Player",
                    "position": "WR",
                    "age": 29,
                    "position_rank": 10,
                    "value_score": 50,
                    "stale_free_agent": True,
                },
            ]
        )
        original = frame.copy(deep=True)
        tap_renderer = Mock(return_value="")

        waivers_ui.render_free_agent_cards(
            frame,
            "value_score",
            recommendation_reason_text=lambda value, _limit: str(value),
            player_display_name=lambda value: value.get("name"),
            cached_headshot_data_url=lambda _player_id: "",
            asset_initials=lambda _name: "P",
            player_status_style=lambda label: {"label": label, "tone": "neutral"},
            canonical_player_status=lambda value: str(value),
            tier_chip_html=lambda _value: "",
            player_support_chip_html=lambda _value, _tone: "",
            player_status_pill_html=lambda _value: "",
            render_tappable_player_html=tap_renderer,
            open_player_quick_view=Mock(),
            render_recommendation_feedback=Mock(),
        )

        pd.testing.assert_frame_equal(frame, original)
        rendered = [call.kwargs["html"] for call in tap_renderer.call_args_list]
        self.assertIn(">Add<", rendered[0])
        self.assertIn(">Watch<", rendered[1])

    def test_card_escapes_player_and_context_content(self):
        html, _, _ = self._render_card(
            {
                "player_id": "safe-id",
                "name": "<script>alert(1)</script>",
                "position": "WR",
                "team": "FA",
                "age": 22,
                "value_score": 60,
                "position_rank": 8,
                "opportunity_label": "<b>Role</b>",
                "opportunity_explanation": "<img src=x onerror=alert(1)>",
                "stale_free_agent": False,
            }
        )

        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<b>Role</b>", html)

    def test_empty_board_uses_canonical_empty_state(self):
        with patch.object(
            waivers_ui.ui_primitives,
            "render_empty_state_panel",
        ) as empty_state:
            waivers_ui.render_free_agent_cards(
                pd.DataFrame(),
                "value_score",
                recommendation_reason_text=Mock(),
                player_display_name=Mock(),
                cached_headshot_data_url=Mock(),
                asset_initials=Mock(),
                player_status_style=Mock(),
                canonical_player_status=Mock(),
                tier_chip_html=Mock(),
                player_support_chip_html=Mock(),
                player_status_pill_html=Mock(),
                render_tappable_player_html=Mock(),
                open_player_quick_view=Mock(),
                render_recommendation_feedback=Mock(),
            )

        empty_state.assert_called_once()
        self.assertEqual(empty_state.call_args.args[0], "No waiver targets available")

    def test_waivers_styles_are_token_backed_and_mobile_safe(self):
        source = Path("modules/waivers_presentation_styles.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("var(--touch-target-min)", source)
        self.assertIn("@media (max-width: 700px)", source)
        self.assertIn("@media (max-width: 390px)", source)
        self.assertNotRegex(source, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotIn("rgb(", source)

    def test_page_header_is_owned_by_waivers_presentation_module(self):
        with patch.object(
            waivers_ui.ui_primitives,
            "render_section_header",
        ) as render_header:
            waivers_ui.render_waivers_page_header()

        render_header.assert_called_once_with(
            "Waivers & FAAB",
            eyebrow="Wire and Budget",
            subtitle=(
                "Best available adds, injury replacements, and a lightweight "
                "FAAB recommendation workflow."
            ),
            heading_level=2,
        )
        app_source = Path("app.py").read_text(encoding="utf-8")
        # Executive command bar owns the page title; do not restack Waivers chrome.
        self.assertNotIn("waivers_ui.render_waivers_page_header()", app_source)

    def test_waivers_faab_helper_is_collapsed_and_espn_limited_mode_is_gated(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('with st.expander("FAAB Helper", expanded=False):', source)
        self.assertIn("Use this after choosing a bid target", source)
        self.assertIn('"Waivers are gated for ESPN until free-agent', source)
        self.assertIn("st.session_state.get(\"active_platform\") == \"espn\"", source)
        self.assertIn("st.session_state.get(\"espn_limited_mode\")", source)
        self.assertIn("app-degraded-state", source)
        self.assertIn("Sleeper remains the full Waivers path", source)


if __name__ == "__main__":
    unittest.main()
