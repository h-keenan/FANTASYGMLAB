import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import live_draft, live_draft_ui
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
        self.assertNotIn("players", visible)

    def test_multiple_draft_selection_labels_are_distinct(self):
        labels = [
            live_draft_ui._draft_label({"draft_id": "a", "status": "drafting", "season": "2026", "metadata": {"name": "Rookie Draft"}}),
            live_draft_ui._draft_label({"draft_id": "b", "status": "complete", "season": "2025", "metadata": {"name": "Startup"}}),
        ]

        self.assertIn("Rookie Draft", labels[0])
        self.assertIn("Drafting", labels[0])
        self.assertNotEqual(labels[0], labels[1])

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

    def test_mobile_markup_classes_exist(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        for marker in ("live-draft-hero", "live-draft-command", "live-draft-rec-grid", "live-draft-pick-row", "live-draft-route-marker"):
            self.assertIn(marker, css)

    def test_experimental_visibility_rules_hide_live_draft_by_default(self):
        hidden = [page.key for page in current_platform_destinations(False, show_experimental=False)]
        visible = [page.key for page in current_platform_destinations(False, show_experimental=True)]

        self.assertNotIn("live_draft", hidden)
        self.assertIn("live_draft", visible)

    def test_app_route_is_experimental_and_read_only(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        registry_source = Path("modules/ui_architecture.py").read_text(encoding="utf-8")

        self.assertIn('if current_page == "live_draft"', app_source)
        self.assertIn("live_draft_ui.render_live_draft_page", app_source)
        self.assertIn('"live_draft": "Read-only Sleeper live draft assistant', app_source)
        self.assertIn('PageDefinition("live_draft", "Live Draft"', registry_source)
        self.assertIn('category="EXPERIMENTAL"', registry_source)

    def test_ui_renders_read_only_label_and_fetches_picks(self):
        fetch_picks = Mock(return_value=([{"player_id": "p1", "pick_no": 1, "roster_id": 1}], ""))
        context = Mock(__enter__=lambda s: s, __exit__=lambda *a: None)
        fragment = lambda run_every: (lambda func: func)
        selectbox = lambda label, options, **kwargs: options[0]
        with (
            patch.object(live_draft_ui.st, "markdown") as markdown,
            patch.object(live_draft_ui.st, "selectbox", side_effect=selectbox),
            patch.object(live_draft_ui.st, "button", return_value=False),
            patch.object(live_draft_ui.st, "caption"),
            patch.object(live_draft_ui.st, "dataframe"),
            patch.object(live_draft_ui.st, "columns", return_value=[context, context]),
            patch.object(live_draft_ui.st, "text_input", return_value=""),
            patch.object(live_draft_ui.st, "expander", return_value=context),
        ):
            with patch.object(live_draft_ui.st, "fragment", create=True, new=fragment):
                live_draft_ui.render_live_draft_page(
                    selected_league_id="league-1",
                    selected_league_name="League",
                    username="user",
                    my_roster_id=1,
                    df_players=pd.DataFrame([{"player_id": "p2", "name": "Available", "position": "RB", "team": "LV", "age": 22, "active": True, "status": "Active", "fantasycalc_value": 80, "value_score": 80}]),
                    roster_df=pd.DataFrame(),
                    rosters=[{"owner_id": "owner", "roster_id": 1}],
                    roster_profiles={"1": {"team_name": "Mine"}},
                    league_settings={"qb_format": "1QB", "scoring_format": "PPR", "league_format": "Dynasty"},
                    score_field="value_score",
                    score_label="Dynasty Score",
                    fetch_league_drafts=lambda league_id: [{"draft_id": "draft", "status": "drafting", "season": "2026"}],
                    fetch_draft=lambda draft_id: {"draft_id": draft_id, "status": "drafting", "settings": {"rounds": 4, "teams": 12}},
                    fetch_draft_picks=fetch_picks,
                )

        fetch_picks.assert_called_once_with("draft")
        rendered = "\n".join(str(call.args[0]) for call in markdown.call_args_list if call.args)
        self.assertIn(live_draft.LIVE_DRAFT_READ_ONLY_LABEL, rendered)

    def test_expired_draft_renders_inactive_state_without_loading_pick_details(self):
        fetch_picks = Mock(return_value=([], ""))
        with (
            patch.object(live_draft_ui.st, "markdown"),
            patch.object(live_draft_ui.st, "info") as info,
        ):
            live_draft_ui.render_live_draft_page(
                selected_league_id="league-1",
                selected_league_name="League",
                username="user",
                my_roster_id=1,
                df_players=pd.DataFrame(),
                roster_df=pd.DataFrame(),
                rosters=[],
                roster_profiles={},
                league_settings={},
                score_field="value_score",
                score_label="Dynasty Score",
                fetch_league_drafts=lambda league_id: [{"draft_id": "old", "status": "complete"}],
                fetch_draft=lambda draft_id: {"draft_id": draft_id, "status": "complete"},
                fetch_draft_picks=fetch_picks,
            )

        fetch_picks.assert_not_called()
        self.assertIn("has ended", info.call_args.args[0])

    def test_recommendation_player_opens_canonical_quick_view(self):
        recommendation = {
            "player_id": "p1",
            "name": "Draft Target",
            "position": "WR",
            "team": "SEA",
            "recommendation_role": "Recommended pick",
            "recommendation_reason": "Best available fit for the current roster.",
            "confidence": "High",
            "position_need_impact": "Addresses a WR need",
            "immediate_roster_impact": "Competes for a starting role",
            "league_adjusted_draft_score": 9100,
        }
        render_tappable = Mock(return_value="p1")
        open_quick_view = Mock()
        with patch.object(live_draft_ui.st, "markdown"):
            live_draft_ui._render_recommendations(
                {"recommendations": [recommendation]},
                render_tappable_player_html=render_tappable,
                open_player_quick_view=open_quick_view,
                draft_id="draft-1",
            )

        render_tappable.assert_called_once()
        self.assertEqual(
            render_tappable.call_args.kwargs["key_prefix"],
            "live_draft_recommendations_draft-1",
        )
        open_quick_view.assert_called_once_with(
            "p1",
            source_label="Live Draft Assistant",
            source_note="Best available fit for the current roster.",
            status_label="Recommended pick",
        )


if __name__ == "__main__":
    unittest.main()
