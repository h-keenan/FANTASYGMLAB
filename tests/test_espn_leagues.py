"""ESPN league import for the FastAPI service (modules.espn_leagues).

No network and no data/players.db: ESPN's League class and the player frame
are both replaced through espn_leagues' provider hooks.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from modules import espn_leagues, sleeper

KEY = "espn:42654852:2026"


def _player(pid, name, position, team, slot):
    return SimpleNamespace(playerId=pid, name=name, position=position, proTeam=team, lineupSlot=slot)


def _team(team_id, name, owner, roster, wins=3, losses=2):
    return SimpleNamespace(
        team_id=team_id,
        team_name=name,
        owners=[{"displayName": owner, "id": "{SECRET-ESPN-GUID}", "notificationSettings": [{"x": 1}]}],
        roster=roster,
        wins=wins,
        losses=losses,
        ties=0,
        points_for=622.96,
        points_against=580.5,
    )


def _league():
    settings = SimpleNamespace(
        name="FFLR Test League",
        team_count=2,
        keeper_count=0,
        playoff_team_count=2,
        position_slot_counts={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "RB/WR/TE": 1, "D/ST": 1, "K": 1, "BE": 7, "IR": 1, "OP": 0},
        scoring_format=[{"abbr": "REC", "points": 1.0}, {"abbr": "PTD", "points": 4.0}],
        _raw_scoring_settings={"scoringItems": [{"statId": 53, "points": 1.0, "pointsOverrides": {"6": 1.5}}]},
    )
    teams = [
        _team(
            1,
            "Austin Astronauts",
            "K5cents",
            [
                _player(1, "Puka Nacua", "WR", "LAR", "WR"),
                _player(2, "Kenneth Walker III", "RB", "KC", "BE"),
                _player(3, "Seahawks D/ST", "D/ST", "SEA", "D/ST"),
            ],
        ),
        _team(2, "Boston Buzzards", "Other GM", [_player(4, "Jahmyr Gibbs", "RB", "DET", "RB")], wins=5, losses=0),
    ]
    return SimpleNamespace(settings=settings, teams=teams, year=2026, current_week=7)


PLAYERS = pd.DataFrame(
    [
        {"player_id": "9493", "name": "Puka Nacua", "position": "WR", "team": "LAR"},
        {"player_id": "8151", "name": "Kenneth Walker", "position": "RB", "team": "KC"},
        {"player_id": "9221", "name": "Jahmyr Gibbs", "position": "RB", "team": "DET"},
    ]
)


@pytest.fixture(autouse=True)
def _fake_espn(monkeypatch):
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return _league()

    monkeypatch.setattr(espn_leagues, "league_factory_provider", lambda: factory)
    monkeypatch.setattr(espn_leagues, "players_frame_provider", lambda: PLAYERS.copy())
    monkeypatch.setattr(espn_leagues, "sleeper_players_provider", lambda: {})
    monkeypatch.setattr(espn_leagues, "espn_crosswalk_provider", lambda _players: {})
    espn_leagues.clear_snapshot_cache()
    yield calls
    espn_leagues.clear_snapshot_cache()


def test_league_keys_carry_the_platform_and_never_look_like_sleeper_ids():
    assert espn_leagues.build_espn_league_key("42654852", 2026) == KEY
    assert espn_leagues.parse_espn_league_key(KEY) == ("42654852", 2026)
    assert espn_leagues.build_espn_league_key("abc", 2026) == ""
    assert espn_leagues.build_espn_league_key("123", 1999) == ""
    assert espn_leagues.parse_espn_league_key("espn:12:20x6") is None
    assert espn_leagues.is_espn_league_key(KEY)
    assert not espn_leagues.is_espn_league_key("1180112345678901234")


def test_only_the_routes_espn_can_feed_are_open():
    for path in (f"/v1/leagues/{KEY}", f"/v1/leagues/{KEY}/my-team", f"/v1/leagues/{KEY}/trade-analyzer",
                 f"/v1/leagues/{KEY}/players/9221/rank", f"/v1/leagues/{KEY}/save", f"/v1/leagues/{KEY}/draft-picks"):
        assert not espn_leagues.gated_league_path(path), path
    # Dashboard and Matchup are open to imported leagues (modules.external_matchups).
    for path in (f"/v1/leagues/{KEY}/dashboard", f"/v1/leagues/{KEY}/matchup", f"/v1/leagues/{KEY}/matchup/what-if"):
        assert not espn_leagues.gated_league_path(path), path
    for path in (f"/v1/leagues/{KEY}/waivers", f"/v1/leagues/{KEY}/alerts",
                 f"/v1/leagues/{KEY}/gm-targets/9221", f"/v1/leagues/{KEY}/trade-hub/abc/share-card.png"):
        assert espn_leagues.gated_league_path(path), path
    assert not espn_leagues.gated_league_path("/v1/leagues/123/dashboard")
    assert not espn_leagues.gated_league_path(f"/v1/portfolio/leagues/{KEY}")


def test_snapshot_is_sleeper_shaped_maps_players_and_keeps_no_owner_secrets(_fake_espn):
    snapshot = espn_leagues.load_league_snapshot(KEY)
    # Public leagues only: no cookies are ever passed to ESPN.
    assert _fake_espn == [{"league_id": 42654852, "year": 2026}]

    league = snapshot["league"]
    assert league["league_id"] == KEY and league["platform"] == "espn"
    assert league["roster_positions"][:3] == ["QB", "RB", "RB"]
    assert "FLEX" in league["roster_positions"] and "DEF" in league["roster_positions"]
    assert league["roster_positions"].count("BN") == 7
    assert league["scoring_settings"] == {"rec": 1.0, "pass_td": 4.0, "bonus_rec_te": 0.5}
    assert league["settings"]["type"] == 0  # no keepers -> redraft

    first = snapshot["rosters"][0]
    # Suffix-stripped name match ("Kenneth Walker III"); the D/ST maps to
    # Sleeper's team-abbreviation DEF id.
    assert first["players"] == ["9493", "8151", "SEA"]
    assert first["starters"] == ["9493", "SEA"]
    assert first["settings"]["fpts"] == 622 and first["settings"]["fpts_against"] == 580
    assert snapshot["users"][0]["display_name"] == "K5cents"
    assert "SECRET" not in repr(snapshot["users"]) + repr(snapshot["teams"])
    assert snapshot["diagnostics"]["canonical_matched_count"] == 4
    assert snapshot["diagnostics"]["total_espn_players_seen"] == 4


def test_snapshot_maps_by_espn_id_crosswalk_and_the_full_sleeper_dump(monkeypatch):
    """Live league 42654852 regression: De'Von Achane and Davante Adams were
    reported unmatched because they were missing from the valued player
    table. The ESPN id crosswalk and Sleeper's full dump resolve them."""

    def league():
        settings = _league().settings
        roster = [
            _player(4429160, "De'Von Achane", "RB", "MIA", "RB"),
            _player(16800, "Davante Adams", "WR", "LAR", "BE"),
            _player(3916387, "Lamar Jackson", "QB", "BAL", "QB"),
        ]
        return SimpleNamespace(settings=settings, teams=[_team(1, "One", "GM", roster)], year=2026, current_week=7)

    dump = {
        "9226": {"full_name": "De'Von Achane", "position": "RB", "team": "MIA", "active": True},
        "2133": {"full_name": "Davante Adams", "position": "WR", "team": "LAR", "active": True},
        "4881": {"full_name": "Lamar Jackson", "position": "QB", "team": "BAL", "active": True, "espn_id": 3916387},
        "6994": {"full_name": "Lamar Jackson", "position": "CB", "team": None, "active": True, "espn_id": 4034849},
    }
    seen = {}

    def crosswalk(players):
        seen["players"] = players
        return {"4429160": "9226"}

    monkeypatch.setattr(espn_leagues, "league_factory_provider", lambda: lambda **_kwargs: league())
    monkeypatch.setattr(espn_leagues, "players_frame_provider", lambda: PLAYERS.copy())
    monkeypatch.setattr(espn_leagues, "sleeper_players_provider", lambda: dump)
    monkeypatch.setattr(espn_leagues, "espn_crosswalk_provider", crosswalk)

    snapshot = espn_leagues.load_league_snapshot(KEY)

    assert seen["players"] is dump
    assert snapshot["rosters"][0]["players"] == ["9226", "2133", "4881"]
    assert snapshot["diagnostics"]["matched_rate"] == 1.0


