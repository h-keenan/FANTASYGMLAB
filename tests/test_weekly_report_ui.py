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

        self.assertEqual(
            [call.args[0] for call in section_header.call_args_list],
            [
                "Weekly Highlights",
                "Power Movement",
                "League Trends",
                "Manager Activity",
                "Transaction Summary",
                "Team Notes",
            ],
        )
        movement_tiles = summary_tiles.call_args_list[1].args[0]
        self.assertEqual(movement_tiles[0]["label"], "Biggest Power Riser")
        self.assertEqual(movement_tiles[0]["note"], "+2 spots | #4 to #2")
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

    def test_empty_prepared_sections_keep_existing_info_paths(self):
        section_header = Mock()
        with (
            patch.object(weekly_report_ui.st, "caption"),
            patch.object(weekly_report_ui.st, "info") as info,
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

        messages = [call.args[0] for call in info.call_args_list]
        self.assertIn(
            "No completed matchup week is available yet for weekly score highlights.",
            messages,
        )
        self.assertIn("No prior snapshot.", messages)
        self.assertIn(
            "No completed weekly transactions were returned for the current report window.",
            messages,
        )
        self.assertIn(
            "No standout team notes were generated from the current league state.",
            messages,
        )


if __name__ == "__main__":
    unittest.main()
