import json
import os
import tempfile
import unittest

from modules.feedback import (
    GLOBAL_FEEDBACK_CATEGORIES,
    append_feedback_report,
    build_feedback_report,
    build_global_feedback_report,
    feedback_context_payload,
)


class TestRecommendationFeedback(unittest.TestCase):
    def test_feedback_payload_and_jsonl_write(self):
        report = build_feedback_report(
            page="trade_hub",
            surface="Trade Hub Trade Idea",
            recommendation_type="trade_idea",
            username="fixture_user",
            league_id="league-1",
            roster_id="7",
            player_ids=["player-1", "player-2"],
            player_names=["Player One", "Player Two"],
            recommendation_title="Test trade",
            recommendation_summary="A synthetic regression fixture.",
            score_fields={"trade_gain": 125},
            confidence_fields={"confidence": "Medium"},
            reason_fields={"partner_reason": "Roster fit"},
            issue_category="Looks wrong",
            user_comment="The return feels light.",
            app_build="test-build",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "feedback.jsonl")
            saved, error = append_feedback_report(report, path, prefer_supabase=False)

            self.assertTrue(saved, error)
            with open(path, "r", encoding="utf-8") as handle:
                stored = json.loads(handle.readline())

        self.assertEqual(stored["status"], "new")
        self.assertEqual(stored["page"], "trade_hub")
        self.assertEqual(stored["league_id"], "league-1")
        self.assertEqual(stored["player_ids"], ["player-1", "player-2"])
        self.assertEqual(stored["score_fields"]["trade_gain"], 125)
        self.assertEqual(stored["user_comment"], "The return feels light.")
        self.assertEqual(stored["app_build"], "test-build")
        self.assertTrue(stored["report_id"])
        self.assertTrue(stored["timestamp"])

    def test_global_feedback_payload_captures_safe_context(self):
        context = feedback_context_payload(
            current_page="trade_hub",
            platform="Sleeper",
            league_id="league-1",
            league_name="Fixture League",
            team_id="team-1",
            roster_id="7",
            user_id="user-1",
            email="user@example.com",
            entitlement="premium",
            viewport_width=1024,
        )
        report = build_global_feedback_report(
            category="Bug or broken page",
            message="The page did not load.",
            context={**context, "access_token": "secret-token"},
            email="user@example.com",
            can_contact=True,
            app_build="test-build",
        )

        self.assertEqual(report["feedback_type"], "global")
        self.assertEqual(report["category"], "Bug or broken page")
        self.assertEqual(report["context"]["page"], "trade_hub")
        self.assertEqual(report["context"]["entitlement"], "premium")
        self.assertEqual(report["context"]["viewport_category"], "desktop")
        self.assertEqual(report["email"], "user@example.com")
        self.assertTrue(report["can_contact"])
        self.assertNotIn("access_token", report["context"])
        self.assertNotIn("email", report["context"])

    def test_global_feedback_categories_cover_beta_issue_types(self):
        self.assertIn("Bug or broken page", GLOBAL_FEEDBACK_CATEGORIES)
        self.assertIn("Confusing page", GLOBAL_FEEDBACK_CATEGORIES)
        self.assertIn("Bad recommendation", GLOBAL_FEEDBACK_CATEGORIES)
        self.assertIn("Feature request", GLOBAL_FEEDBACK_CATEGORIES)
        self.assertIn("Billing or Premium", GLOBAL_FEEDBACK_CATEGORIES)
        self.assertIn("Wrong player/team/league data", GLOBAL_FEEDBACK_CATEGORIES)
        self.assertIn("Other feedback", GLOBAL_FEEDBACK_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
