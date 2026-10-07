"""modules.manager_activity: real per-manager transaction-activity count off
Sleeper's own transaction history — pins the aggregation against realistic
raw Sleeper transaction shapes (modules.league_history's normalize input),
using fake fetchers rather than the live Sleeper API or the real players
table (this module never touches players.db at all).
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

from modules import manager_activity


def test_manager_activity_counts_one_per_involved_roster_per_transaction():
    """A trade between rosters 1 and 2 counts once for each side; a waiver
    claim only counts for the roster that made it."""
    trade = {
        "transaction_id": "tx1",
        "type": "trade",
        "status": "complete",
        "status_updated": 1000,
        "roster_ids": [1, 2],
        "adds": {"p1": 1, "p2": 2},
        "drops": {"p2": 1, "p1": 2},
        "draft_picks": [],
    }
    waiver = {
        "transaction_id": "tx2",
        "type": "waiver",
        "status": "complete",
        "status_updated": 2000,
        "roster_ids": [1],
        "adds": {"p3": 1},
        "drops": {},
        "draft_picks": [],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade, waiver] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = manager_activity.manager_activity_counts("L1")

    assert counts == {1: 2, 2: 1}


def test_manager_activity_counts_ignores_incomplete_and_unsupported_types():
    pending = {
        "transaction_id": "tx3",
        "type": "trade",
        "status": "pending",
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
    }
    commish = {
        "transaction_id": "tx4",
        "type": "commissioner",
        "status": "complete",
        "roster_ids": [1],
        "adds": {"p1": 1},
        "drops": {},
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [pending, commish] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = manager_activity.manager_activity_counts("L1")

    assert counts == {}


def test_manager_activity_counts_empty_league_id_short_circuits():
    assert manager_activity.manager_activity_counts("") == {}


def test_manager_activity_counts_cached_matches_uncached_result():
    """The Redis-backed cached front door (manager_activity_counts_cached)
    must return the exact same result as the uncached function it wraps —
    moving from a per-process functools.lru_cache to
    modules.redis_cache.redis_single_flight_cache changes WHERE the result
    is shared, never WHAT it computes."""

    trade = {
        "transaction_id": "tx1",
        "type": "trade",
        "status": "complete",
        "status_updated": 1000,
        "roster_ids": [1, 2],
        "adds": {"p1": 1, "p2": 2},
        "drops": {"p2": 1, "p1": 2},
        "draft_picks": [],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                uncached = manager_activity.manager_activity_counts("L1")
                cached = manager_activity.manager_activity_counts_cached("L1")

    assert cached == uncached == {1: 1, 2: 1}


def test_manager_activity_counts_cached_concurrent_misses_single_flight(monkeypatch):
    """Two concurrent cache misses for the same (league_id, bucket) key must
    run the real season-long transaction scan exactly once, not once per
    caller/worker.

    Enforced by a Redis-backed distributed lock
    (modules.redis_cache.redis_single_flight_cache), not the old
    per-process functools.lru_cache — the old cache only protected ONE
    mobile-api worker; under docker-compose.yml's multiple workers, each
    worker has its own process memory, so the same scan could still run
    once per worker, and a cache hit in worker A would never help a
    request landing on worker B. tests/conftest.py's autouse fakeredis
    fixture backs manager_activity_counts_cached with a real (fake) Redis
    here, so this test exercises the actual code path."""

    call_count = 0
    call_count_lock = threading.Lock()

    def _slow_stub(league_id):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        time.sleep(0.2)
        return {1: 7}

    monkeypatch.setattr(manager_activity, "manager_activity_counts", _slow_stub)

    results: list[dict[int, int]] = []
    results_lock = threading.Lock()

    def _call():
        result = manager_activity.manager_activity_counts_cached("test-single-flight-league")
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert call_count == 1, "concurrent misses for the same key must single-flight to one real computation"
    assert len(results) == 8
    assert all(result == {1: 7} for result in results)
