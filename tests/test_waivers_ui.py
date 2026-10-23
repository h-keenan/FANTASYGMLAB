import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import player_cards, waivers_logic


class TestWaiversUI(unittest.TestCase):
    @staticmethod
    def _render_card(row):
        tap_renderer = Mock(return_value="")
        quick_view = Mock()
        waivers_logic.render_free_agent_cards(
            pd.DataFrame([row]),
            "value_score",
            recommendation_reason_text=lambda value, _limit: str(value),
            player_display_name=lambda value: value.get("name"),
            cached_headshot_data_url=lambda _player_id: "",
            asset_initials=lambda _name: "P",
            player_status_style=lambda label: {
                "label": label,
                "tone": "neutral",
            },
            canonical_player_status=lambda value: str(value),
            tier_chip_html=lambda value: f"<span class='dg-tier-chip'>{value}</span>" if value else "",
            player_support_chip_html=(
                lambda value, tone: f"<span class='player-support-chip player-support-chip-{tone}'>{value}</span>"
                if value
                else ""
            ),
            player_status_pill_html=lambda value: f"<span>{value}</span>",
            render_tappable_player_html=tap_renderer,
            open_player_quick_view=quick_view,
            render_recommendation_feedback=Mock(),
        )
        return tap_renderer.call_args.kwargs["html"], tap_renderer, quick_view


    def test_top_waiver_suppresses_kicker_when_roster_has_viable_kicker(self):
        free_agents = pd.DataFrame(
            [
                {"player_id": "k-2", "name": "Top Kicker", "position": "K", "value_score": 90},
                {"player_id": "rb-1", "name": "Upside Back", "position": "RB", "value_score": 60},
            ]
        )
        roster = pd.DataFrame(
            [
                {
                    "player_id": "k-1",
                    "name": "Roster Kicker",
                    "position": "K",
                    "team": "DAL",
                    "status": "Active",
                    "injury_status": "",
                }
            ]
        )

        selected = waivers_logic.select_top_waiver_opportunity(
            free_agents,
            roster,
            {"k_count": 1},
            "value_score",
        )

        self.assertEqual(selected["player_id"], "rb-1")

    def test_top_waiver_allows_kicker_for_clear_required_lineup_need(self):
        free_agents = pd.DataFrame(
            [
                {"player_id": "k-2", "name": "Top Kicker", "position": "K", "value_score": 90},
                {"player_id": "rb-1", "name": "Upside Back", "position": "RB", "value_score": 60},
            ]
        )

        selected = waivers_logic.select_top_waiver_opportunity(
            free_agents,
            pd.DataFrame(
                [{"player_id": "rb-0", "position": "RB", "team": "DAL"}]
            ),
            {"k_count": 1},
            "value_score",
        )

        self.assertEqual(selected["player_id"], "k-2")
        self.assertTrue(selected["kicker_need_fit"])
        self.assertIn("requires a kicker", selected["injury_replacement_note"])

    def test_top_waiver_suppresses_kicker_for_a_pre_draft_league(self):
        """coridian_, 2026-10-20, screenshot: a league that "hasn't even
        drafted" surfaced 5 kickers at the top of Priority Adds. A
        pre-draft/mid-draft roster is empty of a kicker for a completely
        different reason than "genuinely forgot one" -- the whole LEAGUE
        is mostly empty, not just this one roster. Same single-player
        roster fixture as test_top_waiver_allows_kicker_for_clear_required_
        lineup_need (so the only variable changed is the league-wide
        rosters list), but now most of the league's 10 other rosters have
        zero players too, matching a real pre-draft league's shape."""

        free_agents = pd.DataFrame(
            [
                {"player_id": "k-2", "name": "Top Kicker", "position": "K", "value_score": 90},
                {"player_id": "rb-1", "name": "Upside Back", "position": "RB", "value_score": 60},
            ]
        )
        my_roster = {"roster_id": 1, "players": ["rb-0"]}
        # 9 of 10 OTHER rosters are still completely empty -- a real
        # pre-draft/mid-draft league shape (population_ratio well under 0.5).
        other_rosters = [{"roster_id": i, "players": []} for i in range(2, 11)]
        rosters = [my_roster] + other_rosters

        selected = waivers_logic.select_top_waiver_opportunity(
            free_agents,
            pd.DataFrame([{"player_id": "rb-0", "position": "RB", "team": "DAL"}]),
            {"k_count": 1},
            "value_score",
            league={"league_id": "pre-draft-league"},
            rosters=rosters,
        )

        self.assertEqual(selected["player_id"], "rb-1")

    def test_top_waiver_still_allows_kicker_when_league_is_populated_even_if_passed(self):
        """Same real roster/league plumbing as the pre-draft test above,
        but with a normally-populated league (population_ratio >= 0.5) --
        proves passing league/rosters through doesn't itself suppress a
        genuine kicker need, only an actual pre-draft league does."""

        free_agents = pd.DataFrame(
            [
                {"player_id": "k-2", "name": "Top Kicker", "position": "K", "value_score": 90},
                {"player_id": "rb-1", "name": "Upside Back", "position": "RB", "value_score": 60},
            ]
        )
        my_roster = {"roster_id": 1, "players": ["rb-0"]}
        other_rosters = [
            {"roster_id": i, "players": [f"p{i}-1", f"p{i}-2", f"p{i}-3"]} for i in range(2, 11)
        ]
        rosters = [my_roster] + other_rosters

        selected = waivers_logic.select_top_waiver_opportunity(
            free_agents,
            pd.DataFrame([{"player_id": "rb-0", "position": "RB", "team": "DAL"}]),
            {"k_count": 1},
            "value_score",
            league={"league_id": "populated-league"},
            rosters=rosters,
        )

        self.assertEqual(selected["player_id"], "k-2")

    def test_top_waiver_does_not_choose_qb_or_te_without_true_need(self):
        free_agents = pd.DataFrame(
            [
                {"player_id": "te-1", "name": "Tight End", "position": "TE", "value_score": 90},
                {"player_id": "qb-1", "name": "Quarterback", "position": "QB", "value_score": 85},
                {"player_id": "rb-1", "name": "Running Back", "position": "RB", "value_score": 60},
            ]
        )

        selected = waivers_logic.select_top_waiver_opportunity(
            free_agents,
            pd.DataFrame(),
            {"k_count": 0},
            "value_score",
            needed_positions=["RB"],
        )

        self.assertEqual(selected["player_id"], "rb-1")


    def test_waiver_confidence_label_reflects_real_need_fit_and_value_signals(self):
        # High: a real, already-computed roster-need match (or an injury
        # replacement fit) — the strongest signal rank_priority_add_candidates
        # itself sorts on first.
        self.assertEqual(
            waivers_logic.waiver_confidence_label(
                {"priority_need_fit": True, "priority_value_opportunity": False, "score": 40},
                3,
            ),
            ("High", "Matches a real roster need on this roster."),
        )
        self.assertEqual(
            waivers_logic.waiver_confidence_label(
                {"priority_need_fit": False, "injury_replacement_fit": True, "score": 40},
                5,
            )[0],
            "High",
        )
        # Medium: elite wire value, but not tied to a stated roster need.
        self.assertEqual(
            waivers_logic.waiver_confidence_label(
                {"priority_need_fit": False, "priority_value_opportunity": True, "score": 40},
                4,
            )[0],
            "Medium",
        )
        self.assertEqual(
            waivers_logic.waiver_confidence_label(
                {"priority_need_fit": False, "priority_value_opportunity": False, "score": 40},
                1,
            )[0],
            "Medium",
        )
        # Low: stale or non-positive score under the current lens.
        self.assertEqual(
            waivers_logic.waiver_confidence_label(
                {"priority_need_fit": True, "priority_value_opportunity": True, "score": 0},
                1,
            )[0],
            "Low",
        )
        self.assertEqual(
            waivers_logic.waiver_confidence_label(
                {
                    "priority_need_fit": True,
                    "priority_value_opportunity": True,
                    "score": 40,
                    "stale_free_agent": True,
                },
                1,
            )[0],
            "Low",
        )
        # Depth-level add: neither a need match nor standout wire value.
        self.assertEqual(
            waivers_logic.waiver_confidence_label(
                {"priority_need_fit": False, "priority_value_opportunity": False, "score": 40},
                8,
            )[0],
            "Low",
        )
        # Rows that never went through the Priority Adds ranker (e.g. Stash/
        # Watchlist/FAAB Shortlist) carry neither flag at all — an honest
        # empty label rather than a fabricated one.
        self.assertEqual(
            waivers_logic.waiver_confidence_label({"score": 40}, 1),
            ("", ""),
        )


    def test_annotate_sleeper_trending_add_marks_only_mapped_players(self):
        free_agents = pd.DataFrame(
            [
                {"player_id": "100", "name": "A"},
                {"player_id": "200", "name": "B"},
            ]
        )
        annotated = waivers_logic.annotate_sleeper_trending_add(
            free_agents, {"100": {"count": 42, "rank": 1}}
        )
        self.assertTrue(bool(annotated.loc[0, "sleeper_trending_add"]))
        self.assertEqual(annotated.loc[0, "sleeper_trending_add_count"], 42)
        self.assertEqual(annotated.loc[0, "sleeper_trending_add_rank"], 1)
        self.assertFalse(bool(annotated.loc[1, "sleeper_trending_add"]))
        self.assertIsNone(annotated.loc[1, "sleeper_trending_add_count"])

    def test_annotate_sleeper_trending_add_defaults_when_map_empty(self):
        free_agents = pd.DataFrame([{"player_id": "100", "name": "A"}])
        annotated = waivers_logic.annotate_sleeper_trending_add(free_agents, None)
        self.assertFalse(bool(annotated.loc[0, "sleeper_trending_add"]))
        self.assertIsNone(annotated.loc[0, "sleeper_trending_add_count"])


if __name__ == "__main__":
    unittest.main()
