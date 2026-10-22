from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from modules import portfolio_exposure


def _league(league_id, name, players):
    return {
        "ok": True,
        "league_id": league_id,
        "league_name": name,
        "players": [
            {"player_id": pid, "name": n, "position": pos, "team": "", "value": v} for pid, n, pos, v in players
        ],
    }


def test_exposure_counts_shares_and_concentration():
    leagues = [
        _league("1", "A", [("b", "Bijan", "RB", 100.0), ("c", "Chase", "WR", 50.0)]),
        _league("2", "B", [("b", "Bijan", "RB", 100.0)]),
        _league("3", "C", [("b", "Bijan", "RB", 100.0), ("d", "Dak", "QB", 50.0)]),
        {"ok": False, "reason": "league_season_ended"},
    ]
    out = portfolio_exposure.aggregate_exposure(leagues)
    assert out["league_count"] == 3
    assert out["total_value"] == 400.0
    bijan = out["players"][0]
    assert bijan["name"] == "Bijan"
    assert bijan["leagues_owned"] == 3 and bijan["share_of_leagues"] == 1.0
    assert bijan["share_of_value"] == 0.75
    chase = next(p for p in out["players"] if p["name"] == "Chase")
    assert chase["leagues_owned"] == 1 and round(chase["share_of_leagues"], 4) == 0.3333
    assert chase["league_names"] == ["A"]
    assert {p["position"]: p["share_of_value"] for p in out["by_position"]} == {"RB": 0.75, "WR": 0.125, "QB": 0.125}
    assert out["concentration"]["top_share_of_value"] == 1.0


def test_exposure_empty_is_safe():
    out = portfolio_exposure.aggregate_exposure([])
    assert out["players"] == [] and out["total_value"] == 0.0
    assert out["concentration"]["top_share_of_value"] == 0.0


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


def _auth_and_profile(entitlement):
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm_dynasty"}]
    return [auth_user_response, profile_response]


def test_endpoint_free_gets_only_the_upsell_before_any_data_work(monkeypatch):
    from services import mobile_api_service

    def _must_not_run(*_a, **_k):
        raise AssertionError("no data work for a Free caller")

    monkeypatch.setattr(mobile_api_service.account_store, "fetch_saved_leagues", _must_not_run)
    monkeypatch.setattr(mobile_api_service.portfolio_exposure, "build_league_ownership", _must_not_run)
    client = _client(monkeypatch)
    with patch("requests.get", side_effect=_auth_and_profile("free")):
        response = client.get("/v1/portfolio/exposure", headers={"Authorization": "Bearer good-token"})
    body = response.json()
    assert response.status_code == 200
    assert body["is_premium"] is False
    assert body["exposure"] is None
    assert body["upsell"]["title"] and body["upsell"]["body"]


def test_endpoint_requires_auth_and_valid_lens(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/portfolio/exposure").status_code == 401
    with patch("requests.get", side_effect=_auth_and_profile("premium")):
        response = client.get("/v1/portfolio/exposure?lens=Nope", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 422


def test_endpoint_pro_aggregates_and_skips_espn(monkeypatch):
    from services import mobile_api_service

    rows = [
        {"league_id": "111", "league_name": "Alpha", "sleeper_username": "gm_dynasty"},
        {"league_id": "222", "league_name": "Beta", "sleeper_username": "gm_dynasty"},
        {"league_id": "espn:9:2026", "league_name": "Espn One", "sleeper_username": ""},
    ]
    monkeypatch.setattr(mobile_api_service.account_store, "fetch_saved_leagues", lambda *a, **k: (rows, ""))
    owned = {
        "111": [("1", "Bijan Robinson", "RB", 100.0), ("2", "Puka Nacua", "WR", 50.0)],
        "222": [("1", "Bijan Robinson", "RB", 90.0)],
    }

    def _ownership(*, league_id, league_name, **_k):
        return _league(league_id, league_name, [(p, n, pos, v) for p, n, pos, v in owned[league_id]])

    monkeypatch.setattr(mobile_api_service.portfolio_exposure, "build_league_ownership", _ownership)
    client = _client(monkeypatch)
    with patch("requests.get", side_effect=_auth_and_profile("premium")):
        response = client.get("/v1/portfolio/exposure", headers={"Authorization": "Bearer good-token"})
    body = response.json()
    assert body["is_premium"] is True and body["upsell"] is None
    assert [s["league_id"] for s in body["skipped_leagues"]] == ["espn:9:2026"]
    assert body["skipped_leagues"][0]["reason"] == "espn_not_supported"
    exposure = body["exposure"]
    assert exposure["league_count"] == 2
    top = exposure["players"][0]
    assert top["name"] == "Bijan Robinson"
    assert top["leagues_owned"] == 2 and top["share_of_leagues"] == 1.0
    assert top["league_names"] == ["Alpha", "Beta"] and top["value"] == 190.0
    assert exposure["concentration"]["top_share_of_value"] == 1.0
    assert {p["position"] for p in exposure["by_position"]} == {"RB", "WR"}
