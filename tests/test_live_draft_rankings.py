import unittest
from pathlib import Path

import pandas as pd

from modules import live_draft, live_draft_ui


def players():
    return pd.DataFrame([
        {"player_id": "qb1", "name": "Quarterback One", "position": "QB", "team": "KC", "age": 29, "value_score": 90, "years_exp": 7},
        {"player_id": "rb1", "name": "Running Back One", "position": "RB", "team": "LV", "age": 24, "value_score": 88, "years_exp": 3},
        {"player_id": "wr1", "name": "Veteran Star", "position": "WR", "team": "CIN", "age": 30, "value_score": 96, "years_exp": 8},
        {"player_id": "wr2", "name": "Young Receiver", "position": "WR", "team": "ARI", "age": 22, "value_score": 86, "years_exp": 1},
        {"player_id": "te1", "name": "Tight End One", "position": "TE", "team": "CHI", "age": 25, "value_score": 84, "years_exp": 2},
        {"player_id": "rqb", "name": "Rookie QB", "position": "QB", "team": "CLE", "age": 21, "value_score": 80, "years_exp": 0},
        {"player_id": "rb2", "name": "Depth Back", "position": "RB", "team": "MIA", "age": 26, "value_score": 70, "years_exp": 4},
        {"player_id": "te2", "name": "Depth Tight End", "position": "TE", "team": "SEA", "age": 27, "value_score": 65, "years_exp": 5},
    ])


def board(settings=None, roster=None, draft=None, previous=None, pool=None):
    return live_draft.build_live_draft_rankings(
        pool if pool is not None else players(),
        roster_df=roster if roster is not None else pd.DataFrame([{"position": "WR"}, {"position": "WR"}, {"position": "RB"}]),
        league_settings=settings or {"league_format": "Dynasty", "qb_format": "1QB"},
        score_field="value_score",
        draft=draft or {"metadata": {"type": "startup"}},
        picks_until_mine=5,
        previous_ranks=previous,
    )


