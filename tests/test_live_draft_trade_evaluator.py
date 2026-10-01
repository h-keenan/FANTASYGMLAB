"""Coverage for the live-draft-pick trade evaluator's pure logic.

Verifies: (1) remaining-pick enumeration/exclusion of already-made picks,
(2) stale-pick detection so a pick drafted mid-evaluation never silently
misvalues a trade, (3) pick valuation reuses the real modeled score when
available and otherwise falls back to the app's existing static
round->value chart (never an invented number), (4) player valuation reuses
the Trade Analyzer's own asset adapter, and (5) the verdict reuses the
real trade_value_band thresholds unchanged.
"""

import unittest

import pandas as pd

from modules import live_draft_trade_evaluator as evaluator
from modules.league_rankings import safe_pick_value


def _draft():
    return {
        "draft_order": {"101": 1, "102": 2, "103": 3, "104": 4},
        "metadata": {},
    }


def _rosters():
    return [
        {"roster_id": 101, "owner_id": "u1"},
        {"roster_id": 102, "owner_id": "u2"},
        {"roster_id": 103, "owner_id": "u3"},
        {"roster_id": 104, "owner_id": "u4"},
    ]


def _profiles():
    return {
        "101": {"team_name": "Alpha"},
        "102": {"team_name": "Beta"},
        "103": {"team_name": "Gamma"},
        "104": {"team_name": "Delta"},
    }


class TestRemainingPickOptions(unittest.TestCase):
    def test_excludes_already_made_picks_and_labels_snake_order(self):
        # Pick 1 (slot 1, round 1) already made; round 2 is reversed (snake).
        picks = [{"pick_no": 1, "round": 1, "roster_id": 101, "player_id": "p1"}]
        options = evaluator.remaining_pick_options(
            draft=_draft(),
            rosters=_rosters(),
            picks=picks,
            rounds=2,
            teams=4,
            roster_profiles=_profiles(),
        )
        pick_keys = [opt["pick_key"] for opt in options]
        self.assertNotIn("pick:1", pick_keys)
        self.assertEqual(len(options), 7)

        # Round 2, slot 1 is pick #8 overall (snake: last pick of round 2
        # goes back to slot 1) and must carry round_pick "2.01".
        round_two_slot_one = next(opt for opt in options if opt["pick_no"] == 8)
        self.assertEqual(round_two_slot_one["round"], 2)
        self.assertEqual(round_two_slot_one["round_pick"], "2.01")
        self.assertEqual(round_two_slot_one["original_roster_id"], 101)
        self.assertEqual(round_two_slot_one["team_name"], "Alpha")

    def test_empty_when_no_teams_or_rounds(self):
        self.assertEqual(
            evaluator.remaining_pick_options(
                draft=_draft(), rosters=_rosters(), picks=[], rounds=0, teams=4
            ),
            [],
        )
        self.assertEqual(
            evaluator.remaining_pick_options(
                draft=_draft(), rosters=_rosters(), picks=[], rounds=2, teams=0
            ),
            [],
        )


class TestValidatePickKeysStillOpen(unittest.TestCase):
    def test_flags_keys_no_longer_in_open_options(self):
        open_options = [{"pick_key": "pick:2"}, {"pick_key": "pick:3"}]
        stale = evaluator.validate_pick_keys_still_open(
            ["pick:1", "pick:2"], open_options=open_options
        )
        self.assertEqual(stale, ["pick:1"])

    def test_no_stale_keys_when_all_still_open(self):
        open_options = [{"pick_key": "pick:2"}, {"pick_key": "pick:3"}]
        stale = evaluator.validate_pick_keys_still_open(
            ["pick:2", "pick:3"], open_options=open_options
        )
        self.assertEqual(stale, [])


