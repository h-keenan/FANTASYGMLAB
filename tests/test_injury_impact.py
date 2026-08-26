import unittest
import time

import pandas as pd

from app import (
    _has_meaningful_team_injury_impact,
    _team_injury_display_label,
    build_league_intelligence_cards,
)
from modules.rankings import summarize_team_injuries
from modules import injury_ui


class TestInjuryImpact(unittest.TestCase):
    @staticmethod
    def _league_row(summary, *, team_name="Test Team"):
        return {
            "roster_id": 1,
            "team_name": team_name,
            "owner_name": "Owner",
            "owner_username": "owner",
            "mode": "contender",
            "avg_age": 25,
            "starter_current_score": 80,
            "power_rank": 1,
            "starter_rank": 1,
            "rebuild_index": 0,
            "draft_capital": 0,
            "first_rounders": 0,
            "pick_count": 0,
            "trade_count": 0,
            "trade_asset_total": 0,
            "top_heavy_ratio": 1,
            "starter_share": 0.5,
            "bench_current_score": 20,
            "undervalued_gap": 0,
            "injured_bench_players": summary["injured_bench_players"],
            "major_injury_count": summary["major_injury_count"],
            **summary,
        }

    def test_major_starter_outweighs_multiple_minor_bench_injuries(self):
        major_starter_roster = pd.DataFrame(
            [
                {
                    "player_id": "starter-1",
                    "name": "Major Starter",
                    "position": "WR",
                    "status": "IR",
                    "injury_status": "season-ending",
                    "news_updated": time.time(),
                    "market_score": 94,
                    "player_tier": "Elite",
                },
                {
                    "player_id": "bench-healthy",
                    "name": "Healthy Bench",
                    "position": "WR",
                    "status": "Active",
                    "injury_status": "",
                    "news_updated": time.time(),
                    "market_score": 20,
                },
            ]
        )
        major_starter_lineup = major_starter_roster.copy()
        major_starter_lineup["suggested_starter"] = [True, False]

        minor_bench_roster = pd.DataFrame(
            [
                {
                    "player_id": f"bench-{index}",
                    "name": f"Minor Bench {index}",
                    "position": "WR",
                    "status": "Questionable",
                    "injury_status": "limited",
                    "news_updated": time.time(),
                    "market_score": 12,
                }
                for index in range(4)
            ]
            + [
                {
                    "player_id": "healthy-starter",
                    "name": "Healthy Starter",
                    "position": "WR",
                    "status": "Active",
                    "injury_status": "",
                    "news_updated": time.time(),
                    "market_score": 75,
                }
            ]
        )
        minor_bench_lineup = minor_bench_roster.copy()
        minor_bench_lineup["suggested_starter"] = [False, False, False, False, True]

        team_a = summarize_team_injuries(major_starter_roster, major_starter_lineup)
        team_b = summarize_team_injuries(minor_bench_roster, minor_bench_lineup)

        self.assertEqual(team_a["major_injured_starters"], 1)
        self.assertEqual(team_a["injury_impact_flag"], "Major Starter Absence")
        self.assertGreater(team_a["injury_impact_score"], team_b["injury_impact_score"])
        self.assertEqual(team_b["injured_bench_players"], 4)
        self.assertNotEqual(team_b["injury_impact_flag"], "Health Watch")
        self.assertFalse(_has_meaningful_team_injury_impact(team_b))
        self.assertEqual(_team_injury_display_label(team_b), "")
        self.assertEqual(team_a["top_injury_impact_players"][0]["name"], "Major Starter")
        self.assertEqual(team_a["top_injury_impact_players"][0]["player_value_score"], 94.0)
        self.assertGreater(team_a["top_injury_impact_players"][0]["impact_contribution"], 100)

    def test_healthy_team_does_not_receive_health_watch(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "healthy-1",
                    "name": "Healthy Starter",
                    "position": "RB",
                    "status": "Active",
                    "injury_status": "",
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        summary = summarize_team_injuries(roster, lineup)

        self.assertEqual(summary["injury_impact_score"], 0.0)
        self.assertEqual(summary["injury_impact_flag"], "Stable")
        self.assertFalse(_has_meaningful_team_injury_impact(summary))
        self.assertEqual(_team_injury_display_label(summary), "")

    def test_one_major_injured_starter_receives_meaningful_health_label(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "major-1",
                    "name": "Major Starter",
                    "position": "WR",
                    "status": "Out",
                    "injury_status": "season-ending",
                    "market_score": 90,
                    "news_updated": time.time(),
                    "player_tier": "Elite",
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        summary = summarize_team_injuries(roster, lineup)

        self.assertEqual(summary["major_injured_starters"], 1)
        self.assertEqual(summary["injury_impact_flag"], "Major Starter Absence")
        self.assertTrue(_has_meaningful_team_injury_impact(summary))
        self.assertEqual(_team_injury_display_label(summary), "Major Starter Absence")

    def test_minor_bench_injuries_do_not_receive_health_watch(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": f"minor-{index}",
                    "name": f"Minor Bench {index}",
                    "position": "WR",
                    "status": "Questionable",
                    "injury_status": "limited",
                    "market_score": 12,
                    "news_updated": time.time(),
                }
                for index in range(3)
            ]
            + [
                {
                    "player_id": "healthy-starter",
                    "name": "Healthy Starter",
                    "position": "WR",
                    "status": "Active",
                    "injury_status": "",
                    "market_score": 70,
                    "news_updated": time.time(),
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [False, False, False, True]

        summary = summarize_team_injuries(roster, lineup)

        self.assertEqual(summary["injured_bench_players"], 3)
        self.assertLess(summary["injury_impact_score"], 12.0)
        self.assertNotEqual(summary["injury_impact_flag"], "Health Watch")
        self.assertFalse(_has_meaningful_team_injury_impact(summary))
        self.assertEqual(_team_injury_display_label(summary), "")
        self.assertEqual(summary["actionable_injury_players"], [])

    def test_current_moderate_star_starter_is_visible_but_not_a_crisis(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "star-questionable",
                    "name": "Star Starter",
                    "position": "WR",
                    "status": "Doubtful",
                    "injury_status": "day-to-day",
                    "market_score": 90,
                    "news_updated": time.time(),
                    "player_tier": "Star",
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        summary = summarize_team_injuries(roster, lineup)

        self.assertEqual(summary["injury_impact_flag"], "Starter Availability Concern")
        self.assertTrue(injury_ui.has_meaningful_team_injury_impact(summary))
        self.assertFalse(injury_ui.is_acute_injury_pressure(summary))
        self.assertEqual(
            injury_ui.team_injury_display_label(summary),
            "Starter Availability Concern",
        )
        self.assertEqual(summary["actionable_injury_players"][0]["name"], "Star Starter")

    def test_injured_developmental_asset_with_cover_is_not_starter_crisis(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "future-te",
                    "name": "Future Tight End",
                    "position": "TE",
                    "status": "IR",
                    "injury_status": "out",
                    "market_score": 90,
                    "age": 21,
                    "years_exp": 0,
                    "depth_chart_slot": 2,
                    "projected_starter": False,
                    "opportunity_label": "Backup With Upside",
                    "news_updated": time.time(),
                },
                {
                    "player_id": "active-te",
                    "name": "Active Tight End",
                    "position": "TE",
                    "status": "Active",
                    "injury_status": "",
                    "market_score": 62,
                    "age": 27,
                    "years_exp": 5,
                    "depth_chart_slot": 1,
                    "projected_starter": True,
                    "opportunity_label": "Strong Opportunity",
                    "news_updated": time.time(),
                },
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [False, True]

        summary = summarize_team_injuries(roster, lineup)
        advice = injury_ui.team_injury_advice(summary)

        self.assertEqual(summary["active_injured_starters"], 0)
        self.assertEqual(summary["future_asset_injury_count"], 1)
        self.assertEqual(summary["covered_future_injury_positions"], ["TE"])
        self.assertEqual(summary["injury_need_positions"], set())
        self.assertEqual(summary["injury_impact_flag"], "Future Asset Health Watch")
        self.assertFalse(injury_ui.is_acute_injury_pressure(summary))
        self.assertEqual(advice["focus"], "future")
        self.assertIn("playable cover", advice["body"])
        self.assertNotIn("starter availability", advice["title"].lower())
        alert = injury_ui.my_team_injury_alert(summary)
        self.assertEqual(alert["value"], "Future asset injury watch")
        self.assertNotIn("injured starter", alert["value"].lower())
        self.assertIn("future asset", alert["note"].lower())

    def test_injured_starter_without_cover_keeps_strong_warning(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "active-rb",
                    "name": "Active Running Back",
                    "position": "RB",
                    "status": "IR",
                    "injury_status": "out",
                    "market_score": 92,
                    "age": 25,
                    "years_exp": 4,
                    "depth_chart_slot": 1,
                    "projected_starter": True,
                    "opportunity_label": "Starter At Risk",
                    "news_updated": time.time(),
                },
                {
                    "player_id": "depth-rb",
                    "name": "Depth Running Back",
                    "position": "RB",
                    "status": "Active",
                    "injury_status": "",
                    "market_score": 8,
                    "age": 28,
                    "years_exp": 6,
                    "depth_chart_slot": 3,
                    "projected_starter": False,
                    "opportunity_label": "Buried Depth",
                    "news_updated": time.time(),
                },
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False]

        summary = summarize_team_injuries(roster, lineup)

        self.assertEqual(summary["active_injured_starters"], 1)
        self.assertEqual(summary["injury_need_positions"], {"RB"})
        self.assertEqual(summary["injury_impact_flag"], "Major Starter Absence")
        self.assertTrue(injury_ui.is_acute_injury_pressure(summary))
        alert = injury_ui.my_team_injury_alert(summary)
        self.assertEqual(alert["value"], "1 injured starter")

    def test_stale_injury_data_is_labeled_uncertain_in_league_card(self):
        stale_time = time.time() - (90 * 24 * 60 * 60)
        roster = pd.DataFrame(
            [
                {
                    "player_id": "stale-major",
                    "name": "Stale Major",
                    "position": "RB",
                    "team": "DAL",
                    "status": "IR",
                    "injury_status": "rehab",
                    "market_score": 85,
                    "news_updated": stale_time,
                    "player_tier": "Elite",
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True
        summary = summarize_team_injuries(roster, lineup)

        self.assertEqual(summary["injury_data_quality"], "stale")
        self.assertIn("stale", summary["top_injury_impact_summary"].lower())
        self.assertIn(
            "Status Uncertain",
            injury_ui.team_injury_display_label(summary),
        )

        league_row = self._league_row(summary, team_name="Stale Team")
        cards = build_league_intelligence_cards(pd.DataFrame([league_row]), "value_score")
        injury_card = next(card for card in cards if card["label"] == "Most Injured Roster")

        self.assertEqual(injury_card["team_name"], "Stale Team")
        self.assertIn("stale", injury_card["note"].lower())

    def test_missing_data_does_not_claim_a_healthy_league(self):
        roster = pd.DataFrame(
            [{"player_id": "unknown-2", "name": "Unknown Status", "position": "WR"}]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True
        summary = summarize_team_injuries(roster, lineup)

        cards = build_league_intelligence_cards(
            pd.DataFrame([self._league_row(summary, team_name="Unknown Team")]),
            "value_score",
        )
        injury_card = next(card for card in cards if card["label"] == "Most Injured Roster")

        self.assertEqual(injury_card["team_name"], "No clear leader")
        self.assertEqual(injury_card["metric"], "Injury data uncertain")
        self.assertIn("missing or stale", injury_card["note"].lower())

    def test_healthy_team_does_not_become_health_drag_leader(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "healthy-2",
                    "name": "Healthy Player",
                    "position": "QB",
                    "team": "DAL",
                    "status": "Active",
                    "injury_status": "",
                    "market_score": 90,
                    "news_updated": time.time(),
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True
        summary = summarize_team_injuries(roster, lineup)

        cards = build_league_intelligence_cards(
            pd.DataFrame([self._league_row(summary, team_name="Healthy Team")]),
            "value_score",
        )
        injury_card = next(card for card in cards if card["label"] == "Most Injured Roster")

        self.assertEqual(injury_card["team_name"], "No clear leader")
        self.assertEqual(injury_card["metric"], "No current high-value injury cluster detected")

    def test_missing_status_fields_are_not_reported_as_stable(self):
        roster = pd.DataFrame(
            [{"player_id": "unknown-1", "name": "Unknown Status", "position": "RB"}]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = True

        summary = summarize_team_injuries(roster, lineup)

        self.assertEqual(summary["injury_data_quality"], "missing")
        self.assertEqual(summary["injury_impact_flag"], "Injury Data Unavailable")
        self.assertNotEqual(summary["injury_impact_flag"], "Health Watch")
        self.assertFalse(_has_meaningful_team_injury_impact(summary))
        self.assertEqual(_team_injury_display_label(summary), "")


    def test_shared_league_injury_index_matches_per_team_summary(self):
        now = time.time()
        major_roster = pd.DataFrame(
            [
                {
                    "player_id": "starter-1",
                    "name": "Major Starter",
                    "position": "WR",
                    "status": "IR",
                    "injury_status": "season-ending",
                    "news_updated": now,
                    "market_score": 94,
                    "player_tier": "Elite",
                },
                {
                    "player_id": "bench-healthy",
                    "name": "Healthy Bench",
                    "position": "WR",
                    "status": "Active",
                    "injury_status": "",
                    "news_updated": now,
                    "market_score": 20,
                },
            ]
        )
        lineup = major_roster.copy()
        lineup["suggested_starter"] = [True, False]
        from modules.rankings import build_player_injury_index

        league_index = build_player_injury_index(major_roster, now=now)
        shared = summarize_team_injuries(
            major_roster,
            lineup,
            player_injury_index=league_index,
        )
        local = summarize_team_injuries(major_roster, lineup)
        self.assertEqual(shared["injury_impact_flag"], local["injury_impact_flag"])
        self.assertEqual(shared["injured_starters"], local["injured_starters"])
        self.assertEqual(shared["injury_need_positions"], local["injury_need_positions"])
        self.assertEqual(
            shared["top_injury_impact_players"][0]["impact_contribution"],
            local["top_injury_impact_players"][0]["impact_contribution"],
        )


if __name__ == "__main__":
    unittest.main()
