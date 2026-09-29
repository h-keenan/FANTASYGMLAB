"""services/mobile_api_service.py's in-memory rate limiting middleware.

Before this fix, one client could hammer any endpoint with no limit at all.
These tests force the limiter on (it is disabled by default under pytest —
see _RateLimitMiddleware.dispatch — so the hundreds of other tests sharing
this one process/module never collide on the same in-memory buckets) and
confirm it actually triggers under repeated requests, returns a clean 429
(not a raw exception), and tracks the tighter mutating-endpoint tier
separately from the generous general-GET tier.
"""

from __future__ import annotations

import pytest


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")

    from services import mobile_api_service

    return TestClient(mobile_api_service.app), mobile_api_service


def _force_rate_limiting(monkeypatch, mobile_api_service, **overrides):
    monkeypatch.setenv("DYNASTYGM_FORCE_RATE_LIMIT", "1")
    monkeypatch.setattr(mobile_api_service, "RATE_LIMIT_ENABLED", True)
    for key, value in overrides.items():
        monkeypatch.setattr(mobile_api_service, key, value)
    mobile_api_service._rate_limiter.reset()


def test_repeated_get_requests_eventually_return_a_clean_429(monkeypatch):
    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_GENERAL_MAX=3,
        RATE_LIMIT_GENERAL_WINDOW_SECONDS=60,
    )

    for _ in range(3):
        response = client.get("/health")
        assert response.status_code == 200

    limited = client.get("/health")
    assert limited.status_code == 429
    body = limited.json()
    assert body["ok"] is False
    assert "too many requests" in body["error"].casefold()
    assert "Retry-After" in limited.headers


def test_mutating_endpoints_use_their_own_tighter_budget(monkeypatch):
    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_GENERAL_MAX=100,
        RATE_LIMIT_GENERAL_WINDOW_SECONDS=60,
        RATE_LIMIT_MUTATING_MAX=2,
        RATE_LIMIT_MUTATING_WINDOW_SECONDS=60,
    )

    # No auth token: these 401 at the route level, but the rate limiter runs
    # ahead of route/dependency resolution, so they still count against the
    # mutating budget.
    for _ in range(2):
        response = client.post("/v1/push/register", json={"token": "x"})
        assert response.status_code == 401

    limited = client.post("/v1/push/register", json={"token": "x"})
    assert limited.status_code == 429

    # The general (GET) budget is untouched by the mutating-tier hits above.
    assert client.get("/health").status_code == 200


def test_rate_limit_disabled_via_env_never_returns_429(monkeypatch):
    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_ENABLED=False,
        RATE_LIMIT_GENERAL_MAX=1,
        RATE_LIMIT_GENERAL_WINDOW_SECONDS=60,
    )

    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_rate_limiting_is_inert_by_default_under_pytest(monkeypatch):
    """Without the explicit opt-in, the rest of the test suite must never be
    at risk of spurious 429s from sharing this module-level limiter."""

    client, mobile_api_service = _client(monkeypatch)
    monkeypatch.delenv("DYNASTYGM_FORCE_RATE_LIMIT", raising=False)
    monkeypatch.setattr(mobile_api_service, "RATE_LIMIT_GENERAL_MAX", 3)
    mobile_api_service._rate_limiter.reset()

    for _ in range(10):
        assert client.get("/health").status_code == 200
