"""Auth error paths (docs/audits/2026-11-auth-offline-error-paths.md). GoTrue is mocked; nothing touches Supabase."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from modules import auth_supabase, experimental_graduation as eg
from services import mobile_api_service as api

CONFIG = {"enabled": True, "url": "https://x.supabase.co", "anon_key": "k"}
HEADERS = {"Authorization": "Bearer tok"}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    auth_supabase.clear_auth_user_cache()
    monkeypatch.setattr(api.auth_supabase, "get_supabase_config", lambda *a, **k: CONFIG)
    yield
    auth_supabase.clear_auth_user_cache()


def _resp(status, payload=None, raises=False):
    r = Mock()
    r.status_code = status
    if raises:
        r.json.side_effect = ValueError("not json")
    else:
        r.json.return_value = payload if payload is not None else {}
    return r


def _get_me(gotrue):
    if isinstance(gotrue, Exception):
        patcher = patch.object(auth_supabase.requests, "get", side_effect=gotrue)
    else:
        patcher = patch.object(auth_supabase.requests, "get", return_value=gotrue)
    with patcher:
        return TestClient(api.app).get("/v1/me", headers=HEADERS)


def test_flag_registered_with_owner():
    row = eg.FLAG_REGISTRY["DYNASTYGM_AUTH_PROVIDER_TYPED_ERRORS_V1"]
    assert row["owner"] == "Zach" and row["default"] == "on"


def test_gotrue_unreachable_is_retryable_503_not_401():
    res = _get_me(requests.ConnectionError("boom"))
    assert res.status_code == 503
    body = res.json()
    assert body["code"] == "auth_unavailable" and body["retryable"] is True
    assert res.headers["Retry-After"] == "5"
    assert "sign-in" in body["error"]


def test_gotrue_timeout_is_503():
    assert _get_me(requests.Timeout("slow")).status_code == 503


def test_gotrue_5xx_is_503():
    assert _get_me(_resp(502, {"msg": "bad gateway"})).status_code == 503


def test_gotrue_rate_limit_is_503_with_longer_wait():
    res = _get_me(_resp(429, {"msg": "too many"}))
    assert res.status_code == 503 and res.headers["Retry-After"] == "30"


def test_gotrue_html_body_is_503():
    assert _get_me(_resp(200, raises=True)).status_code == 503


def test_rejected_token_is_401_session_invalid():
    res = _get_me(_resp(401, {"msg": "invalid JWT: token is expired"}))
    assert res.status_code == 401
    assert res.json()["code"] == "session_invalid"
    assert "Retry-After" not in res.headers


def test_deleted_user_is_401_session_invalid():
    res = _get_me(_resp(403, {"msg": "User from sub claim in JWT does not exist", "error_code": "user_not_found"}))
    assert res.status_code == 401 and res.json()["code"] == "session_invalid"


def test_missing_header_stays_401():
    assert TestClient(api.app).get("/v1/me").status_code == 401


def test_outage_is_not_cached_so_recovery_is_immediate():
    # ``auth_supabase.requests`` is the process-global ``requests`` module, so patching ``get`` also
    # intercepts any other thread's HTTP call (leaked background threads from earlier tests under
    # xdist).  Only GoTrue calls may consume the scripted sequence; everything else fails on its own.
    seq = [requests.ConnectionError("x"), _resp(200, {"id": "u1", "email": "a@b.c"})]

    def gotrue_only(url, *args, **kwargs):
        if "/auth/v1/user" not in str(url):
            raise requests.ConnectionError("unrelated call")
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    with patch.object(auth_supabase.requests, "get", side_effect=gotrue_only), patch.object(
        api, "_fetch_profile_fields", return_value={"entitlement": "free", "sleeper_username": "", "status": "ok"}
    ):
        c = TestClient(api.app)
        assert c.get("/v1/me", headers=HEADERS).status_code == 503
        assert c.get("/v1/me", headers=HEADERS).status_code == 200


def test_kill_switch_restores_legacy_401(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_AUTH_PROVIDER_TYPED_ERRORS_V1", "off")
    res = _get_me(requests.ConnectionError("boom"))
    assert res.status_code == 401 and "code" not in res.json()


def test_unhandled_error_is_json_not_html():
    with patch.object(api, "_fetch_profile_fields", side_effect=RuntimeError("x")), patch.object(
        auth_supabase.requests, "get", return_value=_resp(200, {"id": "u1"})
    ):
        res = TestClient(api.app, raise_server_exceptions=False).get("/v1/me", headers=HEADERS)
    assert res.status_code == 500 and res.headers["content-type"].startswith("application/json")
    assert res.json()["ok"] is False
