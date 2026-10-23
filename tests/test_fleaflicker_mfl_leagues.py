"""Fleaflicker and MFL league import (modules.fleaflicker_leagues / mfl_leagues).

No network and no data/players.db. The fixtures under tests/fixtures/ are
trimmed recordings of real public-league responses (Fleaflicker league 206154,
MFL league 10015, both fetched 2026-10-22), plus one deliberately unmappable
player and a non-player position added to each.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from modules import external_leagues, fleaflicker_leagues, mfl_leagues, sleeper
from modules.external_league_common import ExternalLeagueError

FIXTURES = Path(__file__).parent / "fixtures"
FF_KEY = "fleaflicker:206154:2025"
MFL_KEY = "mfl:10015:2025"


def _load(folder: str, name: str):
    return json.loads((FIXTURES / folder / name).read_text())


PLAYERS = pd.DataFrame(
    [
        {"player_id": "S-POLLARD", "name": "Tony Pollard", "position": "RB", "team": "TEN"},
        {"player_id": "S-HOCK", "name": "T.J. Hockenson", "position": "TE", "team": "MIN"},
        {"player_id": "S-HENRY", "name": "Derrick Henry", "position": "RB", "team": "BAL"},
        {"player_id": "S-ETIENNE", "name": "Travis Etienne", "position": "RB", "team": "JAX"},
        # Moved teams (GB -> DAL): team only breaks ties, so he still matches.
        {"player_id": "S-CLARK-DL", "name": "Kenny Clark", "position": "DL", "team": "GB"},
        # Same name, other position than MFL's DT: must never be picked.
        {"player_id": "S-JONES-CB", "name": "Chris Jones", "position": "DB", "team": "KC"},
        {"player_id": "S-JONES-1", "name": "Mac Jones", "position": "QB", "team": "SF"},
        {"player_id": "S-JONES-2", "name": "Mac Jones", "position": "QB", "team": "SF"},
    ]
)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def ff_fetch(endpoint, params):
        assert params["sport"] == "NFL"
        return _load("fleaflicker", f"{endpoint}.json")

    def mfl_fetch(season, params):
        assert season == 2025
        return _load("mfl", {"league": "league", "rosters": "rosters", "leagueStandings": "leagueStandings", "players": "players"}[params["TYPE"]] + ".json")

    monkeypatch.setattr(fleaflicker_leagues, "fetch_provider", ff_fetch)
    monkeypatch.setattr(fleaflicker_leagues, "players_frame_provider", lambda: PLAYERS.copy())
    monkeypatch.setattr(fleaflicker_leagues, "sleeper_players_provider", lambda: {})
    monkeypatch.setattr(fleaflicker_leagues, "crosswalk_provider", lambda: {"11177": "S-COOPER"})
    monkeypatch.setattr(mfl_leagues, "fetch_provider", mfl_fetch)
    monkeypatch.setattr(mfl_leagues, "players_frame_provider", lambda: PLAYERS.copy())
    monkeypatch.setattr(mfl_leagues, "sleeper_players_provider", lambda: {})
    monkeypatch.setattr(mfl_leagues, "crosswalk_provider", lambda: {"11244": "S-KELCE"})
    external_leagues.clear_snapshot_caches()
    mfl_leagues.clear_players_cache()
    yield
    external_leagues.clear_snapshot_caches()
    mfl_leagues.clear_players_cache()


def test_keys_carry_the_platform_and_dispatch():
    assert fleaflicker_leagues.build_league_key("206154", 2025) == FF_KEY
    assert mfl_leagues.build_league_key("10015", 2025) == MFL_KEY
    assert fleaflicker_leagues.parse_league_key(FF_KEY) == ("206154", 2025)
    assert mfl_leagues.parse_league_key(MFL_KEY) == ("10015", 2025)
    assert fleaflicker_leagues.build_league_key("abc", 2025) == ""
    assert mfl_leagues.build_league_key("1", 1999) == ""
    assert mfl_leagues.parse_league_key(FF_KEY) is None
    assert external_leagues.platform_of(FF_KEY) == "fleaflicker"
    assert external_leagues.platform_of(MFL_KEY) == "mfl"
    assert external_leagues.platform_of("espn:1:2026") == "espn"
    assert external_leagues.platform_of("1180112345678901234") == ""
    assert external_leagues.league_platform(MFL_KEY) == "mfl"


def test_routes_are_gated_with_a_platform_named_message():
    for key, label in ((FF_KEY, "Fleaflicker"), (MFL_KEY, "MFL")):
        assert not external_leagues.gated_league_path(f"/v1/leagues/{key}/my-team")
        assert not external_leagues.gated_league_path(f"/v1/leagues/{key}/trade-analyzer")
        assert external_leagues.gated_league_path(f"/v1/leagues/{key}/dashboard")
        assert external_leagues.gated_league_path(f"/v1/leagues/{key}/matchup")
        payload = external_leagues.not_available_payload(f"/v1/leagues/{key}/dashboard")
        assert payload["error"] == f"Not available for {label} leagues yet."
        assert payload["reason"] == "espn_not_supported" and payload["platform"] == key.split(":")[0]
    assert not external_leagues.gated_league_path("/v1/leagues/123/dashboard")


def test_fleaflicker_snapshot_maps_players_honestly():
    snapshot = fleaflicker_leagues.load_league_snapshot(FF_KEY)
    league = snapshot["league"]
    assert league["platform"] == "fleaflicker" and league["league_id"] == FF_KEY
    assert league["name"] == "Jackpot Dynasty League"
    assert league["roster_positions"][:6] == ["QB", "RB", "RB", "WR", "WR", "TE"]
    assert "FLEX" in league["roster_positions"] and "DL" in league["roster_positions"]
    assert league["roster_positions"].count("BN") == 24
    assert league["scoring_settings"] == {}  # not imported, never assumed

    first, second = snapshot["rosters"]
    # Pollard + Hockenson by name/position/team; Cooper by exact id crosswalk.
    assert first["players"] == ["S-POLLARD", "S-COOPER", "S-HOCK"]
    assert first["settings"]["wins"] == 5 and first["settings"]["losses"] == 8
    assert first["settings"]["fpts"] == 1379
    assert second["players"] == []  # none of those namesakes exist in the table
    assert snapshot["users"][0]["display_name"]

    diagnostics = snapshot["diagnostics"]
    names = {item["name"] for item in diagnostics["unmapped_players"]}
    assert "Zzyzx Unmappable" in names and "Lamar Miller" in names
    assert "Some Punter" not in names  # punters are not valued players
    assert diagnostics["ignored_non_player_count"] == 1
    assert diagnostics["total_players_seen"] == diagnostics["canonical_matched_count"] + diagnostics["unmatched_count"]
    assert diagnostics["matched_rate"] < 0.60
    assert external_leagues.mapping_blocks_import(snapshot)


def test_mfl_snapshot_maps_ids_names_aliases_and_slots():
    snapshot = mfl_leagues.load_league_snapshot(MFL_KEY)
    league = snapshot["league"]
    assert league["platform"] == "mfl" and league["name"] == "Dynasty Pioneer"
    assert league["roster_positions"][:4] == ["QB", "RB", "WR", "WR"]
    assert league["roster_positions"].count("DB") == 4 and league["roster_positions"].count("IR") == 6
    # Ranged IDP positions mean the leftover starters are not guessed as FLEX.
    assert "FLEX" not in league["roster_positions"]

    first, second = snapshot["rosters"]
    assert first["roster_id"] == 1 and second["roster_id"] == 2
    assert "S-KELCE" in first["players"]  # exact mfl_id crosswalk
    assert "S-HENRY" in first["players"]  # "Henry, Derrick" RB BAL by name
    assert "S-ETIENNE" in first["players"]  # JAC -> JAX team alias
    # A same-name different-position player is not picked; two QB Mac Joneses
    # at the same team are ambiguous, not guessed.
    assert "S-CLARK-DL" in second["players"]
    assert "S-JONES-CB" not in first["players"] + second["players"]
    assert "S-JONES-1" not in first["players"] + second["players"]
    assert first["settings"]["wins"] == 10 and first["settings"]["fpts"] == 3602

    unmapped = snapshot["diagnostics"]["unmapped_players"]
    assert any(item["name"] == "Zzyzx Unmappable" and item["reason"] == "no_unique_match" for item in unmapped)
    assert any(item["name"] == "Mac Jones" and item["reason"] == "ambiguous" for item in unmapped)
    assert snapshot["diagnostics"]["ignored_non_player_count"] == 1  # id absent from MFL's player list
    assert snapshot["diagnostics"]["ambiguous_count"] == 1


def test_mfl_reserve_and_taxi_slots_follow_status():
    league = mfl_leagues.normalize_league(
        _load("mfl", "league.json"),
        {"rosters": {"franchise": [{"id": "0001", "player": [{"id": "11244", "status": "INJURED_RESERVE"}, {"id": "12626", "status": "TAXI_SQUAD"}]}]}},
        _load("mfl", "leagueStandings.json"),
        {p["id"]: p for p in _load("mfl", "players.json")["players"]["player"]},
        2025,
    )
    assert [p.slot for p in league.teams[0].players] == ["RESERVE", "TAXI"]


def test_mfl_name_and_team_helpers():
    assert mfl_leagues.display_name("Walker, Kenneth III") == "Kenneth Walker III"
    assert mfl_leagues.display_name("Henry, Derrick") == "Derrick Henry"
    assert mfl_leagues.display_name("Bills, Buffalo") == "Buffalo Bills"
    assert [mfl_leagues.normalize_team_abbreviation(t) for t in ("KCC", "GBP", "LVR", "JAC", "FA", "")] == ["KC", "GB", "LV", "JAX", "", ""]


def test_mfl_single_child_json_objects_are_handled():
    league = mfl_leagues.normalize_league(
        {"league": {"name": "X", "franchises": {"franchise": {"id": "0001", "name": "Solo"}}}},
        {"rosters": {"franchise": {"id": "0001", "player": {"id": "11244", "status": "ROSTER"}}}},
        {"leagueStandings": {"franchise": {"id": "0001", "h2hw": "1", "h2hl": "0", "pf": "1,200.5"}}},
        {"11244": {"id": "11244", "name": "Kelce, Travis", "position": "TE", "team": "KCC"}},
        2025,
    )
    assert league.teams[0].name == "Solo" and league.teams[0].players[0].team == "KC"
    assert league.teams[0].points_for == 1200.5


def test_mfl_errors_are_classified(monkeypatch):
    for message, reason in (
        ("Invalid league ID 10000", "league_not_found"),
        ("You must be logged in to view this league", "private_league"),
        ("something else", "mfl_unavailable"),
    ):
        with pytest.raises(ExternalLeagueError) as caught:
            mfl_leagues._raise_for_error({"error": {"$t": message}})
        assert caught.value.reason == reason


def test_http_failures_do_not_retry_or_leak(monkeypatch):
    class Response:
        def __init__(self, status):
            self.status_code = status

        def json(self):
            return {}

    calls = []
    monkeypatch.setattr(mfl_leagues._throttle, "wait", lambda: None)
    monkeypatch.setattr(fleaflicker_leagues._throttle, "wait", lambda: None)

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        return Response(429 if "myfantasyleague" in url else 404)

    monkeypatch.setattr("requests.get", fake_get)
    with pytest.raises(ExternalLeagueError) as mfl_error:
        mfl_leagues._default_fetch(2025, {"TYPE": "league", "L": "1"})
    assert mfl_error.value.reason == "mfl_rate_limited" and len(calls) == 1  # no retry
    with pytest.raises(ExternalLeagueError) as ff_error:
        fleaflicker_leagues._default_fetch("FetchLeagueRosters", {"sport": "NFL", "league_id": "1"})
    assert ff_error.value.reason == "league_not_found"
    for _url, params, headers in calls:
        assert "APIKEY" not in params and "Cookie" not in headers and "Authorization" not in headers
        assert headers["User-Agent"].startswith("FantasyDesk")


def test_preview_and_save_inputs_through_the_dispatcher(monkeypatch):
    result = external_leagues.preview_league("fleaflicker", "206154", 2025)
    assert result["reason"] == "mapping_too_low" and result["ok"] is False
    assert result["league"]["league_key"] == FF_KEY and result["platform_label"] == "Fleaflicker"
    assert result["diagnostics"]["unmapped_players"]
    assert any(f["status"] == "available" for f in result["features"])
    assert "Fleaflicker" in next(f["note"] for f in result["features"] if f["status"] == "not_available")

    bad = external_leagues.preview_league("mfl", "nope", 2025)
    assert bad["ok"] is False and bad["reason"] == "invalid_input"
    assert external_leagues.preview_league("yahoo", "1", 2025)["reason"] == "invalid_input"

    # A preview seeds the cache the Sleeper-shaped getters read from.
    external_leagues.preview_league("mfl", "10015", 2025)
    monkeypatch.setattr(mfl_leagues, "fetch_provider", lambda *_a, **_k: pytest.fail("cache should be used"))
    assert len(sleeper.get_rosters(MFL_KEY)) == 2


def test_sleeper_getters_serve_imported_leagues_without_calling_sleeper():
    mfl_leagues.store_snapshot(MFL_KEY, mfl_leagues.load_league_snapshot(MFL_KEY))
    rosters = sleeper.get_rosters(MFL_KEY)
    assert len(rosters) == 2 and rosters[0]["platform"] == "mfl"
    assert sleeper.get_league(MFL_KEY)["name"] == "Dynasty Pioneer"
    assert sleeper.get_users(MFL_KEY)[0]["user_id"] == "mfl-team-0001"
    assert sleeper.get_league_drafts(MFL_KEY) == []


def test_other_platform_ids_do_not_leak_through_espn_id_column():
    frame = pd.DataFrame(
        [{"player_id": "S-WRONG", "name": "Someone Else", "position": "WR", "team": "DEN", "espn_id": "11177"}]
    )
    league = fleaflicker_leagues.normalize_league(
        _load("fleaflicker", "FetchLeagueRosters.json"),
        _load("fleaflicker", "FetchLeagueStandings.json"),
        _load("fleaflicker", "FetchLeagueRules.json"),
        2025,
    )
    from modules.external_league_common import build_snapshot

    snapshot = build_snapshot(
        "fleaflicker", league, league_key=FF_KEY, external_league_id="206154", default_name="x",
        df_players=frame, sleeper_players={}, crosswalk={},
    )
    assert "S-WRONG" not in snapshot["rosters"][0]["players"]
