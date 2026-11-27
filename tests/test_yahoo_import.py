"""Yahoo league import (modules.yahoo_leagues / yahoo_connect / yahoo_credentials) and its API routes.

No network, no Yahoo, no data/players.db. The fixtures under tests/fixtures/yahoo
follow Yahoo's documented JSON shape (resources as lists of small dicts,
collections as {"0": .., "count": n}). They are NOT recordings of live Yahoo:
this environment cannot reach it. See docs/yahoo-import.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest
from cryptography.fernet import Fernet

from modules import external_leagues, external_matchups, yahoo_connect, yahoo_credentials, yahoo_leagues
from modules.external_league_common import ExternalLeagueError
from modules.platforms import yahoo_oauth

FIXTURES = Path(__file__).parent / "fixtures" / "yahoo"
KEY = "yahoo:461.l.12345:2026"
ACCESS = "yahoo-access-token-for-tests"


def _fx(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


PLAYERS = pd.DataFrame(
    [
        {"player_id": "S-ALLEN", "name": "Josh Allen", "position": "QB", "team": "BUF"},
        {"player_id": "S-HALL", "name": "Breece Hall", "position": "RB", "team": "NYJ"},
        {"player_id": "S-JJ", "name": "Justin Jefferson", "position": "WR", "team": "MIN"},
        {"player_id": "S-LAPORTA", "name": "Sam LaPorta", "position": "TE", "team": "DET"},
        {"player_id": "S-OLAVE", "name": "Chris Olave", "position": "WR", "team": "NO"},
        {"player_id": "S-WALKER", "name": "Kenneth Walker", "position": "RB", "team": "SEA"},
        {"player_id": "S-LAMAR", "name": "Lamar Jackson", "position": "QB", "team": "BAL"},
        {"player_id": "S-SAQUON", "name": "Saquon Barkley", "position": "RB", "team": "PHI"},
        {"player_id": "S-LAMB", "name": "CeeDee Lamb", "position": "WR", "team": "DAL"},
        {"player_id": "S-MCBRIDE", "name": "Trey McBride", "position": "TE", "team": "ARI"},
    ]
)


def _route(path, token):
    assert token == ACCESS
    if path == "game/nfl":
        return _fx("game_nfl")
    if path.startswith("users;use_login=1/games;game_keys=461/leagues"):
        return _fx("leagues")
    if path.endswith("/settings"):
        return _fx("settings")
    if path.endswith("/standings"):
        return _fx("standings")
    if path.endswith("/scoreboard"):
        return _fx("scoreboard")
    if path == "team/461.l.12345.t.1/roster/players":
        return _fx("roster_1")
    if path == "team/461.l.12345.t.2/roster/players":
        return _fx("roster_2")
    raise AssertionError(f"unexpected Yahoo path {path}")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(yahoo_leagues, "fetch_provider", _route)
    monkeypatch.setattr(yahoo_leagues, "players_frame_provider", lambda: PLAYERS.copy())
    monkeypatch.setattr(yahoo_leagues, "sleeper_players_provider", lambda: {})
    monkeypatch.setattr(yahoo_leagues, "crosswalk_provider", lambda: {"30123": "S-ALLEN"})
    external_leagues.clear_snapshot_caches()
    external_matchups.clear_caches()
    yield
    external_leagues.clear_snapshot_caches()
    external_matchups.clear_caches()


# --- JSON normalisation ---------------------------------------------------------


def test_flatten_handles_yahoos_list_of_dicts_and_indexed_collections():
    assert yahoo_leagues.flatten([{"a": 1}, [], {"b": {"0": {"x": 1}, "1": {"x": 2}, "count": 2}}]) == {
        "a": 1,
        "b": [{"x": 1}, {"x": 2}],
    }
    # Repeated keys must stay a list (roster slots, stat modifiers), never collapse into one.
    assert yahoo_leagues.flatten([{"stat": 1}, {"stat": 2}]) == [{"stat": 1}, {"stat": 2}]
    # Index keys mixed with named keys fold in.
    assert yahoo_leagues.flatten({"week": "9", "0": {"players": {"0": {"player": 1}, "count": 1}}}) == {
        "week": "9",
        "players": [{"player": 1}],
    }


def test_single_item_collections_still_read_as_lists():
    single = yahoo_leagues.flatten([{"roster_position": {"position": "QB", "count": 1}}])
    assert yahoo_leagues.seq(single, "roster_position") == [{"position": "QB", "count": 1}]


# --- keys + league list ------------------------------------------------------------


def test_league_keys():
    assert yahoo_leagues.build_league_key("461.l.12345", 2026) == KEY
    assert yahoo_leagues.parse_league_key(KEY) == ("461.l.12345", 2026)
    assert yahoo_leagues.build_league_key("12345", 2026) == ""
    assert yahoo_leagues.build_league_key("461.l.12345", 1999) == ""
    assert yahoo_leagues.parse_league_key("espn:42:2026") is None
    assert external_leagues.platform_of(KEY) == "yahoo"
    assert external_leagues.label_for(KEY) == "Yahoo"


def test_list_user_leagues_uses_current_game_key(monkeypatch):
    seen = []

    def spy(path, token):
        seen.append(path)
        return _route(path, token)

    monkeypatch.setattr(yahoo_leagues, "fetch_provider", spy)
    leagues = yahoo_leagues.list_user_leagues(ACCESS)
    assert seen == ["game/nfl", "users;use_login=1/games;game_keys=461/leagues"]
    assert [lg["league_key"] for lg in leagues] == [KEY, "yahoo:461.l.777:2026"]
    assert leagues[0]["name"] == "Sunday Funday" and leagues[0]["team_count"] == 2 and leagues[0]["season"] == "2026"


# --- parsing --------------------------------------------------------------------------


def test_settings_map_to_sleeper_vocabulary():
    league = _fx("settings")
    settings = yahoo_leagues.flatten(league)["fantasy_content"]["league"]["settings"]
    assert yahoo_leagues.roster_positions_from_settings(settings) == [
        "QB", "WR", "WR", "RB", "RB", "TE", "FLEX", "K", "DEF", "BN", "BN", "BN", "BN", "BN", "IR",
    ]
    scoring = yahoo_leagues.scoring_from_settings(settings)
    assert scoring["rec"] == 1.0 and scoring["pass_td"] == 4.0 and scoring["pass_int"] == -2.0
    assert scoring["fum_lost"] == -2.0 and scoring["pass_yd"] == 0.04
    assert "57" not in scoring and len(scoring) == 9  # an unknown stat id is never guessed


def test_roster_parse_reads_slots_and_positions():
    players = yahoo_leagues.parse_roster(_fx("roster_1"))
    by_name = {p["name"]: p for p in players}
    assert by_name["Josh Allen"]["position"] == "QB" and by_name["Josh Allen"]["team"] == "BUF"
    assert by_name["Chris Olave"]["yahoo_slot"] == "BN" and by_name["Kenneth Walker"]["yahoo_slot"] == "IR"
    assert by_name["Some Punter"]["position"] == ""  # not a valued position


def test_scoreboard_parse():
    board = yahoo_leagues.parse_scoreboard(_fx("scoreboard"))
    assert board["week"] == 9
    assert board["games"] == [{"a_id": "1", "b_id": "2", "a_points": 88.4, "b_points": 70.15, "status": "midevent"}]


# --- snapshot ---------------------------------------------------------------------------


def test_snapshot_builds_sleeper_shaped_league():
    snapshot = yahoo_leagues.load_league_snapshot(KEY, ACCESS, owner_user_id="u1")
    league = snapshot["league"]
    assert league["platform"] == "yahoo" and league["name"] == "Sunday Funday" and league["total_rosters"] == 2
    assert league["scoring_settings"]["rec"] == 1.0
    assert "FLEX" in league["roster_positions"]
    rosters = {r["roster_id"]: r for r in snapshot["rosters"]}
    assert set(rosters) == {1, 2}
    assert rosters[1]["players"][:1] == ["S-ALLEN"]  # crosswalk id
    assert "S-HALL" in rosters[1]["players"]  # name + position + team match
    assert "DET" in rosters[1]["players"]  # team defense -> Sleeper DEF id
    assert rosters[1]["reserve"] == ["S-WALKER"]
    assert rosters[1]["settings"]["wins"] == 6 and rosters[1]["settings"]["fpts"] == 1012
    users = {u["user_id"]: u for u in snapshot["users"]}
    assert users["yahoo-team-1"]["display_name"] == "alex"
    assert users["yahoo-team-2"]["display_name"] == "Bye Week Bandits"  # hidden manager falls back to the team name
    diag = snapshot["diagnostics"]
    assert diag["ignored_non_player_count"] == 1  # the punter
    assert any(p["name"] == "Unmatched Rookie" for p in diag["unmapped_players"])  # listed, never guessed
    assert snapshot["lineups"]["1"]["starters"] == ["S-ALLEN", "S-HALL", "S-JJ", "S-LAPORTA", "DET"]
    assert snapshot["lineups"]["1"]["unmapped"][0]["name"] == "Unmatched Rookie"
    assert snapshot["week_state"]["week"] == 9
    assert snapshot["week_state"]["pairings"]["1"] == {"opponent": "2", "points": 88.4}


def test_mapping_below_threshold_blocks_import(monkeypatch):
    monkeypatch.setattr(yahoo_leagues, "players_frame_provider", lambda: pd.DataFrame())
    monkeypatch.setattr(yahoo_leagues, "crosswalk_provider", lambda: {})
    snapshot = yahoo_leagues.load_league_snapshot(KEY, ACCESS, owner_user_id="u1")
    assert yahoo_leagues.mapping_blocks_import(snapshot)
    preview = yahoo_leagues.preview_payload(snapshot)
    assert preview["ok"] is False and preview["reason"] == "mapping_too_low"


def test_preview_lists_features_with_yahoo_refusals():
    preview = yahoo_leagues.preview_payload(yahoo_leagues.load_league_snapshot(KEY, ACCESS, owner_user_id="u1"))
    assert preview["ok"] and preview["platform_label"] == "Yahoo"
    refused = [f for f in preview["features"] if f["status"] != "available"]
    assert refused and all(f["note"] == "Not available for Yahoo leagues yet." for f in refused)


def test_not_available_message_and_route_gating():
    assert not external_leagues.gated_league_path(f"/v1/leagues/{KEY}/my-team")
    assert not external_leagues.gated_league_path(f"/v1/leagues/{KEY}/dashboard")
    assert external_leagues.gated_league_path(f"/v1/leagues/{KEY}/waivers")
    assert external_leagues.not_available_payload(f"/v1/leagues/{KEY}/waivers")["error"] == "Not available for Yahoo leagues yet."


def test_failure_modes(monkeypatch):
    def failing(path, token):
        raise ExternalLeagueError("league_not_found", "nope")

    monkeypatch.setattr(yahoo_leagues, "fetch_provider", failing)
    with pytest.raises(ExternalLeagueError) as exc:
        yahoo_leagues.load_league_snapshot(KEY, ACCESS)
    assert exc.value.reason == "league_not_found"
    with pytest.raises(ExternalLeagueError) as bad:
        yahoo_leagues.load_league_snapshot("yahoo:nope", ACCESS)
    assert bad.value.reason == "invalid_input"


def test_http_status_mapping(monkeypatch):
    monkeypatch.setattr(yahoo_leagues, "_throttle", SimpleNamespace(wait=lambda: None))
    for status, reason in ((401, "reconnect_needed"), (404, "league_not_found"), (999, "yahoo_rate_limited"), (500, "yahoo_unavailable")):
        monkeypatch.setattr(yahoo_leagues.requests, "get", lambda *a, _s=status, **k: SimpleNamespace(status_code=_s, json=lambda: {}))
        with pytest.raises(ExternalLeagueError) as exc:
            yahoo_leagues._default_fetch("game/nfl", "tok")
        assert exc.value.reason == reason


# --- per-user isolation -----------------------------------------------------------------


def test_snapshot_is_served_only_to_the_user_who_loaded_it(monkeypatch):
    token = yahoo_leagues.bind_request_access("alice", ACCESS)
    try:
        assert yahoo_leagues.get_league_snapshot(KEY)["owner_user_id"] == "alice"
    finally:
        yahoo_leagues.reset_request_login(token)
    # No bound login (background job, other request): nothing.
    assert yahoo_leagues.get_league_snapshot(KEY) is None
    # Another user loads on their own token, never alice's cache entry.
    calls = []
    monkeypatch.setattr(yahoo_leagues, "fetch_provider", lambda p, t: (calls.append(p), _route(p, t))[1])
    token = yahoo_leagues.bind_request_access("bob", ACCESS)
    try:
        assert yahoo_leagues.get_league_snapshot(KEY)["owner_user_id"] == "bob"
    finally:
        yahoo_leagues.reset_request_login(token)
    assert calls  # bob triggered his own load


def test_matchup_state_and_lineup_from_snapshot():
    token = yahoo_leagues.bind_request_access("alice", ACCESS)
    try:
        state = external_matchups.week_state(KEY)
        assert state["platform"] == "yahoo" and state["week"] == 9
        pair = external_matchups.opponent_of(state, 1)
        assert pair["theirs"] == 2 and pair["mine_points"] == 88.4
        lineup = external_matchups.lineup_for(KEY, 1, state)
        assert lineup["starters"][0] == "S-ALLEN" and lineup["slot_labels"][:2] == ["QB", "RB"]
    finally:
        yahoo_leagues.reset_request_login(token)
    assert external_matchups.week_state(KEY) is None  # no login: the shared week cache is not consulted


# --- credentials (encryption) -----------------------------------------------------------


@pytest.fixture
def fernet_key(monkeypatch):
    monkeypatch.delenv("YAHOO_CREDENTIAL_KEY", raising=False)
    monkeypatch.setenv("ESPN_CREDENTIAL_KEY", Fernet.generate_key().decode())


def test_credentials_roundtrip_and_redaction(fernet_key):
    creds = yahoo_credentials.YahooCredentials("REFRESH-SECRET", "ACCESS-SECRET", 1234.0, "GUID1")
    row = yahoo_credentials.encrypt(creds)
    assert "REFRESH-SECRET" not in json.dumps(row) and "ACCESS-SECRET" not in json.dumps(row)
    back = yahoo_credentials.decrypt(row)
    assert back == creds
    assert "SECRET" not in repr(back)
    assert yahoo_credentials.decrypt({**row, "refresh_token_enc": "garbage"}) is None


def test_credentials_off_without_key(monkeypatch):
    monkeypatch.delenv("YAHOO_CREDENTIAL_KEY", raising=False)
    monkeypatch.delenv("ESPN_CREDENTIAL_KEY", raising=False)
    assert not yahoo_credentials.is_configured()
    with pytest.raises(yahoo_credentials.YahooCredentialError) as exc:
        yahoo_credentials.encrypt(yahoo_credentials.YahooCredentials("r"))
    assert exc.value.reason == "not_configured"


def test_yahoo_specific_key_wins(monkeypatch):
    monkeypatch.setenv("ESPN_CREDENTIAL_KEY", Fernet.generate_key().decode())
    specific = Fernet.generate_key().decode()
    monkeypatch.setenv("YAHOO_CREDENTIAL_KEY", specific)
    row = yahoo_credentials.encrypt(yahoo_credentials.YahooCredentials("r"))
    assert Fernet(specific.encode()).decrypt(row["refresh_token_enc"].encode()) == b"r"


# --- OAuth state, start, callback, refresh ------------------------------------------------


@pytest.fixture
def yahoo_env(monkeypatch, fernet_key):
    monkeypatch.setenv("YAHOO_CLIENT_ID", "client-id-test")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "client-secret-test")
    monkeypatch.delenv("YAHOO_REDIRECT_URI", raising=False)
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.test")


def test_state_is_signed_expiring_and_tamper_proof(yahoo_env):
    state = yahoo_connect.sign_state("user-1", "app")
    assert yahoo_connect.verify_state(state) == {"user_id": "user-1", "return_to": "app"}
    body, _, sig = state.partition(".")
    assert yahoo_connect.verify_state(f"{body}x.{sig}") is None
    assert yahoo_connect.verify_state(body + ".") is None
    assert yahoo_connect.verify_state("") is None
    assert yahoo_connect.verify_state(state, now=time.time() + yahoo_connect.STATE_TTL_SECONDS + 5) is None
    assert yahoo_connect.sign_state("u", "evil") and yahoo_connect.verify_state(yahoo_connect.sign_state("u", "evil"))["return_to"] == "web"


def test_start_url_uses_registered_redirect_and_signed_state(yahoo_env):
    url = yahoo_connect.build_start_url("user-1", "web")
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://api.login.yahoo.com/oauth2/request_auth"
    assert q["redirect_uri"] == ["https://api.fantasygmlab.com/v1/yahoo/oauth/callback"]
    assert q["response_type"] == ["code"] and q["client_id"] == ["client-id-test"]
    assert yahoo_connect.verify_state(q["state"][0])["user_id"] == "user-1"
    assert "client-secret-test" not in url


def _token(refresh="new-refresh", access="new-access", expires=3600, guid="GUID9"):
    return yahoo_oauth.YahooOAuthToken(access, refresh, "bearer", expires, guid, time.time(), {})


def test_callback_exchanges_code_and_stores_encrypted_tokens(yahoo_env, monkeypatch):
    saved = {}
    monkeypatch.setattr(yahoo_oauth, "exchange_code_for_token", lambda **kw: (saved.setdefault("kw", kw), _token())[1])
    monkeypatch.setattr(yahoo_credentials, "save", lambda config, tok, *, user_id, credentials: saved.update(user=user_id, creds=credentials))
    state = yahoo_connect.sign_state("user-7", "web")
    target = yahoo_connect.complete_callback({}, code="abc", state=state)
    assert target == "https://app.example.test/connect-league?yahoo=connected"
    assert saved["user"] == "user-7" and saved["creds"].refresh_token == "new-refresh"
    assert saved["kw"]["redirect_uri"] == "https://api.fantasygmlab.com/v1/yahoo/oauth/callback"
    app_target = yahoo_connect.complete_callback({}, code="abc", state=yahoo_connect.sign_state("user-7", "app"))
    assert app_target == "fantasygmlab://yahoo?status=connected"


def test_callback_failures_redirect_with_a_reason_and_store_nothing(yahoo_env, monkeypatch):
    stored = []
    monkeypatch.setattr(yahoo_credentials, "save", lambda *a, **k: stored.append(1))
    good = yahoo_connect.sign_state("u", "app")
    assert "reason=denied" in yahoo_connect.complete_callback({}, code="", state=good, error="access_denied")
    assert "reason=bad_state" in yahoo_connect.complete_callback({}, code="c", state="forged.state")
    monkeypatch.setattr(yahoo_oauth, "exchange_code_for_token", lambda **kw: (_ for _ in ()).throw(yahoo_oauth.YahooOAuthError("no")))
    assert "reason=exchange_failed" in yahoo_connect.complete_callback({}, code="c", state=good)
    monkeypatch.setattr(yahoo_oauth, "exchange_code_for_token", lambda **kw: _token())
    monkeypatch.setattr(yahoo_credentials, "save", lambda *a, **k: (_ for _ in ()).throw(yahoo_credentials.YahooCredentialError("storage_failed", "x")))
    assert "reason=storage_failed" in yahoo_connect.complete_callback({}, code="c", state=good)
    assert stored == []


def test_access_token_refresh_rotates_and_reports_reconnect(yahoo_env, monkeypatch):
    store = {"creds": yahoo_credentials.YahooCredentials("old-refresh", "old-access", time.time() - 10, "G")}
    monkeypatch.setattr(yahoo_credentials, "load", lambda *a, **k: store["creds"])
    monkeypatch.setattr(yahoo_credentials, "save", lambda c, t, *, user_id, credentials: store.update(creds=credentials))
    refreshed = []

    def fake_refresh(**kw):
        refreshed.append(kw)
        return _token(refresh="rotated-refresh", access="fresh-access", guid="")

    monkeypatch.setattr(yahoo_oauth, "refresh_access_token", fake_refresh)
    token, reason = yahoo_connect.get_access_token({}, "jwt", user_id="u")
    assert (token, reason) == ("fresh-access", "")
    assert refreshed[0]["refresh_token"] == "old-refresh"
    assert store["creds"].refresh_token == "rotated-refresh" and store["creds"].yahoo_guid == "G"
    # still valid: no second refresh
    assert yahoo_connect.get_access_token({}, "jwt", user_id="u") == ("fresh-access", "")
    assert len(refreshed) == 1
    # Yahoo refuses the refresh token
    err = yahoo_oauth.YahooOAuthError("x")
    err.status_code = 400
    monkeypatch.setattr(yahoo_oauth, "refresh_access_token", lambda **kw: (_ for _ in ()).throw(err))
    assert yahoo_connect.get_access_token({}, "jwt", user_id="u", force_refresh=True) == (None, "reconnect_needed")


def test_not_connected_and_not_configured(monkeypatch, fernet_key):
    monkeypatch.delenv("YAHOO_CLIENT_ID", raising=False)
    monkeypatch.delenv("YAHOO_CLIENT_SECRET", raising=False)
    assert yahoo_connect.get_access_token({}, "jwt", user_id="u") == (None, "not_configured")
    monkeypatch.setenv("YAHOO_CLIENT_ID", "a")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "b")
    monkeypatch.setattr(yahoo_credentials, "load", lambda *a, **k: None)
    assert yahoo_connect.get_access_token({}, "jwt", user_id="u") == (None, "not_connected")


# --- API routes ----------------------------------------------------------------------------

USER = {"id": "user-1", "_access_token": "supabase-jwt", "email": "a@b.test"}


@pytest.fixture
def api(monkeypatch, yahoo_env):
    from fastapi.testclient import TestClient

    from services import mobile_api_service as svc

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    monkeypatch.setitem(svc.app.dependency_overrides, svc.require_user, lambda: USER)
    monkeypatch.setattr(yahoo_credentials, "has_saved", lambda *a, **k: True)
    monkeypatch.setattr(yahoo_connect, "get_access_token", lambda *a, **k: (ACCESS, ""))
    monkeypatch.setattr(svc, "_resolve_yahoo_login", lambda token: ("user-1", ACCESS))
    rows: list[dict] = []
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: {"entitlement": "free", "sleeper_username": "", "status": "ok"})
    monkeypatch.setattr(svc.account_store, "fetch_rows", lambda *a, **k: ([dict(r) for r in rows], ""))
    monkeypatch.setattr(svc.account_store, "fetch_saved_leagues", lambda *a, **k: ([dict(r) for r in rows], ""))

    def upsert(_config, _token, payload):
        rows.append(dict(payload))
        return True, ""

    monkeypatch.setattr(svc.account_store, "upsert_saved_league", upsert)
    yield SimpleNamespace(client=TestClient(svc.app, follow_redirects=False), svc=svc, rows=rows, mp=monkeypatch)


def test_status_start_and_disconnect_routes(api, monkeypatch):
    assert api.client.get("/v1/yahoo/status").json() == {"ok": True, "available": True, "connected": True}
    started = api.client.post("/v1/yahoo/oauth/start", json={"return_to": "app"}).json()
    assert started["ok"] and started["authorize_url"].startswith("https://api.login.yahoo.com/oauth2/request_auth?")
    deleted = []
    monkeypatch.setattr(yahoo_credentials, "delete", lambda c, t, *, user_id: deleted.append(user_id))
    assert api.client.post("/v1/yahoo/disconnect").json() == {"ok": True, "connected": False}
    assert deleted == ["user-1"]


def test_start_when_unconfigured_degrades_gracefully(api, monkeypatch):
    monkeypatch.delenv("YAHOO_CLIENT_SECRET", raising=False)
    body = api.client.post("/v1/yahoo/oauth/start", json={}).json()
    assert body["ok"] is False and body["reason"] == "not_configured"
    assert api.client.get("/v1/yahoo/status").json()["available"] is False


def test_callback_route_redirects(api, monkeypatch):
    monkeypatch.setattr(yahoo_connect, "complete_callback", lambda config, **kw: "fantasygmlab://yahoo?status=connected")
    response = api.client.get("/v1/yahoo/oauth/callback?code=c&state=s")
    assert response.status_code == 302 and response.headers["location"] == "fantasygmlab://yahoo?status=connected"
    assert response.headers["cache-control"] == "no-store"


def test_list_preview_and_gated_routes(api):
    listed = api.client.get("/v1/yahoo/leagues").json()
    assert listed["ok"] and listed["leagues"][0]["league_key"] == KEY
    preview = api.client.post("/v1/yahoo/leagues/preview", json={"league_key": KEY}).json()
    assert preview["ok"] and [t["team_name"] for t in preview["teams"]] == ["Gridiron Ghosts", "Bye Week Bandits"]
    assert api.client.post("/v1/yahoo/leagues/preview", json={"league_key": "garbage"}).json()["reason"] == "invalid_input"
    gated = api.client.get(f"/v1/leagues/{KEY}/waivers")
    assert gated.status_code == 409 and gated.json()["error"] == "Not available for Yahoo leagues yet."


def test_list_reports_reconnect(api, monkeypatch):
    monkeypatch.setattr(yahoo_connect, "get_access_token", lambda *a, **k: (None, "reconnect_needed"))
    body = api.client.get("/v1/yahoo/leagues").json()
    assert body["ok"] is False and body["reason"] == "reconnect_needed" and "Connect Yahoo" in body["message"]


def test_save_and_my_roster_use_the_callers_yahoo_login(api):
    from urllib.parse import quote

    auth = {"Authorization": "Bearer supabase-jwt"}
    enc = quote(KEY, safe="")
    assert api.client.post("/v1/leagues/save", json={"league_id": KEY}, headers=auth).json()["reason"] == "espn_team_not_selected"
    saved = api.client.post("/v1/leagues/save", json={"league_id": KEY, "roster_id": "2"}, headers=auth).json()
    assert saved["ok"] is True and saved["league"]["platform"] == "yahoo"
    assert api.rows[0]["league_id"] == KEY and api.rows[0]["sleeper_username"] == ""
    roster = api.client.get(f"/v1/leagues/{enc}/my-roster", headers=auth).json()["roster"]
    assert roster["roster_id"] == 2 and "S-LAMAR" in roster["players"]
    # Without the caller's Yahoo login (e.g. another user) the league does not load.
    api.mp.setattr(api.svc, "_resolve_yahoo_login", lambda token: None)
    yahoo_leagues.clear_snapshot_cache()
    other = api.client.post("/v1/leagues/save", json={"league_id": KEY, "roster_id": "2"}, headers=auth).json()
    assert other["ok"] is False and other["reason"] == "league_not_found"
