import unittest

import pandas as pd

from modules.roster_needs import classify_roster_rooms, true_roster_needs


def player(
    player_id,
    position,
    *,
    age,
    years_exp,
    value,
    role="Flex",
    tier="Contributor",
    opportunity="",
    status="Active",
    injury_status="",
):
    return {
        "player_id": player_id,
        "name": player_id,
        "position": position,
        "team": "DAL",
        "age": age,
        "years_exp": years_exp,
        "value_score": value,
        "market_score": value,
        "role": role,
        "player_tier": tier,
        "opportunity_label": opportunity,
        "status": status,
        "injury_status": injury_status,
    }


class TestRosterNeeds(unittest.TestCase):
    def test_one_qb_room_with_starter_backup_and_developmental_depth_is_covered(self):
        roster = pd.DataFrame(
            [
                player("starter", "QB", age=27, years_exp=5, value=75, tier="Star"),
                player("backup", "QB", age=29, years_exp=7, value=28, opportunity="Strong Opportunity"),
                player("dev-1", "QB", age=22, years_exp=1, value=18, tier="Developmental"),
                player("dev-2", "QB", age=23, years_exp=1, value=15, tier="Developmental"),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False, False, False]

        needs, rooms = true_roster_needs(
            roster,
            lineup,
            {"qb_count": 1, "superflex_count": 0},
            ["QB"],
        )

        self.assertNotIn("QB", needs)
        self.assertFalse(rooms["QB"]["true_need"])
        self.assertEqual(
            rooms["QB"]["need_type"],
            "starter covered with backup/future depth",
        )

    def test_one_qb_room_without_backup_or_future_asset_needs_depth(self):
        roster = pd.DataFrame(
            [player("starter", "QB", age=30, years_exp=8, value=72, tier="Star")]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        needs, rooms = true_roster_needs(
            roster,
            lineup,
            {"qb_count": 1, "superflex_count": 0},
            [],
        )

        self.assertIn("QB", needs)
        self.assertEqual(rooms["QB"]["need_type"], "short-term backup only")

    def test_injured_core_te_with_playable_active_cover_is_not_long_term_need(self):
        roster = pd.DataFrame(
            [
                player(
                    "core-te",
                    "TE",
                    age=22,
                    years_exp=1,
                    value=80,
                    role="Core",
                    tier="Star",
                    status="IR",
                    injury_status="out",
                ),
                player(
                    "active-te",
                    "TE",
                    age=28,
                    years_exp=6,
                    value=35,
                    opportunity="Strong Opportunity",
                ),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [False, True]

        needs, rooms = true_roster_needs(
            roster,
            lineup,
            {"te_count": 1, "te_premium": False},
            ["TE"],
        )

        self.assertNotIn("TE", needs)
        self.assertFalse(rooms["TE"]["true_need"])
        self.assertEqual(
            rooms["TE"]["need_type"],
            "active room covered; future asset injured",
        )

    def test_no_playable_active_te_remains_short_term_need(self):
        roster = pd.DataFrame(
            [
                player(
                    "core-te",
                    "TE",
                    age=22,
                    years_exp=1,
                    value=80,
                    role="Core",
                    tier="Star",
                    status="IR",
                    injury_status="out",
                )
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = False

        needs, rooms = true_roster_needs(
            roster,
            lineup,
            {"te_count": 1, "te_premium": False},
            [],
        )

        self.assertIn("TE", needs)
        self.assertTrue(rooms["TE"]["short_term_need"])

    def test_superflex_requires_more_active_qb_coverage(self):
        roster = pd.DataFrame(
            [
                player("starter", "QB", age=27, years_exp=5, value=75, tier="Star"),
                player("dev", "QB", age=22, years_exp=1, value=16, tier="Developmental"),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False]

        rooms = classify_roster_rooms(
            roster,
            lineup,
            {"qb_count": 1, "superflex_count": 1},
        )

        self.assertTrue(rooms["QB"]["true_need"])
        self.assertEqual(rooms["QB"]["required_starters"], 2)


if __name__ == "__main__":
    unittest.main()
