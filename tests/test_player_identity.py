import unittest

import pandas as pd

from modules import player_identity
from modules import player_images


class TestPlayerIdentity(unittest.TestCase):
    def test_ensure_identity_columns_preserves_player_id_compatibility(self):
        df = pd.DataFrame(
            [
                {"player_id": 101, "name": "Player One"},
                {"player_id": "202", "name": "Player Two"},
            ]
        )

        normalized = player_identity.ensure_identity_columns(df)

        self.assertEqual(normalized["player_id"].tolist(), ["101", "202"])
        self.assertEqual(normalized["canonical_player_id"].tolist(), ["101", "202"])
        self.assertEqual(normalized["sleeper_id"].tolist(), ["101", "202"])

    def test_sleeper_ids_canonicalize_directly(self):
        self.assertEqual(player_identity.canonicalize_player_id("sleeper", 123), "123")
        self.assertEqual(
            player_identity.canonicalize_player_ids("sleeper", [123, "123", "abc"]),
            ["123", "abc"],
        )

    def test_unknown_platform_id_returns_none_without_mapping(self):
        self.assertIsNone(player_identity.canonicalize_player_id("espn", "42"))

    def test_identity_map_can_resolve_future_platform_ids(self):
        identity_map = {
            "canon-1": {
                "canonical_player_id": "canon-1",
                "sleeper_id": "111",
                "espn_id": "222",
            }
        }

        self.assertEqual(
            player_identity.canonicalize_player_id("espn", "222", identity_map),
            "canon-1",
        )

    def test_exact_unique_name_team_position_match_resolves(self):
        df = pd.DataFrame(
            [
                {"player_id": "1", "name": "Unique Player", "team": "DAL", "position": "WR"},
                {"player_id": "2", "name": "Other Player", "team": "NYG", "position": "WR"},
            ]
        )

        self.assertEqual(
            player_identity.match_player_by_identity(
                df,
                "Unique Player",
                team="DAL",
                position="WR",
            ),
            "1",
        )

    def test_ambiguous_name_match_does_not_auto_resolve(self):
        df = pd.DataFrame(
            [
                {"player_id": "1", "name": "Duplicate Player", "team": "DAL", "position": "WR"},
                {"player_id": "2", "name": "Duplicate Player", "team": "NYG", "position": "WR"},
            ]
        )

        self.assertIsNone(player_identity.match_player_by_identity(df, "Duplicate Player"))

    def test_normalize_player_name_strips_generational_suffixes(self):
        # Found during live ESPN validation: ESPN's API returns full
        # generational suffixes (e.g. "Kenneth Walker III", "James Cook III")
        # while the shared player table stores the base name, so suffix-aware
        # normalization is required for cross-platform name matching to work.
        self.assertEqual(
            player_identity.normalize_player_name("Kenneth Walker III"),
            player_identity.normalize_player_name("Kenneth Walker"),
        )
        self.assertEqual(
            player_identity.normalize_player_name("James Cook III"),
            player_identity.normalize_player_name("James Cook"),
        )
        self.assertEqual(
            player_identity.normalize_player_name("Travis Etienne Jr."),
            player_identity.normalize_player_name("Travis Etienne"),
        )
        self.assertEqual(player_identity.normalize_player_name("Odell Beckham Jr."), "odell beckham")

    def test_normalize_player_name_joins_apostrophes_and_initials(self):
        normalize = player_identity.normalize_player_name
        self.assertEqual(normalize("De'Von Achane"), "devon achane")
        self.assertEqual(normalize("De'Von Achane"), normalize("DeVon Achane"))
        self.assertEqual(normalize("Ja\u2019Marr Chase"), normalize("Ja'Marr Chase"))
        self.assertEqual(normalize("A.J. Brown"), normalize("AJ Brown"))
        self.assertEqual(normalize("Amon-Ra St. Brown"), "amon ra st brown")

    def test_resolve_identity_candidates_narrows_by_position_team_then_active(self):
        resolve = player_identity.resolve_identity_candidates
        lamars = [
            {"id": "4881", "position": "QB", "team": "BAL", "active": True},
            {"id": "6994", "position": "CB", "team": "", "active": True},
        ]
        self.assertEqual(resolve(lamars, position="QB", team="BAL"), ("4881", False))
        # A player who changed teams still matches on position alone.
        self.assertEqual(resolve(lamars, position="QB", team="NYJ"), ("4881", False))
        # Position is a hard filter: never map a QB onto the namesake CB.
        self.assertEqual(resolve(lamars[1:], position="QB", team="BAL"), (None, False))

        same_position = [
            {"id": "a", "position": "RB", "team": "DAL", "active": True},
            {"id": "b", "position": "RB", "team": "NYG", "active": True},
        ]
        self.assertEqual(resolve(same_position, position="RB", team="NYG"), ("b", False))
        self.assertEqual(resolve(same_position, position="RB", team="KC"), (None, True))

        one_active = [
            {"id": "a", "position": "WR", "team": "DAL", "active": True},
            {"id": "b", "position": "WR", "team": "", "active": False},
        ]
        self.assertEqual(resolve(one_active, position="WR", team="KC"), ("a", False))
        self.assertEqual(resolve([], position="WR"), (None, False))

    def test_match_by_identity_resolves_despite_source_suffix_mismatch(self):
        df = pd.DataFrame(
            [
                {"player_id": "1", "name": "Kenneth Walker", "team": "SEA", "position": "RB"},
                {"player_id": "2", "name": "Other Player", "team": "NYG", "position": "WR"},
            ]
        )

        self.assertEqual(
            player_identity.match_player_by_identity(
                df,
                "Kenneth Walker III",
                team="SEA",
                position="RB",
            ),
            "1",
        )

    def test_id_normalization_handles_ints_strings_and_none(self):
        self.assertEqual(player_identity.normalize_player_id(123.0), "123")
        self.assertEqual(player_identity.normalize_player_id("  abc "), "abc")
        self.assertEqual(player_identity.normalize_player_id(None), "")

    def test_player_image_helper_uses_sleeper_id_when_available(self):
        self.assertTrue(
            player_images.get_player_image_url(
                {"canonical_player_id": "canon-1", "sleeper_id": "999"}
            ).endswith("/999.jpg")
        )

    def test_player_image_helper_handles_missing_sleeper_id(self):
        self.assertEqual(
            player_images.get_player_image_url({"canonical_player_id": "canon-1", "sleeper_id": ""}),
            "",
        )

    def test_existing_sleeper_rows_still_join_on_player_id(self):
        df = player_identity.ensure_identity_columns(
            pd.DataFrame(
                [
                    {"player_id": "10", "name": "Rostered"},
                    {"player_id": "20", "name": "Other"},
                ]
            )
        )
        roster_ids = ["10"]

        joined = df[df["player_id"].isin(roster_ids)]

        self.assertEqual(joined["name"].tolist(), ["Rostered"])


if __name__ == "__main__":
    unittest.main()
