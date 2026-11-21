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


def _start_of_fresh_window(*window_seconds: int, margin: float = 3.0) -> None:
    """The limiter counts in FIXED wall-clock windows (floor(now / window)). A test that fires a handful of requests
    and expects the Nth to be limited would see the counter reset (and the 429 turn into a 401/200) whenever a window
    boundary falls between its requests: a ~1-in-several-hundred flake that shows up on unrelated PRs. Wait out the
    last `margin` seconds of the current window (at most `margin` seconds, only when we are that close) so the whole
    test runs inside one window."""
    for window in window_seconds:
        remaining = window - (time.time() % window)
        if remaining < margin:
            time.sleep(remaining + 0.05)


def _force_rate_limiting(monkeypatch, mobile_api_service, **overrides):
    _start_of_fresh_window(*(int(v) for k, v in overrides.items() if k.endswith("_WINDOW_SECONDS")))
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


def test_analytics_ingest_has_its_own_budget_and_spares_mutating_tier(monkeypatch):
    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_MUTATING_MAX=2,
        RATE_LIMIT_ANALYTICS_MAX=5,
    )
    body = {"event": "page_view", "anon_id": "anon_x", "props": {"route": "/x"}}
    for _ in range(5):
        assert client.post("/v1/analytics/event", json=body).status_code == 200
    assert client.post("/v1/analytics/event", json=body).status_code == 429
    # analytics traffic never consumed the mutating budget
    other = client.post("/v1/preferences", json={})
    assert other.status_code != 429


def test_analytics_alias_path_shares_the_analytics_budget(monkeypatch):
    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_MUTATING_MAX=2,
        RATE_LIMIT_ANALYTICS_MAX=4,
    )
    body = {"event": "page_view", "anon_id": "anon_x", "props": {"route": "/x"}}
    for path in ("/v1/e", "/v1/analytics/event", "/v1/e", "/v1/analytics/event"):
        assert client.post(path, json=body).status_code == 200
    assert client.post("/v1/e", json=body).status_code == 429
    assert client.post("/v1/analytics/event", json=body).status_code == 429


def test_rotating_the_authorization_header_does_not_mint_a_fresh_budget(monkeypatch):
    """The identity bucket is keyed on a hash of the Authorization header, so a caller sending a new bogus bearer token
    per request used to get a new bucket every time. The per-IP ceiling (multiplier x the identity limit) closes that."""
    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_GENERAL_MAX=2,
        RATE_LIMIT_GENERAL_WINDOW_SECONDS=60,
        RATE_LIMIT_IP_CEILING_MULTIPLIER=3,
    )

    # Ceiling is 2 * 3 = 6 per window for this IP, regardless of how many distinct tokens are presented.
    for i in range(6):
        response = client.get("/health", headers={"Authorization": f"Bearer bogus-{i}"})
        assert response.status_code == 200

    limited = client.get("/health", headers={"Authorization": "Bearer bogus-new"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_distinct_ips_keep_independent_ip_ceilings(monkeypatch):
    client, mobile_api_service = _client(monkeypatch)
    _force_rate_limiting(
        monkeypatch,
        mobile_api_service,
        RATE_LIMIT_GENERAL_MAX=1,
        RATE_LIMIT_GENERAL_WINDOW_SECONDS=60,
        RATE_LIMIT_IP_CEILING_MULTIPLIER=2,
    )

    for i in range(2):
        assert client.get("/health", headers={"Authorization": f"Bearer t{i}", "X-Forwarded-For": "203.0.113.1"}).status_code == 200
    assert client.get("/health", headers={"Authorization": "Bearer t9", "X-Forwarded-For": "203.0.113.1"}).status_code == 429
    assert client.get("/health", headers={"Authorization": "Bearer t9", "X-Forwarded-For": "203.0.113.2"}).status_code == 200


def test_fail_open_log_does_not_contain_the_client_ip(monkeypatch, caplog):
    import logging

    from modules import redis_cache

    _client(monkeypatch)
    from services import mobile_api_service

    class _Boom:
        def incr(self, *_a, **_k):
            raise redis_cache.RedisError("down")

    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: _Boom())
    with caplog.at_level(logging.WARNING):
        allowed, _ = mobile_api_service._rate_limiter.hit("general|198.51.100.7:abcd", 5, 60)
    assert allowed is True
    assert "198.51.100.7" not in caplog.text


def test_client_ip_uses_rightmost_trusted_hop_not_client_supplied_first(monkeypatch):
    _client(monkeypatch)
    from services import mobile_api_service as svc

    class _Req:
        def __init__(self, xff):
            self.headers = {"x-forwarded-for": xff}
            self.client = None

    monkeypatch.setattr(svc, "TRUSTED_PROXY_COUNT", 1)
    assert svc._client_ip(_Req("6.6.6.6, 203.0.113.9")) == "203.0.113.9"
    monkeypatch.setattr(svc, "TRUSTED_PROXY_COUNT", 2)
    assert svc._client_ip(_Req("6.6.6.6, 203.0.113.9, 10.0.0.1")) == "203.0.113.9"
    monkeypatch.setattr(svc, "TRUSTED_PROXY_COUNT", 0)
    assert svc._client_ip(_Req("6.6.6.6")) == "unknown"


def test_health_hides_deploy_time_keeps_build(monkeypatch):
    client, _svc = _client(monkeypatch)
    monkeypatch.setenv("DYNASTYGM_DEPLOYED_AT", "2026-11-01T00:00:00Z")
    body = client.get("/health").json()
    assert "deployed_at" not in body
    assert "build" in body


def test_analytics_hash_uses_env_salt_with_fallback(monkeypatch):
    from modules import launch_analytics as la

    monkeypatch.delenv("ANALYTICS_HASH_SALT", raising=False)
    legacy = la.hash_account_id("user-1")
    monkeypatch.setenv("ANALYTICS_HASH_SALT", "s3cret")
    salted = la.hash_account_id("user-1")
    assert salted != legacy and salted.startswith("acct_")
