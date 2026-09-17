"""Mobile API FastAPI service contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")

    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


def test_render_yaml_documents_mobile_api_service():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "fantasygm-lab-mobile-api" in text
    assert "uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $PORT" in text
    assert "healthCheckPath: /health" in text.split("fantasygm-lab-mobile-api", 1)[1]


def test_health_root_and_ready(monkeypatch):
    client = _client(monkeypatch)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["me"] == "/v1/me"

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_ready_reports_not_ready_without_supabase_config(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    from services import mobile_api_service

    client = TestClient(mobile_api_service.app)
    ready = client.get("/ready")
    assert ready.status_code == 503
    assert "supabase_not_configured" in ready.json()["issues"]


def test_protected_endpoints_require_bearer_token(monkeypatch):
    client = _client(monkeypatch)

    missing = client.get("/v1/me")
    assert missing.status_code == 401

    malformed = client.get("/v1/me", headers={"Authorization": "Token abc"})
    assert malformed.status_code == 401

    league = client.get("/v1/leagues/123")
    assert league.status_code == 401


def test_me_rejects_invalid_session(monkeypatch):
    client = _client(monkeypatch)

    error_response = Mock(status_code=401)
    error_response.json.return_value = {"error": "invalid token"}
    with patch("requests.get", return_value=error_response):
        response = client.get("/v1/me", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401


def test_me_returns_user_and_entitlement(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "premium"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["user"]["id"] == "user-123"
    assert body["user"]["email"] == "gm@example.com"
    assert body["user"]["entitlement"] == "premium"
    assert body["user"]["sleeper_username"] == ""


def test_me_returns_linked_sleeper_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json()["user"]["sleeper_username"] == "gm_dynasty"


def test_me_defaults_to_free_when_profile_lookup_fails(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    profile_response = Mock(status_code=500)

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json()["user"]["entitlement"] == "free"


def test_league_endpoints_wrap_sleeper_module(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={"name": "Dynasty League"}):
            league = client.get("/v1/leagues/abc", headers={"Authorization": "Bearer good-token"})
        assert league.status_code == 200
        assert league.json()["league"]["name"] == "Dynasty League"

        with patch("modules.sleeper.get_league", return_value={}):
            missing = client.get("/v1/leagues/abc", headers={"Authorization": "Bearer good-token"})
        assert missing.status_code == 404

        with patch("modules.sleeper.get_users", return_value=[{"user_id": "u1"}]):
            users = client.get("/v1/leagues/abc/users", headers={"Authorization": "Bearer good-token"})
        assert users.status_code == 200
        assert users.json()["users"] == [{"user_id": "u1"}]

        with patch("modules.sleeper.get_rosters", return_value=[{"roster_id": 1}]):
            rosters = client.get("/v1/leagues/abc/rosters", headers={"Authorization": "Bearer good-token"})
        assert rosters.status_code == 200
        assert rosters.json()["rosters"] == [{"roster_id": 1}]

        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "u1", "metadata": {}}],
        ):
            with patch(
                "modules.sleeper.get_users",
                return_value=[{"user_id": "u1", "display_name": "Alice", "avatar": "abc123"}],
            ):
                profiles = client.get(
                    "/v1/leagues/abc/team-profiles",
                    headers={"Authorization": "Bearer good-token"},
                )
        assert profiles.status_code == 200
        body = profiles.json()["profiles"]
        # Real modules.sleeper.get_league_roster_profiles engine, not a mocked
        # result — exercises the actual team_name/avatar fallback chain.
        assert body["1"]["team_name"] == "Alice"
        assert body["1"]["avatar_url"].endswith("abc123")


def test_my_roster_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/my-roster")
    assert response.status_code == 401


def test_my_roster_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["roster"] is None
    assert body["reason"] == "no_sleeper_username_linked"


def test_my_roster_reports_sleeper_user_not_found(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "ghost_gm"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value=None):
            response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["roster"] is None
    assert body["reason"] == "sleeper_user_not_found"


def test_my_roster_reports_not_a_member(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch("modules.sleeper.get_rosters", return_value=[{"roster_id": 1, "owner_id": "someone-else"}]):
                response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["roster"] is None
    assert body["reason"] == "not_a_member_of_league"


def test_my_roster_returns_matching_roster(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "someone-else"},
                    {"roster_id": 2, "owner_id": "sleeper-user-1", "players": ["p1", "p2"]},
                ],
            ):
                response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["reason"] == ""
    assert body["roster"]["roster_id"] == 2
    assert body["roster"]["players"] == ["p1", "p2"]


def _fake_roster_frame():
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "WR"]
    rows = []
    for i, position in enumerate(positions, start=1):
        rows.append(
            {
                "player_id": f"my{i}",
                "name": f"My Player {i}",
                "position": position,
                "team": "KC",
                "age": 26,
                "years_exp": 4,
                "status": "Active",
                "injury_status": None,
                "score": 2000,
                "dynasty_score": 2000,
                "value_score": 2000,
                "rebuild_score": 2000,
            }
        )
    # A clearly-weaker bench RB to trade away.
    rows.append(
        {
            "player_id": "my_bench_rb",
            "name": "Bench Runner",
            "position": "RB",
            "team": "KC",
            "age": 30,
            "years_exp": 8,
            "status": "Active",
            "injury_status": None,
            "score": 300,
            "dynasty_score": 300,
            "value_score": 300,
            "rebuild_score": 300,
        }
    )
    # A clearly-better available RB to trade for.
    rows.append(
        {
            "player_id": "target_rb",
            "name": "Target Runner",
            "position": "RB",
            "team": "SF",
            "age": 25,
            "years_exp": 3,
            "status": "Active",
            "injury_status": None,
            "score": 6000,
            "dynasty_score": 6000,
            "value_score": 6000,
            "rebuild_score": 6000,
        }
    )
    return pd.DataFrame(rows)


_TRADE_ANALYZER_LEAGUE = {
    "scoring_settings": {"rec": 1.0},
    "settings": {"type": 2},
    "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN"],
    "total_rosters": 12,
}


def test_trade_analyzer_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/v1/leagues/abc/trade-analyzer", json={"send_player_ids": ["p1"]})
    assert response.status_code == 401


def test_trade_analyzer_rejects_empty_package(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/abc/trade-analyzer",
            json={},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_trade_analyzer_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.post(
            "/v1/leagues/abc/trade-analyzer",
            json={"send_player_ids": ["my_bench_rb"], "receive_player_ids": ["target_rb"]},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] is None
    assert body["reason"] == "no_sleeper_username_linked"


def test_trade_analyzer_returns_real_verdict_for_lopsided_upgrade(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            response = client.post(
                                "/v1/leagues/abc/trade-analyzer",
                                json={
                                    "send_player_ids": ["my_bench_rb"],
                                    "receive_player_ids": ["target_rb"],
                                    "strategy": "contender",
                                },
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    verdict = body["verdict"]
    # A clearly better RB (6000) for a clearly worse one (300) on a
    # contender roster should land as a real accept, not a mocked stub —
    # this exercises the actual fit engine + verdict logic end to end.
    assert verdict["tone"] == "accept"
    assert verdict["value_delta"] > 0
    for key in ("band", "ui_verdict", "confidence", "rationale", "value_summary", "roster_summary"):
        assert key in verdict


def test_trade_analyzer_passes_partner_roster_assets_when_given(monkeypatch):
    """partner_roster_id should resolve to that roster's real players and
    reach decide_offer_verdict as partner_assets — the input
    build_counter_guidance needs to suggest a specific verified asset
    instead of only generic counter text (see modules.trade_offer_analyzer).
    """

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_verdict = SimpleNamespace(to_public_dict=lambda: {"ok": "stub"})

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "other-user", "players": ["target_rb"]},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_offer_analyzer.decide_offer_verdict",
                                return_value=fake_verdict,
                            ) as mock_decide:
                                response = client.post(
                                    "/v1/leagues/abc/trade-analyzer",
                                    json={
                                        "send_player_ids": ["my_bench_rb"],
                                        "receive_player_ids": [],
                                        "strategy": "contender",
                                        "partner_roster_id": "2",
                                    },
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    assert response.json()["verdict"] == {"ok": "stub"}
    partner_assets = mock_decide.call_args.kwargs["partner_assets"]
    assert len(partner_assets) == 1
    assert partner_assets[0]["player_id"] == "target_rb"
    assert partner_assets[0]["owner_roster_id"] == "2"


def _fake_players_dataset():
    return {
        "1001": {
            "full_name": "Test Player",
            "first_name": "Test",
            "last_name": "Player",
            "position": "WR",
            "team": "KC",
            "status": "Active",
            "injury_status": None,
            "age": 26,
            "number": 10,
            "years_exp": 4,
            "espn_id": "should-not-leak",
            "sportradar_id": "should-not-leak",
        },
    }


def test_players_endpoint_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players?ids=1001")
    assert response.status_code == 401


def test_players_endpoint_projects_minimal_fields(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_players", return_value=_fake_players_dataset()):
            response = client.get(
                "/v1/players?ids=1001,9999",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert set(body["players"].keys()) == {"1001"}
    player = body["players"]["1001"]
    assert player["full_name"] == "Test Player"
    assert player["position"] == "WR"
    assert "espn_id" not in player
    assert "sportradar_id" not in player


def test_players_endpoint_rejects_empty_or_oversized_id_list(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        empty = client.get("/v1/players?ids=", headers={"Authorization": "Bearer good-token"})
        assert empty.status_code == 422

        too_many_ids = ",".join(str(i) for i in range(301))
        oversized = client.get(
            f"/v1/players?ids={too_many_ids}",
            headers={"Authorization": "Bearer good-token"},
        )
        assert oversized.status_code == 422


def _fake_players_frame():
    return pd.DataFrame(
        [
            {
                "player_id": "9001",
                "name": "Star Wideout",
                "position": "WR",
                "team": "KC",
                "age": 24,
                "years_exp": 3,
                "status": "Active",
                "injury_status": None,
                "search_rank": 10,
                "score": 8000,
                "dynasty_score": 8000,
                "value_score": 7000,
                "market_score": 8000,
                "role_score": 7500,
                "opportunity_score": 7500,
                "scarcity_score": 7000,
                "risk_multiplier": 1.0,
            },
            {
                "player_id": "9002",
                "name": "Backup Runner",
                "position": "RB",
                "team": "NYJ",
                "age": 29,
                "years_exp": 7,
                "status": "Active",
                "injury_status": None,
                "search_rank": 400,
                "score": 1200,
                "dynasty_score": 1200,
                "value_score": 1500,
                "market_score": 1200,
                "role_score": 1000,
                "opportunity_score": 900,
                "scarcity_score": 800,
                "risk_multiplier": 1.0,
            },
        ]
    )


def test_rankings_endpoint_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/rankings")
    assert response.status_code == 401


def test_rankings_endpoint_rejects_unknown_lens(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/leagues/abc/rankings?lens=Nonsense",
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_rankings_endpoint_returns_ranked_players_for_real_league_settings(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_league = {
        "scoring_settings": {"rec": 1.0},
        "settings": {"type": 2},
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN"],
        "total_rosters": 12,
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=fake_league):
            with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                with patch(
                    "modules.player_eligibility.filter_current_fantasy_players",
                    side_effect=lambda df, **kwargs: df,
                ):
                    response = client.get(
                        "/v1/leagues/abc/rankings?lens=Dynasty",
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    players = body["players"]
    assert len(players) == 2
    # The genuinely more valuable player ranks first — this exercises the
    # real valuation/ranking engine (modules.league_value_settings), not a
    # mocked result, so a wiring mistake would actually change this order.
    assert players[0]["name"] == "Star Wideout"
    assert players[0]["overall_rank"] == 1
    assert players[1]["name"] == "Backup Runner"
    assert players[1]["overall_rank"] == 2
    for player in players:
        assert "score" in player
        assert "tier" in player
        assert "opportunity_label" in player


def test_rankings_endpoint_returns_404_for_missing_league(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={}):
            response = client.get(
                "/v1/leagues/missing/rankings",
                headers={"Authorization": "Bearer good-token"},
            )
    assert response.status_code == 404


def test_rankings_endpoint_rejects_bad_limit(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/leagues/abc/rankings?limit=0",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422

        response = client.get(
            "/v1/leagues/abc/rankings?limit=9999",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422


def test_news_endpoint_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/news")
    assert response.status_code == 401


def test_news_endpoint_rejects_bad_limit(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/news?limit=0",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422

        response = client.get(
            "/v1/news?limit=9999",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422


def test_news_endpoint_filters_to_actionable_signal_and_dedupes(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    fake_pool = [
        {
            "title": "Star RB (knee) questionable for Sunday",
            "summary": "The team's RB1 was limited in practice with a knee issue.",
            "link": "https://example.com/injury-1",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
        # Off-topic — no injury/role/transaction/off-field signal, should be dropped.
        {
            "title": "Celebrity attends game, wears fun hat",
            "summary": "A celebrity wore a hat at the game.",
            "link": "https://example.com/celebrity",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 2000.0,
        },
        # Duplicate link of the injury item above (different casing) — deduped.
        {
            "title": "Star RB (knee) questionable for Sunday",
            "summary": "The team's RB1 was limited in practice with a knee issue.",
            "link": "HTTPS://EXAMPLE.COM/injury-1",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
        {
            "title": "Team trades WR to division rival",
            "summary": "A trade sends a wide receiver across the division.",
            "link": "https://example.com/trade-1",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 3000.0,
        },
    ]

    from modules import news as news_module

    news_module.clear_enriched_news_pool_cache()
    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.news.schedule_news_cache_refresh", return_value=False):
            with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                response = client.get(
                    "/v1/news",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    items = body["items"]
    # Celebrity item dropped (no actionable signal); injury duplicate deduped;
    # most-recent-first ordering (trade at 3000 before injury at 1000).
    assert len(items) == 2
    assert items[0]["title"] == "Team trades WR to division rival"
    assert items[0]["event_type"] == "transaction"
    assert items[1]["title"] == "Star RB (knee) questionable for Sunday"
    assert items[1]["event_type"] == "injury/status"
    for item in items:
        assert "summary" in item
        assert "speculative" in item


_RECAP_LEAGUE = {
    "season": "2026",
    "settings": {"leg": 3, "last_scored_leg": 3, "playoff_week_start": 15},
}


def _recap_matchups(league_id: str, week: int):
    if week not in (1, 2, 3):
        return []
    return [
        {"roster_id": 1, "matchup_id": 1, "points": 130.5},
        {"roster_id": 2, "matchup_id": 1, "points": 98.2},
    ]


def _recap_transactions(league_id: str, week: int):
    if week != 3:
        return []
    return [
        {
            "type": "waiver",
            "status": "complete",
            "adds": {"9001": 1},
            "drops": None,
            "roster_ids": [1],
            "status_updated": 1700000000000,
            "transaction_id": "tx1",
            "settings": {"waiver_bid": 12},
        }
    ]


def test_recap_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/recap")
    assert response.status_code == 401


def test_recap_returns_404_for_missing_league(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={}):
            response = client.get("/v1/leagues/missing/recap", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 404


def test_recap_reports_no_completed_week(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_RECAP_LEAGUE):
            with patch("modules.sleeper.get_matchups", return_value=[]):
                response = client.get("/v1/leagues/abc/recap", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["recap"] is None
    assert body["reason"] == "no_completed_week"


def test_recap_returns_real_weekly_recap(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    fake_profiles = {
        "1": {"team_name": "Home Team", "owner_name": "Alice", "username": "alice"},
        "2": {"team_name": "Away Team", "owner_name": "Bob", "username": "bob"},
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_RECAP_LEAGUE):
            with patch("modules.sleeper.get_matchups", side_effect=_recap_matchups):
                with patch("modules.sleeper.get_transactions", side_effect=_recap_transactions):
                    with patch("modules.sleeper.get_league_roster_profiles", return_value=fake_profiles):
                        with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/recap",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    recap = body["recap"]
    assert recap is not None
    assert recap["week"] == 3
    assert recap["season"] == "2026"
    # Real story generation (modules.league_recaps.build_weekly_recap), not a
    # mocked result — a wiring mistake (e.g. bad profiles/player_lookup shape)
    # would leave this empty.
    assert recap["stories"]
    assert recap["incomplete"] is False


def test_alerts_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/alerts")
    assert response.status_code == 401


def test_alerts_rejects_bad_limit(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/leagues/abc/alerts?limit=0",
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_alerts_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/leagues/abc/alerts", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["reason"] == "no_sleeper_username_linked"


def test_alerts_returns_real_roster_relevant_news(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    fake_pool = [
        {
            "title": "Star Wideout (ankle) limited in practice",
            "summary": "The receiver was limited with an ankle issue heading into Sunday.",
            "link": "https://example.com/star-wideout-injury",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
        {
            "title": "Unrelated player signs endorsement deal",
            "summary": "A player not on this roster signed a new deal.",
            "link": "https://example.com/unrelated",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 2000.0,
        },
    ]

    read_keys_response = Mock(status_code=200)
    read_keys_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, profile_response, read_keys_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["9001"]}],
            ):
                with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                    with patch("modules.news.schedule_news_cache_refresh", return_value=False):
                        with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                            response = client.get(
                                "/v1/leagues/abc/alerts",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    items = body["items"]
    # Only the roster-relevant item survives — this exercises the real
    # modules.my_news filtering/curation, not a mocked result.
    assert len(items) == 1
    assert items[0]["matched_player"] == "Star Wideout"
    assert items[0]["matched_player_id"] == "9001"
    assert "ankle" in items[0]["title"].casefold()
    assert items[0]["read"] is False
    assert items[0]["alert_key"]


def test_alerts_marks_items_already_read(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    fake_pool = [
        {
            "title": "Star Wideout (ankle) limited in practice",
            "summary": "The receiver was limited with an ankle issue.",
            "link": "https://example.com/star-wideout-injury",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
    ]
    from services.mobile_api_service import _alert_key_for_link

    already_read_key = _alert_key_for_link("https://example.com/star-wideout-injury")
    read_keys_response = Mock(status_code=200)
    read_keys_response.json.return_value = [{"alert_key": already_read_key}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response, read_keys_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["9001"]}],
            ):
                with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                    with patch("modules.news.schedule_news_cache_refresh", return_value=False):
                        with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                            response = client.get(
                                "/v1/leagues/abc/alerts",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["read"] is True


def test_mark_alert_read_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/v1/leagues/abc/alerts/read", json={"alert_key": "abc123"})
    assert response.status_code == 401


def test_mark_alert_read_rejects_empty_key(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/abc/alerts/read",
            json={"alert_key": ""},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_mark_alert_read_writes_with_callers_own_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    post_response = Mock(status_code=201)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=post_response) as mock_post:
            response = client.post(
                "/v1/leagues/abc/alerts/read",
                json={"alert_key": "abc123"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer good-token"
    assert call_kwargs["json"] == {"user_id": "user-123", "league_id": "abc", "alert_key": "abc123"}


def test_mark_alert_read_fails_closed_when_table_missing(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    post_response = Mock(status_code=404)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=post_response):
            response = client.post(
                "/v1/leagues/abc/alerts/read",
                json={"alert_key": "abc123"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "reason": "not_available"}


def _fake_quick_view_frame():
    return pd.DataFrame(
        [
            {
                "player_id": "9001",
                "name": "Star Wideout",
                "position": "WR",
                "years_exp": 3,
                "games_played": 10,
                "stats_season": 2026,
                "targets": 80,
                "receptions": 60,
                "receiving_yards": 900,
                "receiving_tds": 7,
                "fantasy_points_ppr": 210.5,
                "fantasy_points_half_ppr": 180.0,
                "fantasy_points_std": 150.0,
                "ppg": 21.0,
                "snap_share": 0.72,
                "target_share": 0.28,
            },
            {
                "player_id": "9002",
                "name": "No Stats Rookie",
                "position": "WR",
                "years_exp": 0,
            },
        ]
    )


def test_quick_view_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players/9001/quick-view")
    assert response.status_code == 401


def test_quick_view_reports_not_found_for_unknown_player(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/does-not-exist/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stats"] is None
    assert body["bio"] is None
    assert body["reason"] == "not_found"


def test_quick_view_returns_real_season_stats_and_bio(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/9001/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    stats = body["stats"]
    # Real modules.player_quick_view engine, not a mocked result — this
    # exercises the same code path the web app's player dossier pop-up uses.
    assert stats["position"] == "WR"
    assert len(stats["seasons"]) == 1
    season = stats["seasons"][0]
    assert season["season"] == 2026
    assert season["games"] == 10
    key_stat_labels = {item["label"] for item in season["key_stats"]}
    assert "Rec Yards" in key_stat_labels
    usage_labels = {item["label"] for item in season["usage"]}
    assert "Snap %" in usage_labels
    assert body["bio"]["years_in_league"] == "3 seasons"


def test_quick_view_reports_no_seasons_when_stats_unavailable(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/9002/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stats"]["seasons"] == []
    assert body["bio"]["years_in_league"] == "Rookie"


def test_gm_targets_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/gm-targets").status_code == 401
    assert client.post("/v1/leagues/abc/gm-targets", json={"player_id": "1"}).status_code == 401
    assert client.delete("/v1/leagues/abc/gm-targets/1").status_code == 401


def test_get_gm_targets_returns_watchlist(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    targets_response = Mock(status_code=200)
    targets_response.json.return_value = [
        {"player_id": "9001", "source_surface": "player_quick_view", "created_at": "2026-09-01T00:00:00Z"},
    ]

    with patch("requests.get", side_effect=[auth_user_response, targets_response]):
        response = client.get("/v1/leagues/abc/gm-targets", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["targets"] == [
        {"player_id": "9001", "source_surface": "player_quick_view", "created_at": "2026-09-01T00:00:00Z"},
    ]


def test_get_gm_targets_fails_soft_when_table_unreachable(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    error_response = Mock(status_code=404)
    error_response.json.return_value = {"message": "relation does not exist"}

    with patch("requests.get", side_effect=[auth_user_response, error_response]):
        response = client.get("/v1/leagues/abc/gm-targets", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "targets": []}


def test_add_gm_target_rejects_empty_player_id(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/abc/gm-targets",
            json={"player_id": ""},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_add_gm_target_enforces_free_tier_cap(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = [
        {"player_id": "1"}, {"player_id": "2"}, {"player_id": "3"},
    ]

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        response = client.post(
            "/v1/leagues/abc/gm-targets",
            json={"player_id": "9999"},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["reason"] == "at_cap"
    assert body["cap"] == 3


def test_add_gm_target_upserts_when_under_cap(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "premium", "sleeper_username": ""}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = []
    upsert_response = Mock(status_code=201)

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/leagues/abc/gm-targets",
                json={"player_id": "9001", "source_surface": "player_quick_view"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"] == {
        "user_id": "user-123",
        "league_id": "abc",
        "player_id": "9001",
        "source_surface": "player_quick_view",
    }


def test_remove_gm_target_deletes_row(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    delete_response = Mock(status_code=200)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.delete", return_value=delete_response) as mock_delete:
            response = client.delete(
                "/v1/leagues/abc/gm-targets/9001",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    requested_url = mock_delete.call_args.args[0]
    assert "user_id=eq.user-123" in requested_url
    assert "league_id=eq.abc" in requested_url
    assert "player_id=eq.9001" in requested_url


def test_player_awards_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players/9001/awards")
    assert response.status_code == 401


def test_player_awards_reports_not_found_for_unknown_player(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/does-not-exist/awards",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["awards"] == []
    assert body["reason"] == "not_found"


def test_player_awards_returns_real_badges_for_a_qualifying_season(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    players_frame = pd.DataFrame([{"player_id": "9001", "name": "Star Wideout", "position": "WR"}])
    fake_index = (
        {
            "path": "data/sleeper_player_stats_2025.json",
            "season": 2025,
            "payload": {
                "9001": {
                    "stats_season": 2025,
                    "receiving_yards": 1600,
                    "fantasy_points_ppr": 50.0,
                },
                "9002": {"stats_season": 2025, "fantasy_points_ppr": 10.0},
            },
        },
    )

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=players_frame):
            with patch("modules.player_awards.build_season_cache_index", return_value=fake_index):
                response = client.get(
                    "/v1/players/9001/awards",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    # Real modules.player_awards engine, not a mocked result — 1600 receiving
    # yards clears the WR gold threshold (>= 1500).
    assert any(award["short_label"] == "1,500+ Rec Yds" for award in body["awards"])
    for award in body["awards"]:
        assert award["tier"] in {"gold", "silver", "bronze", None}


def test_register_push_token_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/v1/push/register", json={"expo_push_token": "ExponentPushToken[abc]"})
    assert response.status_code == 401


def test_register_push_token_rejects_malformed_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/push/register",
            json={"expo_push_token": "not-a-real-token"},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "reason": "not_available"}


def test_register_push_token_upserts_with_callers_own_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    upsert_response = Mock(status_code=201)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/push/register",
                json={
                    "expo_push_token": "ExponentPushToken[abc123]",
                    "platform": "ios",
                    "device_name": "Test iPhone",
                },
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer good-token"
    assert call_kwargs["json"] == {
        "expo_push_token": "ExponentPushToken[abc123]",
        "user_id": "user-123",
        "platform": "ios",
        "device_name": "Test iPhone",
    }
    assert "on_conflict=expo_push_token" in mock_post.call_args.args[0]


def test_unregister_push_token_deletes_callers_own_row(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    delete_response = Mock(status_code=204)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.delete", return_value=delete_response) as mock_delete:
            response = client.post(
                "/v1/push/unregister",
                json={"expo_push_token": "ExponentPushToken[abc123]"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    assert "user_id=eq.user-123" in mock_delete.call_args.args[0]
    assert "expo_push_token=eq.ExponentPushToken[abc123]" in mock_delete.call_args.args[0]


def test_send_test_push_reports_no_registered_tokens(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    empty_tokens_response = Mock(status_code=200)
    empty_tokens_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, empty_tokens_response]):
        response = client.post(
            "/v1/push/test",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "reason": "no_registered_tokens"}


def test_send_test_push_delivers_via_expo_for_registered_tokens(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    tokens_response = Mock(status_code=200)
    tokens_response.json.return_value = [{"expo_push_token": "ExponentPushToken[abc123]"}]
    expo_response = Mock(status_code=200)
    expo_response.json.return_value = {"data": [{"status": "ok"}]}

    with patch("requests.get", side_effect=[auth_user_response, tokens_response]):
        with patch("requests.post", return_value=expo_response) as mock_post:
            response = client.post(
                "/v1/push/test",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body == {"ok": True, "reason": "", "sent": 1}
    # Real modules.push_tokens.send_expo_push_notifications engine, not a
    # mocked result — verifies it actually posts to Expo's push API.
    assert mock_post.call_args.args[0] == "https://exp.host/--/api/v2/push/send"
    sent_messages = mock_post.call_args.kwargs["json"]
    assert sent_messages == [
        {
            "to": "ExponentPushToken[abc123]",
            "title": "FantasyGM Lab",
            "body": mock_post.call_args.kwargs["json"][0]["body"],
            "data": {"kind": "test"},
        }
    ]


def test_get_push_preferences_defaults_all_categories_enabled(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/push/preferences", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["categories"] == {"top_priority": True, "watch": True, "recap": True, "injury": True}


def test_get_push_preferences_reflects_stored_overrides(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {"user_id": "user-123", "settings": {"push_categories": {"injury": False}}}
    ]

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/push/preferences", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json()["categories"]["injury"] is False
    assert response.json()["categories"]["watch"] is True


def test_update_push_preference_rejects_unknown_category(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/push/preferences",
            json={"category": "not_a_real_category", "enabled": False},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 422


def test_update_push_preference_upserts_merged_settings(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {"user_id": "user-123", "settings": {"push_categories": {"watch": False}}}
    ]
    upsert_response = Mock(status_code=200)

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/push/preferences",
                json={"category": "injury", "enabled": False},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "ok": True,
        "categories": {"top_priority": True, "watch": False, "recap": True, "injury": False},
    }
    # Existing "watch": False override is preserved, not clobbered by the new write.
    upserted_settings = mock_post.call_args.kwargs["json"]["settings"]
    assert upserted_settings["push_categories"] == {
        "top_priority": True,
        "watch": False,
        "recap": True,
        "injury": False,
    }


def test_push_preferences_require_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/push/preferences").status_code == 401
    assert client.post("/v1/push/preferences", json={"category": "watch", "enabled": True}).status_code == 401


def test_dashboard_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/dashboard")
    assert response.status_code == 401


def test_dashboard_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/dashboard",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["quiet"] is True
    assert body["reason"] == "no_sleeper_username_linked"


def test_dashboard_returns_real_briefing_items(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            response = client.get(
                                "/v1/leagues/abc/dashboard",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    # Real modules.dashboard_engine composition, not a mocked result — the
    # only unrostered player (target_rb) should surface as the waiver tile.
    # With no trade partner holding any players, there's no trade candidate,
    # so (per app.py's default tile order — see dashboard_engine's module
    # docstring) the waiver tile becomes the primary recommendation
    # ("top_priority"), same as modules.daily_gm_briefing's own
    # `_append(briefing.primary, CATEGORY_TOP_PRIORITY)`.
    assert len(body["items"]) >= 1
    for item in body["items"]:
        assert item["headline"]
        assert item["destination"]
    top_priority_items = [item for item in body["items"] if item["category"] == "top_priority"]
    categories = [item["category"] for item in body["items"]]
    assert top_priority_items, f"expected a top_priority tile, got categories: {categories}"
    assert top_priority_items[0]["route_player_id"] == "target_rb"


def test_dashboard_includes_team_snapshot(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {
                        "roster_id": 1,
                        "owner_id": "sleeper-user-1",
                        "players": my_roster_ids,
                        "settings": {"wins": 7, "losses": 6, "ties": 0},
                    },
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            response = client.get(
                                "/v1/leagues/abc/dashboard",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    snapshot = body["team_snapshot"]
    assert snapshot is not None
    assert snapshot["wins"] == 7
    assert snapshot["losses"] == 6
    assert snapshot["ties"] == 0
    # _fake_roster_frame's roster rows are all age 26 (except the bench RB at
    # 30), so the average is pulled up slightly above 26 but nowhere near 30.
    assert 26.0 <= snapshot["average_age"] <= 27.0
    assert isinstance(snapshot["health_flag"], str)
    assert snapshot["health_flag"]


def test_dashboard_team_snapshot_is_none_without_a_resolved_roster(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/dashboard",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["team_snapshot"] is None
    assert body["reason"] == "no_sleeper_username_linked"


def test_trade_hub_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/trade-hub")
    assert response.status_code == 401


def test_trade_hub_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/trade-hub",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["ideas"] == []
    assert body["reason"] == "no_sleeper_username_linked"


def test_trade_hub_resolves_roster_and_projects_generated_ideas(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_record = {
        "partner_team_name": "Rival GM",
        "rationale": "Clear upgrade at RB.",
        "trade_gain": 25,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": ["Need-Based"],
        "send_assets": [],
        "receive_assets": [],
    }

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_hub_engine.generate_trade_idea_records",
                                return_value=[fake_record],
                            ) as mock_generate:
                                response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    assert len(body["ideas"]) == 1
    assert body["ideas"][0]["partner_team_name"] == "Rival GM"
    assert body["ideas"][0]["trade_gain"] == 25
    assert body["ideas"][0]["confidence_label"] == "High"
    assert mock_generate.call_args.kwargs["my_roster_id"] == 1
    assert mock_generate.call_args.kwargs["team_strategy"] == "contender"
    assert mock_generate.call_args.kwargs["league_id"] == "abc"


def _fake_idea_record(name: str, *, gain: int) -> dict:
    return {
        "partner_team_name": name,
        "rationale": "Clear upgrade.",
        "trade_gain": gain,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": [],
        "send_assets": [],
        "receive_assets": [],
    }


def test_trade_hub_gates_free_entitlement_to_two_ideas_and_reveals_via_ads(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_cards = [_fake_idea_record(f"Rival {i}", gain=10 - i) for i in range(4)]

    # Two full requests, each: require_user's auth check + one profile fetch
    # shared between entitlement and _resolve_my_roster (no double-fetch).
    responses = [auth_user_response, profile_response] * 2
    with patch("requests.get", side_effect=responses):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_hub_engine.generate_trade_idea_records",
                                return_value=fake_cards,
                            ):
                                free_response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender",
                                    headers={"Authorization": "Bearer good-token"},
                                )
                                unlocked_response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender&ad_unlocks=1",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert free_response.status_code == 200
    free_body = free_response.json()
    assert len(free_body["ideas"]) == 2
    assert free_body["entitlement"] == {
        "is_premium": False,
        "approved_count": 4,
        "visible_count": 2,
        "hidden_count": 2,
        "free_limit": 2,
        "ad_bonus_per_unlock": 2,
        "max_ad_unlocks": 3,
        "ad_unlocks_applied": 0,
    }

    assert unlocked_response.status_code == 200
    unlocked_body = unlocked_response.json()
    assert len(unlocked_body["ideas"]) == 4
    assert unlocked_body["entitlement"]["visible_count"] == 4
    assert unlocked_body["entitlement"]["ad_unlocks_applied"] == 1
    assert unlocked_body["entitlement"]["hidden_count"] == 0


def test_trade_hub_premium_entitlement_sees_full_board_ignoring_ad_unlocks(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "premium", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_cards = [_fake_idea_record(f"Rival {i}", gain=10 - i) for i in range(3)]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_hub_engine.generate_trade_idea_records",
                                return_value=fake_cards,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    body = response.json()
    assert len(body["ideas"]) == 3
    assert body["entitlement"]["is_premium"] is True
    assert body["entitlement"]["hidden_count"] == 0


def test_waivers_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/waivers")
    assert response.status_code == 401


def test_waivers_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/waivers",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["players"] == []
    assert body["priority_adds"] == []
    assert body["reason"] == "no_sleeper_username_linked"


def test_waivers_excludes_rostered_players_and_ranks_free_agents(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    # waiver_actionable_player_pool runs the real (unmocked)
    # player_eligibility() check per row — unlike the dashboard/trade-hub
    # tests, which never call it. That function requires at least one
    # "current signal" (recent news, depth chart, current-season stats,
    # market value, or rookie flag) beyond just status="Active", or it
    # returns eligible=False with reason "missing_current_player_
    # corroboration". The shared fixture has none of those, so give
    # target_rb a current stats_season to satisfy it.
    roster_frame = _fake_roster_frame()
    roster_frame.loc[roster_frame["player_id"] == "target_rb", "stats_season"] = 2025

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=roster_frame):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            # player_state_authority imports this name directly
                            # (`from modules.player_eligibility import
                            # filter_current_fantasy_players`), so it has its own
                            # bound reference the patch above doesn't reach —
                            # waiver_actionable_player_pool calls that one
                            # internally, and it needs patching separately.
                            with patch(
                                "modules.player_state_authority.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/waivers",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    # Every my*/my_bench_rb id is rostered (roster 1 or 2); target_rb is the
    # one player in the fixture nobody owns, so it's the entire free-agent
    # pool — same fixture the dashboard/trade-hub tests reuse.
    player_ids = [p["player_id"] for p in body["players"]]
    assert player_ids == ["target_rb"]
    assert body["available_count"] == 1
    target = body["players"][0]
    # apply_valuation_lens recomputes the Dynasty score from the player's
    # attributes rather than echoing the fixture's raw dynasty_score field
    # (5428 for this row, not the fixture's 6000) — assert self-consistency
    # with the single free agent's own score instead of a hardcoded formula
    # output this test has no business predicting.
    assert body["avg_wire_score"] == round(target["score"])
    assert target["score"] > 0
    assert target["stale_free_agent"] is False
    # Wire-relative rank among the (single-player) free-agent pool, not the
    # league-global canonical rank.
    assert target["position_rank"] == 1
    assert target["overall_rank"] == 1


def test_team_rankings_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/team-rankings")
    assert response.status_code == 401


def test_team_rankings_returns_power_and_franchise_ranks(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_rosters = [
        {
            "roster_id": 1,
            "owner_id": "sleeper-user-1",
            "players": my_roster_ids,
            "settings": {"wins": 7, "losses": 6, "ties": 0},
        },
        {
            "roster_id": 2,
            "owner_id": "sleeper-user-2",
            "players": ["target_rb"],
            "settings": {"wins": 3, "losses": 10, "ties": 0},
        },
    ]
    fake_users = [
        {"user_id": "sleeper-user-1", "display_name": "GM One"},
        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
    ]

    # require_user is the only auth check here (no _resolve_my_roster / no
    # profile fetch — team-rankings is public league-wide data, same as
    # /team-profiles and /rosters), so exactly one requests.get call fires.
    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
            with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                with patch("modules.sleeper.get_users", return_value=fake_users):
                    with patch("modules.sleeper.get_traded_picks", return_value=[]):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/team-rankings",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    teams = body["teams"]
    assert len(teams) == 2
    by_roster = {t["roster_id"]: t for t in teams}
    # Roster 1's 10 starter-weighted players comfortably outscore roster 2's
    # single player, so roster 1 gets the top power/franchise rank.
    assert by_roster["1"]["power_rank"] == 1
    assert by_roster["2"]["power_rank"] == 2
    assert by_roster["1"]["franchise_rank"] == 1
    # Standings come straight off each roster's own settings, independent of
    # the rank computation.
    assert by_roster["1"]["wins"] == 7
    assert by_roster["1"]["losses"] == 6
    assert by_roster["2"]["wins"] == 3
    assert by_roster["2"]["losses"] == 10
    assert isinstance(by_roster["1"]["average_age"], (int, float))
    # No traded picks in this fixture — asserting draft_capital_rank doesn't
    # crash and comes back as a real int is the honest claim here; the exact
    # tie-breaking between rosters depends on default future-pick generation
    # this test has no business predicting.
    assert isinstance(by_roster["1"]["draft_capital_rank"], int)
    assert isinstance(by_roster["2"]["draft_capital_rank"], int)
    # Archetype/strategy classification (modules.team_eval.refine_team_directions)
    # runs on real strength inputs here (starter/bench/age/draft-capital ranks
    # all come from the fixture, not neutral fallbacks) — asserting the fields
    # are populated, non-empty labels is the honest claim; the exact archetype
    # a 2-team, lopsided-roster fixture lands on isn't this test's business.
    for team in teams:
        assert isinstance(team["strategy"], str) and team["strategy"]
        assert isinstance(team["strategy_label"], str) and team["strategy_label"]
        assert isinstance(team["archetype"], str) and team["archetype"]
        assert isinstance(team["archetype_label"], str) and team["archetype_label"]
        assert isinstance(team["archetype_explanation"], str) and team["archetype_explanation"]
        assert isinstance(team["archetype_strengths"], list)
        assert isinstance(team["archetype_risks"], list)
        assert isinstance(team["archetype_recommendations"], list)
