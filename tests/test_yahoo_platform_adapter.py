"""Unit tests for the Yahoo platform adapter stub (modules/platforms/yahoo.py).

These exercise only the adapter's parsing/normalization logic against
fixture JSON shaped like Yahoo's *documented and commonly-reported* JSON
auto-conversion format (collections as {"0": ..., "1": ..., "count": N}
objects, nested under a top-level "fantasy_content" key). No live Yahoo API
call is made anywhere in this file (a ``fetcher`` callable is injected
instead of real HTTP). See modules/platforms/yahoo.py's module docstring:
this fixture shape is a best-effort reconstruction from documentation and
community reports, not a verified contract — a human completing the real
spike must confirm it against an actual captured response and this test
file (and the adapter) should be updated accordingly.
"""

from __future__ import annotations

import unittest

from modules.platforms.yahoo import YahooAPIError, YahooPlatformAdapter


def league_meta():
    return {
        "league_key": "414.l.12345",
        "league_id": "12345",
        "name": "Test Dynasty League",
        "season": "2026",
        "num_teams": 12,
        "scoring_type": "head",
        "settings": [
            {
                "stat_modifiers": {"0": {"stat": {"stat_id": "5", "value": "1"}}, "count": 1},
                "roster_positions": [{"roster_position": {"position": "QB"}}],
            }
        ],
    }


def fake_league_resource():
    return {"league": [league_meta(), {}]}


def fake_teams_resource():
    return {
        "league": [
            league_meta(),
            {
                "teams": {
                    "0": {
                        "team": [
                            {"team_key": "414.l.12345.t.1", "name": "Team One", "manager_id": "m1"},
                        ]
                    },
                    "1": {
                        "team": [
                            {"team_key": "414.l.12345.t.2", "name": "Team Two", "manager_id": "m2"},
                        ]
                    },
                    "count": 2,
                }
            },
        ]
    }


def fake_roster_resource(team_key, players):
    return {
        "team": [
            {"team_key": team_key},
            {
                "roster": [
                    {"coverage_type": "week"},
                    {
                        "players": {
                            **{
                                str(i): {"player": [{"player_key": pid}]}
                                for i, pid in enumerate(players)
                            },
                            "count": len(players),
                        }
                    },
                ]
            },
        ]
    }


def fake_transactions_resource():
    return {
        "league": [
            league_meta(),
            {
                "transactions": {
                    "0": {"transaction": [{"type": "add"}]},
                    "1": {"transaction": [{"type": "trade"}]},
                    "count": 2,
                }
            },
        ]
    }


class FakeFetcher:
    """Routes resource paths to canned Yahoo-shaped JSON for the adapter under test."""

    def __init__(self, rosters):
        self.rosters = rosters
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        if path == "league/414.l.12345":
            return fake_league_resource()
        if path == "league/414.l.12345/teams":
            return fake_teams_resource()
        if path == "league/414.l.12345/transactions":
            return fake_transactions_resource()
        if path.startswith("team/") and path.endswith("/roster"):
            team_key = path.split("/")[1]
            return fake_roster_resource(team_key, self.rosters.get(team_key, []))
        raise AssertionError(f"Unexpected path requested in test: {path}")


class TestYahooPlatformAdapter(unittest.TestCase):
    def test_get_league_normalizes_metadata(self):
        fetcher = FakeFetcher(rosters={})
        adapter = YahooPlatformAdapter(fetcher=fetcher)

        league = adapter.get_league("414.l.12345")

        self.assertEqual(league["platform"], "yahoo")
        self.assertEqual(league["league_id"], "414.l.12345")
        self.assertEqual(league["name"], "Test Dynasty League")
        self.assertEqual(league["season"], "2026")
        self.assertEqual(league["settings"]["team_count"], 12)

    def test_get_rosters_normalizes_teams_and_players(self):
        fetcher = FakeFetcher(
            rosters={
                "414.l.12345.t.1": ["414.p.100"],
                "414.l.12345.t.2": ["414.p.200"],
            }
        )
        adapter = YahooPlatformAdapter(fetcher=fetcher)

        rosters = adapter.get_rosters("414.l.12345")

        self.assertEqual(len(rosters), 2)
        self.assertEqual(rosters[0]["roster_id"], "414.l.12345.t.1")
        self.assertEqual(rosters[0]["team_name"], "Team One")
        self.assertEqual(rosters[0]["platform_player_ids"], ["414.p.100"])
        # No identity_map provided, so canonical players can't resolve (honest empty result).
        self.assertEqual(rosters[0]["players"], [])

    def test_get_rosters_resolves_canonical_players_via_identity_map(self):
        identity_map = {
            "canon-1": {"canonical_player_id": "canon-1", "yahoo_id": "414.p.100"},
        }
        fetcher = FakeFetcher(rosters={"414.l.12345.t.1": ["414.p.100"], "414.l.12345.t.2": []})
        adapter = YahooPlatformAdapter(fetcher=fetcher, identity_map=identity_map)

        rosters = adapter.get_rosters("414.l.12345")

        self.assertEqual(rosters[0]["players"], ["canon-1"])

    def test_get_transactions_returns_normalized_list(self):
        fetcher = FakeFetcher(rosters={})
        adapter = YahooPlatformAdapter(fetcher=fetcher)

        transactions = adapter.get_transactions("414.l.12345", round_num=1)

        self.assertEqual(len(transactions), 2)
        self.assertEqual({t["type"] for t in transactions}, {"add", "trade"})
        self.assertTrue(all(t["platform"] == "yahoo" for t in transactions))

    def test_get_user_leagues_is_honestly_unsupported(self):
        adapter = YahooPlatformAdapter(fetcher=FakeFetcher(rosters={}))
        result = adapter.get_user_leagues("some-username")
        self.assertEqual(result, [])
        self.assertIn("does not support username-based", adapter.last_error)

    def test_get_traded_picks_is_honestly_unimplemented(self):
        adapter = YahooPlatformAdapter(fetcher=FakeFetcher(rosters={}))
        result = adapter.get_traded_picks("414.l.12345")
        self.assertEqual(result, [])
        self.assertTrue(adapter.last_error)

    def test_no_token_and_no_fetcher_raises_clear_error(self):
        adapter = YahooPlatformAdapter()
        with self.assertRaises(YahooAPIError):
            adapter.get_league("414.l.12345")

    def test_normalize_draft_pick_handles_missing_fields(self):
        adapter = YahooPlatformAdapter(fetcher=FakeFetcher(rosters={}))
        pick = adapter.normalize_draft_pick(None)
        self.assertEqual(pick["platform"], "yahoo")
        self.assertEqual(pick["player_id"], "")


if __name__ == "__main__":
    unittest.main()
