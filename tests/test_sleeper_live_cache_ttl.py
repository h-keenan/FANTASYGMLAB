"""modules.sleeper's live-endpoint cache: bounded by a TTL, not forever.

get_league/get_rosters/get_users used to be bare lru_cache — correct for
the web app (which clears them on its own Game Plan TTL/manual refresh),
silently wrong for services/mobile_api_service.py, which never calls that
clear function and runs as its own long-lived process. A league fetched
once there would stay frozen for the rest of that process's uptime. These
tests pin the fix: an automatic time-bucketed expiry.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from modules import sleeper


def _clear_all():
    sleeper._get_league_cached.cache_clear()
    sleeper._get_rosters_cached.cache_clear()
    sleeper._get_users_cached.cache_clear()


def test_get_league_hits_cache_within_the_same_ttl_bucket():
    _clear_all()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"league_id": "L1", "name": "Same Bucket"}
    with patch("requests.get", return_value=response) as mock_get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=42):
            first = sleeper.get_league("L1")
            second = sleeper.get_league("L1")
    assert first == second == {"league_id": "L1", "name": "Same Bucket"}
    assert mock_get.call_count == 1


def test_get_league_refetches_once_the_ttl_bucket_advances():
    _clear_all()
    stale = Mock(status_code=200)
    stale.json.return_value = {"league_id": "L1", "name": "Stale"}
    fresh = Mock(status_code=200)
    fresh.json.return_value = {"league_id": "L1", "name": "Fresh"}
    with patch("requests.get", side_effect=[stale, fresh]) as mock_get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=1):
            first = sleeper.get_league("L1")
        with patch("modules.sleeper._live_league_cache_bucket", return_value=2):
            second = sleeper.get_league("L1")
    assert first["name"] == "Stale"
    assert second["name"] == "Fresh"
    assert mock_get.call_count == 2


def test_get_rosters_and_get_users_also_expire_on_bucket_advance():
    _clear_all()
    stale = Mock(status_code=200)
    stale.json.return_value = [{"roster_id": 1}]
    fresh = Mock(status_code=200)
    fresh.json.return_value = [{"roster_id": 1}, {"roster_id": 2}]
    with patch("requests.get", side_effect=[stale, fresh]):
        with patch("modules.sleeper._live_league_cache_bucket", return_value=1):
            first = sleeper.get_rosters("L1")
        with patch("modules.sleeper._live_league_cache_bucket", return_value=2):
            second = sleeper.get_rosters("L1")
    assert len(first) == 1
    assert len(second) == 2


def test_clear_live_league_endpoint_caches_does_not_raise():
    _clear_all()
    # This is the same call the web app makes on Game Plan TTL/manual
    # refresh — must keep working now that get_league/get_rosters/get_users
    # are plain wrappers, not lru_cache objects themselves.
    sleeper.clear_live_league_endpoint_caches()
