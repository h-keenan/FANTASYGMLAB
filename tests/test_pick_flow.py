"""modules.pick_flow: real per-roster future-pick flow (acquired vs. sent,
1st-rounders tracked separately) off Sleeper's own transaction history — the
data half of the "Pick Hoarder"/"Pick Seller" team badge. Same fake-fetcher
pattern tests/test_manager_activity.py uses: pins the aggregation against
realistic raw Sleeper transaction shapes rather than the live Sleeper API.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

from modules import pick_flow


def test_pick_flow_counts_first_round_pick_changing_hands():
    """A trade sends roster 2's future 1st to roster 1 — roster 1 gets
    firsts_acquired, roster 2 gets firsts_sent, both get picks_acquired/sent
    tallied too."""
    trade = {
        "transaction_id": "tx1",
        "type": "trade",
        "status": "complete",
        "status_updated": 1000,
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
        "draft_picks": [
            {"owner_id": 1, "previous_owner_id": 2, "round": 1, "season": "2027"},
        ],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = pick_flow.league_pick_flow_counts("L1")

    assert counts[1] == {"picks_acquired": 1, "picks_sent": 0, "firsts_acquired": 1, "firsts_sent": 0}
    assert counts[2] == {"picks_acquired": 0, "picks_sent": 1, "firsts_acquired": 0, "firsts_sent": 1}


def test_pick_flow_counts_non_first_round_pick_does_not_count_as_a_first():
    trade = {
        "transaction_id": "tx2",
        "type": "trade",
        "status": "complete",
        "status_updated": 2000,
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
        "draft_picks": [
            {"owner_id": 1, "previous_owner_id": 2, "round": 3, "season": "2027"},
        ],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = pick_flow.league_pick_flow_counts("L1")

    assert counts[1]["picks_acquired"] == 1
    assert counts[1]["firsts_acquired"] == 0
    assert counts[2]["picks_sent"] == 1
    assert counts[2]["firsts_sent"] == 0


def test_pick_flow_counts_empty_league_id_short_circuits():
    assert pick_flow.league_pick_flow_counts("") == {}


def test_classify_pick_flow_hoarder_when_more_firsts_acquired_than_sent():
    assert pick_flow.classify_pick_flow(2, 0) == "Pick Hoarder"
    assert pick_flow.classify_pick_flow(1, 0) == "Pick Hoarder"


def test_classify_pick_flow_seller_when_more_firsts_sent_than_acquired():
    assert pick_flow.classify_pick_flow(0, 1) == "Pick Seller"
    assert pick_flow.classify_pick_flow(1, 2) == "Pick Seller"


def test_classify_pick_flow_no_badge_when_even():
    assert pick_flow.classify_pick_flow(0, 0) is None
    assert pick_flow.classify_pick_flow(1, 1) is None


def test_league_pick_flow_counts_cached_matches_uncached_result():
    """The Redis-backed cached front door (league_pick_flow_counts_cached)
    must return the exact same result as the uncached function it wraps —
    moving from a per-process functools.lru_cache to
    modules.redis_cache.redis_single_flight_cache changes WHERE the result
    is shared, never WHAT it computes. This was a real gap: Team Rankings'
    own pick-flow badge used a bare lru_cache that only protected one
    mobile-api worker process, unlike the identical pattern already fixed
    in modules.manager_activity/modules.team_trade_history."""

    trade = {
        "transaction_id": "tx1",
        "type": "trade",
        "status": "complete",
        "status_updated": 1000,
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
        "draft_picks": [
            {"owner_id": 1, "previous_owner_id": 2, "round": 1, "season": "2027"},
        ],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                uncached = pick_flow.league_pick_flow_counts("L1")
                cached = pick_flow.league_pick_flow_counts_cached("L1")

    assert cached == uncached
    assert cached[1] == {"picks_acquired": 1, "picks_sent": 0, "firsts_acquired": 1, "firsts_sent": 0}


def test_league_pick_flow_counts_cached_concurrent_misses_single_flight(monkeypatch):
    """Two concurrent cache misses for the same (league_id, bucket) key must
    run the real season-long transaction scan exactly once, not once per
    caller/worker — enforced by the Redis-backed distributed lock
    (modules.redis_cache.redis_single_flight_cache), not a per-process
    functools.lru_cache. tests/conftest.py's autouse fakeredis fixture backs
    league_pick_flow_counts_cached with a real (fake) Redis here, so this
    test exercises the actual code path."""

    call_count = 0
    call_count_lock = threading.Lock()

    def _slow_stub(league_id):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        time.sleep(0.2)
        return {1: {"picks_acquired": 1, "picks_sent": 0, "firsts_acquired": 0, "firsts_sent": 0}}

    monkeypatch.setattr(pick_flow, "league_pick_flow_counts", _slow_stub)

    results: list[dict] = []
    results_lock = threading.Lock()

    def _call():
        result = pick_flow.league_pick_flow_counts_cached("test-single-flight-league")
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert call_count == 1, "concurrent misses for the same key must single-flight to one real computation"
    assert len(results) == 8
    assert all(result == {1: {"picks_acquired": 1, "picks_sent": 0, "firsts_acquired": 0, "firsts_sent": 0}} for result in results)
