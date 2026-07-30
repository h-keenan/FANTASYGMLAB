import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import draft_assistant


def player(
    player_id,
    name,
    position,
    *,
    value,
    age=24,
    market=None,
    scarcity=0,
    tier="Starter",
    opportunity="",
    status="Active",
):
    return {
        "player_id": player_id,
        "name": name,
        "position": position,
        "team": "DAL",
        "age": age,
        "value_score": value,
        "dynasty_score": value,
        "market_score": value if market is None else market,
        "scarcity_score": scarcity,
        "player_tier": tier,
        "opportunity_label": opportunity,
        "active": True,
        "status": status,
        "fantasycalc_value": value,
    }


class TestDraftAssistant(unittest.TestCase):
    def test_live_drafted_ids_extract_from_top_level_and_metadata(self):
        picks = [
            {"player_id": "101", "roster_id": 1},
            {"metadata": {"player_id": 202, "roster_id": 2}},
            {"metadata": {"picked_player_id": "p3", "owner_id": 3}},
            {"metadata": {"drafted_player_id": "p4"}},
            {"sleeper_id": "p5"},
            {"player_id": None},
        ]

        self.assertEqual(
            [draft_assistant.draft_pick_player_id(pick) for pick in picks],
            ["101", "202", "p3", "p4", "p5", ""],
        )
        self.assertEqual(
            [draft_assistant.draft_pick_roster_id(pick) for pick in picks],
            [1, 2, 3, 0, 0, 0],
        )

    def test_manual_and_live_drafted_ids_merge(self):
        merged = draft_assistant.merge_drafted_ids(["p1", "p2"], ["p2", "p3", ""])

        self.assertEqual(merged, {"p1", "p2", "p3"})

    def test_manual_state_key_is_scoped_by_user_league_and_draft(self):
        first = draft_assistant.manual_drafted_state_key("UserA", "league-1", "draft-1")
        second = draft_assistant.manual_drafted_state_key("UserA", "league-2", "draft-1")
        third = draft_assistant.manual_drafted_state_key("UserA", "league-1", "draft-2")

        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertIn("usera", first)
        self.assertIn("league-1", first)
        self.assertIn("draft-1", first)

    def test_available_pool_excludes_live_and_manual_drafted_players(self):
        df = pd.DataFrame(
            [
                player("p1", "Drafted Live", "RB", value=90),
                player("p2", "Available", "WR", value=80),
                player("p3", "Drafted Manual", "QB", value=70),
            ]
        )
        drafted_ids = draft_assistant.merge_drafted_ids(["p1"], ["p3"])

        available = draft_assistant.build_available_player_pool(
            df,
            drafted_ids,
            score_field="value_score",
        )

        self.assertEqual(available["player_id"].tolist(), ["p2"])

    def test_available_pool_normalizes_numeric_string_id_mismatch(self):
        df = pd.DataFrame(
            [
                player(101.0, "Drafted Numeric", "RB", value=90),
                player("202", "Available", "WR", value=80),
            ]
        )

        available = draft_assistant.build_available_player_pool(
            df,
            ["101"],
            score_field="value_score",
        )

        self.assertEqual(available["player_id"].map(str).tolist(), ["202"])

    def test_available_pool_excludes_drafted_ids_from_sleeper_id_column(self):
        df = pd.DataFrame(
            [
                player("internal-1", "Drafted", "RB", value=90) | {"sleeper_id": "101"},
                player("internal-2", "Available", "WR", value=80) | {"sleeper_id": "202"},
            ]
        ).drop(columns=["player_id"])

        available = draft_assistant.build_available_player_pool(
            df,
            ["101"],
            score_field="value_score",
        )

        self.assertEqual(available["sleeper_id"].tolist(), ["202"])

    def test_available_pool_excludes_drafted_ids_from_canonical_player_id_column(self):
        df = pd.DataFrame(
            [
                player("internal-1", "Drafted", "RB", value=90)
                | {"canonical_player_id": "101"},
                player("internal-2", "Available", "WR", value=80)
                | {"canonical_player_id": "202"},
            ]
        ).drop(columns=["player_id"])

        available = draft_assistant.build_available_player_pool(
            df,
            ["101"],
            score_field="value_score",
        )

        self.assertEqual(available["canonical_player_id"].tolist(), ["202"])

    def test_multiple_drafts_prefer_active_then_future_then_latest_completed(self):
        options = [
            {"draft_id": "complete-old", "status": "complete", "season": 2025, "start_time": 1},
            {"draft_id": "complete-new", "status": "complete", "season": 2026, "start_time": 2},
            {"draft_id": "future", "status": "pre_draft", "season": 2026, "start_time": 3},
            {"draft_id": "live", "status": "drafting", "season": 2025, "start_time": 4},
        ]

        selected = draft_assistant.select_default_draft_option(options)

        self.assertEqual(selected["draft_id"], "live")

    def test_selected_draft_id_is_respected_when_not_in_option_list(self):
        with patch.object(draft_assistant.sleeper, "get_league_drafts", return_value=[]), patch.object(
            draft_assistant.sleeper,
            "get_draft",
            return_value={
                "draft_id": "selected-draft",
                "status": "drafting",
                "settings": {"rounds": 3},
            },
        ) as get_draft, patch.object(
            draft_assistant.sleeper,
            "get_draft_picks",
            return_value=[{"player_id": "p1"}],
        ) as get_picks, patch.object(
            draft_assistant.sleeper,
            "get_league",
            return_value={"settings": {"num_teams": 12}},
        ), patch.object(
            draft_assistant.sleeper,
            "get_rosters",
            return_value=[],
        ):
            context = draft_assistant.build_live_draft_context(
                "league-1",
                selected_draft_id="selected-draft",
            )

        get_draft.assert_called_with("selected-draft")
        get_picks.assert_called_with("selected-draft")
        self.assertEqual(context["selected_draft_id"], "selected-draft")
        self.assertEqual(context["live_drafted_player_ids"], ["p1"])

    def test_completed_draft_picks_are_not_ignored(self):
        with patch.object(
            draft_assistant.sleeper,
            "get_league_drafts",
            return_value=[
                {
                    "draft_id": "completed-draft",
                    "status": "complete",
                    "season": 2026,
                    "settings": {"rounds": 4},
                }
            ],
        ), patch.object(
            draft_assistant.sleeper,
            "get_draft",
            return_value={
                "draft_id": "completed-draft",
                "status": "complete",
                "season": 2026,
                "settings": {"rounds": 4},
            },
        ), patch.object(
            draft_assistant.sleeper,
            "get_draft_picks",
            return_value=[
                {"player_id": "p1", "roster_id": 1},
                {"metadata": {"player_id": "p2", "roster_id": 2}},
            ],
        ), patch.object(
            draft_assistant.sleeper,
            "get_league",
            return_value={"settings": {"num_teams": 12}},
        ), patch.object(
            draft_assistant.sleeper,
            "get_rosters",
            return_value=[],
        ):
            context = draft_assistant.build_live_draft_context("league-1")

        self.assertEqual(context["draft_status"], "complete")
        self.assertEqual(context["picks_made"], 2)
        self.assertEqual(context["live_drafted_player_ids"], ["p1", "p2"])

    def test_name_fallback_matches_unique_metadata_name(self):
        df = pd.DataFrame(
            [
                player("p1", "Unique Prospect", "RB", value=90),
                player("p2", "Other Prospect", "WR", value=80),
            ]
        )

        analysis = draft_assistant.analyze_drafted_pick_matches(
            [{"player_id": "missing", "metadata": {"first_name": "Unique", "last_name": "Prospect"}}],
            df,
        )

        self.assertEqual(analysis["id_match_count"], 0)
        self.assertEqual(analysis["fallback_match_count"], 1)
        self.assertEqual(analysis["matched_ids"], ["p1"])
        self.assertFalse(analysis["unmatched_picks"])

    def test_ambiguous_name_fallback_remains_unmatched(self):
        df = pd.DataFrame(
            [
                player("p1", "Duplicate Name", "RB", value=90),
                player("p2", "Duplicate Name", "WR", value=80),
            ]
        )

        analysis = draft_assistant.analyze_drafted_pick_matches(
            [{"player_id": "missing", "metadata": {"full_name": "Duplicate Name"}}],
            df,
        )

        self.assertEqual(analysis["fallback_match_count"], 0)
        self.assertEqual(analysis["unmatched_count"], 1)
        self.assertEqual(analysis["unmatched_picks"][0]["reason"], "Ambiguous metadata name match")

    def test_available_pool_excludes_fallback_matched_drafted_player(self):
        df = pd.DataFrame(
            [
                player("p1", "Fallback Pick", "RB", value=90),
                player("p2", "Available", "WR", value=80),
            ]
        )
        analysis = draft_assistant.analyze_drafted_pick_matches(
            [{"player_id": "missing", "metadata": {"full_name": "Fallback Pick"}}],
            df,
        )

        available = draft_assistant.build_available_player_pool(
            df,
            analysis["matched_ids"],
            score_field="value_score",
        )

        self.assertEqual(available["player_id"].tolist(), ["p2"])

    def test_short_rookie_style_draft_filters_veteran_pool_when_enough_young_players_exist(self):
        rows = [
            player(f"rookie-{idx}", f"Rookie {idx}", "WR", value=50 + idx, age=22, status="Active")
            | {"years_exp": 0}
            for idx in range(25)
        ]
        rows.append(
            player("vet", "Veteran", "WR", value=99, age=29, status="Active")
            | {"years_exp": 6}
        )

        filtered = draft_assistant.apply_draft_pool_filter(
            pd.DataFrame(rows),
            {"draft_rounds": 4},
        )

        self.assertNotIn("vet", set(filtered["player_id"]))
        self.assertEqual(len(filtered), 25)

    def test_completed_short_rookie_draft_uses_stricter_rookie_pool(self):
        rows = [
            player(f"rookie-{idx}", f"Rookie {idx}", "WR", value=50 + idx, age=22, status="Active")
            | {"years_exp": 0}
            for idx in range(25)
        ]
        rows.append(
            player("second-year", "Second Year", "TE", value=99, age=23, status="Active")
            | {"years_exp": 2}
        )

        filtered = draft_assistant.apply_draft_pool_filter(
            pd.DataFrame(rows),
            {"draft_rounds": 4, "draft_status": "complete"},
        )

        self.assertNotIn("second-year", set(filtered["player_id"]))
        self.assertEqual(len(filtered), 25)

    def test_refresh_path_clears_sleeper_draft_caches(self):
        with patch.object(draft_assistant.sleeper, "get_league_drafts") as drafts, patch.object(
            draft_assistant.sleeper,
            "get_draft",
        ) as draft, patch.object(draft_assistant.sleeper, "get_draft_picks") as picks:
            drafts.cache_clear = Mock()
            draft.cache_clear = Mock()
            picks.cache_clear = Mock()

            draft_assistant.clear_sleeper_draft_caches()

        drafts.cache_clear.assert_called_once()
        draft.cache_clear.assert_called_once()
        picks.cache_clear.assert_called_once()

    def test_upcoming_user_picks_infer_snake_order_from_slot_map(self):
        draft = {
            "type": "snake",
            "metadata": {"slot_to_roster_id": {"3": "10"}},
        }

        upcoming = draft_assistant.infer_upcoming_pick_numbers(
            draft,
            my_roster_id=10,
            league_size=12,
            rounds=3,
            picks_made=12,
            limit=3,
        )

        self.assertEqual(upcoming, [22, 27])

    def test_recommendation_buckets_use_available_players(self):
        board = draft_assistant.build_available_player_pool(
            pd.DataFrame(
                [
                    player("p1", "Top RB", "RB", value=95, scarcity=2),
                    player("p2", "Safe WR", "WR", value=88, age=26),
                    player("p3", "Young Upside", "WR", value=76, age=22, opportunity="Strong Opportunity"),
                ]
            ),
            [],
            score_field="value_score",
        )

        buckets = draft_assistant.build_recommendation_buckets(
            board,
            roster_df=pd.DataFrame(),
            lineup_df=pd.DataFrame(),
            league_settings={"qb_format": "1QB"},
            score_field="value_score",
        )

        self.assertTrue(buckets)
        self.assertTrue(
            {
                "Best Overall",
                "Best Value",
                "Safest Pick",
            }.issubset({bucket["bucket"] for bucket in buckets})
        )
        self.assertTrue(
            all(bucket["player"]["player_id"] in {"p1", "p2", "p3"} for bucket in buckets)
        )
        bucket_player_ids = [bucket["player"]["player_id"] for bucket in buckets]
        self.assertEqual(len(bucket_player_ids), len(set(bucket_player_ids)))

    def test_recommendation_buckets_prefer_distinct_players(self):
        board = draft_assistant.build_available_player_pool(
            pd.DataFrame(
                [
                    player("p1", "Top RB", "RB", value=95, scarcity=2),
                    player("p2", "Safe WR", "WR", value=88, age=26),
                    player("p3", "Young Upside", "WR", value=76, age=22, opportunity="Strong Opportunity"),
                ]
            ),
            [],
            score_field="value_score",
        )

        buckets = draft_assistant.build_recommendation_buckets(
            board,
            roster_df=pd.DataFrame(),
            lineup_df=pd.DataFrame(),
            league_settings={},
            score_field="value_score",
        )

        player_ids = [bucket["player"]["player_id"] for bucket in buckets]
        self.assertEqual(len(player_ids), len(set(player_ids)))

    def test_best_positional_fit_respects_covered_one_qb_room(self):
        available = draft_assistant.build_available_player_pool(
            pd.DataFrame(
                [
                    player("qb-target", "QB Target", "QB", value=82, scarcity=10),
                    player("rb-target", "RB Target", "RB", value=78, scarcity=5),
                ]
            ),
            [],
            score_field="value_score",
        )
        roster = pd.DataFrame(
            [
                player("qb1", "Starter QB", "QB", value=90, age=27, tier="Star"),
                player("qb2", "Backup QB", "QB", value=35, age=29, opportunity="Strong Opportunity"),
                player("rb1", "Only RB", "RB", value=30, age=27, tier="Contributor"),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False, True]

        buckets = draft_assistant.build_recommendation_buckets(
            available,
            roster_df=roster,
            lineup_df=lineup,
            league_settings={"qb_count": 1, "superflex_count": 0, "rb_count": 2},
            score_field="value_score",
        )
        fit_buckets = {
            item["bucket"]: item["player"]["position"]
            for item in buckets
            if item["bucket"] in {"Best Team Fit", "Best Positional Fit"}
        }

        self.assertNotEqual(fit_buckets.get("Best Team Fit"), "QB")
        self.assertNotEqual(fit_buckets.get("Best Positional Fit"), "QB")

    def test_superflex_can_make_qb_a_positional_fit(self):
        available = draft_assistant.build_available_player_pool(
            pd.DataFrame(
                [
                    player("qb-target", "QB Target", "QB", value=82, scarcity=10),
                    player("rb-target", "RB Target", "RB", value=78, scarcity=5),
                ]
            ),
            [],
            score_field="value_score",
        )
        roster = pd.DataFrame(
            [player("qb1", "Starter QB", "QB", value=90, age=27, tier="Star")]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        buckets = draft_assistant.build_recommendation_buckets(
            available,
            roster_df=roster,
            lineup_df=lineup,
            league_settings={"qb_count": 1, "superflex_count": 1},
            score_field="value_score",
        )
        fit_positions = [
            item["player"]["position"]
            for item in buckets
            if item["bucket"] in {"Best Team Fit", "Best Positional Fit"}
        ]

        self.assertIn("QB", fit_positions)

    def test_status_labels_handle_common_states(self):
        self.assertEqual(draft_assistant.draft_status_label("drafting"), "In Progress")
        self.assertEqual(draft_assistant.draft_status_label("pre_draft"), "Not Started")
        self.assertEqual(draft_assistant.draft_status_label("complete"), "Complete")
        self.assertEqual(draft_assistant.draft_status_label("completed"), "Complete")
        self.assertEqual(draft_assistant.draft_status_label("done"), "Complete")
        self.assertTrue(draft_assistant.is_completed_draft_status("done"))
        self.assertTrue(draft_assistant.is_completed_draft_status("completed"))
        self.assertEqual(draft_assistant.draft_status_label(""), "Unknown")

    def test_completed_draft_context_sets_review_flags(self):
        with patch.object(draft_assistant.sleeper, "get_league_drafts", return_value=[]), patch.object(
            draft_assistant.sleeper,
            "get_draft",
            return_value={
                "draft_id": "draft-1",
                "status": "completed",
                "settings": {"rounds": 1},
            },
        ), patch.object(
            draft_assistant.sleeper,
            "get_draft_picks",
            return_value=[],
        ), patch.object(
            draft_assistant.sleeper,
            "get_league",
            return_value={"settings": {"num_teams": 2}},
        ), patch.object(
            draft_assistant.sleeper,
            "get_rosters",
            return_value=[{"roster_id": 1}, {"roster_id": 2}],
        ):
            context = draft_assistant.build_live_draft_context(
                "league-1",
                username="user",
                my_roster_id=1,
                selected_draft_id="draft-1",
            )

        self.assertEqual(context["draft_status"], "complete")
        self.assertTrue(context["is_completed"])
        self.assertTrue(context["review_mode"])
        self.assertFalse(draft_assistant.should_render_active_draft_sections(context))
        self.assertTrue(draft_assistant.should_render_active_draft_sections({"draft_status": "pre_draft"}))

    def test_completed_pick_review_rows_group_and_grade_matched_picks(self):
        picks = [
            {"round": 2, "pick_no": 15, "player_id": "p2", "roster_id": 9},
            {"round": 1, "pick_no": 2, "player_id": "p1", "roster_id": 5},
        ]
        rows = draft_assistant.completed_pick_review_rows(
            picks,
            pd.DataFrame(
                [
                    player("p1", "Round One", "WR", value=93),
                    player("p2", "Round Two", "RB", value=70),
                ]
            ),
            my_roster_id=5,
        )

        self.assertEqual([row["pick_number"] for row in rows], [2, 15])
        self.assertNotEqual(rows[0]["grade"], "Ungraded")
        self.assertTrue(rows[0]["is_my_pick"])
        grouped = draft_assistant.group_picks_by_round(picks)
        self.assertEqual(list(grouped.keys()), [1, 2])

    def test_completed_pick_grades_have_realistic_spread(self):
        grade, reason = draft_assistant.grade_completed_draft_pick(
            {"value_score": 96},
            pick_number=1,
            value_rank=1,
        )
        self.assertIn(grade, {"A", "A-"})
        self.assertIn("Best available", reason)
        self.assertEqual(
            draft_assistant.grade_completed_draft_pick(
                {"value_score": 94},
                pick_number=1,
                value_rank=2,
            )[0],
            "A-",
        )
        self.assertIn(
            draft_assistant.grade_completed_draft_pick(
                {"value_score": 90},
                pick_number=5,
                value_rank=1,
            )[0],
            {"A", "A+"},
        )
        self.assertIn(
            draft_assistant.grade_completed_draft_pick(
                {"value_score": 80},
                pick_number=10,
                value_rank=10,
            )[0],
            {"B", "B+"},
        )
        self.assertIn(
            draft_assistant.grade_completed_draft_pick(
                {"value_score": 76},
                pick_number=10,
                value_rank=12,
            )[0],
            {"B+", "A-"},
        )
        self.assertIn(
            draft_assistant.grade_completed_draft_pick(
                {"value_score": 74},
                pick_number=10,
                value_rank=15,
            )[0],
            {"B-", "C+"},
        )
        self.assertIn(
            draft_assistant.grade_completed_draft_pick(
                {"value_score": 70},
                pick_number=10,
                value_rank=30,
            )[0],
            {"C", "D", "F"},
        )

    def test_completed_pick_review_uses_corrected_top_board_grade_path(self):
        picks = [{"round": 1, "pick_no": 1, "player_id": "love", "roster_id": 1}]
        rows = draft_assistant.completed_pick_review_rows(
            picks,
            pd.DataFrame(
                [
                    player("love", "Jeremiyah Love", "RB", value=99),
                    player("alt-1", "Alternative One", "WR", value=94),
                    player("alt-2", "Alternative Two", "TE", value=91),
                ]
            ),
        )

        self.assertEqual(rows[0]["value_rank"], 1)
        self.assertIn(rows[0]["grade"], {"A", "A-"})
        self.assertIn("Best available", rows[0]["grade_reason"])

    def test_completed_pick_review_grades_against_remaining_available_pool(self):
        picks = [
            {"round": 1, "pick_no": 1, "player_id": "p1", "roster_id": 1},
            {"round": 1, "pick_no": 2, "player_id": "p2", "roster_id": 2},
        ]
        rows = draft_assistant.completed_pick_review_rows(
            picks,
            pd.DataFrame(
                [
                    player("p1", "Best Player", "RB", value=100),
                    player("p2", "Second Player", "WR", value=95),
                    player("p3", "Third Player", "TE", value=90),
                ]
            ),
        )

        self.assertIn(rows[0]["grade"], {"A", "A-"})
        self.assertIn(rows[1]["grade"], {"A", "A-", "B+"})
        self.assertEqual(rows[1]["value_rank"], 1)

    def test_completed_pick_review_excludes_previously_drafted_alternatives(self):
        picks = [
            {"round": 1, "pick_no": 1, "player_id": "elite-1", "roster_id": 1},
            {"round": 1, "pick_no": 2, "player_id": "elite-2", "roster_id": 2},
            {"round": 1, "pick_no": 3, "player_id": "elite-3", "roster_id": 3},
        ]
        rows = draft_assistant.completed_pick_review_rows(
            picks,
            pd.DataFrame(
                [
                    player("elite-1", "Elite One", "RB", value=100),
                    player("elite-2", "Elite Two", "WR", value=99),
                    player("elite-3", "Elite Three", "WR", value=98),
                    player("depth", "Depth Option", "RB", value=60),
                ]
            ),
        )

        self.assertEqual([row["value_rank"] for row in rows], [1, 1, 1])
        self.assertTrue(all(row["grade"] in {"A", "A-"} for row in rows))

    def test_completed_pick_review_marks_large_reach_against_remaining_pool(self):
        picks = [{"round": 1, "pick_no": 10, "player_id": "reach", "roster_id": 1}]
        df_players = pd.DataFrame(
            [player(f"better-{index}", f"Better {index}", "WR", value=100 - index) for index in range(1, 30)]
            + [player("reach", "Reach Pick", "TE", value=50)]
        )

        rows = draft_assistant.completed_pick_review_rows(picks, df_players)

        self.assertIn(rows[0]["grade"], {"C", "C-", "D", "F"})
        self.assertGreaterEqual(rows[0]["value_rank"], 25)

    def test_remaining_board_rank_ignores_already_drafted_players(self):
        rank = draft_assistant.remaining_board_rank(
            "p3",
            ["p1", "p2", "p3", "p4"],
            {"p1", "p2"},
        )

        self.assertEqual(rank, 1)

    def test_completed_pick_review_rows_leave_unmatched_ungraded(self):
        rows = draft_assistant.completed_pick_review_rows(
            [{"round": 1, "pick_no": 1, "metadata": {"first_name": "Unknown", "last_name": "Player"}}],
            pd.DataFrame([player("p1", "Known Player", "WR", value=90)]),
        )

        self.assertEqual(rows[0]["grade"], "Ungraded")
        self.assertIn("Unmatched", rows[0]["grade_reason"])

    def test_completed_draft_ui_hides_active_recommendations(self):
        source = Path("modules/draft_center_ui.py").read_text(encoding="utf-8")

        completed_idx = source.index('workspace_ui.render_section_header(\n            "Completed Draft Review"')
        return_idx = source.index("return", completed_idx)
        recommendation_idx = source.index("Recommendation Buckets")
        available_idx = source.index('"Available Board"')

        self.assertLess(return_idx, recommendation_idx)
        self.assertLess(return_idx, available_idx)
        self.assertIn("Completed Draft Review", source)
        self.assertIn("Historical remaining pool", source)
        self.assertIn("Unmatched Sleeper picks", source)
        self.assertIn('"review_mode": True', source)
        self.assertIn('"active_mode": True', source)
        self.assertIn("draft-review-pick-card", source)
        self.assertIn("_completed_round_cards_html", source)
        self.assertIn("Your picks in this draft", source)
        self.assertNotIn("Your picked player IDs", source)
        round_start = source.index("for round_no in sorted(round_groups):")
        historical_start = source.index('with st.expander("Historical remaining pool"', round_start)
        completed_round_block = source[round_start:historical_start]
        self.assertNotIn("st.dataframe", completed_round_block)
        self.assertIn("Best Overall", "".join(draft_assistant.RECOMMENDATION_BUCKETS))

    def test_draft_center_mobile_hierarchy_demotes_diagnostics_and_manual_overrides(self):
        source = Path("modules/draft_center_ui.py").read_text(encoding="utf-8")

        self.assertIn("Review mode: this Sleeper draft is complete", source)
        self.assertIn("Diagnostics: Unmatched Sleeper picks", source)
        self.assertIn('manual_expander_label = "Manual overrides (optional)"', source)
        self.assertIn("Active draft mode only", source)
        self.assertIn("Review mode only", source)
        self.assertIn("Historical remaining pool", source)

    def test_draft_center_espn_limited_mode_has_degraded_state(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('"ESPN limited review mode"', source)
        self.assertIn("Draft Center is gated for ESPN", source)
        self.assertIn("st.session_state.get(\"espn_limited_mode\")", source)
        self.assertIn("app-degraded-state", source)
        self.assertIn("Sleeper remains the full Draft Center path", source)

    def test_completed_draft_review_mobile_card_css_exists(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn(".draft-review-round-grid", css)
        self.assertIn("grid-template-columns: 1fr", css)
        self.assertIn(".draft-review-pick-card", css)
        self.assertIn("min-height: 0", css)


if __name__ == "__main__":
    unittest.main()