class TestPickAssetForOption(unittest.TestCase):
    def _option(self):
        return {
            "pick_key": "pick:2",
            "round": 1,
            "round_pick": "1.02",
            "original_roster_id": 102,
            "team_name": "Beta",
        }

    def test_uses_modeled_score_when_matching_asset_exists(self):
        draft_pick_assets = [
            {
                "asset_type": "pick",
                "season": 2026,
                "round": 1,
                "original_roster_id": 102,
                "owner_roster_id": 999,
                "owner_team_name": "Traded-To Team",
                "score": 7200,
            }
        ]
        asset = evaluator.pick_asset_for_option(
            self._option(), season=2026, draft_pick_assets=draft_pick_assets
        )
        self.assertEqual(asset["score"], 7200)
        self.assertEqual(asset["pick_source"], "modeled")
        # Current (post-trade) owner surfaces, not the original slot holder.
        self.assertEqual(asset["owner_roster_id"], 999)
        self.assertEqual(asset["owner_team_name"], "Traded-To Team")
        self.assertEqual(asset["original_roster_id"], 102)

    def test_falls_back_to_existing_static_round_chart_when_unmatched(self):
        asset = evaluator.pick_asset_for_option(
            self._option(), season=2026, draft_pick_assets=[]
        )
        self.assertEqual(asset["pick_source"], "round_default")
        # Must equal the app's own existing fallback chart, not a new number.
        self.assertEqual(asset["score"], safe_pick_value({"round": 1}))

    def test_does_not_match_wrong_season_or_round(self):
        draft_pick_assets = [
            {
                "asset_type": "pick",
                "season": 2027,
                "round": 1,
                "original_roster_id": 102,
                "score": 9999,
            },
            {
                "asset_type": "pick",
                "season": 2026,
                "round": 2,
                "original_roster_id": 102,
                "score": 8888,
            },
        ]
        asset = evaluator.pick_asset_for_option(
            self._option(), season=2026, draft_pick_assets=draft_pick_assets
        )
        self.assertEqual(asset["pick_source"], "round_default")


class TestDraftedPlayerAsset(unittest.TestCase):
    def _players(self):
        return pd.DataFrame(
            [
                {
                    "player_id": "p1",
                    "name": "Test Running Back",
                    "position": "RB",
                    "team": "KC",
                    "value_score": 4500,
                }
            ]
        )

    def test_returns_real_player_asset_shape(self):
        asset = evaluator.drafted_player_asset("p1", df_players=self._players())
        self.assertIsNotNone(asset)
        self.assertEqual(asset["asset_type"], "player")
        self.assertEqual(asset["score"], 4500)
        self.assertEqual(asset["position"], "RB")

    def test_none_for_unknown_player(self):
        self.assertIsNone(evaluator.drafted_player_asset("missing", df_players=self._players()))

    def test_none_for_empty_frame(self):
        self.assertIsNone(
            evaluator.drafted_player_asset("p1", df_players=pd.DataFrame())
        )


class TestEvaluateTrade(unittest.TestCase):
    def test_favorable_band_when_receiving_more_value(self):
        result = evaluator.evaluate_trade(
            send_assets=[{"score": 1000}],
            receive_assets=[{"score": 1800}],
        )
        self.assertEqual(result["delta"], 800)
        self.assertEqual(result["verdict"], "Favorable")

    def test_fair_band_near_even(self):
        result = evaluator.evaluate_trade(
            send_assets=[{"score": 1000}],
            receive_assets=[{"score": 1100}],
        )
        self.assertEqual(result["verdict"], "Fair")

    def test_slight_overpay_band(self):
        result = evaluator.evaluate_trade(
            send_assets=[{"score": 2000}],
            receive_assets=[{"score": 1200}],
        )
        self.assertEqual(result["delta"], -800)
        self.assertEqual(result["verdict"], "Slight Overpay")

    def test_major_overpay_band(self):
        result = evaluator.evaluate_trade(
            send_assets=[{"score": 3000}],
            receive_assets=[{"score": 500}],
        )
        self.assertEqual(result["verdict"], "Major Overpay")

    def test_empty_sides_are_even(self):
        result = evaluator.evaluate_trade(send_assets=[], receive_assets=[])
        self.assertEqual(result["send_total"], 0)
        self.assertEqual(result["receive_total"], 0)
        self.assertEqual(result["delta"], 0)
        self.assertEqual(result["verdict"], "Fair")


if __name__ == "__main__":
    unittest.main()
