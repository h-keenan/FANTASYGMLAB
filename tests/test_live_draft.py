import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import live_draft
from modules.ui_architecture import current_platform_destinations


class TestLiveDraft(unittest.TestCase):
    def test_active_draft_discovery_prioritizes_drafting(self):
        drafts = [
            {"draft_id": "complete", "status": "complete", "season": "2026"},
            {"draft_id": "active", "status": "drafting", "season": "2026"},
            {"draft_id": "pre", "status": "pre_draft", "season": "2026"},
        ]
        result = live_draft.discover_live_drafts(
            "league-1",
            fetch_league_drafts=lambda league_id: drafts,
            fetch_draft=lambda draft_id: {"draft_id": draft_id, "settings": {"rounds": 4}},
        )

        self.assertEqual(result["active_draft"]["draft_id"], "active")
        self.assertEqual([draft["draft_id"] for draft in result["drafts"]][:2], ["active", "pre"])

    def test_only_drafting_or_paused_rooms_activate_production_workspace(self):
        self.assertTrue(live_draft.has_active_live_draft([{"status": "drafting"}]))
        self.assertTrue(live_draft.has_active_live_draft([{"status": "paused"}]))
        self.assertFalse(live_draft.has_active_live_draft([{"status": "pre_draft"}]))
        self.assertFalse(live_draft.has_active_live_draft([{"status": "complete"}]))

        visible = {
            page.key
            for page in current_platform_destinations(
                False,
                enabled_experimental=("live_draft",),
            )
        }
        self.assertIn("live_draft", visible)
        # Players graduated to CORE (#232) and is visible independently of Live Draft.
        self.assertIn("players", visible)
        # Trade Analyzer graduated as incoming-offer CORE surface.
        self.assertIn("trade_analyzer", visible)


    def test_drafted_players_are_excluded_from_available_pool(self):
        players = pd.DataFrame(
            [
                {"player_id": "p1", "name": "Drafted Player", "position": "WR", "active": True, "status": "Active", "fantasycalc_value": 99, "value_score": 99},
                {"player_id": "p2", "name": "Available Player", "position": "WR", "active": True, "status": "Active", "fantasycalc_value": 88, "value_score": 88},
            ]
        )
        pool = live_draft.available_player_pool(players, [{"player_id": "p1", "pick_no": 1}], score_field="value_score")

        self.assertEqual(pool["player_id"].tolist(), ["p2"])

    def test_current_user_slot_and_on_the_clock_detection(self):
        draft = {"status": "drafting", "draft_order": {"owner-a": 1, "owner-b": 2}, "settings": {"rounds": 2, "teams": 2}}
        rosters = [{"owner_id": "owner-a", "roster_id": 10}, {"owner_id": "owner-b", "roster_id": 20}]
        players = pd.DataFrame([{"player_id": "p2", "name": "Available", "position": "RB", "team": "NYG", "age": 22, "active": True, "status": "Active", "fantasycalc_value": 80, "value_score": 80}])

        state = live_draft.build_live_draft_state(
            draft=draft,
            picks=[],
            df_players=players,
            roster_df=pd.DataFrame(),
            roster_profiles={
                "10": {"team_name": "My Team", "owner_name": "Alex"},
                "20": {"team_name": "Other Team", "owner_name": "Jordan"},
            },
            rosters=rosters,
            my_roster_id=10,
            league_settings={"qb_format": "1QB"},
            score_field="value_score",
        )

        self.assertEqual(state["my_slot"], 1)
        self.assertTrue(state["is_my_pick"])
        self.assertEqual(state["picks_until_mine"], 0)
        self.assertEqual(state["current_round"], 1)
        self.assertEqual(state["current_manager_name"], "Alex")
        self.assertEqual(state["my_upcoming_picks"], [1, 4])

    def test_picks_until_next_selection_handles_snake(self):
        self.assertEqual(
            live_draft.picks_until_next_selection(current_pick=2, my_slot=1, team_count=3, rounds=2, snake=True),
            4,
        )

        self.assertEqual(
            live_draft.upcoming_selection_numbers(
                current_pick=2,
                my_slot=1,
                team_count=3,
                rounds=4,
                snake=True,
            ),
            [6, 7, 12],
        )

    def test_completed_draft_status_is_supported_and_pauses_polling_label(self):
        self.assertEqual(live_draft.normalize_draft_status("complete"), "complete")
        self.assertIn("complete", live_draft.LIVE_DRAFT_SUPPORTED_STATUSES)

    def test_api_failure_returns_degraded_state(self):
        picks, error = live_draft.fetch_sleeper_draft_picks("")

        self.assertEqual(picks, [])
        self.assertEqual(error, "draft_missing")

    def test_no_write_mutation_sleeper_methods_exist(self):
        source = Path("modules/live_draft.py").read_text(encoding="utf-8").casefold()

        for blocked in ("requests.post", "requests.put", "requests.patch", "requests.delete", "submit", "autopick", "queue", "message"):
            self.assertNotIn(blocked, source)
        self.assertEqual(live_draft.LIVE_DRAFT_WRITE_METHOD_TOKENS, ())

    def test_league_format_affects_recommendation_context_without_reordering_hidden_logic(self):
        players = pd.DataFrame(
            [
                {"player_id": "qb", "name": "Quarterback", "position": "QB", "team": "KC", "age": 23, "active": True, "status": "Active", "fantasycalc_value": 90, "value_score": 90},
                {"player_id": "rb", "name": "Running Back", "position": "RB", "team": "LV", "age": 22, "active": True, "status": "Active", "fantasycalc_value": 80, "value_score": 80},
            ]
        )
        roster = pd.DataFrame([{"position": "RB"}, {"position": "WR"}, {"position": "WR"}])
        recs = live_draft.build_live_draft_recommendations(
            players,
            roster_df=roster,
            league_settings={"qb_format": "Superflex"},
            score_field="value_score",
        )

        self.assertEqual(recs[0]["name"], "Quarterback")
        self.assertTrue(any(rec["label"] == "Best Fit" for rec in recs))

    def test_recommendation_briefing_reports_need_adp_confidence_and_impact(self):
        rankings = pd.DataFrame(
            [{
                "player_id": "p1", "name": "Best Player", "position": "RB", "team": "LV",
                "age": 23, "tier": "Star", "overall_rank": 1, "base_value": 90,
                "league_adjusted_draft_score": 96, "roster_fit_score": 4,
                "recommendation_reason": "Best combination of value and roster fit.", "adp": 8,
            }]
        )
        briefing = live_draft.build_recommendation_briefings(
            rankings,
            roster_needs=["RB"],
        )[0]

        self.assertEqual(briefing["recommendation_role"], "Recommended pick")
        self.assertEqual(briefing["adp_delta"], 7.0)
        self.assertEqual(briefing["confidence"], "High")
        self.assertEqual(briefing["position_need_impact"], "Fills RB need")
        self.assertIn("thin RB room", briefing["immediate_roster_impact"])

    def test_missing_adp_is_reported_as_missing_not_fabricated(self):
        rankings = pd.DataFrame(
            [{
                "player_id": "p1", "name": "Best Player", "position": "WR",
                "overall_rank": 1, "base_value": 90, "league_adjusted_draft_score": 91,
            }]
        )
        briefing = live_draft.build_recommendation_briefings(rankings, roster_needs=[])[0]
        self.assertIsNone(briefing["adp"])
        self.assertIsNone(briefing["adp_delta"])

    def test_fully_covered_roster_has_no_live_draft_position_need(self):
        roster = pd.DataFrame(
            [{"position": "QB"} for _ in range(2)]
            + [{"position": "RB"} for _ in range(5)]
            + [{"position": "WR"} for _ in range(6)]
            + [{"position": "TE"} for _ in range(2)]
        )
        players = pd.DataFrame(
            [
                {
                    "player_id": "qb",
                    "name": "Quarterback",
                    "position": "QB",
                    "team": "KC",
                    "age": 23,
                    "active": True,
                    "status": "Active",
                    "fantasycalc_value": 90,
                    "value_score": 90,
                },
                {
                    "player_id": "wr",
                    "name": "Wide Receiver",
                    "position": "WR",
                    "team": "MIN",
                    "age": 22,
                    "active": True,
                    "status": "Active",
                    "fantasycalc_value": 88,
                    "value_score": 88,
                },
            ]
        )

        needs = live_draft.roster_position_needs(
            roster,
            {"qb_format": "1QB", "qb_slots": 1, "superflex_slots": 0},
        )
        recs = live_draft.build_live_draft_recommendations(
            players,
            roster_df=roster,
            league_settings={"qb_format": "1QB"},
            score_field="value_score",
        )

        self.assertEqual(needs, [])
        self.assertFalse(any(rec["label"] == "Position Need" for rec in recs))
        self.assertFalse(any("thinnest current roster room" in rec["reason"] for rec in recs))


    def test_experimental_visibility_rules_hide_live_draft_by_default(self):
        hidden = [page.key for page in current_platform_destinations(False, show_experimental=False)]
        visible = [page.key for page in current_platform_destinations(False, show_experimental=True)]

        self.assertNotIn("live_draft", hidden)
        self.assertIn("live_draft", visible)


if __name__ == "__main__":
    unittest.main()
