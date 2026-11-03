import unittest

import pandas as pd

from modules import model_status
from modules.roster_needs import (
    assessment_from_model,
    classify_shallow_position_rooms,
    room_records,
    select_need_headline,
    true_shallow_position_needs,
)
from tests.need_model_fixtures import room, team_needs


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


class TestAssessmentFromModel(unittest.TestCase):
    """The need model's result, reshaped for the Dashboard / My Team ladder."""

    def test_primary_and_secondary_rooms_are_short_term_needs_in_model_order(self):
        result = team_needs(
            room("RB", "primary", slot="RB1", rank=12),
            room("WR", "secondary", slot="WR3", rank=10),
            room("QB", "covered"),
            room("TE", "watch", rank=7),
        )
        assessment = assessment_from_model(result)

        self.assertEqual(assessment.true_needs, ("RB", "WR"))
        self.assertEqual(assessment.for_position("RB").classification, "short_term_need")
        self.assertEqual(assessment.for_position("RB").severity, 1.0)
        self.assertEqual(assessment.for_position("WR").severity, 0.8)
        self.assertEqual(assessment.for_position("QB").classification, "covered")
        self.assertFalse(assessment.model_status["degraded"])

    def test_watch_room_trailing_the_league_is_an_upgrade_opportunity_not_a_need(self):
        assessment = assessment_from_model(team_needs(room("TE", "watch", rank=7), room("QB", "covered")))

        self.assertEqual(assessment.true_needs, ())
        self.assertEqual(assessment.upgrade_opportunities, ("TE",))
        self.assertEqual(select_need_headline(assessment)["category"], "upgrade")
        self.assertEqual(select_need_headline(assessment)["value"], "TE")

    def test_aging_starters_without_young_cover_are_a_future_risk(self):
        assessment = assessment_from_model(team_needs(room("QB", "watch", rank=3, future_gap=True)))

        self.assertEqual(assessment.future_risks, ("QB",))
        self.assertEqual(assessment.for_position("QB").classification, "future_risk")
        self.assertEqual(select_need_headline(assessment)["category"], "future_risk")

    def test_an_injured_starter_is_injury_pressure_ahead_of_the_need_headline(self):
        assessment = assessment_from_model(team_needs(room("RB", "secondary", rank=10, injured=["Hurt RB"])))

        self.assertEqual(assessment.true_needs, ("RB",))
        self.assertEqual(assessment.temporary_injury_pressures, ("RB",))
        # A need that is only an injury blip headlines as injury pressure, as before.
        self.assertEqual(select_need_headline(assessment)["category"], "injury_pressure")

    def test_a_covered_roster_headlines_balanced(self):
        assessment = assessment_from_model(team_needs(room("QB", "covered"), room("RB", "covered")))

        self.assertEqual(select_need_headline(assessment)["category"], "balanced")

    def test_no_result_is_degraded_never_covered(self):
        assessment = assessment_from_model(None)

        self.assertEqual(assessment.true_needs, ())
        self.assertEqual(model_status.codes(assessment.model_status), ["need_model_unavailable"])
        self.assertTrue(all(item.data_quality == "missing" for item in assessment.positions))
        self.assertEqual(assessment.for_position("RB").reason_codes, ("need_model_unavailable",))

    def test_an_empty_result_is_not_degraded(self):
        # A reference roster with no league to rank against has no needs; that
        # is an answer, not a failure.
        assessment = assessment_from_model({})

        self.assertEqual(assessment.true_needs, ())
        self.assertFalse(assessment.model_status["degraded"])

    def test_room_records_carry_the_label_the_trade_copy_reads(self):
        rooms = room_records(
            team_needs(room("RB", "secondary", slot="RB1", rank=10), room("WR", "covered", surplus_ids=["w9"]))
        )

        self.assertEqual(rooms["RB"]["need_type"], "short-term starter coverage")
        self.assertTrue(rooms["RB"]["true_need"])
        self.assertTrue(rooms["WR"]["surplus"])
        self.assertEqual(rooms["RB"]["weakest_slot"]["rank"], 10)
        self.assertEqual(room_records(None), {})


class TestShallowPositionRooms(unittest.TestCase):
    """K/DEF get their own, simpler binary coverage check (see
    roster_needs.classify_shallow_position_rooms): a league starts one of each,
    so the lineup / league-rank need model that prices QB/RB/WR/TE
    (modules.roster_value_model) does not apply.
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
