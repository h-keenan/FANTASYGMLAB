import unittest
from unittest.mock import patch

import pandas as pd

from modules.platforms.espn import ESPNAdapterUnavailable, ESPNPlatformAdapter


class FakePlayer:
    def __init__(self, player_id, name, position="WR", team="DAL"):
        self.playerId = player_id
        self.name = name
        self.position = position
        self.proTeam = team


class FakeTeam:
    def __init__(self, team_id, name, roster):
        self.team_id = team_id
        self.teamName = name
        self.owner = f"owner-{team_id}"
        self.roster = roster


class FakeSettings:
    name = "ESPN Test League"
    team_count = 2
    scoring_settings = {"rec": 1.0}
    roster_positions = ["QB", "RB", "WR", "TE", "FLEX"]


class FakeLeague:
    def __init__(self, **kwargs):
        if kwargs.get("league_id") == 999:
            raise RuntimeError("401 unauthorized cookie value should not leak")
        self.league_id = kwargs.get("league_id")
        self.year = kwargs.get("year")
        self.settings = FakeSettings()
        self.teams = [
            FakeTeam(1, "One", [FakePlayer(101, "Mapped Player", "WR", "DAL")]),
            FakeTeam(2, "Two", [FakePlayer(202, "Unmatched Player", "RB", "NYG")]),
        ]
        self.draft = [{"player": FakePlayer(101, "Mapped Player", "WR", "DAL"), "pick": 1, "round_num": 1}]


def player_table():
    return pd.DataFrame(
        [
            {"player_id": "canon-1", "canonical_player_id": "canon-1", "sleeper_id": "s1", "espn_id": "101", "name": "Mapped Player", "position": "WR", "team": "DAL"},
            {"player_id": "canon-2", "canonical_player_id": "canon-2", "sleeper_id": "s2", "name": "Unique Name", "position": "RB", "team": "NYG"},
        ]
    )


class TestESPNPlatformAdapter(unittest.TestCase):
    def test_normalizes_league_metadata(self):
        adapter = ESPNPlatformAdapter(df_players=player_table(), league_factory=FakeLeague)

        league = adapter.get_league("123", season=2026)

        self.assertEqual(league["platform"], "espn")
        self.assertEqual(league["league_id"], "123")
        self.assertEqual(league["name"], "ESPN Test League")
        self.assertEqual(league["season"], 2026)

    def test_normalizes_rosters_and_preserves_platform_ids(self):
        adapter = ESPNPlatformAdapter(df_players=player_table(), league_factory=FakeLeague)

        rosters = adapter.get_rosters("123", season=2026)

        self.assertEqual(rosters[0]["players"], ["canon-1"])
        self.assertEqual(rosters[0]["platform_player_ids"], ["101"])
        self.assertEqual(rosters[1]["players"], [])
        self.assertEqual(rosters[1]["platform_player_ids"], ["202"])

    def test_existing_identity_map_exact_espn_id_matches_canonical_player_id(self):
        identity_map = {
            "canon-map": {
                "canonical_player_id": "canon-map",
                "espn_id": "303",
            }
        }
        adapter = ESPNPlatformAdapter(identity_map=identity_map)

        roster = adapter.normalize_roster(FakeTeam(1, "One", [FakePlayer(303, "Whatever", "TE", "KC")]))

        self.assertEqual(roster["players"], ["canon-map"])
        self.assertEqual(roster["platform_player_ids"], ["303"])

    def test_unique_name_position_team_fallback_maps_player(self):
        adapter = ESPNPlatformAdapter(df_players=player_table())

        roster = adapter.normalize_roster(FakeTeam(1, "One", [FakePlayer(404, "Unique Name", "RB", "NYG")]))

        self.assertEqual(roster["players"], ["canon-2"])
        self.assertEqual(roster["platform_player_ids"], ["404"])

    def test_unmatched_espn_player_does_not_crash(self):
        adapter = ESPNPlatformAdapter(df_players=player_table())

        roster = adapter.normalize_roster(FakeTeam(1, "One", [FakePlayer(505, "Missing Person", "QB", "LV")]))

        self.assertEqual(roster["players"], [])
        self.assertEqual(roster["unmatched_players"][0]["espn_id"], "505")
        self.assertEqual(adapter.mapping_diagnostics()["unmatched_count"], 1)

    def test_ambiguous_name_match_is_not_auto_mapped(self):
        df = pd.DataFrame(
            [
                {"player_id": "a", "canonical_player_id": "a", "name": "Duplicate Player", "position": "WR", "team": "DAL"},
                {"player_id": "b", "canonical_player_id": "b", "name": "Duplicate Player", "position": "RB", "team": "NYG"},
            ]
        )
        adapter = ESPNPlatformAdapter(df_players=df)

        roster = adapter.normalize_roster(FakeTeam(1, "One", [FakePlayer(606, "Duplicate Player", "TE", "KC")]))

        self.assertEqual(roster["players"], [])
        self.assertEqual(adapter.mapping_diagnostics()["ambiguous_count"], 1)

    def test_get_draft_picks_normalizes_player_identity(self):
        adapter = ESPNPlatformAdapter(df_players=player_table(), league_factory=FakeLeague)

        picks = adapter.get_draft_picks("draft", league_id="123", season=2026)

        self.assertEqual(picks[0]["platform"], "espn")
        self.assertEqual(picks[0]["platform_player_id"], "101")
        self.assertEqual(picks[0]["player_id"], "canon-1")

    def test_unsupported_traded_picks_returns_empty(self):
        adapter = ESPNPlatformAdapter()

        self.assertEqual(adapter.get_traded_picks("123"), [])

    def test_missing_dependency_error_is_friendly(self):
        adapter = ESPNPlatformAdapter()
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("espn_api"):
                raise ImportError("missing espn_api")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import), self.assertRaises(ESPNAdapterUnavailable) as caught:
            adapter._league("123", season=2026)

        exc = caught.exception
        self.assertIn("optional espn_api package", str(exc))

    def test_private_league_error_does_not_include_cookie_values(self):
        adapter = ESPNPlatformAdapter(league_factory=FakeLeague)

        with self.assertRaises(RuntimeError) as caught:
            adapter.get_league("999", season=2026, swid="{secret-swid}", espn_s2="secret-s2-token")

        message = str(caught.exception)
        self.assertIn("Private leagues require valid SWID and ESPN_S2 cookies", message)
        self.assertNotIn("secret-s2-token", message)
        self.assertNotIn("secret-swid", message)


if __name__ == "__main__":
    unittest.main()
