"""GET /v1/leagues/{id}/trade-target: gating and wiring (engine: test_trade_target_offers)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from tests.test_mobile_api_service import _TRADE_ANALYZER_LEAGUE, _client


def _auth_responses(entitlement):
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile = Mock(status_code=200)
    profile.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm_dynasty"}]
    return [auth, profile]


def test_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/trade-target?player_id=p1").status_code == 401


def test_rejects_invalid_lens_and_missing_player(monkeypatch):
    client = _client(monkeypatch)
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    with patch("requests.get", return_value=auth):
        bad_lens = client.get(
            "/v1/leagues/abc/trade-target?player_id=p1&lens=NotReal", headers={"Authorization": "Bearer t"}
        )
        no_player = client.get("/v1/leagues/abc/trade-target", headers={"Authorization": "Bearer t"})
    assert bad_lens.status_code == 422
    assert no_player.status_code == 422


def test_free_accounts_get_the_pro_upsell_and_no_search(monkeypatch):
    client = _client(monkeypatch)
    with patch("modules.sleeper.get_league", return_value={"status": "in_season"}):
        with patch("requests.get", side_effect=_auth_responses("free")):
            with patch("modules.trade_hub_engine.generate_target_offer_result") as engine:
                response = client.get(
                    "/v1/leagues/abc/trade-target?player_id=p1", headers={"Authorization": "Bearer t"}
                )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "locked" and body["is_premium"] is False
    assert body["offers"] == [] and "Pro" in body["upsell"]["body"]
    engine.assert_not_called()


def test_pro_accounts_get_the_engines_offers_for_their_roster(monkeypatch):
    client = _client(monkeypatch)
    from services import mobile_api_service as svc

    monkeypatch.setattr(svc, "_fetch_gm_target_player_ids", lambda *a, **k: ((), ("untouchable-1",)))
    monkeypatch.setattr(svc, "_fetch_team_stance", lambda *a, **k: "")
    monkeypatch.setattr(svc, "_trade_idea_keeper_round_penalty", lambda *a, **k: 0)
    monkeypatch.setattr(
        svc, "_resolve_trade_posture", lambda *a, **k: {"key": "contender", "label": "Contender", "source": "auto"}
    )
    fake = {"status": "found", "headline": "1 way to get X from Y.", "offers": [{"rank": 1}], "target": {"id": "p1"}}
    my_roster_ids = ["my1", "my2"]
    with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
        ):
            with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                with patch("requests.get", side_effect=_auth_responses("premium")):
                    with patch("modules.trade_hub_engine.generate_target_offer_result", return_value=fake) as engine:
                        response = client.get(
                            "/v1/leagues/abc/trade-target?player_id=p1&strategy=retool",
                            headers={"Authorization": "Bearer t"},
                        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True and body["status"] == "found" and body["offers"] == [{"rank": 1}]
    kwargs = engine.call_args.kwargs
    assert kwargs["target_player_id"] == "p1"
    assert kwargs["roster_id"] == 1
    assert kwargs["strategy"] == "contender"  # the server-resolved posture, not the client's "retool"
    assert kwargs["untouchable_player_ids"] == ("untouchable-1",)


def test_engine_failure_is_an_error_status_not_an_empty_result(monkeypatch):
    client = _client(monkeypatch)
    from services import mobile_api_service as svc

    monkeypatch.setattr(svc, "_fetch_gm_target_player_ids", lambda *a, **k: ((), ()))
    monkeypatch.setattr(svc, "_fetch_team_stance", lambda *a, **k: "")
    monkeypatch.setattr(svc, "_trade_idea_keeper_round_penalty", lambda *a, **k: 0)
    monkeypatch.setattr(svc, "_resolve_trade_posture", lambda *a, **k: {"key": "retool"})
    with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["my1"]}],
        ):
            with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                with patch("requests.get", side_effect=_auth_responses("premium")):
                    with patch("modules.trade_hub_engine.generate_target_offer_result", side_effect=RuntimeError("boom")):
                        response = client.get(
                            "/v1/leagues/abc/trade-target?player_id=p1", headers={"Authorization": "Bearer t"}
                        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error" and body["offers"] == []
    assert "not a real" in body["headline"]
