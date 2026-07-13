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
            roster_profiles={"10": {"team_name": "My Team"}},
            rosters=rosters,
            my_roster_id=10,
            league_settings={"qb_format": "1QB"},
            score_field="value_score",
        )

        self.assertEqual(state["my_slot"], 1)
        self.assertTrue(state["is_my_pick"])
        self.assertEqual(state["picks_until_mine"], 0)

    def test_picks_until_next_selection_handles_snake(self):
        self.assertEqual(
            live_draft.picks_until_next_selection(current_pick=2, my_slot=1, team_count=3, rounds=2, snake=True),
            4,
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


if __name__ == "__main__":
    unittest.main()