def test_private_and_missing_leagues_map_to_stable_reasons(monkeypatch):
    class ESPNAccessDenied(Exception):
        pass

    class ESPNInvalidLeague(Exception):
        pass

    for exc, reason in ((ESPNAccessDenied("espn_s2 and swid are required"), "private_league"),
                        (ESPNInvalidLeague("nope"), "league_not_found"),
                        (TimeoutError("slow"), "espn_unavailable")):
        def factory(_exc=exc, **_kwargs):
            raise _exc

        monkeypatch.setattr(espn_leagues, "league_factory_provider", lambda f=factory: f)
        with pytest.raises(espn_leagues.ESPNLeagueError) as caught:
            espn_leagues.load_league_snapshot(KEY)
        assert caught.value.reason == reason
        assert "espn_s2" not in caught.value.message


def test_http_status_classification_private_vs_not_found_vs_outage(monkeypatch):
    class HttpError(Exception):
        def __init__(self, status):
            super().__init__(f"HTTP {status}")
            self.status_code = status

    for status, reason in ((401, "private_league"), (403, "private_league"), (404, "league_not_found"),
                           (500, "espn_unavailable"), (503, "espn_unavailable")):
        def factory(_s=status, **_kwargs):
            raise HttpError(_s)

        monkeypatch.setattr(espn_leagues, "league_factory_provider", lambda f=factory: f)
        with pytest.raises(espn_leagues.ESPNLeagueError) as caught:
            espn_leagues.load_league_snapshot(KEY)
        assert caught.value.reason == reason
    assert "Make League Viewable to Public" in espn_leagues.ERROR_MESSAGES["private_league"]


