import unittest
import time

import pandas as pd

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

    def test_taxi_squad_player_with_a_minor_injury_is_not_called_out(self):
        """coridian_, 2026-10-18: "If someone's in taxi squad they don't
        need to be always listed especially if it's not a crazy injury."
        A taxi player can't be started/sat regardless of health, so a
        minor/moderate tag has no decision attached to it — even a high-
        value one shouldn't surface by name."""

        roster = pd.DataFrame(
            [
                {
                    "player_id": "taxi-questionable",
                    "name": "Taxi Rookie",
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
        lineup["suggested_starter"] = False

        summary = summarize_team_injuries(roster, lineup, taxi_player_ids=["taxi-questionable"])

        self.assertEqual(summary["actionable_injury_players"], [])

    def test_taxi_squad_player_with_a_real_injury_still_shows(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "taxi-major",
                    "name": "Taxi Rookie",
                    "position": "WR",
                    "status": "IR",
                    "injury_status": "season-ending",
                    "market_score": 90,
                    "news_updated": time.time(),
                    "player_tier": "Star",
                }
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = False

        summary = summarize_team_injuries(roster, lineup, taxi_player_ids=["taxi-major"])

        self.assertEqual(summary["actionable_injury_players"][0]["name"], "Taxi Rookie")

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
        # Real player identity for the single unambiguous starter this alert
        # routes to — position/score come straight from the same
        # injury-impact record; tier is "" (never fabricated) since this
        # fixture carries no player_tier column at all.
        self.assertEqual(alert["route_player_id"], "active-rb")
        self.assertEqual(alert["route_player_position"], "RB")
        self.assertEqual(alert["route_player_tier"], "")
        self.assertGreater(alert["route_player_score"], 0)

    def test_injured_starter_alert_carries_real_tier_when_present(self):
        roster = pd.DataFrame(
            [
                {
                    "player_id": "active-rb",
                    "name": "Active Running Back",
                    "position": "RB",
                    "team": "SEA",
                    "status": "IR",
                    "injury_status": "out",
                    "market_score": 92,
                    "age": 25,
                    "years_exp": 4,
                    "depth_chart_slot": 1,
                    "projected_starter": True,
                    "opportunity_label": "Starter At Risk",
                    "news_updated": time.time(),
                    "player_tier": "Elite",
                },
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True]

        summary = summarize_team_injuries(roster, lineup)
        alert = injury_ui.my_team_injury_alert(summary)

        self.assertEqual(alert["route_player_id"], "active-rb")
        self.assertEqual(alert["route_player_team"], "SEA")
        # Same canonical stored-tier column every other player-identity
        # surface reads — not a second/fabricated tier scheme.
        self.assertEqual(alert["route_player_tier"], "Elite")

    def test_injury_alert_mentions_every_actionable_player_not_just_the_starter(self):
        # coridian_, 2026-10-17: "all players mentioned need to have the
        # player pfp" — a card naming 3 players (1 starter + 2 future
        # assets) previously only carried identity for the single starter
        # `route_player_*` routes to; `mentioned_players` carries all of
        # them, same identity shape, so a client can show a photo for each.
        roster = pd.DataFrame(
            [
                {
                    "player_id": "starter-qb",
                    "name": "Starter QB",
                    "position": "QB",
                    "team": "PHI",
                    "status": "Questionable",
                    "injury_status": "questionable",
                    "market_score": 95,
                    "age": 27,
                    "years_exp": 5,
                    "depth_chart_slot": 1,
                    "projected_starter": True,
                    "opportunity_label": "Starter At Risk",
                    "news_updated": time.time(),
                    "player_tier": "Elite",
                },
                {
                    "player_id": "future-qb",
                    "name": "Future QB",
                    "position": "QB",
                    "team": "PHI",
                    "status": "IR",
                    "injury_status": "out",
                    "market_score": 40,
                    "age": 22,
                    "years_exp": 1,
                    "depth_chart_slot": 2,
                    "projected_starter": False,
                    "opportunity_label": "Backup With Upside",
                    "news_updated": time.time(),
                    "player_tier": "Depth",
                },
                {
                    "player_id": "future-wr",
                    "name": "Future WR",
                    "position": "WR",
                    "team": "PHI",
                    "status": "IR",
                    "injury_status": "out",
                    "market_score": 35,
                    "age": 21,
                    "years_exp": 0,
                    "depth_chart_slot": 3,
                    "projected_starter": False,
                    "opportunity_label": "Backup With Upside",
                    "news_updated": time.time(),
                    "player_tier": "Depth",
                },
            ]
        )
        lineup = roster.copy()
        lineup["suggested_starter"] = [True, False, False]

        summary = summarize_team_injuries(roster, lineup)
        alert = injury_ui.my_team_injury_alert(summary)

        mentioned_ids = {item["player_id"] for item in alert["mentioned_players"]}
        self.assertEqual(mentioned_ids, {"starter-qb", "future-qb", "future-wr"})
        by_id = {item["player_id"]: item for item in alert["mentioned_players"]}
        self.assertEqual(by_id["starter-qb"]["position"], "QB")
        self.assertEqual(by_id["starter-qb"]["player_tier"], "Elite")
        self.assertEqual(by_id["future-wr"]["player_tier"], "Depth")


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
