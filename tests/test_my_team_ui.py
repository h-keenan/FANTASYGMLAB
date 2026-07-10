import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import app
from modules import my_team_ui


class TestMyTeamUI(unittest.TestCase):
    def test_prospect_watchlist_uses_mobile_readable_card_structure(self):
        with patch.object(my_team_ui.st, "markdown") as markdown:
            my_team_ui.render_prospect_watchlist(
                ["RB"],
                prospects_for_positions=lambda _positions, limit: [
                    {
                        "name": "Test Prospect",
                        "position": "RB",
                        "school": "Test School",
                        "note": "Useful fit note.",
                        "source": "Test Source",
                    }
                ][:limit],
            )

        html = markdown.call_args.args[0]
        self.assertIn("prospect-card-head", html)
        self.assertIn("prospect-card-title-group", html)
        self.assertIn("Test Prospect", html)
    def test_get_needed_positions_uses_smart_qb_and_te_room_coverage(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "qb-starter",
                    "name": "QB Starter",
                    "position": "QB",
                    "team": "DAL",
                    "age": 27,
                    "years_exp": 5,
                    "value_score": 75,
                    "market_score": 75,
                    "player_tier": "Star",
                    "opportunity_label": "Strong Opportunity",
                    "status": "Active",
                },
                {
                    "player_id": "qb-backup",
                    "name": "QB Backup",
                    "position": "QB",
                    "team": "DAL",
                    "age": 28,
                    "years_exp": 6,
                    "value_score": 28,
                    "market_score": 28,
                    "player_tier": "Contributor",
                    "opportunity_label": "Backup With Upside",
                    "status": "Active",
                },
                {
                    "player_id": "te-core",
                    "name": "TE Core",
                    "position": "TE",
                    "team": "DAL",
                    "age": 22,
                    "years_exp": 1,
                    "value_score": 80,
                    "market_score": 80,
                    "role": "Core",
                    "player_tier": "Star",
                    "status": "IR",
                    "injury_status": "out",
                },
                {
                    "player_id": "te-cover",
                    "name": "TE Cover",
                    "position": "TE",
                    "team": "DAL",
                    "age": 28,
                    "years_exp": 6,
                    "value_score": 32,
                    "market_score": 32,
                    "player_tier": "Contributor",
                    "opportunity_label": "Strong Opportunity",
                    "status": "Active",
                },
                {
                    "player_id": "rb-1",
                    "name": "RB",
                    "position": "RB",
                    "team": "DAL",
                    "age": 27,
                    "years_exp": 5,
                    "value_score": 30,
                    "status": "Active",
                },
                {
                    "player_id": "wr-1",
                    "name": "WR",
                    "position": "WR",
                    "team": "DAL",
                    "age": 27,
                    "years_exp": 5,
                    "value_score": 30,
                    "status": "Active",
                },
            ]
        )

        needs = app.get_needed_positions(
            roster,
            {"weaknesses": ["QB", "TE", "RB"]},
            {
                "qb_count": 1,
                "superflex_count": 0,
                "rb_count": 2,
                "wr_count": 3,
                "te_count": 1,
                "flex_count": 0,
            },
            include_fallback=False,
        )

        self.assertNotIn("QB", needs)
        self.assertNotIn("TE", needs)
        self.assertIn("RB", needs)

    def test_roster_limit_treats_kicker_as_replaceable_not_long_term_thin(self):
        rows = [
            ("qb-1", "Quarterback", "QB", 70, 27, 5, "Starter", "Strong Opportunity"),
            ("rb-1", "Running Back", "RB", 70, 25, 4, "Starter", "Strong Opportunity"),
            ("wr-1", "Wide Receiver", "WR", 70, 25, 4, "Starter", "Strong Opportunity"),
            ("te-1", "Tight End", "TE", 65, 26, 4, "Starter", "Strong Opportunity"),
            ("k-1", "Starting Kicker", "K", 12, 30, 7, "Starter", "Strong Opportunity"),
            ("k-2", "Extra Kicker", "K", 2, 31, 8, "Depth", "Buried Depth"),
            ("wr-2", "Depth Receiver", "WR", 20, 27, 5, "Contributor", "Backup With Upside"),
        ]
        roster = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "name": name,
                    "position": position,
                    "team": "DAL",
                    "status": "Active",
                    "injury_status": "",
                    "value_score": score,
                    "market_score": score,
                    "opportunity_score": score,
                    "age": age,
                    "years_exp": years_exp,
                    "search_rank": index + 1,
                    "role": "Bench" if "Depth" in tier else "Flex",
                    "player_tier": tier,
                    "opportunity_label": opportunity,
                }
                for index, (
                    player_id,
                    name,
                    position,
                    score,
                    age,
                    years_exp,
                    tier,
                    opportunity,
                ) in enumerate(rows)
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [
            True,
            True,
            True,
            True,
            True,
            False,
            False,
        ]

        with (
            patch(
                "app.get_league",
                return_value={
                    "roster_positions": ["QB", "RB", "WR", "TE", "K", "BN"],
                    "settings": {},
                },
            ),
            patch(
                "app.get_rosters",
                return_value=[
                    {
                        "roster_id": 1,
                        "players": roster["player_id"].tolist(),
                        "reserve": [],
                        "taxi": [],
                    }
                ],
            ),
        ):
            result = app.roster_limit_status(
                league_id="league-1",
                roster_id=1,
                roster_df=roster,
                lineup_df=lineup,
                league_settings={"k_count": 1},
                score_field="value_score",
                active_team_strategy="contender",
                needed_positions=["QB", "TE"],
                surplus_positions=["WR"],
                untouchables=[],
            )

        self.assertNotIn("K", result["thinnest_positions"])
        self.assertIn("K", result["strongest_surplus_positions"])
        self.assertEqual(
            result["drop_candidates_structured"][0]["player_id"],
            "k-2",
        )
        self.assertIn(
            "Replaceable kicker surplus",
            result["drop_candidates_structured"][0]["reason"],
        )

    def test_app_exposes_my_team_render_helpers(self):
        self.assertIs(app.render_advice_cards, my_team_ui.render_advice_cards)

    def test_roster_limit_wrapper_preserves_feedback_and_card_callbacks(self):
        limit_context = {
            "over_limit": True,
            "over_by": 1,
            "current_roster_size": 29,
            "max_roster_size": 28,
            "total_rostered_players": 31,
            "drop_candidates_structured": [
                {
                    "player_id": "drop-1",
                    "player_name": "Drop Player",
                    "bucket": "drop",
                    "reason": "Lowest utility roster spot.",
                }
            ],
        }

        with (
            patch.object(my_team_ui.st, "markdown") as markdown,
            patch.object(app, "render_summary_tiles") as summary_tiles,
            patch.object(app, "render_structured_decision_cards") as decision_cards,
            patch.object(app, "render_recommendation_feedback") as feedback,
            patch.object(app, "render_visible_decision_source_debug"),
            patch.object(app, "render_no_team_player_debug"),
            patch.object(app, "render_roster_utility_debug"),
        ):
            app.render_roster_limit_alert(limit_context, compact=True)

        self.assertFalse(summary_tiles.called)
        self.assertTrue(any("roster-limit-strip" in str(call.args[0]) for call in markdown.call_args_list))
        self.assertEqual(
            decision_cards.call_args.kwargs["container_class"],
            "decision-panel-grid-alert",
        )
        self.assertEqual(feedback.call_args.kwargs["player_ids"], ["drop-1"])
        self.assertEqual(
            feedback.call_args.kwargs["key_prefix"],
            "my_team_roster_limit_feedback",
        )

    def test_workspace_preserves_section_order_and_card_keys(self):
        row = {
            "player_id": "player-1",
            "name": "Test Player",
            "position": "WR",
            "team": "DAL",
            "role": "Core",
            "value_score": 75,
        }
        player_df = pd.DataFrame([row])
        render_section_header = Mock()
        render_home_command_tiles = Mock()
        render_roster_limit_alert = Mock()
        render_player_scan_cards = Mock()
        render_roster_utility_debug = Mock()
        render_no_team_player_debug = Mock()
        render_summary_tiles = Mock()

        my_team_ui.render_my_team_workspace(
            biggest_need_value="RB",
            biggest_need_note="Weakest room.",
            trade_target_value="Target Player",
            trade_opportunity_note="Best current path.",
            trade_target_row=pd.Series(row),
            waiver_value="Waiver Player",
            waiver_note="Best available add.",
            top_waiver=pd.Series(row),
            roster_limit_value="28 / 28",
            roster_limit_note="At the limit.",
            injury_alert_value="Stable",
            injury_alert_note="No acute pressure.",
            immediate_value="Hold",
            immediate_note="Stay patient.",
            immediate_tone="strategy",
            my_roster_limit={"over_limit": False},
            core_assets_df=player_df,
            untouchables_df=player_df,
            trade_candidates_df=player_df,
            hold_candidates_df=player_df,
            drop_candidates_df=player_df,
            trade_note_map={"player-1": "Trade reason."},
            hold_note_map={"player-1": "Hold reason."},
            drop_note_map={"player-1": "Drop reason."},
            starters=player_df.assign(slot="WR"),
            key_backups_df=player_df,
            strengths=["WR"],
            weaknesses=["RB"],
            team_row=pd.Series(
                {
                    "starter_score": 100,
                    "starter_rank": 2,
                    "archetype_label": "Contender",
                    "archetype_explanation": "Strong current roster.",
                    "power_rank": 2,
                    "franchise_rank": 3,
                    "draft_capital_rank": 6,
                    "age_rank": 4,
                }
            ),
            active_team_strategy_label="Contender",
            auto_team_strategy="contender",
            health_flag="Stable",
            injured_starters=0,
            key_injuries_summary="",
            selected_league_id="league-1",
            my_roster_id=7,
            score_field="value_score",
            render_section_header=render_section_header,
            render_home_command_tiles=render_home_command_tiles,
            render_roster_limit_alert=render_roster_limit_alert,
            render_player_scan_cards=render_player_scan_cards,
            render_roster_utility_debug=render_roster_utility_debug,
            render_no_team_player_debug=render_no_team_player_debug,
            render_summary_tiles=render_summary_tiles,
            player_display_name=lambda player: str(player.get("name")),
            format_score=lambda value: str(value),
            format_rank=lambda value: f"#{value}",
            truncate_text=lambda value, limit: value[:limit],
            team_strategy_label=lambda value: str(value).title(),
        )

        self.assertEqual(
            [call.args[0] for call in render_section_header.call_args_list],
            [
                "Roster Priorities",
                "Room Snapshot",
                "Roster Decisions",
                "Lineup & Depth",
                "Team Outlook",
            ],
        )
        calls_by_title = {
            call.kwargs["title"]: call.kwargs
            for call in render_player_scan_cards.call_args_list
        }
        self.assertEqual(
            calls_by_title["Core Assets"]["quick_view_key_prefix"],
            "my_team_core_assets_league-1_7",
        )
        self.assertEqual(
            calls_by_title["Trade Candidates"]["feedback_recommendation_type"],
            "trade_candidate",
        )
        self.assertEqual(
            calls_by_title["Drop Candidates"]["quick_view_source_label"],
            "My Team - Drop Candidates",
        )
        room_snapshot_items = render_summary_tiles.call_args_list[0].args[0]
        outlook_items = render_summary_tiles.call_args_list[-1].args[0]
        self.assertIn("detail_items", room_snapshot_items[1])
        self.assertEqual(room_snapshot_items[1]["label"], "Weak Positions")
        power_tile = next(item for item in outlook_items if item["label"] == "Power Rank")
        health_tile = next(item for item in outlook_items if item["label"] == "Health Outlook")
        self.assertIn("detail_items", power_tile)
        self.assertIn("detail_items", health_tile)
        self.assertFalse(render_roster_limit_alert.called)

    def test_workspace_uses_collapsed_secondary_mobile_sections(self):
        source = Path("modules/my_team_ui.py").read_text(encoding="utf-8")

        self.assertIn('with st.expander("Protected players and secondary decisions", expanded=False):', source)
        self.assertIn('with st.expander("Key backups", expanded=False):', source)
        self.assertIn('"Room Snapshot"', source)
        self.assertIn('"Roster Priorities"', source)
        self.assertIn("quick_view_key_prefix=f\"my_team_drop_candidates_", source)

    def test_my_team_espn_limited_mode_has_degraded_state(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('"My Team is gated for ESPN until roster mapping', source)
        self.assertIn("st.session_state.get(\"active_platform\") == \"espn\"", source)
        self.assertIn("st.session_state.get(\"espn_limited_mode\")", source)
        self.assertIn("app-degraded-state", source)
        self.assertIn("Sleeper remains the full My Team path", source)


if __name__ == "__main__":
    unittest.main()
