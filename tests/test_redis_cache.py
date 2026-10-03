"""modules/redis_cache.py — the shared Redis client + distributed
single-flight cache helper behind services/mobile_api_service.py's rate
limiter and the three per-module single-flight caches (trade_hub_engine,
league_rankings x2, playoff_simulator).

tests/conftest.py's autouse `_fake_redis_for_tests` fixture already points
modules.redis_cache at a fresh fakeredis instance for every test in this
suite; these tests exercise the helper directly rather than through one of
its three call sites (those have their own dedicated single-flight tests
in test_trade_hub_engine.py/test_league_rankings.py/test_playoff_simulator.py).
"""

from __future__ import annotations

import threading

from modules import redis_cache


def test_second_call_for_the_same_key_hits_the_cache_without_recomputing():
    calls = []

    def _compute():
        calls.append(1)
        return {"n": len(calls)}

    first = redis_cache.redis_single_flight_cache(cache_key="k1", ttl_seconds=30, compute=_compute)
    second = redis_cache.redis_single_flight_cache(cache_key="k1", ttl_seconds=30, compute=_compute)

    assert len(calls) == 1
    assert first == second == {"n": 1}


def test_different_keys_each_compute_independently():
    calls = []

    def _compute():
        calls.append(1)
        return len(calls)

    first = redis_cache.redis_single_flight_cache(cache_key="a", ttl_seconds=30, compute=_compute)
    second = redis_cache.redis_single_flight_cache(cache_key="b", ttl_seconds=30, compute=_compute)

    assert len(calls) == 2
    assert first == 1
    assert second == 2


def test_concurrent_misses_for_the_same_key_collapse_to_one_real_computation():
    """The core distributed single-flight guarantee: N threads that all
    miss the same key before the first finishes must still only trigger
    one real `compute()` call — every other caller gets the first caller's
    result instead of redoing the work."""

    import time

    call_count = 0
    call_count_lock = threading.Lock()

    def _slow_compute():
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        time.sleep(0.2)
        return {"ok": True}

    results: list[dict] = []
    results_lock = threading.Lock()

    def _call():
        result = redis_cache.redis_single_flight_cache(
            cache_key="concurrent-key", ttl_seconds=30, compute=_slow_compute
        )
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert call_count == 1, "concurrent misses for the same key must single-flight to one real computation"
    assert len(results) == 8
    assert all(r == {"ok": True} for r in results)


def test_corrupt_cached_entry_is_recomputed_not_raised():
    client = redis_cache.get_redis_client()
    client.set("corrupt-key", b"not a valid pickle stream", ex=30)

    result = redis_cache.redis_single_flight_cache(
        cache_key="corrupt-key", ttl_seconds=30, compute=lambda: "recomputed"
    )
    assert result == "recomputed"


class _BrokenRedisClient:
    """Every method raises, simulating Redis being completely unreachable
    (connection refused/timeout) -- used to exercise the fail-open paths."""

    def get(self, *_args, **_kwargs):
        raise redis_cache.RedisError("connection refused")

    def set(self, *_args, **_kwargs):
        raise redis_cache.RedisError("connection refused")

    def incr(self, *_args, **_kwargs):
        raise redis_cache.RedisError("connection refused")

    def expire(self, *_args, **_kwargs):
        raise redis_cache.RedisError("connection refused")

    def pipeline(self, *_args, **_kwargs):
        raise redis_cache.RedisError("connection refused")


def test_redis_unreachable_fails_open_to_uncached_compute(monkeypatch):
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: _BrokenRedisClient())

    calls = []

    def _compute():
        calls.append(1)
        return "fine"

    # Must not raise -- a Redis outage degrades to "every caller computes
    # its own uncached answer," never a request failure.
    result = redis_cache.redis_single_flight_cache(cache_key="x", ttl_seconds=30, compute=_compute)
    assert result == "fine"
    assert len(calls) == 1

    # A second call also just recomputes (no crash, no stuck state).
    result2 = redis_cache.redis_single_flight_cache(cache_key="x", ttl_seconds=30, compute=_compute)
    assert result2 == "fine"
    assert len(calls) == 2


def test_build_cache_key_is_stable_and_distinguishes_different_parts():
    key_a = redis_cache.build_cache_key("ns", "league-1", "Dynasty", 30)
    key_b = redis_cache.build_cache_key("ns", "league-1", "Dynasty", 30)
    key_c = redis_cache.build_cache_key("ns", "league-2", "Dynasty", 30)

    assert key_a == key_b
    assert key_a != key_c
    assert key_a.startswith("ns:")


def test_set_redis_client_for_testing_overrides_env_derived_client(monkeypatch):
    """A test override must win even if REDIS_URL also changes afterward --
    otherwise get_redis_client()'s own "rebind if the URL changed" logic
    (for real deployments) would clobber the test's injected fake client."""

    monkeypatch.setenv("REDIS_URL", "redis://unused-host-for-this-test:6379/0")
    import fakeredis

    fake = fakeredis.FakeRedis(server=fakeredis.FakeServer())
    redis_cache.set_redis_client_for_testing(fake)
    assert redis_cache.get_redis_client() is fake

    monkeypatch.setenv("REDIS_URL", "redis://still-unused:6379/0")
    assert redis_cache.get_redis_client() is fake
