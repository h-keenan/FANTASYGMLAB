"""modules.sleeper_cache: cluster-wide single-flight + stale-while-error."""

from __future__ import annotations

import threading
import time
from unittest.mock import Mock, patch

from modules import redis_cache, sleeper, sleeper_budget, sleeper_cache

URL = "https://api.sleeper.app/v1/league/L1/rosters"


def _ok(payload):
    r = Mock(status_code=200)
    r.json.return_value = payload
    return r


def _fetch():
    return sleeper._request_json("sleeper_league_rosters", URL, timeout=5, max_retries=0)


def _shared(ttl=30):
    return sleeper_cache.shared_json(URL, ttl=ttl, fetch=_fetch)


def test_second_call_within_ttl_does_not_hit_upstream():
    with patch("requests.get", return_value=_ok([{"roster_id": 1}])) as g:
        a = _shared()
        b = _shared()
    assert a == b == [{"roster_id": 1}]
    assert g.call_count == 1


def test_empty_payload_is_cached_not_treated_as_failure():
    with patch("requests.get", return_value=_ok([])) as g:
        _shared()
        assert _shared() == []
    assert g.call_count == 1


def test_another_worker_with_no_local_copy_reads_redis():
    with patch("requests.get", return_value=_ok({"a": 1})) as g:
        _shared()
        with sleeper_cache._lock:
            sleeper_cache._local.clear()  # a different worker process
        assert _shared() == {"a": 1}
    assert g.call_count == 1


def test_concurrent_cold_callers_coalesce_to_one_upstream_call():
    calls = []

    def slow_get(*a, **k):
        calls.append(1)
        time.sleep(0.2)
        return _ok([{"roster_id": 1}])

    results = []
    with patch("requests.get", side_effect=slow_get):
        threads = [threading.Thread(target=lambda: results.append(_shared())) for _ in range(12)]
        [t.start() for t in threads]
        [t.join() for t in threads]
    assert len(calls) == 1
    assert results == [[{"roster_id": 1}]] * 12


def test_follower_waits_on_redis_lock_instead_of_fetching():
    key = sleeper_cache.cache_key(URL)
    client = redis_cache.get_redis_client()
    client.set("lock:" + key, b"other-worker", px=5000)  # another worker leads
    calls = []

    def publish_later():
        time.sleep(0.15)
        sleeper_cache._put_entry(key, ["from-leader"], time.time())

    t = threading.Thread(target=publish_later)
    with patch("requests.get", side_effect=lambda *a, **k: calls.append(1) or _ok(["mine"])):
        t.start()
        got = _shared()
        t.join()
    assert got == ["from-leader"]
    assert calls == []


def test_stale_while_error_serves_last_real_payload_and_marks_stale():
    with patch("requests.get", return_value=_ok(["fresh"])):
        _shared(ttl=0.01)
    time.sleep(0.05)
    sleeper_budget.begin_request()
    with patch("requests.get", return_value=Mock(status_code=429)):
        got = _shared(ttl=0.01)
    assert got == ["fresh"]
    assert sleeper_budget.stale_as_of() is not None
    assert sleeper_cache.snapshot()["stale"] == 1


def test_stale_payload_is_never_rewritten_as_fresh():
    with patch("requests.get", return_value=_ok(["fresh"])):
        _shared(ttl=0.01)
    ts0 = sleeper_cache._get_entry(sleeper_cache.cache_key(URL))[1]
    time.sleep(0.05)
    with patch("requests.get", return_value=Mock(status_code=503)):
        _shared(ttl=0.01)
    assert sleeper_cache._get_entry(sleeper_cache.cache_key(URL))[1] == ts0


def test_failure_with_nothing_cached_returns_none_and_negative_caches():
    with patch("requests.get", return_value=Mock(status_code=429)) as g:
        assert _shared() is None
        n = g.call_count
        assert _shared() is None
        assert g.call_count == n


def test_redis_outage_fails_open_to_local_store():
    class Dead:
        def __getattr__(self, name):
            raise redis_cache.RedisError("down")

    redis_cache.set_redis_client_for_testing(Dead())
    with patch("requests.get", return_value=_ok(["v"])) as g:
        assert _shared() == ["v"]
        assert _shared() == ["v"]
    assert g.call_count == 1


def test_explicit_refresh_forces_a_refetch():
    with patch("requests.get", return_value=_ok(["old"])):
        _shared()
    time.sleep(0.01)
    sleeper_cache.clear_local()
    with patch("requests.get", return_value=_ok(["new"])) as g:
        assert _shared() == ["new"]
    assert g.call_count == 1


def test_get_rosters_uses_shared_cache_across_lru_clears():
    sleeper._get_rosters_cached.cache_clear()
    with patch("requests.get", return_value=_ok([{"roster_id": 9}])) as g:
        sleeper.get_rosters("LZ")
        sleeper._get_rosters_cached.cache_clear()  # as a fresh worker would
        assert sleeper.get_rosters("LZ") == [{"roster_id": 9}]
    assert g.call_count == 1
