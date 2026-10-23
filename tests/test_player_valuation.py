import unittest

import pandas as pd

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
