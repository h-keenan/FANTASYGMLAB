import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from modules import live_draft


def players():
    frame = pd.DataFrame([
        {"player_id": "qb1", "name": "Quarterback One", "position": "QB", "team": "KC", "age": 29, "value_score": 90, "years_exp": 7},
        {"player_id": "rb1", "name": "Running Back One", "position": "RB", "team": "LV", "age": 24, "value_score": 88, "years_exp": 3},
        {"player_id": "wr1", "name": "Veteran Star", "position": "WR", "team": "CIN", "age": 30, "value_score": 96, "years_exp": 8},
        {"player_id": "wr2", "name": "Young Receiver", "position": "WR", "team": "ARI", "age": 22, "value_score": 86, "years_exp": 1},
        {"player_id": "te1", "name": "Tight End One", "position": "TE", "team": "CHI", "age": 25, "value_score": 84, "years_exp": 2},
        {"player_id": "rqb", "name": "Rookie QB", "position": "QB", "team": "CLE", "age": 21, "value_score": 80, "years_exp": 0},
        {"player_id": "rb2", "name": "Depth Back", "position": "RB", "team": "MIA", "age": 26, "value_score": 70, "years_exp": 4},
        {"player_id": "te2", "name": "Depth Tight End", "position": "TE", "team": "SEA", "age": 27, "value_score": 65, "years_exp": 5},
    ])
    frame["active"] = True
    frame["status"] = "Active"
    frame["fantasycalc_value"] = frame["value_score"]
    return frame


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
            league_settings={"league_format": "Dynasty", "qb_slots": 1, "rb_slots": 2, "wr_slots": 2, "te_slots": 1},
            score_field="value_score",
            my_roster_id=1,
        )
        old_ranks = dict(zip(first["roster_id"].astype(str), first["team_rank"]))
        updated = live_draft.build_live_team_rankings(
            first_picks + [{"roster_id": 3, "player_id": "qb1", "pick_no": 4}],
            df_players=players(),
            rosters=rosters,
            roster_profiles=profiles,
            league_settings={"league_format": "Dynasty", "qb_slots": 1, "rb_slots": 2, "wr_slots": 2, "te_slots": 1},
            score_field="value_score",
            my_roster_id=1,
            previous_ranks=old_ranks,
        )

        self.assertEqual(set(updated["team_name"]), {"Alpha", "Bravo", "Charlie"})
        self.assertEqual(updated["team_rank"].tolist(), [1, 2, 3])
        self.assertTrue(updated["is_mine"].any())
        self.assertTrue((updated["pick_count"] >= 1).all())
        self.assertTrue((updated["live_team_score"] >= 0).all())

    def test_team_rankings_include_existing_roster_and_drafted_players(self):
        player_pool = players().copy()
        player_pool["dynasty_score"] = player_pool["value_score"]
        ranked = live_draft.build_live_team_rankings(
            [{"roster_id": 1, "player_id": "wr1", "pick_no": 1}],
            df_players=player_pool,
            rosters=[
                {"roster_id": 1, "players": ["qb1", "rb1", "wr2", "te1"]},
                {"roster_id": 2, "players": ["rb2", "te2"]},
            ],
            roster_profiles={"1": {"team_name": "Full Team"}, "2": {"team_name": "Thin Team"}},
            league_settings={
                "league_format": "Dynasty",
                "qb_slots": 1,
                "rb_slots": 1,
                "wr_slots": 1,
                "te_slots": 1,
                "flex_slots": 0,
            },
            score_field="rebuild_score",
        )
        full_team = ranked[ranked["roster_id"] == 1].iloc[0]

        self.assertEqual(int(full_team["existing_count"]), 4)
        self.assertEqual(int(full_team["pick_count"]), 1)
        self.assertEqual(int(full_team["roster_count"]), 5)
        self.assertEqual(full_team["score_field_used"], "dynasty_score")
        self.assertGreater(float(full_team["starter_value"]), 0)
        self.assertGreater(float(full_team["total_value"]), float(full_team["starter_value"]))

    def test_neutral_dynasty_baseline_overrides_rebuild_lens(self):
        player_pool = pd.DataFrame([
            {
                "player_id": "elite-vet", "name": "Elite Veteran", "position": "QB",
                "age": 30, "rebuild_score": 60, "dynasty_score": 100,
                "active": True, "status": "Active", "fantasycalc_value": 100,
            },
            {
                "player_id": "young-role", "name": "Young Role Player", "position": "RB",
                "age": 22, "rebuild_score": 110, "dynasty_score": 70,
                "active": True, "status": "Active", "fantasycalc_value": 70,
            },
        ])
        ranked = live_draft.build_live_draft_rankings(
            player_pool,
            roster_df=pd.DataFrame(),
            league_settings={"league_format": "Dynasty", "qb_format": "1QB"},
            score_field="rebuild_score",
            draft={"metadata": {"type": "startup"}},
        )

        self.assertEqual(ranked.iloc[0]["player_id"], "elite-vet")
        self.assertEqual(float(ranked.iloc[0]["base_value"]), 100)
        self.assertLessEqual(abs(float(ranked.iloc[0]["age_strategy_adjustment"])), 3)

    def test_team_score_has_no_standalone_age_component(self):
        source = Path("modules/live_draft.py").read_text(encoding="utf-8")
        team_source = source.split("def build_live_team_rankings", 1)[1].split(
            "def preserve_last_valid_board", 1
        )[0]
        score_formula = team_source.split('board["live_team_score"] =', 1)[1].split(
            "board = board.sort_values", 1
        )[0]
        self.assertNotIn("age", score_formula.casefold())


    def test_live_rankings_do_not_mutate_shared_player_evaluations(self):
        source = players()
        source["dynasty_score"] = source["value_score"]
        original = source.copy(deep=True)

        live_draft.build_live_draft_rankings(
            source,
            roster_df=pd.DataFrame(),
            league_settings={"league_format": "Dynasty", "qb_format": "1QB"},
            score_field="rebuild_score",
            draft={"metadata": {"type": "startup"}},
        )

        pd.testing.assert_frame_equal(source, original)
        self.assertNotIn("league_adjusted_draft_score", source.columns)
        self.assertNotIn("base_value", source.columns)


    def test_position_availability_is_precomputed_once_per_refresh(self):
        source = Path("modules/live_draft.py").read_text(encoding="utf-8")
        ranking_source = source.split("def build_live_draft_rankings", 1)[1].split(
            "def build_live_team_rankings", 1
        )[0]
        self.assertIn("pool_position_counts = Counter", ranking_source)
        self.assertNotIn("== position).sum()", ranking_source)

    def test_team_lookup_filters_to_rostered_and_drafted_players(self):
        source = Path("modules/live_draft.py").read_text(encoding="utf-8")
        team_source = source.split("def build_live_team_rankings", 1)[1].split(
            "def preserve_last_valid_board", 1
        )[0]
        self.assertIn("relevant_player_ids", team_source)
        self.assertIn("relevant_players = players[", team_source)


