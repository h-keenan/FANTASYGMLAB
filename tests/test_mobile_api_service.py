"""Mobile API FastAPI service contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

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
