import unittest

import pandas as pd

from modules.roster_needs import (
    assess_team_needs,
    classify_roster_rooms,
    classify_shallow_position_rooms,
    true_roster_needs,
    true_shallow_position_needs,
)


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

    def test_canonical_assessment_separates_covered_relative_qb_weakness(self):
        roster = pd.DataFrame(
            [
                player("elite-qb", "QB", age=27, years_exp=5, value=75, tier="Star"),
                player(
                    "backup-qb",
                    "QB",
                    age=29,
                    years_exp=7,
                    value=28,
                    opportunity="Backup With Upside",
                ),
                player(
                    "rookie-qb",
                    "QB",
                    age=22,
                    years_exp=1,
                    value=18,
                    tier="Developmental",
                ),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False, False]

        assessment = assess_team_needs(
            roster,
            lineup,
            {"qb_count": 1, "superflex_count": 0, "qb_format": "1QB"},
            relative_weaknesses=["QB"],
        )
        qb = assessment.for_position("QB")

        self.assertIsNotNone(qb)
        self.assertEqual(qb.classification, "covered")
        self.assertFalse(qb.true_need)
        self.assertTrue(qb.relative_weakness)
        self.assertNotIn("QB", assessment.true_needs)
        self.assertIn("QB", assessment.relative_weaknesses)
        self.assertIn("QB", assessment.upgrade_opportunities)
        self.assertIn("covered_relative_weakness", qb.reason_codes)

    def test_canonical_assessment_does_not_promote_covered_relative_rb_weakness(self):
        roster = pd.DataFrame(
            [
                player(
                    "starter-rb",
                    "RB",
                    age=23,
                    years_exp=2,
                    value=60,
                    tier="Core Starter",
                ),
                player(
                    "depth-rb",
                    "RB",
                    age=22,
                    years_exp=1,
                    value=25,
                    tier="Developmental",
                ),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False]

        assessment = assess_team_needs(
            roster,
            lineup,
            {"rb_count": 1},
            relative_weaknesses=["RB"],
        )
        rb = assessment.for_position("RB")

        self.assertEqual(rb.classification, "covered")
        self.assertFalse(rb.true_need)
        self.assertTrue(rb.relative_weakness)
        self.assertNotIn("RB", assessment.true_needs)
        self.assertIn("RB", assessment.relative_weaknesses)
        self.assertIn("RB", assessment.upgrade_opportunities)
        self.assertIn("covered_relative_weakness", rb.reason_codes)

    def test_canonical_assessment_marks_no_playable_qb_starter_as_true_need(self):
        roster = pd.DataFrame(
            [
                player(
                    "unavailable-qb",
                    "QB",
                    age=30,
                    years_exp=8,
                    value=72,
                    tier="Star",
                    status="IR",
                    injury_status="out",
                )
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        assessment = assess_team_needs(
            roster,
            lineup,
            {"qb_count": 1, "superflex_count": 0},
        )
        qb = assessment.for_position("QB")

        self.assertTrue(qb.true_need)
        self.assertEqual(qb.classification, "short_term_need")
        self.assertTrue(qb.temporary_injury_pressure)
        self.assertIn("insufficient_active_coverage", qb.reason_codes)

    def test_canonical_assessment_preserves_conservative_incomplete_metadata(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "unknown-qb",
                    "name": "Unknown QB",
                    "position": "QB",
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        assessment = assess_team_needs(
            roster,
            lineup,
            {"qb_count": 1, "superflex_count": 0},
        )
        qb = assessment.for_position("QB")

        self.assertTrue(qb.true_need)
        self.assertEqual(qb.data_quality, "limited")
        self.assertIn("limited_player_metadata", qb.reason_codes)

    def test_superflex_developmental_depth_does_not_replace_active_starter(self):
        roster = pd.DataFrame(
            [
                player("starter", "QB", age=27, years_exp=5, value=75, tier="Star"),
                player(
                    "developmental",
                    "QB",
                    age=22,
                    years_exp=1,
                    value=18,
                    tier="Developmental",
                ),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False]

        assessment = assess_team_needs(
            roster,
            lineup,
            {"qb_count": 1, "superflex_count": 1, "qb_format": "Superflex"},
        )
        qb = assessment.for_position("QB")

        self.assertTrue(qb.true_need)
        self.assertEqual(qb.required_starters, 2)
        self.assertEqual(qb.classification, "short_term_need")
        self.assertIn("insufficient_active_coverage", qb.reason_codes)

    def test_two_qb_format_requires_two_active_qb_starters(self):
        roster = pd.DataFrame(
            [
                player("starter", "QB", age=27, years_exp=5, value=75, tier="Star"),
                player(
                    "developmental",
                    "QB",
                    age=22,
                    years_exp=1,
                    value=18,
                    tier="Developmental",
                ),
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False]

        assessment = assess_team_needs(
            roster,
            lineup,
            {"qb_count": 2, "superflex_count": 0, "qb_format": "2QB"},
        )
        qb = assessment.for_position("QB")

        self.assertTrue(qb.true_need)
        self.assertEqual(qb.required_starters, 2)
        self.assertEqual(qb.classification, "short_term_need")


class TestShallowPositionRooms(unittest.TestCase):
    """K/DEF get their own, simpler binary-ish coverage model (see
    roster_needs.classify_shallow_position_rooms) instead of being folded
    into the CORE_POSITIONS depth-gradient machinery above, which is the
    model `TestRosterNeeds` exercises.
    """

    def test_one_startable_kicker_is_covered_not_a_need(self):
        roster = pd.DataFrame([player("k1", "K", age=28, years_exp=5, value=10)])

        rooms = classify_shallow_position_rooms(roster, {})
        needs, _ = true_shallow_position_needs(roster, {})

        self.assertFalse(rooms["K"]["true_need"])
        self.assertNotIn("K", needs)

    def test_one_startable_defense_is_covered_not_a_need(self):
        roster = pd.DataFrame([player("def1", "DEF", age=0, years_exp=0, value=8)])

        rooms = classify_shallow_position_rooms(roster, {})
        needs, _ = true_shallow_position_needs(roster, {})

        self.assertFalse(rooms["DEF"]["true_need"])
        self.assertNotIn("DEF", needs)

    def test_no_rostered_kicker_is_a_true_need(self):
        roster = pd.DataFrame([player("rb1", "RB", age=24, years_exp=2, value=50)])

        rooms = classify_shallow_position_rooms(roster, {})
        needs, _ = true_shallow_position_needs(roster, {})

        self.assertTrue(rooms["K"]["true_need"])
        self.assertTrue(rooms["DEF"]["true_need"])
        self.assertIn("K", needs)
        self.assertIn("DEF", needs)

    def test_rostered_kicker_on_ir_does_not_count_as_covered(self):
        roster = pd.DataFrame(
            [
                player(
                    "k1",
                    "K",
                    age=28,
                    years_exp=5,
                    value=10,
                    status="IR",
                    injury_status="out",
                ),
                player("def1", "DEF", age=0, years_exp=0, value=8),
            ]
        )

        rooms = classify_shallow_position_rooms(roster, {})
        needs, _ = true_shallow_position_needs(roster, {})

        self.assertTrue(rooms["K"]["true_need"])
        self.assertIn("K", needs)
        self.assertFalse(rooms["DEF"]["true_need"])
        self.assertNotIn("DEF", needs)

    def test_empty_roster_needs_both_shallow_positions(self):
        roster = pd.DataFrame(columns=["player_id", "position", "status", "injury_status"])

        needs, rooms = true_shallow_position_needs(roster, {})

        self.assertEqual(sorted(needs), ["DEF", "K"])
        self.assertTrue(rooms["K"]["true_need"])
        self.assertTrue(rooms["DEF"]["true_need"])


if __name__ == "__main__":
    unittest.main()
