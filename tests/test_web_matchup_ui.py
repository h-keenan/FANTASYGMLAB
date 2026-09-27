"""Tests for modules.web_matchup_ui's data-assembly/formatting logic.

Scope: this file tests THIS module's own shaping (not-ready reasons,
projection attachment/formatting, presentation adapters) — not
modules.player_projections itself (see tests/test_player_projections.py) and
not services.mobile_api_service's reused _matchup_side/_real_current_lineup
helpers (already covered by tests/test_mobile_api_service.py's own matchup
tests, whose fixtures this file mirrors for the happy-path case below).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from modules import web_matchup_ui


def _fake_matchup_players_frame() -> pd.DataFrame:
    """Two full rosters: mine (season value 2000/player) and my opponent's
    (1000/player) — mirrors tests/test_mobile_api_service.py's own fixture so
    the reused _matchup_side/_real_current_lineup helpers behave identically
    here as they do for the mobile endpoint.
    """

    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "WR"]
    rows = []
    for prefix, score, tier, opportunity in (
        ("mine", 2000, "Elite", "Workhorse"),
        ("opp", 1000, "Solid", "Rotational"),
    ):
        for i, position in enumerate(positions, start=1):
            rows.append(
                {
                    "player_id": f"{prefix}{i}",
                    "name": f"{prefix.title()} Player {i}",
                    "position": position,
                    "team": "KC",
                    "age": 26,
                    "years_exp": 4,
                    "status": "Active",
                    "injury_status": None,
                    "player_tier": tier,
                    "opportunity_label": opportunity,
                    "score": score,
                    "dynasty_score": score,
                    "value_score": score,
                    "rebuild_score": score,
                }
            )
    return pd.DataFrame(rows)


_SETTINGS = {"type": 2, "leg": 5, "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN"]}

_ROSTERS_BY_ID = {
    "1": {
        "roster_id": 1,
        "owner_id": "sleeper-user-1",
        "players": [f"mine{i}" for i in range(1, 10)],
        "settings": {"wins": 3, "losses": 1, "ties": 0},
    },
    "2": {
        "roster_id": 2,
        "owner_id": "sleeper-user-2",
        "players": [f"opp{i}" for i in range(1, 10)],
        "settings": {"wins": 2, "losses": 2, "ties": 0},
    },
}

_PROFILES = {
    "1": {"team_name": "My Squad", "owner_name": "Me", "avatar_url": None},
    "2": {"team_name": "Their Squad", "owner_name": "Them", "avatar_url": None},
}


def _no_projection_stub(player_id, week, season, *, players=None, defense_strength=None):
    return {"status": "insufficient_player_data", "player_id": player_id, "week": week, "season": season}


class TestBuildMatchupViewNotReadyReasons(unittest.TestCase):
    def _base_kwargs(self, **overrides):
        kwargs = dict(
            current_week=5,
            matchups=[{"roster_id": 1, "matchup_id": 3}, {"roster_id": 2, "matchup_id": 3}],
            my_roster_id="1",
            rosters_by_id=_ROSTERS_BY_ID,
            profiles=_PROFILES,
            valued=_fake_matchup_players_frame(),
            settings=_SETTINGS,
            score_field="value_score",
            season=2026,
            players_map={},
            defense_strength={},
        )
        kwargs.update(overrides)
        return kwargs

    def test_no_current_week(self):
        result = web_matchup_ui.build_matchup_view(**self._base_kwargs(current_week=0))
        self.assertEqual(result["reason"], "no_current_week")
        self.assertIsNone(result["my_team"])

    def test_no_current_week_when_none(self):
        result = web_matchup_ui.build_matchup_view(**self._base_kwargs(current_week=None))
        self.assertEqual(result["reason"], "no_current_week")

    def test_no_matchup_data(self):
        result = web_matchup_ui.build_matchup_view(**self._base_kwargs(matchups=[]))
        self.assertEqual(result["reason"], "no_matchup_data")
        self.assertEqual(result["week"], 5)

    def test_roster_not_in_matchups(self):
        result = web_matchup_ui.build_matchup_view(
            **self._base_kwargs(matchups=[{"roster_id": 2, "matchup_id": 3}])
        )
        self.assertEqual(result["reason"], "roster_not_in_matchups")

    def test_bye_week_when_matchup_id_is_none(self):
        result = web_matchup_ui.build_matchup_view(
            **self._base_kwargs(matchups=[{"roster_id": 1, "matchup_id": None}])
        )
        self.assertEqual(result["reason"], "bye_week")

    def test_bye_week_when_no_opponent_shares_matchup_id(self):
        result = web_matchup_ui.build_matchup_view(
            **self._base_kwargs(matchups=[{"roster_id": 1, "matchup_id": 3}, {"roster_id": 2, "matchup_id": 4}])
        )
        self.assertEqual(result["reason"], "bye_week")

    def test_roster_not_in_matchups_when_my_roster_id_unmatched(self):
        result = web_matchup_ui.build_matchup_view(**self._base_kwargs(my_roster_id="99"))
        self.assertEqual(result["reason"], "roster_not_in_matchups")

    def test_not_a_member_of_league_when_paired_roster_missing_from_rosters(self):
        # Sleeper's matchups payload says roster 1 is paired this week, but
        # the rosters fetch didn't return roster 1 itself -- a narrow,
        # defensive edge case distinct from "not paired at all" (bye_week).
        rosters = {"2": _ROSTERS_BY_ID["2"]}
        result = web_matchup_ui.build_matchup_view(**self._base_kwargs(rosters_by_id=rosters))
        self.assertEqual(result["reason"], "not_a_member_of_league")

    def test_opponent_roster_missing(self):
        rosters = {"1": _ROSTERS_BY_ID["1"]}
        result = web_matchup_ui.build_matchup_view(**self._base_kwargs(rosters_by_id=rosters))
        self.assertEqual(result["reason"], "opponent_roster_missing")

    def test_no_player_data_when_valued_is_empty(self):
        result = web_matchup_ui.build_matchup_view(**self._base_kwargs(valued=pd.DataFrame()))
        self.assertEqual(result["reason"], "no_player_data")


class TestBuildMatchupViewHappyPath(unittest.TestCase):
    def test_assembles_both_sides_with_projections_attached(self):
        with patch("modules.web_matchup_ui.project_player_week", side_effect=_no_projection_stub):
            result = web_matchup_ui.build_matchup_view(
                current_week=5,
                matchups=[
                    {
                        "roster_id": 1,
                        "matchup_id": 3,
                        "starters": ["mine1", "mine2"],
                        "starters_points": [12.5, 8.0],
                        "points": 20.5,
                    },
                    {
                        "roster_id": 2,
                        "matchup_id": 3,
                        "starters": ["opp1", "opp2"],
                        "starters_points": [5.0, 6.0],
                        "points": 11.0,
                    },
                ],
                my_roster_id="1",
                rosters_by_id=_ROSTERS_BY_ID,
                profiles=_PROFILES,
                valued=_fake_matchup_players_frame(),
                settings=_SETTINGS,
                score_field="value_score",
                season=2026,
                players_map={},
                defense_strength={},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["week"], 5)

        mine = result["my_team"]
        theirs = result["opponent"]
        self.assertEqual(mine["team_name"], "My Squad")
        self.assertEqual(theirs["team_name"], "Their Squad")
        self.assertGreater(mine["season_value_total"], theirs["season_value_total"])
        self.assertEqual(result["comparison"]["edge"], "you")

        # Real Sleeper live data surfaced additively.
        self.assertTrue(mine["has_live_data"])
        self.assertEqual(mine["real_points"], 20.5)
        self.assertTrue(result["real_comparison"]["edge"] == "you")

        # Every starter (suggested AND real) got a projection attached —
        # honoring the injected stub's honest edge-case status rather than a
        # fabricated number.
        for player in mine["starters"] + theirs["starters"] + mine["real_starters"] + theirs["real_starters"]:
            self.assertIn("projection", player)
            self.assertEqual(player["projection"]["status"], "insufficient_player_data")
            self.assertEqual(player["projection_note"], "Not enough recent games yet for a projection.")

    def test_empty_roster_when_neither_roster_has_players(self):
        rosters = {
            "1": {**_ROSTERS_BY_ID["1"], "players": []},
            "2": {**_ROSTERS_BY_ID["2"], "players": []},
        }
        with patch("modules.web_matchup_ui.project_player_week", side_effect=_no_projection_stub):
            result = web_matchup_ui.build_matchup_view(
                current_week=5,
                matchups=[{"roster_id": 1, "matchup_id": 3}, {"roster_id": 2, "matchup_id": 3}],
                my_roster_id="1",
                rosters_by_id=rosters,
                profiles=_PROFILES,
                valued=_fake_matchup_players_frame(),
                settings=_SETTINGS,
                score_field="value_score",
                season=2026,
                players_map={},
                defense_strength={},
            )
        self.assertEqual(result["reason"], "empty_roster")


class TestFormatProjectionNote(unittest.TestCase):
    def test_none_projection(self):
        self.assertEqual(web_matchup_ui.format_projection_note(None), "")

    def test_ok_status_with_tier_and_opponent(self):
        note = web_matchup_ui.format_projection_note(
            {
                "status": "ok",
                "point_estimate": 14.2,
                "low": 10.5,
                "high": 17.9,
                "confidence": "medium",
                "opponent": "DEN",
                "basis": {"opponent_defense_tier": "tough"},
            }
        )
        self.assertEqual(note, "Proj 14.2 pts (10.5–17.9) · medium confidence · vs tough DEN defense")

    def test_ok_status_without_defense_signal(self):
        note = web_matchup_ui.format_projection_note(
            {
                "status": "ok",
                "point_estimate": 9.0,
                "low": 6.0,
                "high": 12.0,
                "confidence": "low",
                "opponent": "DEN",
                "basis": {"opponent_defense_tier": None},
            }
        )
        self.assertEqual(note, "Proj 9.0 pts (6.0–12.0) · low confidence")

    def test_bye_week(self):
        self.assertEqual(
            web_matchup_ui.format_projection_note({"status": "bye_week"}),
            "Bye week — no game this week.",
        )

    def test_insufficient_player_data(self):
        self.assertEqual(
            web_matchup_ui.format_projection_note({"status": "insufficient_player_data"}),
            "Not enough recent games yet for a projection.",
        )

    def test_unsupported_position(self):
        self.assertEqual(
            web_matchup_ui.format_projection_note({"status": "unsupported_position"}),
            "No weekly projection for this position.",
        )

    def test_unknown_status_falls_back_to_generic_honest_copy(self):
        self.assertEqual(
            web_matchup_ui.format_projection_note({"status": "some_new_status_not_yet_mapped"}),
            "No projection available.",
        )

    def test_ok_status_missing_numeric_fields_never_fabricates(self):
        self.assertEqual(
            web_matchup_ui.format_projection_note({"status": "ok"}),
            "No projection available.",
        )


class TestProjectionBadgeHtml(unittest.TestCase):
    def test_none_projection(self):
        self.assertEqual(web_matchup_ui.projection_badge_html(None), "")

    def test_high_confidence(self):
        html = web_matchup_ui.projection_badge_html({"status": "ok", "confidence": "high"})
        self.assertIn("High confidence", html)
        self.assertIn("dg-ui-badge--success", html)

    def test_medium_confidence(self):
        html = web_matchup_ui.projection_badge_html({"status": "ok", "confidence": "medium"})
        self.assertIn("dg-ui-badge--information", html)

    def test_low_confidence(self):
        html = web_matchup_ui.projection_badge_html({"status": "ok", "confidence": "low"})
        self.assertIn("dg-ui-badge--caution", html)

    def test_bye_week_badge(self):
        html = web_matchup_ui.projection_badge_html({"status": "bye_week"})
        self.assertIn("Bye week", html)

    def test_unsupported_position_has_no_badge(self):
        self.assertEqual(
            web_matchup_ui.projection_badge_html({"status": "unsupported_position"}), ""
        )

    def test_other_edge_case_gets_neutral_badge(self):
        html = web_matchup_ui.projection_badge_html({"status": "unknown_player"})
        self.assertIn("No projection yet", html)


class TestAttachProjection(unittest.TestCase):
    def test_blank_player_id_gets_no_projection(self):
        player = {"player_id": None, "name": "Team DEF"}
        with patch("modules.web_matchup_ui.project_player_week") as mocked:
            result = web_matchup_ui.attach_projection(
                player, week=5, season=2026, players_map={}, defense_strength={}
            )
        mocked.assert_not_called()
        self.assertIsNone(result["projection"])
        self.assertEqual(result["projection_note"], "")
        self.assertEqual(result["projection_badge_html"], "")

    def test_valid_player_id_calls_project_player_week_with_batched_inputs(self):
        player = {"player_id": "mine1", "name": "Mine Player 1"}
        players_map = {"mine1": {"position": "QB"}}
        defense_strength = {"DEN": {"QB": {"tier": "tough"}}}
        stub_result = {"status": "ok", "point_estimate": 15.0, "low": 12.0, "high": 18.0, "confidence": "high"}
        with patch("modules.web_matchup_ui.project_player_week", return_value=stub_result) as mocked:
            result = web_matchup_ui.attach_projection(
                player, week=5, season=2026, players_map=players_map, defense_strength=defense_strength
            )
        mocked.assert_called_once_with(
            "mine1", 5, 2026, players=players_map, defense_strength=defense_strength
        )
        self.assertEqual(result["projection"], stub_result)
        self.assertTrue(result["projection_note"].startswith("Proj 15.0 pts"))


class TestPresentationAdapters(unittest.TestCase):
    def test_row_for_compact_card_maps_tier_to_player_tier(self):
        row = web_matchup_ui.row_for_compact_card({"player_id": "p1", "tier": "Elite"})
        self.assertEqual(row["player_tier"], "Elite")
        # Original key preserved too -- this is additive, not a rename.
        self.assertEqual(row["tier"], "Elite")

    def test_suggested_starter_note_combines_why_and_projection(self):
        note = web_matchup_ui.suggested_starter_note(
            {"why": "Elite tier · top QB on this roster by season value", "projection_note": "Proj 15.0 pts (12.0–18.0) · high confidence"}
        )
        self.assertEqual(
            note,
            "Elite tier · top QB on this roster by season value · Proj 15.0 pts (12.0–18.0) · high confidence",
        )

    def test_suggested_starter_note_without_projection(self):
        note = web_matchup_ui.suggested_starter_note({"why": "Best available.", "projection_note": ""})
        self.assertEqual(note, "Best available.")

    def test_real_starter_note_combines_live_points_and_projection(self):
        note = web_matchup_ui.real_starter_note(
            {"actual_points": 12.5, "projection_note": "Bye week — no game this week."}
        )
        self.assertEqual(note, "Live: 12.5 pts · Bye week — no game this week.")

    def test_real_starter_note_without_actual_points_yet(self):
        note = web_matchup_ui.real_starter_note({"actual_points": None, "projection_note": "Proj 9.0 pts"})
        self.assertEqual(note, "Proj 9.0 pts")


class TestFetchMatchupInputs(unittest.TestCase):
    """This is the single call site for this feature's real provider fetches
    (see fetch_matchup_inputs's docstring) -- covering it here means app.py's
    page block never needs its own duplicate fetch logic.
    """

    def test_fetches_every_input_and_derives_current_week_from_league_leg(self):
        league = {"settings": {"leg": 7}}
        rosters = [{"roster_id": 1}, {"roster_id": 2}]
        profiles = {"1": {"team_name": "Mine"}}
        matchups = [{"roster_id": 1, "matchup_id": 9}]
        players_map = {"p1": {"position": "QB"}}
        defense_strength = {"DEN": {"QB": {"tier": "tough"}}}

        with patch("modules.web_matchup_ui.sleeper.get_league", return_value=league) as m_league, patch(
            "modules.web_matchup_ui.sleeper.get_rosters", return_value=rosters
        ) as m_rosters, patch(
            "modules.web_matchup_ui.sleeper.get_league_roster_profiles", return_value=profiles
        ) as m_profiles, patch(
            "modules.web_matchup_ui.sleeper.get_matchups", return_value=matchups
        ) as m_matchups, patch(
            "modules.web_matchup_ui.sleeper.default_player_stats_season", return_value=2026
        ), patch(
            "modules.web_matchup_ui.sleeper.get_players", return_value=players_map
        ), patch(
            "modules.web_matchup_ui.team_defense_points_allowed_by_position",
            return_value=defense_strength,
        ) as m_defense:
            result = web_matchup_ui.fetch_matchup_inputs("league-abc")

        m_league.assert_called_once_with("league-abc")
        m_rosters.assert_called_once_with("league-abc")
        m_profiles.assert_called_once_with("league-abc")
        m_matchups.assert_called_once_with("league-abc", 7)
        m_defense.assert_called_once_with(2026, upto_week=6)

        self.assertEqual(result["current_week"], 7)
        self.assertEqual(result["matchups"], matchups)
        self.assertEqual(result["rosters_by_id"], {"1": {"roster_id": 1}, "2": {"roster_id": 2}})
        self.assertEqual(result["profiles"], profiles)
        self.assertEqual(result["season"], 2026)
        self.assertEqual(result["players_map"], players_map)
        self.assertEqual(result["defense_strength"], defense_strength)

    def test_skips_matchup_and_defense_fetches_when_no_current_week(self):
        with patch("modules.web_matchup_ui.sleeper.get_league", return_value={"settings": {}}), patch(
            "modules.web_matchup_ui.sleeper.get_rosters", return_value=[]
        ), patch("modules.web_matchup_ui.sleeper.get_league_roster_profiles", return_value={}), patch(
            "modules.web_matchup_ui.sleeper.get_matchups"
        ) as m_matchups, patch(
            "modules.web_matchup_ui.sleeper.default_player_stats_season", return_value=2026
        ), patch(
            "modules.web_matchup_ui.sleeper.get_players", return_value={}
        ), patch(
            "modules.web_matchup_ui.team_defense_points_allowed_by_position"
        ) as m_defense:
            result = web_matchup_ui.fetch_matchup_inputs("league-abc")

        m_matchups.assert_not_called()
        m_defense.assert_not_called()
        self.assertEqual(result["current_week"], 0)
        self.assertEqual(result["matchups"], [])
        self.assertEqual(result["defense_strength"], {})


class TestNotReadyMessages(unittest.TestCase):
    def test_every_reason_has_nonempty_copy(self):
        for reason, message in web_matchup_ui.NOT_READY_MESSAGES.items():
            self.assertTrue(message.strip(), msg=f"reason {reason!r} has blank copy")


if __name__ == "__main__":
    unittest.main()
