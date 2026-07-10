import unittest
from unittest.mock import patch

import pandas as pd

from modules.trade_ideas import (
    _build_team_shape,
    _team_roster_size_context,
    _temporary_injury_trade_guardrail,
    _trade_confidence_context,
    _trade_reasoning_context,
    _trade_surface_sort_key,
    evaluate_trade_market_realism,
    trade_strategy_fit_context,
)


def player(
    name,
    score,
    age,
    *,
    tier="Contributor",
    role="Flex",
    position="WR",
):
    return {
        "asset_type": "player",
        "label": name,
        "name": name,
        "score": score,
        "age": age,
        "player_tier": tier,
        "role": role,
        "position": position,
        "status": "Active",
        "injury_status": "",
    }


def pick(label="2027 1st", score=6500):
    return {
        "asset_type": "pick",
        "label": label,
        "score": score,
        "round": 1,
        "position": "PICK",
    }


class TestTradeStrategyFit(unittest.TestCase):
    def test_trade_shape_filters_covered_te_from_relative_weaknesses(self):
        roster = pd.DataFrame(
            [
                player(
                    "Core TE",
                    80,
                    22,
                    tier="Star",
                    role="Core",
                    position="TE",
                )
                | {
                    "player_id": "te-core",
                    "team": "DAL",
                    "years_exp": 1,
                    "status": "IR",
                    "injury_status": "out",
                },
                player(
                    "Active TE",
                    35,
                    28,
                    tier="Contributor",
                    position="TE",
                )
                | {
                    "player_id": "te-cover",
                    "team": "DAL",
                    "years_exp": 6,
                    "opportunity_label": "Strong Opportunity",
                    "status": "Active",
                    "injury_status": "",
                },
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [False, True]

        with (
            patch(
                "modules.trade_ideas.get_team_vs_league",
                return_value={
                    "strategy": "retool",
                    "mode": "competitive",
                    "weaknesses": ["TE"],
                    "strengths": [],
                },
            ),
            patch(
                "modules.trade_ideas.suggest_optimal_lineup",
                return_value=lineup,
            ),
        ):
            shape = _build_team_shape(
                pd.DataFrame(),
                1,
                roster,
                league_settings={"te_count": 1},
            )

        self.assertNotIn("TE", shape["needs"])
        self.assertEqual(
            shape["room_coverage"]["TE"]["need_type"],
            "active room covered; future asset injured",
        )

    def test_rebuild_prefers_picks_and_youth_over_old_win_now_return(self):
        shape = {"strategy": "rebuild", "archetype_label": "Full Rebuild"}
        outgoing = [player("Older Veteran", 6000, 29)]

        future = trade_strategy_fit_context(
            shape,
            outgoing,
            [player("Young Player", 3000, 22), pick(score=3000)],
        )
        win_now = trade_strategy_fit_context(
            shape,
            outgoing,
            [player("Older Starter", 6000, 30)],
        )

        self.assertGreater(future["score"], win_now["score"])
        self.assertIn("future flexibility", future["reason"].lower())

    def test_contender_prefers_immediate_lineup_upgrade(self):
        shape = {"strategy": "contender", "archetype_label": "Balanced Contender"}
        outgoing = [player("Depth Player", 4000, 25)]

        upgrade = trade_strategy_fit_context(
            shape,
            outgoing,
            [player("Lineup Upgrade", 5000, 28, tier="Star")],
        )
        picks = trade_strategy_fit_context(shape, outgoing, [pick(score=5000)])

        self.assertGreater(upgrade["score"], picks["score"])
        self.assertIn("immediate lineup help", upgrade["reason"].lower())

    def test_retool_avoids_extreme_future_spend_without_upgrade(self):
        shape = {"strategy": "retool", "archetype_label": "Retool Candidate"}

        balanced = trade_strategy_fit_context(
            shape,
            [player("Older Flex", 4500, 28)],
            [player("Younger Flex", 4700, 24)],
        )
        reckless = trade_strategy_fit_context(
            shape,
            [pick(score=6500)],
            [player("Marginal Starter", 4300, 28)],
        )

        self.assertGreater(balanced["score"], reckless["score"])
        self.assertIn("balances present help", balanced["reason"].lower())

    def test_young_powerhouse_favors_consolidation_and_protects_core(self):
        shape = {
            "strategy": "fringe_contender",
            "archetype_label": "Young Competitive Team",
        }
        consolidation = trade_strategy_fit_context(
            shape,
            [
                player("Depth One", 3500, 24),
                player("Depth Two", 3400, 23),
            ],
            [player("Premium Target", 7600, 25, tier="Elite")],
        )
        core_sale = trade_strategy_fit_context(
            shape,
            [player("Young Core", 7000, 23, tier="Star", role="Core")],
            [player("Older Return", 7100, 29, tier="Star")],
        )

        self.assertGreater(consolidation["score"], core_sale["score"])
        self.assertIn("consolidation", consolidation["reason"].lower())

    def test_incompatible_archetype_does_not_override_user_strategy(self):
        shape = {"strategy": "rebuild", "archetype_label": "Aging Contender"}
        context = trade_strategy_fit_context(
            shape,
            [player("Veteran", 6000, 29)],
            [player("Young Player", 3000, 22), pick(score=3000)],
        )

        self.assertEqual(context["archetype"], "")
        self.assertEqual(context["strategy"], "rebuild")
        self.assertIn("rebuild", context["reason"].lower())

    def test_strategy_weight_does_not_rescue_clearly_bad_value(self):
        shape = {"strategy": "rebuild", "archetype_label": "Full Rebuild"}
        context = trade_strategy_fit_context(
            shape,
            [player("Premium Veteran", 9000, 29)],
            [pick(score=4000), player("Young Throw In", 1500, 22)],
        )

        self.assertLessEqual(context["score"], 0)

    def test_strategy_changes_reasoning_and_surface_order(self):
        base_shape = {
            "needs": [],
            "surplus": [],
            "counts": {},
            "minimums": {},
            "draft_capital_tier": "middle",
            "injured_starter_positions": set(),
            "injury_burden": 0,
        }
        partner_shape = {
            **base_shape,
            "strategy": "retool",
            "mode": "competitive",
        }
        send = [player("Veteran", 6000, 29)]
        receive = [player("Young Player", 3000, 22), pick(score=3000)]
        rebuild_reasoning = _trade_reasoning_context(
            {**base_shape, "strategy": "rebuild", "archetype_label": "Full Rebuild"},
            partner_shape,
            send,
            receive,
            "Partner",
        )
        contender_reasoning = _trade_reasoning_context(
            {**base_shape, "strategy": "contender", "archetype_label": "Balanced Contender"},
            partner_shape,
            send,
            receive,
            "Partner",
        )

        self.assertGreater(
            rebuild_reasoning["strategy_fit_score"],
            contender_reasoning["strategy_fit_score"],
        )
        self.assertIn("full rebuild", rebuild_reasoning["strategy_fit_reason"].lower())

        common = {
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "High",
            "market_realism_score": 85,
            "fit_score": 20,
            "partner_fit_score": 10,
            "priority": 100,
        }
        rebuild_idea = {
            **common,
            "strategy_fit_score": rebuild_reasoning["strategy_fit_score"],
        }
        contender_idea = {
            **common,
            "strategy_fit_score": contender_reasoning["strategy_fit_score"],
        }
        self.assertGreater(
            _trade_surface_sort_key(rebuild_idea),
            _trade_surface_sort_key(contender_idea),
        )

    def test_temporary_injury_te_need_blocks_core_wr_overpay(self):
        my_shape = {
            "strategy": "contender",
            "mode": "contender",
            "needs": [],
            "surplus": [],
            "temporary_injury_need_positions": {"TE"},
            "injured_starter_positions": {"TE"},
            "counts": {"TE": 2, "WR": 5},
            "minimums": {"TE": 1, "WR": 4},
        }
        partner_shape = {
            "strategy": "retool",
            "mode": "competitive",
            "needs": ["WR"],
            "surplus": ["TE"],
            "counts": {"TE": 3, "WR": 3},
            "minimums": {"TE": 1, "WR": 4},
        }
        send = [player("Core WR Starter", 7800, 23, tier="Star", role="Core", position="WR")]
        receive = [player("Temporary TE Cover", 4700, 29, tier="Starter", position="TE")]

        reasoning = _trade_reasoning_context(my_shape, partner_shape, send, receive, "Partner")

        self.assertTrue(reasoning["guardrail_hard_fail"])
        self.assertLess(reasoning["score"], 0)
        self.assertIn("Temporary Injury Need", reasoning["tags"])
        self.assertIn("Core Starter Protected", reasoning["tags"])
        self.assertIn("temporary injury coverage", reasoning["summary"].lower())

    def test_temporary_injury_te_need_blocks_starting_te_for_backup_cover(self):
        my_shape = {
            "strategy": "contender",
            "mode": "contender",
            "needs": [],
            "surplus": [],
            "temporary_injury_need_positions": {"TE"},
            "injured_starter_positions": {"TE"},
            "counts": {"TE": 2},
            "minimums": {"TE": 1},
        }
        partner_shape = {
            "strategy": "retool",
            "mode": "competitive",
            "needs": [],
            "surplus": ["TE"],
            "counts": {"TE": 3},
            "minimums": {"TE": 1},
        }
        send = [player("Starting TE", 6200, 23, tier="Core Starter", role="Core", position="TE")]
        receive = [player("Backup TE Cover", 4300, 30, tier="Starter", position="TE")]

        guardrail = _temporary_injury_trade_guardrail(my_shape, send, receive)

        self.assertTrue(guardrail["hard_fail"])
        self.assertIn("Backup After Injury Return", guardrail["tags"])
        self.assertIn("Core Starter Protected", guardrail["tags"])

    def test_temporary_injury_cover_allows_low_cost_depth_trade(self):
        my_shape = {
            "strategy": "contender",
            "mode": "contender",
            "needs": [],
            "surplus": ["WR"],
            "temporary_injury_need_positions": {"TE"},
            "injured_starter_positions": {"TE"},
            "counts": {"TE": 2, "WR": 6},
            "minimums": {"TE": 1, "WR": 4},
        }
        send = [player("Depth WR", 2600, 27, tier="Depth", role="Bench", position="WR")]
        receive = [player("Low Cost TE Cover", 3600, 28, tier="Contributor", position="TE")]

        guardrail = _temporary_injury_trade_guardrail(my_shape, send, receive)

        self.assertTrue(guardrail["applied"])
        self.assertFalse(guardrail["hard_fail"])
        self.assertIn("Low-Cost Coverage", guardrail["tags"])
        self.assertGreaterEqual(guardrail["score_delta"], -6)

    def test_true_long_term_te_upgrade_can_survive_injury_context(self):
        my_shape = {
            "strategy": "contender",
            "mode": "contender",
            "needs": [],
            "surplus": ["WR"],
            "temporary_injury_need_positions": {"TE"},
            "injured_starter_positions": {"TE"},
            "counts": {"TE": 2, "WR": 6},
            "minimums": {"TE": 1, "WR": 4},
        }
        partner_shape = {
            "strategy": "rebuild",
            "mode": "rebuild",
            "needs": ["WR"],
            "surplus": ["TE"],
            "counts": {"TE": 3, "WR": 3},
            "minimums": {"TE": 1, "WR": 4},
        }
        send = [player("Movable WR", 6000, 27, tier="Starter", role="Flex", position="WR")]
        receive = [player("Long Term TE Upgrade", 7200, 24, tier="Star", position="TE")]

        reasoning = _trade_reasoning_context(my_shape, partner_shape, send, receive, "Partner")

        self.assertFalse(reasoning["guardrail_hard_fail"])
        self.assertIn("Temporary Injury Need", reasoning["tags"])
        self.assertGreater(reasoning["score"], 0)

    def test_over_limit_roster_blocks_net_incoming_player_trade(self):
        my_shape = {
            "strategy": "contender",
            "mode": "contender",
            "needs": [],
            "surplus": [],
            "counts": {"WR": 5, "RB": 4},
            "minimums": {"WR": 4, "RB": 3},
            "roster_at_limit": True,
            "roster_over_limit": True,
        }
        partner_shape = {
            "strategy": "retool",
            "mode": "competitive",
            "needs": [],
            "surplus": ["WR", "RB"],
            "counts": {"WR": 6, "RB": 5},
            "minimums": {"WR": 4, "RB": 3},
        }
        send = [player("Playable Starter", 5600, 25, tier="Starter", position="WR")]
        receive = [
            player("Return One", 3300, 24, tier="Contributor", position="WR"),
            player("Return Two", 2800, 25, tier="Contributor", position="RB"),
        ]

        market = evaluate_trade_market_realism(
            send_assets=send,
            receive_assets=receive,
            my_shape=my_shape,
            partner_shape=partner_shape,
            partner_name="Partner",
        )

        self.assertTrue(market["hard_fail"])
        self.assertIn("roster_limit_pressure", market["hard_fail_flags"])
        self.assertIn("roster spots", market["summary"].lower())

    def test_roster_pressure_uses_active_max_roster_size_for_trade_guardrail(self):
        df_team = pd.DataFrame(
            [
                {
                    "player_id": str(index),
                    "name": f"Player {index}",
                    "position": "WR",
                }
                for index in range(31)
            ]
        )

        context = _team_roster_size_context(
            df_team,
            {
                "starter_count": 10,
                "bench_count": 18,
                "max_roster_size": 28,
                "ir_count": 4,
                "taxi_slots": 4,
            },
        )

        self.assertTrue(context["roster_over_limit"])
        self.assertEqual(context["active_roster_limit"], 28)

    def test_user_cornerstone_asset_cannot_headline_negative_value_trade(self):
        my_shape = {
            "strategy": "fringe_contender",
            "mode": "contender",
            "needs": [],
            "surplus": ["RB"],
            "counts": {"RB": 5, "WR": 5},
            "minimums": {"RB": 3, "WR": 4},
        }
        partner_shape = {
            "strategy": "retool",
            "mode": "competitive",
            "needs": ["RB"],
            "surplus": ["WR"],
            "counts": {"RB": 3, "WR": 6},
            "minimums": {"RB": 3, "WR": 4},
        }
        send = [
            player("Cornerstone RB", 9400, 22, tier="Star", role="Flex", position="RB"),
            player("Depth QB", 800, 32, tier="Depth", role="Bench", position="QB"),
        ]
        receive = [player("Strong WR", 8150, 24, tier="Star", role="Flex", position="WR")]

        market = evaluate_trade_market_realism(
            send_assets=send,
            receive_assets=receive,
            my_shape=my_shape,
            partner_shape=partner_shape,
            partner_name="Partner",
        )

        self.assertTrue(market["hard_fail"])
        self.assertIn("user_core_protection", market["hard_fail_flags"])
        self.assertIn("cornerstone", market["summary"].lower())

    def test_user_cornerstone_plus_extra_requires_clear_tier_up(self):
        my_shape = {
            "strategy": "fringe_contender",
            "mode": "contender",
            "needs": [],
            "surplus": ["RB"],
            "counts": {"RB": 5, "WR": 5},
            "minimums": {"RB": 3, "WR": 4},
        }
        partner_shape = {
            "strategy": "retool",
            "mode": "competitive",
            "needs": ["RB"],
            "surplus": ["WR"],
            "counts": {"RB": 3, "WR": 6},
            "minimums": {"RB": 3, "WR": 4},
        }
        send = [
            player("Cornerstone RB", 9400, 22, tier="Elite", role="Flex", position="RB"),
            player("Depth QB", 800, 32, tier="Depth", role="Bench", position="QB"),
        ]
        receive = [player("Slightly Better WR", 10100, 24, tier="Elite", role="Flex", position="WR")]

        market = evaluate_trade_market_realism(
            send_assets=send,
            receive_assets=receive,
            my_shape=my_shape,
            partner_shape=partner_shape,
            partner_name="Partner",
        )

        self.assertTrue(market["hard_fail"])
        self.assertIn("user_core_protection", market["hard_fail_flags"])
        self.assertIn("tier-up", market["summary"].lower())

    def test_user_cornerstone_plus_pick_requires_clear_tier_up(self):
        my_shape = {
            "strategy": "fringe_contender",
            "mode": "contender",
            "needs": [],
            "surplus": ["WR"],
            "counts": {"RB": 4, "WR": 6},
            "minimums": {"RB": 3, "WR": 4},
        }
        partner_shape = {
            "strategy": "retool",
            "mode": "competitive",
            "needs": ["WR"],
            "surplus": ["RB"],
            "counts": {"RB": 5, "WR": 3},
            "minimums": {"RB": 3, "WR": 4},
        }
        send = [
            player("Cornerstone WR", 8700, 23, tier="Star", role="Flex", position="WR"),
            pick(label="2027 3rd", score=500),
        ]
        receive = [player("Slightly Better RB", 9100, 21, tier="Elite", role="Flex", position="RB")]

        market = evaluate_trade_market_realism(
            send_assets=send,
            receive_assets=receive,
            my_shape=my_shape,
            partner_shape=partner_shape,
            partner_name="Partner",
        )

        self.assertTrue(market["hard_fail"])
        self.assertIn("user_core_protection", market["hard_fail_flags"])

    def test_one_qb_does_not_buy_qb_with_premium_receiver(self):
        my_shape = {
            "strategy": "fringe_contender",
            "mode": "contender",
            "needs": [],
            "surplus": ["WR"],
            "counts": {"QB": 2, "WR": 6},
            "minimums": {"QB": 1, "WR": 4},
        }
        partner_shape = {
            "strategy": "retool",
            "mode": "competitive",
            "needs": ["WR"],
            "surplus": ["QB"],
            "counts": {"QB": 3, "WR": 3},
            "minimums": {"QB": 1, "WR": 4},
        }
        send = [player("Premium WR", 5400, 27, tier="Star", role="Flex", position="WR")]
        receive = [
            player("1QB Starter", 4600, 28, tier="Starter", role="Flex", position="QB"),
            pick(label="2027 3rd", score=500),
        ]

        market = evaluate_trade_market_realism(
            send_assets=send,
            receive_assets=receive,
            my_shape=my_shape,
            partner_shape=partner_shape,
            partner_name="Partner",
            league_settings={"qb_format": "1QB"},
        )

        self.assertTrue(market["hard_fail"])
        self.assertIn("one_qb_qb_cost", market["hard_fail_flags"])

    def test_temporary_injury_negative_value_trade_downgrades_confidence(self):
        strong_fit = {"score": 28, "partner_score": 10}
        strong_market = {"score": 84, "hard_fail": False, "value_delta": -1300}

        normal = _trade_confidence_context(
            fit_context=strong_fit,
            market_context=strong_market,
            reasoning_tags=["Value Arbitrage"],
            reasoning_summary="Useful market path.",
        )
        injury_patch = _trade_confidence_context(
            fit_context=strong_fit,
            market_context=strong_market,
            reasoning_tags=["Temporary Injury Need", "Short-Term Coverage Only"],
            reasoning_summary="Useful market path.",
        )

        self.assertEqual(normal["label"], "High")
        self.assertLess(injury_patch["score"], normal["score"])
        self.assertNotEqual(injury_patch["label"], "High")


if __name__ == "__main__":
    unittest.main()
