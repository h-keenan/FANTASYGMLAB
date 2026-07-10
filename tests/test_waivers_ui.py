import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import app
from modules import waivers_ui


class TestWaiversUI(unittest.TestCase):
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
        self.assertIn("app-section-title", header_html)

    def test_waiver_copy_and_avatar_polish_markers_are_present(self):
        rankings_source = Path("modules/rankings.py").read_text(encoding="utf-8")
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn("_append_display_sentence", rankings_source)
        self.assertNotIn("alive Player", rankings_source)
        self.assertNotIn("role Player", rankings_source)
        self.assertIn(".free-agent-avatar", css)
        self.assertIn("--avatar-size: 56px !important", css)
        self.assertIn("--avatar-size: 48px !important", css)
        self.assertIn("border-radius: 3px !important", css)
        self.assertIn("object-position: center 42% !important", css)

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