def test_sleeper_getters_serve_espn_keys_from_the_snapshot_and_never_call_sleeper():
    with patch("modules.sleeper._request_json") as request_json:
        assert sleeper.get_league(KEY)["name"] == "FFLR Test League"
        assert [r["roster_id"] for r in sleeper.get_rosters(KEY)] == [1, 2]
        assert sleeper.get_users(KEY)[1]["display_name"] == "Other GM"
        assert sleeper.get_traded_picks(KEY) == []
        assert sleeper.get_transactions(KEY, 1) == []
        assert sleeper.get_matchups(KEY, 1) == []
        assert sleeper.get_league_drafts(KEY) == []
        assert sleeper.get_league_roster_profiles(KEY)["2"]["team_name"] == "Boston Buzzards"
    request_json.assert_not_called()


def test_snapshot_cache_loads_once(_fake_espn):
    espn_leagues.get_league_snapshot(KEY)
    espn_leagues.get_league_snapshot(KEY)
    assert len(_fake_espn) == 1


# --- API ---------------------------------------------------------------


USER = {"id": "user-espn-1", "email": "gm@example.com", "_access_token": "token"}


@pytest.fixture
def api(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    rows: list[dict] = []
    monkeypatch.setitem(svc.app.dependency_overrides, svc.require_user, lambda: USER)
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: {"entitlement": "free", "sleeper_username": "", "status": "ok"})
    monkeypatch.setattr(svc.account_store, "fetch_rows", lambda *a, **k: ([dict(r) for r in rows], ""))
    monkeypatch.setattr(svc.account_store, "fetch_saved_leagues", lambda *a, **k: ([dict(r) for r in rows], ""))

    def upsert(_config, _token, payload):
        rows.append(dict(payload))
        return True, ""

    monkeypatch.setattr(svc.account_store, "upsert_saved_league", upsert)
    return SimpleNamespace(client=TestClient(svc.app), rows=rows, svc=svc)