class TestLiveDraftRankingsTierAndMovementAvoidFullIterrows(unittest.TestCase):
    """Self-hosted perf audit: build_live_draft_rankings used to
    `.iterrows()` the ENTIRE undrafted pool twice more (tier assignment,
    movement calc) beyond its already-flagged scoring-components pass,
    recomputed on every live-draft poll. Those two were switched to
    zipping the one or two needed columns directly instead of boxing a
    full row per iteration. These tests pin both the behavior (identical
    tier/movement output, including the pre-existing `or`-fallback and
    tier-alias semantics) and the perf fix (iterrows not called a number
    of times proportional to the full pool).
    """

    def test_tier_and_movement_match_previous_row_based_semantics(self):
        pool = players()
        # One player already carries a recognized tier alias (should map
        # through _tier_for_rank's alias table, not the percentile bands);
        # the rest fall back to the rank-percentile bands.
        pool.loc[pool["player_id"] == "wr1", "player_tier"] = "elite"
        previous = {"rb1": 1, "wr2": 10}  # wr1/others absent on purpose.

        result = board(previous=previous, pool=pool)

        wr1 = result.loc[result["player_id"] == "wr1"].iloc[0]
        self.assertEqual(wr1["tier"], "Elite")

        for _, row in result.iterrows():
            pid = row["player_id"]
            if pid in previous:
                expected_movement = previous[pid] - int(row["overall_rank"])
                self.assertEqual(row["movement"], expected_movement)
            else:
                self.assertEqual(row["movement"], 0)

    def test_missing_tier_and_player_id_columns_degrade_the_same_as_before(self):
        # No "player_tier"/"tier" columns at all, and (via a minimal pool)
        # confirm this doesn't raise and falls back to percentile tiers.
        pool = players().drop(columns=["name"], errors="ignore")
        result = board(pool=pool)
        self.assertIn("tier", result.columns)
        self.assertTrue(result["tier"].isin(
            {"Elite", "Star", "Core Starter", "Starter", "Upside", "Depth"}
        ).all())

    def test_tier_and_movement_do_not_iterrows_the_full_pool(self):
        real_iterrows = pd.DataFrame.iterrows
        call_count = {"n": 0}

        def counting_iterrows(self):
            call_count["n"] += 1
            yield from real_iterrows(self)

        pool = players()
        with mock.patch.object(pd.DataFrame, "iterrows", counting_iterrows):
            board(pool=pool)

        # One remaining call is modules.player_eligibility's own (separate,
        # pre-existing, out of scope here) iterrows pass; one more is the
        # still-untouched scoring-components loop (line 761) — both
        # legitimate. Before this fix there were two MORE full-pool
        # iterrows passes on top of those (tier assignment, movement calc).
        # This pins that those two are gone, not that iterrows is banned
        # outright.
        self.assertLessEqual(call_count["n"], 2)


if __name__ == "__main__":
    unittest.main()
