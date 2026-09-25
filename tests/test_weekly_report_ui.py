import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from modules import weekly_report_ui


class TestWeeklyReportUI(unittest.TestCase):
    def test_prepared_report_preserves_section_order_and_movement_table(self):
        weekly_report = {
            "report_label": "Week 4",
            "matchup_history_available": True,
            "highlights": [{"label": "High Score", "value": "150", "note": "Team A"}],
            "trend_cards": [{"label": "Trend", "title": "Hot", "items": ["Team A"]}],
            "activity_tiles": [{"label": "Moves", "value": "8", "note": "Team B"}],
            "trade_cards": [{"label": "Trade", "title": "Deal", "items": ["A for B"]}],
            "waiver_cards": [],
            "move_cards": [],
            "team_note_cards": [{"label": "Team", "title": "Note", "items": ["Context"]}],
        }
        movement = {
            "available": True,
            "note": "Compared with Week 3.",
            "power_riser": {
                "team_name": "Team A",
                "power_delta": 2,
                "power_before": 4,
                "power_after": 2,
            },
            "power_faller": {
                "team_name": "Team B",
                "power_delta": -2,
                "power_before": 2,
                "power_after": 4,
            },
            "franchise_riser": {
                "team_name": "Team C",
                "franchise_delta": 1,
                "franchise_before": 3,
                "franchise_after": 2,
            },
            "franchise_faller": {
                "team_name": "Team D",
                "franchise_delta": -1,
                "franchise_before": 2,
                "franchise_after": 3,
            },
            "rows": [
                {
                    "team_name": "Team A",
                    "power_before": 4,
                    "power_after": 2,
                    "power_delta": 2,
                    "franchise_before": 3,
                    "franchise_after": 2,
                    "franchise_delta": 1,
                }
            ],
        }
        section_header = Mock()
        summary_tiles = Mock()
        analysis_cards = Mock()

        with (
            patch.object(weekly_report_ui.st, "caption"),
            patch.object(weekly_report_ui.st, "info"),
            patch.object(weekly_report_ui.st, "expander", return_value=nullcontext()),
            patch.object(weekly_report_ui.st, "dataframe") as dataframe,
        ):
            weekly_report_ui.render_weekly_report(
                weekly_report,
                movement,
                format_rank=lambda value: f"#{value}",
                render_section_header=section_header,
                render_summary_tiles=summary_tiles,
                render_analysis_cards=analysis_cards,
            )

        # Transaction Summary (this report week's specific moves) now renders
        # ahead of Manager Activity (season-to-date totals): this is a
        # per-week report, so the week-specific "what happened" belongs
        # before the cumulative reference leaderboard it contextualizes —
        # a deliberate hierarchy reorder, not the prior build order.
        self.assertEqual(
            [call.args[0] for call in section_header.call_args_list],
            [
                "Weekly Highlights",
                "Power Movement",
                "League Trends",
                "Transaction Summary",
                "Manager Activity",
                "Team Notes",
            ],
        )
        movement_tiles = summary_tiles.call_args_list[1].args[0]
        self.assertEqual(movement_tiles[0]["label"], "Biggest Power Riser")
        self.assertEqual(movement_tiles[0]["note"], "+2 spots | #4 to #2")
        # Rank movement direction (up/down) now carries a consistent
        # success/danger-colored badge independent of each tile's own
        # power/franchise/risk category tone.
        self.assertIn("wr-move-badge--up", movement_tiles[0]["graphic"])
        self.assertIn("wr-move-badge--down", movement_tiles[1]["graphic"])
        self.assertIn("wr-move-badge--up", movement_tiles[2]["graphic"])
        self.assertIn("wr-move-badge--down", movement_tiles[3]["graphic"])
        # Each movement tile now carries a plain-language explanation and an
        # on-page next-step pointer through the existing tap-to-detail
        # affordance (see test_workspace_ui.py's non-comparison "detail" tile
        # case) — a clarity fix, not a new component or navigation target.
        self.assertIn("Power Rank", movement_tiles[0]["detail"])
        self.assertIn("Transaction Summary", movement_tiles[0]["supporting_context"])
        self.assertIn("Franchise Rank", movement_tiles[2]["detail"])
        columns = list(dataframe.call_args.args[0].columns)
        self.assertEqual(
            columns,
            [
                "Team",
                "Power Before",
                "Power After",
                "Power Change",
                "Franchise Before",
                "Franchise After",
                "Franchise Change",
            ],
        )

    def test_empty_prepared_sections_use_shared_empty_state_panel(self):
        """Per-section 'no data yet' states use the shared empty-state panel
        (modules.ui_primitives.render_empty_state_panel) — the same component
        already used for this by My Team/Waivers/Trade Hub/League Intelligence
        — rather than a bare st.info box. The page-level partial-data caveat
        (matchup_history_available) is a banner, not a section empty state,
        and still uses st.info."""
        section_header = Mock()
        with (
            patch.object(weekly_report_ui.st, "caption"),
            patch.object(weekly_report_ui.st, "info") as info,
            patch.object(
                weekly_report_ui.ui_primitives, "render_empty_state_panel"
            ) as empty_state,
        ):
            weekly_report_ui.render_weekly_report(
                {
                    "report_label": "",
                    "matchup_history_available": False,
                    "highlights": [],
                    "trend_cards": [],
                    "activity_tiles": [],
                    "trade_cards": [],
                    "waiver_cards": [],
                    "move_cards": [],
                    "team_note_cards": [],
                },
                {"available": False, "note": "No prior snapshot."},
                format_rank=str,
                render_section_header=section_header,
                render_summary_tiles=Mock(),
                render_analysis_cards=Mock(),
            )

        info_messages = [call.args[0] for call in info.call_args_list]
        self.assertIn(
            "Sleeper matchup history did not return completed weekly scores yet. "
            "Transaction and team-context sections will still render when possible.",
            info_messages,
        )

        empty_state_calls = {
            call.args[0]: call.args[1] for call in empty_state.call_args_list
        }
        self.assertEqual(
            empty_state_calls["No weekly score highlights yet"],
            "No completed matchup week is available yet for weekly score highlights.",
        )
        self.assertEqual(empty_state_calls["No rank movement yet"], "No prior snapshot.")
        self.assertEqual(
            empty_state_calls["No transactions yet"],
            "No completed weekly transactions were returned for the current report window.",
        )
        self.assertEqual(
            empty_state_calls["No standout team notes yet"],
            "No standout team notes were generated from the current league state.",
        )
        for call in empty_state.call_args_list:
            self.assertEqual(call.kwargs.get("kind"), "no-data")
            self.assertTrue(call.kwargs.get("recovery_guidance"))


    def test_with_tile_context_adds_detail_for_known_labels_only(self):
        items = [
            {"label": "Highest Score", "value": "150", "note": "Team A"},
            {"label": "Some Unmapped Tile", "value": "1", "note": "Team B"},
            {"label": "Team of the Week", "value": "150", "note": "Team A", "detail": "Already set"},
        ]
        enriched = weekly_report_ui._with_tile_context(items)
        self.assertIn("detail", enriched[0])
        self.assertIn("scored the most fantasy points", enriched[0]["detail"])
        self.assertNotIn("detail", enriched[1])
        # An existing caller-provided "detail" is never overwritten.
        self.assertEqual(enriched[2]["detail"], "Already set")
        # Original inputs are untouched (no in-place mutation).
        self.assertNotIn("detail", items[0])

    def test_with_trend_followup_only_appends_when_there_is_a_real_signal(self):
        cards = [
            {"label": "Hottest Team", "title": "Team A", "items": ["3-game win streak"]},
            {"label": "Coldest Team", "title": "No clear skid", "items": ["Need completed matchup history first."]},
            {"label": "Win Streaks", "title": "Current heaters", "items": ["Team A: 3 straight wins"]},
        ]
        enriched = weekly_report_ui._with_trend_followup(cards)
        self.assertEqual(
            enriched[0]["items"],
            ["3-game win streak", "See Team Notes below for the roster story behind the streak."],
        )
        # A "no clear skid" placeholder card gets no followup pointer appended.
        self.assertEqual(enriched[1]["items"], ["Need completed matchup history first."])
        # A card with no mapped followup (Win Streaks) is passed through as-is.
        self.assertEqual(enriched[2]["items"], ["Team A: 3 straight wins"])


if __name__ == "__main__":
    unittest.main()
