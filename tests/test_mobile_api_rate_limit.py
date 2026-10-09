"""services/mobile_api_service.py's Redis-backed rate limiting middleware.

Before the original fix, one client could hammer any endpoint with no
limit at all. These tests force the limiter on (it is disabled by default
under pytest — see _RateLimitMiddleware.dispatch — so the hundreds of
other tests sharing this one process/module never collide on the same
counters) and confirm it actually triggers under repeated requests,
returns a clean 429 (not a raw exception), and tracks the tighter
mutating-endpoint tier separately from the generous general-GET tier.

The limiter's backing store moved from an in-memory dict to Redis (see
modules/redis_cache.py) so every mobile-api worker process shares one
counter per client/scope instead of each enforcing its own separate
budget. tests/conftest.py's autouse `_fake_redis_for_tests` fixture points
it at a fresh fakeredis instance for every test here, so these tests
exercise the real Redis-backed code path without a live Redis server.
"""

from __future__ import annotations

import threading
import time

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


def test_hit_fails_open_when_redis_is_unreachable(monkeypatch):
    """The rate limiter is an auxiliary system, not the main request path
    (same philosophy as e.g. Team Situation fetch failures elsewhere in
    this codebase) — a Redis outage must degrade to "requests are allowed,
    unthrottled" rather than ever raising out of hit() and 500ing the
    request.
    """

    pytest.importorskip("httpx")
    from modules import redis_cache
    from services import mobile_api_service

    class _BrokenRedisClient:
        def incr(self, *_args, **_kwargs):
            raise redis_cache.RedisError("connection refused")

        def expire(self, *_args, **_kwargs):
            raise redis_cache.RedisError("connection refused")

    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: _BrokenRedisClient())

    limiter = mobile_api_service._RedisFixedWindowRateLimiter()
    allowed, retry_after = limiter.hit("client-x", limit=1, window_seconds=60)
    assert allowed is True
    assert retry_after == 0.0

    # Repeated hits past what the limit would normally allow still pass —
    # there is no in-memory fallback counter either; Redis down means
    # "not currently rate limited," full stop, until it recovers.
    for _ in range(5):
        allowed, _retry_after = limiter.hit("client-x", limit=1, window_seconds=60)
        assert allowed is True


def test_repeated_get_requests_still_return_a_clean_429_end_to_end_when_redis_is_unreachable_is_not_the_case(
    monkeypatch,
):
    """Sanity companion to the fail-open test above: with Redis actually
    reachable (the default fakeredis fixture), the end-to-end 429 behavior
    asserted earlier in this file is the real, exercised path — this isn't
    accidentally always falling into the fail-open branch."""

    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_GENERAL_MAX=1,
        RATE_LIMIT_GENERAL_WINDOW_SECONDS=60,
    )

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 429


def test_slow_redis_hit_does_not_block_other_concurrent_requests(monkeypatch):
    """Regression test for the event-loop-blocking bug fixed by wrapping
    _rate_limiter.hit() in asyncio.to_thread() inside dispatch(): before the
    fix, hit()'s synchronous redis-py calls ran directly on the worker's
    event loop, so one slow (but not erroring -- the RedisError fail-open
    path only helps once Redis is actually unreachable, not merely slow)
    Redis round-trip stalled every other concurrent request on that worker,
    not just the one being rate limited.

    Plain `TestClient(app)` spins up a brand-new portal (and therefore a
    brand-new event loop in its own thread) for every single request it
    sends, which would make two concurrent requests run on two independent
    event loops regardless of whether dispatch() blocks -- not a faithful
    stand-in for one real uvicorn worker serving concurrent requests on one
    shared loop. Using the client as a context manager (`with TestClient(app)
    as client:`) instead reuses one shared portal/event loop across every
    request made through it (see starlette.testclient.TestClient.__enter__),
    which is what actually exercises this bug: if hit() still blocked that
    loop synchronously, two concurrent requests each paying a simulated 0.3s
    "slow redis" hit would serialize to roughly 0.6s wall clock; offloaded
    via asyncio.to_thread, they run concurrently and the pair completes in
    roughly 0.3s.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")

    from services import mobile_api_service

    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_GENERAL_MAX=1000,
        RATE_LIMIT_GENERAL_WINDOW_SECONDS=60,
    )

    real_hit = mobile_api_service._rate_limiter.hit

    def _slow_hit(key, limit, window_seconds):
        time.sleep(0.3)
        return real_hit(key, limit, window_seconds)

    monkeypatch.setattr(mobile_api_service._rate_limiter, "hit", _slow_hit)

    results: list[int] = []

    with TestClient(mobile_api_service.app) as client:

        def _do_request():
            results.append(client.get("/health").status_code)

        start = time.monotonic()
        threads = [threading.Thread(target=_do_request) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - start

    assert results == [200, 200]
    # Concurrent (offloaded) execution: ~0.3s. Serialized (blocked event
    # loop): ~0.6s. 0.5s comfortably separates the two without being tight
    # enough to flake on normal scheduling jitter.
    assert elapsed < 0.5, (
        f"requests appear to have serialized on the event loop (elapsed={elapsed:.3f}s); "
        "a slow (but reachable) Redis should only delay the request hitting it, not every "
        "other concurrent request on the same worker"
    )
