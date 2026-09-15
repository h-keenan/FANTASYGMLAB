"""RevenueCat webhook FastAPI service + entitlement sync contracts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _fake_response(status_code: int, json_data: dict | None = None, text: str = ""):
    return type(
        "R",
        (),
        {"status_code": status_code, "json": lambda self, _d=json_data: _d or {}, "text": text},
    )()


def test_render_yaml_revenuecat_webhook_health_and_start_command():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "fantasygm-lab-revenuecat-webhook" in text
    webhook_block = text.split("fantasygm-lab-revenuecat-webhook", 1)[1]
    assert "healthCheckPath: /health" in webhook_block
    assert "uvicorn services.revenuecat_webhook_service:app --host 0.0.0.0 --port $PORT" in webhook_block
    assert "SUPABASE_SERVICE_ROLE_KEY" in webhook_block
    assert "REVENUECAT_WEBHOOK_AUTH_TOKEN" in webhook_block


def test_supabase_migration_doc_matches_webhook_columns():
    sql = (ROOT / "docs" / "supabase_revenuecat_billing.sql").read_text(encoding="utf-8")
    for column in (
        "revenuecat_app_user_id",
        "revenuecat_event_id",
        "revenuecat_event_type",
        "revenuecat_environment",
        "revenuecat_event_created_at",
    ):
        assert column in sql


def _client():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from services import revenuecat_webhook_service

    return TestClient(revenuecat_webhook_service.app)


def _base_env(**overrides: str) -> dict[str, str]:
    env = {
        "REVENUECAT_SECRET_KEY": "sk_test_x",
        "REVENUECAT_PROJECT_ID": "proj123",
        "REVENUECAT_WEBHOOK_AUTH_TOKEN": "whtoken-x",
        "REVENUECAT_BILLING_MODE": "test",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role",
    }
    env.update(overrides)
    return env


def test_health_ready_and_root():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["webhook"] == "/revenuecat/webhook"

    with patch.dict(os.environ, {}, clear=True):
        not_ready = client.get("/ready")
    assert not_ready.status_code == 503
    assert "revenuecat_webhook_auth_token_missing" in not_ready.json()["issues"]

    with patch.dict(os.environ, _base_env(), clear=True):
        ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_missing_authorization_header_is_rejected():
    client = _client()
    response = client.post("/revenuecat/webhook", content=b"{}")
    assert response.status_code == 400
    assert "authorization" in response.json()["error"].casefold()


def test_wrong_authorization_token_is_rejected():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()
    with patch.dict(os.environ, _base_env(), clear=True):
        response = client.post(
            "/revenuecat/webhook",
            content=b"{}",
            headers={"Authorization": "wrong-token"},
        )
    assert response.status_code == 401


def test_test_event_type_is_skipped_without_supabase_call():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()
    session = Mock()
    body = b'{"event": {"id": "evt_test_1", "type": "TEST", "app_user_id": "user-1", "environment": "SANDBOX"}}'
    with (
        patch.dict(os.environ, _base_env(), clear=True),
        patch("modules.revenuecat_webhook.requests.patch", session.patch),
    ):
        response = client.post(
            "/revenuecat/webhook",
            content=body,
            headers={"Authorization": "whtoken-x"},
        )
    assert response.status_code == 200
    assert response.json()["skipped"] is True
    session.patch.assert_not_called()


def test_sandbox_event_rejected_in_live_mode():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()
    session = Mock()
    body = b'{"event": {"id": "evt_env_1", "type": "INITIAL_PURCHASE", "app_user_id": "user-1", "environment": "SANDBOX"}}'
    with (
        patch.dict(os.environ, _base_env(REVENUECAT_BILLING_MODE="live"), clear=True),
        patch("modules.revenuecat_webhook.requests.patch", session.patch),
    ):
        response = client.post(
            "/revenuecat/webhook",
            content=body,
            headers={"Authorization": "whtoken-x"},
        )
    assert response.status_code == 200
    assert response.json()["skipped"] is True
    session.patch.assert_not_called()


def test_initial_purchase_grants_premium_via_current_entitlement_lookup():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()
    patch_session = Mock()
    patch_session.patch.return_value = _fake_response(204)
    get_session = Mock()
    get_session.get.return_value = _fake_response(200, {"items": [{"lookup_key": "premium", "id": "entl1"}]})
    body = b'{"event": {"id": "evt_grant_1", "type": "INITIAL_PURCHASE", "app_user_id": "user-1", "environment": "SANDBOX", "event_timestamp_ms": 1700000000000}}'
    with (
        patch.dict(os.environ, _base_env(), clear=True),
        patch("modules.revenuecat_webhook.requests.patch", patch_session.patch),
        patch("modules.revenuecat_billing.requests.get", get_session.get),
    ):
        response = client.post(
            "/revenuecat/webhook",
            content=body,
            headers={"Authorization": "whtoken-x"},
        )
    assert response.status_code == 200
    body_json = response.json()
    assert body_json["entitlement"] == "premium"
    assert patch_session.patch.call_count == 1
    sent_payload = patch_session.patch.call_args.kwargs["json"]
    assert sent_payload["entitlement"] == "premium"
    assert sent_payload["revenuecat_event_id"] == "evt_grant_1"


def test_expiration_revokes_premium_when_no_active_entitlement():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()
    patch_session = Mock()
    patch_session.patch.return_value = _fake_response(204)
    get_session = Mock()
    get_session.get.return_value = _fake_response(200, {"items": []})
    body = b'{"event": {"id": "evt_expire_1", "type": "EXPIRATION", "app_user_id": "user-1", "environment": "SANDBOX"}}'
    with (
        patch.dict(os.environ, _base_env(), clear=True),
        patch("modules.revenuecat_webhook.requests.patch", patch_session.patch),
        patch("modules.revenuecat_billing.requests.get", get_session.get),
    ):
        response = client.post(
            "/revenuecat/webhook",
            content=body,
            headers={"Authorization": "whtoken-x"},
        )
    assert response.status_code == 200
    assert response.json()["entitlement"] == "free"


def test_duplicate_event_id_skips_second_supabase_patch():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()
    patch_session = Mock()
    patch_session.patch.return_value = _fake_response(204)
    get_session = Mock()
    get_session.get.return_value = _fake_response(200, {"items": [{"lookup_key": "premium"}]})
    body = b'{"event": {"id": "evt_dup_1", "type": "RENEWAL", "app_user_id": "user-1", "environment": "SANDBOX"}}'
    with (
        patch.dict(os.environ, _base_env(), clear=True),
        patch("modules.revenuecat_webhook.requests.patch", patch_session.patch),
        patch("modules.revenuecat_billing.requests.get", get_session.get),
    ):
        first = client.post("/revenuecat/webhook", content=body, headers={"Authorization": "whtoken-x"})
        second = client.post("/revenuecat/webhook", content=body, headers={"Authorization": "whtoken-x"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json().get("skipped") is True
    assert patch_session.patch.call_count == 1


def test_missing_app_user_id_is_skipped_not_errored():
    from modules import revenuecat_webhook

    revenuecat_webhook.clear_processed_event_ids_for_tests()
    client = _client()
    session = Mock()
    body = b'{"event": {"id": "evt_no_user", "type": "INITIAL_PURCHASE", "app_user_id": "", "environment": "SANDBOX"}}'
    with (
        patch.dict(os.environ, _base_env(), clear=True),
        patch("modules.revenuecat_webhook.requests.patch", session.patch),
    ):
        response = client.post(
            "/revenuecat/webhook",
            content=body,
            headers={"Authorization": "whtoken-x"},
        )
    assert response.status_code == 200
    assert response.json()["skipped"] is True
    session.patch.assert_not_called()
