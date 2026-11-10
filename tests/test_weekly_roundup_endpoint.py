from unittest.mock import Mock, patch

import pytest

AUTH = {"Authorization": "Bearer good-token"}
SPEC = {"q": "QB", "r1": "RB", "r2": "RB", "r3": "RB", "w1": "WR", "t": "TE"}
LEAGUE = {
    "season": "2026",
    "settings": {"leg": 4, "last_scored_leg": 3, "playoff_week_start": 15},
    "roster_positions": ["QB", "RB", "RB", "WR", "TE", "BN"],
    "scoring_settings": {"rec": 1},
}
PTS = {"q": 20.0, "r1": 12.0, "r2": 3.0, "r3": 18.0, "w1": 10.0, "t": 7.0}


def _matchups(league_id, week):
    if week not in (1, 2, 3):
        return []
    return [
        {"roster_id": 1, "matchup_id": 1, "points": 70.0, "starters": ["q", "r1", "r2", "w1", "t"], "players_points": PTS},
        {"roster_id": 2, "matchup_id": 1, "points": 60.0, "starters": [], "players_points": {}},
    ]


def _players():
    return {pid: {"full_name": f"Name {pid}", "position": pos, "team": "XX"} for pid, pos in SPEC.items()}


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from modules import league_warmup
    from services import mobile_api_service

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    monkeypatch.setattr(league_warmup, "start_warmup", Mock(return_value=True))
    return TestClient(mobile_api_service.app)


def _get(client, monkeypatch, *, entitlement, roster=({"roster_id": 1, "reserve": [], "taxi": []}, ""), league=LEAGUE, path="/v1/leagues/abc/roundup"):
    monkeypatch.setattr("services.mobile_api_service._fetch_profile_fields", lambda *a, **k: {"entitlement": entitlement, "sleeper_username": "gm"})
    monkeypatch.setattr("services.mobile_api_service._resolve_my_roster", lambda *a, **k: roster)
    monkeypatch.setattr("services.mobile_api_service._league_access_allowed", lambda *a, **k: True)
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-1", "email": "gm@example.com"}
    with patch("requests.get", return_value=auth), patch("modules.sleeper.get_league", return_value=league), patch(
        "modules.sleeper.get_matchups", side_effect=_matchups
    ), patch("modules.sleeper.get_players", return_value=_players()), patch("modules.sleeper.cached_season_weekly_map", return_value={}):
        return client.get(path, headers=AUTH)


def test_roundup_requires_auth(monkeypatch):
    assert _client(monkeypatch).get("/v1/leagues/abc/roundup").status_code == 401


def test_pro_gets_full_roundup(monkeypatch):
    body = _get(_client(monkeypatch), monkeypatch, entitlement="premium").json()
    assert body["ok"] and body["reason"] == "" and body["is_premium"] is True
    assert body["week"] == 3 and body["max_completed_week"] == 3
    assert body["roundup"]["left_on_bench"] == 15.0
    assert body["roundup"]["lineup"] and body["season"]["weeks_reviewed"] == 3
    assert "point-in-time" in body["method"]


def test_free_gets_headline_and_top_swap_only(monkeypatch):
    body = _get(_client(monkeypatch), monkeypatch, entitlement="free").json()
    assert body["is_premium"] is False and body["upsell"]
    assert body["roundup"]["left_on_bench"] == 15.0
    assert len(body["roundup"]["swaps"]) == 1 and body["roundup"]["lineup"] == []
    assert body["season"] is None


def test_explicit_week_and_clamp(monkeypatch):
    body = _get(_client(monkeypatch), monkeypatch, entitlement="premium", path="/v1/leagues/abc/roundup?week=2").json()
    assert body["week"] == 2 and body["season"]["weeks_reviewed"] == 2


def test_offseason_and_no_roster_degrade(monkeypatch):
    offseason = dict(LEAGUE, settings={"leg": 0, "last_scored_leg": 0})
    body = _get(_client(monkeypatch), monkeypatch, entitlement="premium", league=offseason).json()
    assert body["roundup"] is None and body["reason"] == "no_completed_week"
    body = _get(_client(monkeypatch), monkeypatch, entitlement="premium", roster=(None, "no_sleeper_username_linked")).json()
    assert body["roundup"] is None and body["reason"] == "no_sleeper_username_linked"


def test_external_league_is_unsupported(monkeypatch):
    monkeypatch.setattr("modules.external_leagues.is_external_league_key", lambda key: True)
    body = _get(_client(monkeypatch), monkeypatch, entitlement="premium").json()
    assert body["reason"] == "unsupported_platform" and body["roundup"] is None


def test_roundup_notice_for_alerts_feed():
    from services import mobile_api_service as svc

    with patch("modules.sleeper.get_league", return_value=dict(LEAGUE, status="in_season")):
        notice = svc._roundup_notice("abc")
    assert notice["week"] == 3 and "week 3 roundup" in notice["title"]
    with patch("modules.sleeper.get_league", return_value=dict(LEAGUE, status="complete")):
        assert svc._roundup_notice("abc") is None
    with patch("modules.sleeper.get_league", return_value={"status": "in_season", "settings": {}}):
        assert svc._roundup_notice("abc") is None