class TestLiveDraftRankings(unittest.TestCase):
    def test_drafted_players_are_excluded(self):
        pool = live_draft.available_player_pool(players(), [{"player_id": "wr1"}], score_field="value_score")
        ranked = board(pool=pool)
        self.assertNotIn("wr1", ranked["player_id"].tolist())

    def test_overall_and_positional_ranks(self):
        ranked = board()
        self.assertEqual(ranked["overall_rank"].tolist(), list(range(1, len(ranked) + 1)))
        wrs = ranked[ranked["position"] == "WR"]
        self.assertEqual(wrs["position_rank"].tolist(), list(range(1, len(wrs) + 1)))

    def test_superflex_boosts_quarterbacks(self):
        one_qb = board({"league_format": "Dynasty", "qb_format": "1QB"})
        superflex = board({"league_format": "Dynasty", "qb_format": "Superflex", "superflex_slots": 1})
        one = float(one_qb.loc[one_qb.player_id == "qb1", "format_adjustment"].iloc[0])
        sf = float(superflex.loc[superflex.player_id == "qb1", "format_adjustment"].iloc[0])
        self.assertGreater(sf, one)

    def test_te_premium_boosts_tight_ends(self):
        normal = board({"league_format": "Dynasty", "qb_format": "1QB"})
        premium = board({"league_format": "Dynasty", "qb_format": "1QB", "te_premium": True})
        self.assertGreater(
            float(premium.loc[premium.player_id == "te1", "format_adjustment"].iloc[0]),
            float(normal.loc[normal.player_id == "te1", "format_adjustment"].iloc[0]),
        )

    def test_roster_fit_rewards_thin_position(self):
        roster = pd.DataFrame([{"position": "WR"}] * 7 + [{"position": "QB"}] * 2)
        ranked = board(roster=roster)
        rb_fit = float(ranked.loc[ranked.player_id == "rb1", "roster_fit_score"].iloc[0])
        wr_fit = float(ranked.loc[ranked.player_id == "wr2", "roster_fit_score"].iloc[0])
        self.assertGreater(rb_fit, wr_fit)

    def test_contender_and_rebuilder_age_calibration(self):
        contender = board({"league_format": "Dynasty", "team_strategy": "Contender"})
        rebuild = board({"league_format": "Dynasty", "team_strategy": "Rebuild"})
        contender_age = float(contender.loc[contender.player_id == "wr1", "age_strategy_adjustment"].iloc[0])
        rebuild_age = float(rebuild.loc[rebuild.player_id == "wr1", "age_strategy_adjustment"].iloc[0])
        self.assertGreater(contender_age, rebuild_age)
        self.assertGreaterEqual(rebuild_age, -3.0)

    def test_elite_veteran_beats_weaker_young_player(self):
        ranked = board({"league_format": "Dynasty", "team_strategy": "Rebuild"})
        veteran_rank = int(ranked.loc[ranked.player_id == "wr1", "overall_rank"].iloc[0])
        youth_rank = int(ranked.loc[ranked.player_id == "wr2", "overall_rank"].iloc[0])
        self.assertLess(veteran_rank, youth_rank)

    def test_rookie_draft_does_not_apply_startup_age_logic(self):
        ranked = board(
            {"league_format": "Dynasty", "team_strategy": "Rebuild"},
            draft={"metadata": {"type": "rookie"}},
        )
        self.assertTrue((ranked["age_strategy_adjustment"] == 0).all())
        veteran_format = float(ranked.loc[ranked.player_id == "wr1", "format_adjustment"].iloc[0])
        self.assertLess(veteran_format, -100)

    def test_ranking_updates_after_pick(self):
        first = board()
        old = dict(zip(first["player_id"], first["overall_rank"]))
        picked_id = first.iloc[0]["player_id"]
        remaining = live_draft.available_player_pool(players(), [{"player_id": picked_id}], score_field="value_score")
        updated = board(previous=old, pool=remaining)
        self.assertNotIn(picked_id, updated["player_id"].tolist())
        self.assertEqual(int(updated.iloc[0]["overall_rank"]), 1)

    def test_api_failure_preserves_last_valid_board(self):
        valid = board()
        preserved = live_draft.preserve_last_valid_board(pd.DataFrame(), valid, api_error=True)
        pd.testing.assert_frame_equal(valid, preserved)

    def test_no_sleeper_mutation_calls(self):
        source = Path("modules/live_draft.py").read_text(encoding="utf-8").casefold()
        for token in ("requests.post", "requests.put", "requests.patch", "requests.delete"):
            self.assertNotIn(token, source)
        self.assertEqual(live_draft.LIVE_DRAFT_WRITE_METHOD_TOKENS, ())

    def test_mobile_rankings_use_compact_rows(self):
        source = Path("modules/live_draft_ui.py").read_text(encoding="utf-8")
        self.assertIn("live-rank-row", source)
        self.assertIn("Live Draft Rankings", source)
        self.assertNotIn("def _render_available_pool", source)
        self.assertIn("with st.expander(\"How the live score is built\"", source)

    def test_labels_and_tiers_are_not_uniform(self):
        ranked = board()
        self.assertGreater(len(set(ranked["tier"])), 1)
        labels = set(ranked["recommendation_label"]) - {""}
        self.assertIn("Best Available", labels)
        self.assertIn("Avoid / Reach", labels)
        self.assertGreater(len(labels), 2)


    def test_duplicate_valuation_columns_do_not_crash_rankings(self):
        source = players()
        source["scarcity_score"] = 99
        source["base_value"] = source["value_score"]
        source = pd.concat([source, source[["scarcity_score"]]], axis=1)
        self.assertTrue(source.columns.duplicated().any())

        ranked = board(pool=source)

        self.assertFalse(ranked.columns.duplicated().any())
        self.assertEqual(len(ranked), len(source))
        self.assertIn("league_adjusted_draft_score", ranked.columns)


    def test_multiple_ranking_rows_do_not_become_markdown_code_blocks(self):
        rows = board().head(3).to_dict("records")
        rendered_rows = [live_draft_ui._ranking_row_html(row) for row in rows]
        combined = "".join(rendered_rows)

        self.assertTrue(all(html.startswith("<article") for html in rendered_rows))
        self.assertTrue(all(html.endswith("</article>") for html in rendered_rows))
        self.assertNotIn("\n    <article", combined)
        self.assertNotIn("\n<article", combined)
        self.assertEqual(combined.count("<article class='live-rank-row'>"), 3)


    def test_live_team_rankings_rerank_rosters_as_picks_arrive(self):
        rosters = [
            {"roster_id": 1, "owner_id": "a"},
            {"roster_id": 2, "owner_id": "b"},
            {"roster_id": 3, "owner_id": "c"},
        ]
        profiles = {
            "1": {"team_name": "Alpha"},
            "2": {"team_name": "Bravo"},
            "3": {"team_name": "Charlie"},
        }
        first_picks = [
            {"roster_id": 1, "player_id": "wr1", "pick_no": 1},
            {"roster_id": 2, "player_id": "rb2", "pick_no": 2},
            {"roster_id": 3, "player_id": "te2", "pick_no": 3},
        ]
        first = live_draft.build_live_team_rankings(
            first_picks,
            df_players=players(),
            rosters=rosters,
            roster_profiles=profiles,
            score_field="value_score",
            my_roster_id=1,
        )
        old_ranks = dict(zip(first["roster_id"].astype(str), first["team_rank"]))
        updated = live_draft.build_live_team_rankings(
            first_picks + [{"roster_id": 3, "player_id": "qb1", "pick_no": 4}],
            df_players=players(),
            rosters=rosters,
            roster_profiles=profiles,
            score_field="value_score",
            my_roster_id=1,
            previous_ranks=old_ranks,
        )

        self.assertEqual(set(updated["team_name"]), {"Alpha", "Bravo", "Charlie"})
        self.assertEqual(updated["team_rank"].tolist(), [1, 2, 3])
        self.assertTrue(updated["is_mine"].any())
        self.assertTrue((updated["pick_count"] >= 1).all())
        self.assertTrue((updated["live_team_score"] >= 0).all())

    def test_team_rankings_normalize_temporary_pick_count_difference(self):
        ranked = live_draft.build_live_team_rankings(
            [
                {"roster_id": 1, "player_id": "wr2", "pick_no": 1},
                {"roster_id": 1, "player_id": "rb2", "pick_no": 2},
                {"roster_id": 2, "player_id": "wr1", "pick_no": 3},
            ],
            df_players=players(),
            rosters=[{"roster_id": 1}, {"roster_id": 2}],
            roster_profiles={"1": {"team_name": "Two Picks"}, "2": {"team_name": "One Elite Pick"}},
            score_field="value_score",
        )
        elite = ranked[ranked["roster_id"] == 2].iloc[0]
        self.assertGreater(float(elite["adjusted_total_value"]), float(elite["total_value"]))

    def test_main_draft_center_uses_shared_mobile_ranking_cards(self):
        source = Path("modules/draft_center_ui.py").read_text(encoding="utf-8")
        self.assertIn("live_draft.build_live_draft_rankings", source)
        self.assertIn("live_draft_ui._ranking_row_html", source)
        active_board = source.split('"Available Board"', 1)[1].split("return {", 1)[0]
        self.assertNotIn("st.dataframe(", active_board)

    def test_live_team_rankings_are_rendered_before_available_players(self):
        source = Path("modules/live_draft_ui.py").read_text(encoding="utf-8")
        self.assertIn("Live Team Rankings", source)
        snapshot = source.split("def render_snapshot()", 1)[1]
        self.assertLess(
            snapshot.index("_render_live_team_rankings(state)"),
            snapshot.index("_render_live_rankings(state"),
        )


if __name__ == "__main__":
    unittest.main()
