"""Live Sleeper league getters are shared across workers through Redis.

Each uvicorn worker has its own lru_cache; clearing that cache between two
calls stands in for "a second worker". The second call must read the first
worker's payload from Redis instead of hitting Sleeper again, but only a
genuine live payload may be shared.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from modules import sleeper, sleeper_budget


def _worker_boundary():
    sleeper._get_league_cached.cache_clear()
    sleeper._get_rosters_cached.cache_clear()
    sleeper._get_matchups_cached.cache_clear()


def _ok(payload):
    resp = Mock(status_code=200)
    resp.json.return_value = payload
    return resp


def test_second_worker_reads_the_first_workers_fetch_from_redis():
    _worker_boundary()
    with patch("requests.get", return_value=_ok([{"roster_id": 1}])) as get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=7):
            first = sleeper.get_rosters("L-shared")
            _worker_boundary()
            second = sleeper.get_rosters("L-shared")
    assert first == second == [{"roster_id": 1}]
    assert get.call_count == 1


def test_matchups_are_shared_per_round():
    _worker_boundary()
    with patch("requests.get", return_value=_ok([{"matchup_id": 1}])) as get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=7):
            sleeper.get_matchups("L-m", 3)
            _worker_boundary()
            sleeper.get_matchups("L-m", 3)
            _worker_boundary()
            sleeper.get_matchups("L-m", 4)
    assert get.call_count == 2


def test_new_bucket_refetches():
    _worker_boundary()
    with patch("requests.get", side_effect=[_ok({"name": "a"}), _ok({"name": "b"})]) as get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=1):
            sleeper.get_league("L-b")
        _worker_boundary()
        with patch("modules.sleeper._live_league_cache_bucket", return_value=2):
            assert sleeper.get_league("L-b") == {"name": "b"}
    assert get.call_count == 2


def test_failed_fetch_is_not_shared():
    _worker_boundary()
    bad = Mock(status_code=404)
    with patch("requests.get", side_effect=[bad, _ok({"name": "ok"})]) as get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=9):
            assert sleeper.get_league("L-f") == {}
            _worker_boundary()
            assert sleeper.get_league("L-f") == {"name": "ok"}
    assert get.call_count == 2


def test_stale_last_known_payload_is_not_shared():
    _worker_boundary()
    url = f"{sleeper.SLEEPER_BASE}/league/L-s/rosters"
    sleeper_budget.remember(url, [{"roster_id": "stale"}])
    limited = Mock(status_code=429)
    with patch.object(sleeper, "SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS", 0):
        with patch("modules.sleeper._live_league_cache_bucket", return_value=11):
            with patch("requests.get", return_value=limited):
                assert sleeper.get_rosters("L-s") == [{"roster_id": "stale"}]
            _worker_boundary()
            with patch("requests.get", return_value=_ok([{"roster_id": "fresh"}])) as get:
                assert sleeper.get_rosters("L-s") == [{"roster_id": "fresh"}]
            assert get.call_count == 1


def test_clear_live_league_endpoint_caches_also_drops_the_shared_copy():
    _worker_boundary()
    with patch("requests.get", side_effect=[_ok({"name": "a"}), _ok({"name": "b"})]) as get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=5):
            assert sleeper.get_league("L-c") == {"name": "a"}
            sleeper.clear_live_league_endpoint_caches()
            assert sleeper.get_league("L-c") == {"name": "b"}
    assert get.call_count == 2
