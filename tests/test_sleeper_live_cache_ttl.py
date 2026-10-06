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
    sleeper._get_traded_picks_cached.cache_clear()
    sleeper._get_transactions_cached.cache_clear()
    sleeper._get_matchups_cached.cache_clear()


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


def test_get_traded_picks_expires_on_bucket_advance():
    _clear_all()
    stale = Mock(status_code=200)
    stale.json.return_value = []
    fresh = Mock(status_code=200)
    fresh.json.return_value = [{"season": "2027", "round": 1, "owner_id": "2"}]
    with patch("requests.get", side_effect=[stale, fresh]) as mock_get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=1):
            first = sleeper.get_traded_picks("L1")
        with patch("modules.sleeper._live_league_cache_bucket", return_value=2):
            second = sleeper.get_traded_picks("L1")
    assert first == []
    assert len(second) == 1
    assert mock_get.call_count == 2


def test_get_transactions_expires_on_bucket_advance():
    _clear_all()
    stale = Mock(status_code=200)
    stale.json.return_value = []
    fresh = Mock(status_code=200)
    fresh.json.return_value = [{"type": "waiver", "status": "complete"}]
    with patch("requests.get", side_effect=[stale, fresh]) as mock_get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=1):
            first = sleeper.get_transactions("L1", 3)
        with patch("modules.sleeper._live_league_cache_bucket", return_value=2):
            second = sleeper.get_transactions("L1", 3)
    assert first == []
    assert len(second) == 1
    assert mock_get.call_count == 2


def test_get_matchups_expires_on_bucket_advance():
    _clear_all()
    stale = Mock(status_code=200)
    stale.json.return_value = [{"roster_id": 1, "points": 90.0}]
    fresh = Mock(status_code=200)
    fresh.json.return_value = [{"roster_id": 1, "points": 112.4}]
    with patch("requests.get", side_effect=[stale, fresh]) as mock_get:
        with patch("modules.sleeper._live_league_cache_bucket", return_value=1):
            first = sleeper.get_matchups("L1", 3)
        with patch("modules.sleeper._live_league_cache_bucket", return_value=2):
            second = sleeper.get_matchups("L1", 3)
    assert first[0]["points"] == 90.0
    assert second[0]["points"] == 112.4
    assert mock_get.call_count == 2


def test_clear_live_league_endpoint_caches_does_not_raise():
    _clear_all()
    # This is the same call the web app makes on Game Plan TTL/manual
    # refresh — must keep working now that get_league/get_rosters/get_users
    # are plain wrappers, not lru_cache objects themselves.
    sleeper.clear_live_league_endpoint_caches()


class TestSleeperTrendingPlayers:
    """modules.sleeper's Sleeper trending-add/drop client: real endpoint,

    GLOBAL (cross-league) scope, its own cache bucket separate from the
    per-league live-endpoint TTL above.
    """

    def test_get_trending_players_hits_the_real_sleeper_trending_endpoint(self):
        sleeper.clear_trending_player_caches()
        response = Mock(status_code=200)
        response.json.return_value = [{"player_id": "1001", "count": 500}]
        with patch("requests.get", return_value=response) as mock_get:
            with patch("modules.sleeper._trending_cache_bucket", return_value=1):
                rows = sleeper.get_trending_players("add", lookback_hours=24, limit=50)
        assert rows == [{"player_id": "1001", "count": 500}]
        called_url = mock_get.call_args[0][0]
        assert "players/nfl/trending/add" in called_url
        assert "lookback_hours=24" in called_url
        assert "limit=50" in called_url

    def test_get_trending_players_defaults_an_unknown_type_to_add(self):
        sleeper.clear_trending_player_caches()
        response = Mock(status_code=200)
        response.json.return_value = []
        with patch("requests.get", return_value=response) as mock_get:
            with patch("modules.sleeper._trending_cache_bucket", return_value=2):
                sleeper.get_trending_players("bogus")
        assert "trending/add" in mock_get.call_args[0][0]

    def test_get_trending_players_hits_cache_within_the_same_ttl_bucket(self):
        sleeper.clear_trending_player_caches()
        response = Mock(status_code=200)
        response.json.return_value = [{"player_id": "1001", "count": 500}]
        with patch("requests.get", return_value=response) as mock_get:
            with patch("modules.sleeper._trending_cache_bucket", return_value=7):
                first = sleeper.get_trending_players("add")
                second = sleeper.get_trending_players("add")
        assert first == second
        assert mock_get.call_count == 1

    def test_get_trending_players_refetches_once_the_ttl_bucket_advances(self):
        sleeper.clear_trending_player_caches()
        stale = Mock(status_code=200)
        stale.json.return_value = [{"player_id": "1001", "count": 500}]
        fresh = Mock(status_code=200)
        fresh.json.return_value = [{"player_id": "1001", "count": 900}]
        with patch("requests.get", side_effect=[stale, fresh]) as mock_get:
            with patch("modules.sleeper._trending_cache_bucket", return_value=1):
                first = sleeper.get_trending_players("add")
            with patch("modules.sleeper._trending_cache_bucket", return_value=2):
                second = sleeper.get_trending_players("add")
        assert first[0]["count"] == 500
        assert second[0]["count"] == 900
        assert mock_get.call_count == 2

    def test_get_trending_players_fails_neutral_on_bad_status(self):
        sleeper.clear_trending_player_caches()
        response = Mock(status_code=500)
        with patch("requests.get", return_value=response):
            with patch("modules.sleeper._trending_cache_bucket", return_value=3):
                rows = sleeper.get_trending_players("add")
        assert rows == []

    def test_trending_add_rank_map_builds_count_and_1_indexed_rank(self):
        sleeper.clear_trending_player_caches()
        response = Mock(status_code=200)
        response.json.return_value = [
            {"player_id": "1001", "count": 500},
            {"player_id": "1002", "count": 300},
        ]
        with patch("requests.get", return_value=response):
            with patch("modules.sleeper._trending_cache_bucket", return_value=4):
                mapping = sleeper.trending_add_rank_map()
        assert mapping["1001"] == {"count": 500, "rank": 1}
        assert mapping["1002"] == {"count": 300, "rank": 2}

    def test_trending_add_rank_map_empty_on_provider_failure(self):
        sleeper.clear_trending_player_caches()
        with patch("requests.get", side_effect=Exception("boom")):
            with patch("modules.sleeper._trending_cache_bucket", return_value=5):
                assert sleeper.trending_add_rank_map() == {}
