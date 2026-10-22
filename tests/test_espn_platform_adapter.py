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

    def test_apostrophe_spellings_match_either_way(self):
        df = pd.DataFrame([{"player_id": "9226", "name": "DeVon Achane", "position": "RB", "team": "MIA"}])
        adapter = ESPNPlatformAdapter(df_players=df)

        roster = adapter.normalize_roster(FakeTeam(1, "One", [FakePlayer(4429160, "De'Von Achane", "RB", "MIA")]))

        self.assertEqual(roster["players"], ["9226"])

    def test_duplicate_name_is_disambiguated_by_position_team_and_active(self):
        df = pd.DataFrame(
            [
                {"player_id": "4881", "name": "Lamar Jackson", "position": "QB", "team": "BAL", "active": 1},
                {"player_id": "6994", "name": "Lamar Jackson", "position": "CB", "team": None, "active": 1},
                {"player_id": "r1", "name": "Same Name", "position": "RB", "team": "DAL", "active": 1},
                {"player_id": "r2", "name": "Same Name", "position": "RB", "team": None, "active": 0},
            ]
        )
        adapter = ESPNPlatformAdapter(df_players=df)

        roster = adapter.normalize_roster(
            FakeTeam(
                1,
                "One",
                [FakePlayer(1, "Lamar Jackson", "QB", "BAL"), FakePlayer(2, "Same Name", "RB", "KC")],
            )
        )

        # Position separates the Lamars; active status (with a team) breaks
        # the RB tie after the ESPN team matched neither.
        self.assertEqual(roster["players"], ["4881", "r1"])
        self.assertEqual(adapter.mapping_diagnostics()["ambiguous_count"], 0)

    def test_espn_id_crosswalk_is_preferred_over_names(self):
        df = pd.DataFrame(
            [
                {"player_id": "x1", "name": "Shared Name", "position": "WR", "team": "DAL"},
                {"player_id": "x2", "name": "Shared Name", "position": "WR", "team": "DAL"},
            ]
        )
        sleeper_players = {
            "x2": {"full_name": "Shared Name", "position": "WR", "team": "DAL", "active": True},
            "k9": {"full_name": "Kicker Guy", "position": "K", "team": "DAL", "active": True},
        }
        adapter = ESPNPlatformAdapter(
            df_players=df,
            sleeper_players=sleeper_players,
            espn_crosswalk={"700": "x2", "701": "k9", "702": "9226"},
        )

        roster = adapter.normalize_roster(
            FakeTeam(
                1,
                "One",
                [
                    FakePlayer(700, "Shared Name", "WR", "DAL"),
                    # A crosswalk row that disagrees on both position and
                    # name is ignored rather than trusted.
                    FakePlayer(701, "Some Receiver", "WR", "DAL"),
                    # Not in the valued table or the dump: the id still maps.
                    FakePlayer(702, "De'Von Achane", "RB", "MIA"),
                ],
            )
        )

        self.assertEqual(roster["players"], ["x2", "9226"])
        self.assertEqual(roster["unmatched_players"][0]["espn_id"], "701")

    def test_sleeper_dump_matches_players_missing_from_the_valued_table(self):
        sleeper_players = {
            "2133": {"full_name": "Davante Adams", "position": "WR", "team": "LAR", "active": True},
            "7543": {"full_name": "Travis Etienne Jr.", "position": "RB", "team": "NO", "active": True},
        }
        adapter = ESPNPlatformAdapter(df_players=player_table(), sleeper_players=sleeper_players)

        roster = adapter.normalize_roster(
            FakeTeam(
                1,
                "One",
                [FakePlayer(16800, "Davante Adams", "WR", "LAR"), FakePlayer(4239996, "Travis Etienne Jr.", "RB", "NO")],
            )
        )

        self.assertEqual(roster["players"], ["2133", "7543"])

    def test_team_defenses_map_to_sleeper_def_ids(self):
        adapter = ESPNPlatformAdapter(df_players=player_table())

        roster = adapter.normalize_roster(
            FakeTeam(
                1,
                "One",
                [
                    FakePlayer(-16026, "Seahawks D/ST", "D/ST", "SEA"),
                    FakePlayer(-16028, "Commanders D/ST", "D/ST", "WSH"),
                    FakePlayer(-16099, "Nowhere D/ST", "D/ST", "XYZ"),
                ],
            )
        )

        self.assertEqual(roster["players"], ["SEA", "WAS"])
        self.assertEqual(roster["unmatched_players"][0]["espn_id"], "-16099")

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
