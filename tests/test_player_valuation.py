import unittest

import pandas as pd

import app
from modules.rankings import current_availability_multiplier, injury_multiplier


def valuation_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "qb",
                "name": "Quarterback",
                "position": "QB",
                "team": "DAL",
                "age": 26,
                "years_exp": 4,
                "dynasty_score": 5000,
                "value_score": 5000,
                "market_score": 5000,
                "role_score": 5000,
                "opportunity_score": 5000,
                "scarcity_score": 5000,
                "risk_multiplier": 1.0,
                "status": "Active",
                "injury_status": "",
                "search_rank": 100,
            },
            {
                "player_id": "te",
                "name": "Tight End",
                "position": "TE",
                "team": "DAL",
                "age": 25,
                "years_exp": 3,
                "dynasty_score": 5000,
                "value_score": 5000,
                "market_score": 5000,
                "role_score": 5000,
                "opportunity_score": 5000,
                "scarcity_score": 5000,
                "risk_multiplier": 1.0,
                "status": "Active",
                "injury_status": "",
                "search_rank": 100,
            },
            {
                "player_id": "old-rb",
                "name": "Older RB",
                "position": "RB",
                "team": "DAL",
                "age": 29,
                "years_exp": 7,
                "dynasty_score": 5000,
                "value_score": 5000,
                "market_score": 5000,
                "role_score": 5000,
                "opportunity_score": 5000,
                "scarcity_score": 5000,
                "risk_multiplier": 1.0,
                "status": "Active",
                "injury_status": "",
                "search_rank": 100,
            },
            {
                "player_id": "young-wr",
                "name": "Young WR",
                "position": "WR",
                "team": "DAL",
                "age": 22,
                "years_exp": 1,
                "dynasty_score": 5000,
                "value_score": 5000,
                "market_score": 5000,
                "role_score": 5000,
                "opportunity_score": 5000,
                "scarcity_score": 5000,
                "risk_multiplier": 1.0,
                "status": "Active",
                "injury_status": "",
                "search_rank": 100,
            },
        ]
    )


class TestPlayerValuationContext(unittest.TestCase):
    def test_superflex_increases_qb_value_relative_to_1qb(self):
        base = valuation_frame()
        one_qb = app.apply_valuation_lens(base, "Dynasty", {"qb_format": "1QB"})
        superflex = app.apply_valuation_lens(base, "Dynasty", {"qb_format": "Superflex", "superflex_count": 1})

        one_qb_value = int(one_qb.loc[one_qb["player_id"].eq("qb"), "dynasty_score"].iloc[0])
        superflex_value = int(superflex.loc[superflex["player_id"].eq("qb"), "dynasty_score"].iloc[0])

        self.assertGreater(superflex_value, one_qb_value)

    def test_te_premium_increases_te_value(self):
        base = valuation_frame()
        normal = app.apply_valuation_lens(base, "Dynasty", {"te_premium": False})
        premium = app.apply_valuation_lens(base, "Dynasty", {"te_premium": True})

        normal_value = int(normal.loc[normal["player_id"].eq("te"), "dynasty_score"].iloc[0])
        premium_value = int(premium.loc[premium["player_id"].eq("te"), "dynasty_score"].iloc[0])

        self.assertGreater(premium_value, normal_value)

    def test_dynasty_rebuild_lens_penalizes_older_rb_vs_young_asset(self):
        valued = app.apply_valuation_lens(valuation_frame(), "Rebuild", {"league_format": "Dynasty"})

        old_rb = int(valued.loc[valued["player_id"].eq("old-rb"), "rebuild_score"].iloc[0])
        young_wr = int(valued.loc[valued["player_id"].eq("young-wr"), "rebuild_score"].iloc[0])

        self.assertLess(old_rb, young_wr)

    def test_minor_injury_has_small_current_availability_hit(self):
        healthy = current_availability_multiplier("Active", "DAL", 100, "")
        minor = current_availability_multiplier("Questionable", "DAL", 100, "limited")

        self.assertGreaterEqual(minor, healthy * 0.90)

    def test_major_injury_discount_is_meaningful_but_not_zero_for_dynasty(self):
        major = injury_multiplier("Injured Reserve", "season-ending")

        self.assertGreater(major, 0.50)
        self.assertLess(major, 0.80)

    def test_redraft_season_ending_availability_is_heavily_discounted(self):
        healthy = current_availability_multiplier("Active", "DAL", 100, "")
        major = current_availability_multiplier("Injured Reserve", "DAL", 100, "season-ending")

        self.assertLess(major, healthy * 0.50)


if __name__ == "__main__":
    unittest.main()
