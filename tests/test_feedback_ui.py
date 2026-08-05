import unittest
import re
from pathlib import Path
from unittest.mock import Mock, patch

from modules import feedback_ui


class _ContextManager:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class TestFeedbackUI(unittest.TestCase):
    def test_feedback_key_root_preserves_existing_key_rules(self):
        self.assertEqual(
            feedback_ui.feedback_key_root("Trade Hub / Player One"),
            "Trade_Hub_Player_One",
        )
        self.assertEqual(
            feedback_ui.feedback_key_root(""),
            "recommendation_feedback",
        )

    def test_submitted_form_builds_and_writes_same_payload(self):
        build_report = Mock(return_value={"report_id": "fixture"})
        append_report = Mock(return_value=(True, ""))

        with (
            patch.object(feedback_ui.st, "container", return_value=_ContextManager()),
            patch.object(feedback_ui.st, "markdown"),
            patch.object(feedback_ui.st, "popover", return_value=_ContextManager()),
            patch.object(feedback_ui.st, "caption") as caption,
            patch.object(feedback_ui.st, "form", return_value=_ContextManager()) as form,
            patch.object(
                feedback_ui.st,
                "selectbox",
                return_value="Looks wrong",
            ) as selectbox,
            patch.object(
                feedback_ui.st,
                "text_area",
                return_value="The recommendation feels stale.",
            ) as text_area,
            patch.object(
                feedback_ui.st,
                "form_submit_button",
                return_value=True,
            ),
            patch.object(feedback_ui.st, "success") as success,
        ):
            with patch.object(feedback_ui, "ENABLE_INLINE_RECOMMENDATION_FEEDBACK", True):
                feedback_ui.render_feedback_form(
                    page="trade_hub",
                    surface="Trade Hub Trade Idea",
                    recommendation_type="trade_idea",
                    key_prefix="trade feedback",
                    username="fixture_user",
                    league_id="league-1",
                    league_name="Fixture League",
                    team_id="team-2",
                    roster_id="7",
                    player_ids=["player-1"],
                    player_names=["Player One"],
                    recommendation_title="Test trade",
                    recommendation_summary="Synthetic recommendation.",
                    score_fields={"trade_gain": 25},
                    confidence_fields={"confidence": "Medium"},
                    reason_fields={"reason": "Roster fit"},
                    build_feedback_report=build_report,
                    append_feedback_report=append_report,
                )

        caption.assert_called_once_with(
            "Flag a recommendation that looks wrong, confusing, stale, or untrustworthy."
        )
        form.assert_called_once_with("trade_feedback_form", clear_on_submit=True)
        selectbox.assert_called_once_with(
            "Issue",
            list(feedback_ui.ISSUE_CATEGORIES),
            key="trade_feedback_category",
        )
        text_area.assert_called_once_with(
            "What looks wrong?",
            placeholder="Optional context for the FantasyGM Lab team",
            max_chars=1000,
            key="trade_feedback_comment",
        )
        build_report.assert_called_once_with(
            page="trade_hub",
            surface="Trade Hub Trade Idea",
            recommendation_type="trade_idea",
            username="fixture_user",
            league_id="league-1",
            league_name="Fixture League",
            team_id="team-2",
            roster_id="7",
            player_ids=["player-1"],
            player_names=["Player One"],
            recommendation_title="Test trade",
            recommendation_summary="Synthetic recommendation.",
            score_fields={"trade_gain": 25},
            confidence_fields={"confidence": "Medium"},
            reason_fields={"reason": "Roster fit"},
            issue_category="Looks wrong",
            user_comment="The recommendation feels stale.",
        )
        append_report.assert_called_once_with({"report_id": "fixture"})
        success.assert_called_once_with("Report submitted.")

    def test_inline_recommendation_feedback_is_disabled_by_default(self):
        with (
            patch.object(feedback_ui.st, "container") as container,
            patch.object(feedback_ui.st, "popover") as popover,
        ):
            feedback_ui.render_feedback_form(
                page="trade_hub",
                surface="Trade Hub Trade Idea",
                recommendation_type="trade_idea",
                key_prefix="hidden feedback",
                build_feedback_report=Mock(),
                append_feedback_report=Mock(),
            )

        container.assert_not_called()
        popover.assert_not_called()

    def test_global_feedback_button_builds_context_report(self):
        build_report = Mock(return_value={"report_id": "global", "category": "Billing or Premium", "message": "Lock still appears.", "feedback_type": "global", "context": {"page": "dashboard"}})
        append_report = Mock(return_value=(True, ""))
        context = {"page": "dashboard", "league_id": "league-1", "entitlement": "premium"}

        with (
            patch.object(feedback_ui.st, "container", return_value=_ContextManager()),
            patch.object(feedback_ui.st, "markdown"),
            patch.object(feedback_ui.st, "popover", return_value=_ContextManager()),
            patch.object(feedback_ui.st, "caption"),
            patch.object(feedback_ui.st, "form", return_value=_ContextManager()) as form,
            patch.object(feedback_ui.st, "selectbox", return_value="Billing or Premium") as selectbox,
            patch.object(feedback_ui.st, "text_area", return_value="Lock still appears.") as text_area,
            patch.object(feedback_ui.st, "text_input", return_value="user@example.com") as text_input,
            patch.object(feedback_ui.st, "checkbox", return_value=True) as checkbox,
            patch.object(feedback_ui.st, "form_submit_button", return_value=True),
            patch.object(feedback_ui.st, "success") as success,
            patch.object(feedback_ui.st, "session_state", {}, create=True),
        ):
            feedback_ui.st.session_state = {}
            feedback_ui.render_global_feedback_button(
                context=context,
                build_global_feedback_report=build_report,
                append_feedback_report=append_report,
                default_email="user@example.com",
            )

        form.assert_called_once_with("global_feedback_form", clear_on_submit=True)
        selectbox.assert_called_once()
        self.assertEqual(selectbox.call_args.args[1], list(feedback_ui.GLOBAL_FEEDBACK_CATEGORIES))
        text_area.assert_called_once()
        text_input.assert_called_once()
        checkbox.assert_called_once()
        build_report.assert_called_once_with(
            category="Billing or Premium",
            message="Lock still appears.",
            context=context,
            email="user@example.com",
            can_contact=True,
        )
        append_report.assert_called_once_with(build_report.return_value)
        success.assert_called_once_with(
            "Feedback submitted. Thank you — the Founder Beta team will review it."
        )

    def test_global_feedback_shell_is_bottom_right_and_distinct_from_gm(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("_global_feedback_control", css)
        self.assertIn("right: calc(0.85rem + env(safe-area-inset-right))", css)
        self.assertIn("bottom: calc(0.85rem + env(safe-area-inset-bottom))", css)
        self.assertIn("right: max(16px, env(safe-area-inset-right))", css)
        self.assertIn("bottom: max(16px, env(safe-area-inset-bottom))", css)
        self.assertIn("pointer-events: none !important", css)
        self.assertIn("pointer-events: auto !important", css)
        self.assertIn("width: max-content !important", css)
        self.assertIn("z-index: 1000990", css)
        self.assertIn("mobile_gm_sheet_trigger_", css)
        self.assertIn("mobile-gm-floating-trigger-marker", css)
        self.assertNotIn("mobile_gm_command_menu_", css)
        self.assertIn("z-index: 1001000", css)
        self.assertIn("render_global_feedback_entry(", app_source)
        self.assertIn("feedback_context_payload(", app_source)
        self.assertIn("build_global_feedback_report", app_source)
        self.assertIn("Feedback", Path("modules/feedback_ui.py").read_text(encoding="utf-8"))
        self.assertIn('content: "Report"', css)
        self.assertIn('body:has(div[data-testid="stDialog"]) div[class*="st-key-"][class*="_global_feedback_control"]', css)
        self.assertIn("width: 54px !important", css)

    def test_floating_controls_do_not_use_full_width_hitboxes(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")
        feedback_blocks = re.findall(r'div\[class\*="st-key-"\]\[class\*="_global_feedback_control"\] \{([^}]*)\}', css)
        gm_blocks = re.findall(r'div\[class\*="st-key-mobile_gm_sheet_trigger_"\] \{([^}]*)\}', css)
        marker_blocks = re.findall(
            r'div\[data-testid="stVerticalBlock"\]:has\(> div\[data-testid="stElementContainer"\] \.mobile-gm-floating-trigger-marker\),\s*div\[class\*="st-key-mobile_gm_sheet_trigger_"\] \{([^}]*)\}',
            css,
        )
        feedback_block = next(block for block in feedback_blocks if "pointer-events: none" in block)
        gm_block = marker_blocks[0] if marker_blocks else next(block for block in gm_blocks if "pointer-events: auto" in block)

        self.assertIn("pointer-events: none", feedback_block)
        self.assertIn("width: max-content", feedback_block)
        self.assertIn("left: auto", feedback_block)
        self.assertIn("right: max(16px, env(safe-area-inset-right))", feedback_block)
        self.assertIn("pointer-events: auto", gm_block)
        self.assertIn("width: max-content", gm_block)
        self.assertIn("left: max(16px, env(safe-area-inset-left))", gm_block)
        self.assertIn("bottom: max(16px, env(safe-area-inset-bottom))", gm_block)
        self.assertIn("height: auto", gm_block)
        self.assertIn("overflow: visible", gm_block)
        self.assertNotIn("display: none !important", gm_block)


if __name__ == "__main__":
    unittest.main()
