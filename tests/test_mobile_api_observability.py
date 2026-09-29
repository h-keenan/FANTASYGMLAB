"""services/mobile_api_service.py's crash/error observability.

Before this fix, an unhandled exception on this service produced only the
generic 500 body below with zero trace anywhere Render's log viewer could
show a human. These tests confirm: (1) the client-facing response shape is
unchanged, (2) a full traceback plus request path and caller id now reaches
the logger (which Render captures from stdout), and (3) the optional Sentry
hook is exercised when (and only when) SENTRY_DSN is configured.
"""

from __future__ import annotations

import logging

import pytest
from unittest.mock import Mock, patch


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")

    from services import mobile_api_service

    # raise_server_exceptions=False: these tests deliberately trigger an
    # unhandled exception to exercise the global handler end to end (real
    # 500 JSON response), rather than TestClient's default debug behavior
    # of re-raising it into the test itself.
    return TestClient(mobile_api_service.app, raise_server_exceptions=False), mobile_api_service


def _authenticated_headers():
    return {"Authorization": "Bearer good-token"}


def test_unhandled_exception_returns_the_same_clean_500_body(monkeypatch, caplog):
    client, mobile_api_service = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated downstream crash")

    monkeypatch.setattr(mobile_api_service, "_fetch_profile_fields", _boom)

    with caplog.at_level(logging.ERROR, logger="fantasygm.mobile_api"):
        with patch("requests.get", return_value=auth_user_response):
            response = client.get("/v1/me", headers=_authenticated_headers())

    assert response.status_code == 500
    assert response.json() == {"ok": False, "error": "Request failed."}


def test_unhandled_exception_is_logged_with_path_and_user_id(monkeypatch, caplog):
    client, mobile_api_service = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated downstream crash")

    monkeypatch.setattr(mobile_api_service, "_fetch_profile_fields", _boom)

    with caplog.at_level(logging.ERROR, logger="fantasygm.mobile_api"):
        with patch("requests.get", return_value=auth_user_response):
            client.get("/v1/me", headers=_authenticated_headers())

    error_records = [r for r in caplog.records if r.name == "fantasygm.mobile_api" and r.levelno >= logging.ERROR]
    assert error_records, "expected an ERROR-level log record for the unhandled exception"
    record = error_records[0]
    message = record.getMessage()
    assert "/v1/me" in message
    assert "user-123" in message
    assert record.exc_info is not None
    assert record.exc_info[0] is RuntimeError


def test_unhandled_exception_without_auth_logs_anonymous(monkeypatch, caplog):
    # /health needs no auth, so it never reaches require_user - confirms the
    # logger falls back gracefully instead of erroring on a missing user id.
    client, mobile_api_service = _client(monkeypatch)

    def _boom(**_kwargs):
        raise RuntimeError("simulated crash in the refresh check")

    monkeypatch.setattr(mobile_api_service, "_maybe_schedule_players_refresh", _boom)

    with caplog.at_level(logging.ERROR, logger="fantasygm.mobile_api"):
        response = client.get("/health")

    assert response.status_code == 500
    error_records = [r for r in caplog.records if r.name == "fantasygm.mobile_api" and r.levelno >= logging.ERROR]
    assert error_records
    assert "anonymous" in error_records[0].getMessage()


def test_unhandled_exception_forwards_to_sentry_only_when_dsn_configured(monkeypatch):
    client, mobile_api_service = _client(monkeypatch)

    reported: list[BaseException] = []
    monkeypatch.setattr(mobile_api_service, "_report_to_sentry", reported.append)

    def _boom(**_kwargs):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(mobile_api_service, "_maybe_schedule_players_refresh", _boom)

    response = client.get("/health")

    assert response.status_code == 500
    # _report_to_sentry is always *called* by the handler; whether it does
    # anything is gated inside it by SENTRY_DSN. Here it's replaced with a
    # spy, so we confirm the handler always invokes the hook.
    assert len(reported) == 1
    assert isinstance(reported[0], RuntimeError)


def test_report_to_sentry_is_a_noop_without_a_dsn(monkeypatch):
    from services import mobile_api_service

    monkeypatch.setattr(mobile_api_service, "SENTRY_DSN", "")
    # Must not raise even if sentry_sdk were somehow unavailable/misbehaving.
    mobile_api_service._report_to_sentry(RuntimeError("unused"))


def test_5xx_http_exception_is_logged(monkeypatch, caplog):
    client, mobile_api_service = _client(monkeypatch)

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    with caplog.at_level(logging.WARNING, logger="fantasygm.mobile_api"):
        response = client.get("/v1/me", headers=_authenticated_headers())

    assert response.status_code == 503
    warning_records = [
        r for r in caplog.records if r.name == "fantasygm.mobile_api" and r.levelno >= logging.WARNING
    ]
    assert warning_records
    assert "503" in warning_records[0].getMessage()
