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


def test_prune_is_throttled_once_bucket_count_stays_over_the_cap(monkeypatch):
    """Regression test for a lock-contention bug: once `_buckets` stays
    above `_RATE_LIMIT_MAX_TRACKED_KEYS` with all-current-window (non-stale)
    keys, `_prune` can't remove anything, so the old code re-ran a full
    O(len(_buckets)) dict scan — while holding the limiter's lock — on
    EVERY subsequent `hit()` call, serializing every request in the process
    on that scan. The fix caps actual prune attempts to at most one per
    `_PRUNE_MIN_INTERVAL_SECONDS`, regardless of call volume."""

    pytest.importorskip("httpx")
    from services import mobile_api_service

    limiter = mobile_api_service._InMemoryFixedWindowRateLimiter()
    cap = mobile_api_service._RATE_LIMIT_MAX_TRACKED_KEYS

    # Seed the limiter past the cap with distinct, all-current-window keys
    # (nothing stale to collect) — the exact scenario where the old code
    # would scan on every single call and never shrink.
    for i in range(cap + 10):
        limiter.hit(f"client-{i}", limit=1_000_000, window_seconds=60)

    prune_calls = []
    original_prune = limiter._prune

    def _counting_prune(now, window_seconds):
        prune_calls.append(now)
        return original_prune(now, window_seconds)

    monkeypatch.setattr(limiter, "_prune", _counting_prune)

    # Many more hits in rapid succession, still over the cap and still
    # within the cooldown window — must not re-scan every time.
    for i in range(200):
        limiter.hit(f"client-extra-{i}", limit=1_000_000, window_seconds=60)

    assert len(prune_calls) <= 1

    # After the cooldown elapses, a prune attempt is allowed again.
    limiter._last_prune_at -= mobile_api_service._InMemoryFixedWindowRateLimiter._PRUNE_MIN_INTERVAL_SECONDS + 1
    limiter.hit("client-after-cooldown", limit=1_000_000, window_seconds=60)
    assert len(prune_calls) >= 1