def test_preview_lists_teams_diagnostics_and_feature_support(api):
    body = api.client.post("/v1/espn/leagues/preview", json={"league_id": "42654852", "season": 2026}).json()
    assert body["ok"] is True
    assert body["league"]["league_key"] == KEY
    assert [t["team_name"] for t in body["teams"]] == ["Austin Astronauts", "Boston Buzzards"]
    statuses = {item["feature"]: item["status"] for item in body["features"]}
    assert statuses["My Team"] == "available" and statuses["Waivers"] == "not_available"


def test_preview_rejects_bad_input_and_reports_private_leagues(api, monkeypatch):
    assert api.client.post("/v1/espn/leagues/preview", json={"league_id": "abc", "season": 2026}).json()["reason"] == "invalid_input"

    class ESPNAccessDenied(Exception):
        pass

    def factory(**_kwargs):
        raise ESPNAccessDenied("espn_s2 and swid are required")

    monkeypatch.setattr(espn_leagues, "league_factory_provider", lambda: factory)
    body = api.client.post("/v1/espn/leagues/preview", json={"league_id": "1", "season": 2026}).json()
    assert body == {"ok": False, "reason": "private_league", "message": espn_leagues.ERROR_MESSAGES["private_league"]}


def test_save_requires_a_team_and_stores_the_platform_in_the_league_id(api):
    no_team = api.client.post("/v1/leagues/save", json={"league_id": KEY}).json()
    assert no_team["reason"] == "espn_team_not_selected"
    assert api.rows == []

    saved = api.client.post("/v1/leagues/save", json={"league_id": KEY, "roster_id": "1", "league_name": "FFLR"}).json()
    assert saved["ok"] is True and saved["league"]["platform"] == "espn"
    assert api.rows[0]["league_id"] == KEY
    assert api.rows[0]["roster_id"] == "1"
    # No Sleeper username on an ESPN row, so Sleeper rollover never touches it.
    assert api.rows[0]["sleeper_username"] == ""


def test_my_roster_resolves_from_the_saved_team_and_draft_picks_are_empty(api):
    from urllib.parse import quote

    enc = quote(KEY, safe="")
    assert api.client.get(f"/v1/leagues/{enc}/my-roster").json()["reason"] == "espn_team_not_selected"
    # Saving must drop the cached (pre-save) saved_leagues read, or My Team
    # would keep answering espn_team_not_selected for the cache's TTL.
    assert api.client.post("/v1/leagues/save", json={"league_id": KEY, "roster_id": "2"}).json()["ok"] is True
    roster = api.client.get(f"/v1/leagues/{enc}/my-roster").json()["roster"]
    assert roster["roster_id"] == 2 and roster["players"] == ["9221"]
    picks = api.client.get(f"/v1/leagues/{enc}/draft-picks").json()
    assert picks == {"ok": True, "picks": [], "reason": "espn_not_supported"}


def test_sleeper_only_features_answer_not_available_for_espn(api):
    from urllib.parse import quote

    enc = quote(KEY, safe="")
    for route in ("waivers", "trade-hub", "alerts", "gm-plan"):
        response = api.client.get(f"/v1/leagues/{enc}/{route}")
        assert response.status_code == 409, route
        assert response.json()["reason"] == "espn_not_supported"
        assert response.json()["detail"] == "Not available for ESPN leagues yet."


def test_portfolio_reports_espn_leagues_as_not_supported_without_computing(api):
    with patch.object(api.svc.dashboard_engine, "build_league_summary") as summary:
        row = api.svc._build_portfolio_row({}, "u", "t", "Dynasty", "", "free", {"league_id": KEY, "league_name": "FFLR"})
    summary.assert_not_called()
    assert row == {"status": "failed", "league_id": KEY, "league_name": "FFLR", "reason": "espn_not_supported"}


def test_rollover_resolution_never_loads_an_espn_league(api):
    with patch.object(api.svc.sleeper, "get_league", Mock(side_effect=AssertionError("loaded"))):
        assert api.svc.resolve_league_path_id(KEY, user=USER) == KEY
