"""Round 4: precompute on league open + scheduled re-warm, and the in-process Memo's stale-while-revalidate mode."""

from __future__ import annotations

import threading

import pytest

from modules import derived_cache, league_prewarm, redis_cache


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setattr(league_prewarm, "_disabled", lambda: False)
    league_prewarm._recent_local.clear()
    monkeypatch.setattr(league_prewarm, "_scheduler_started", False)


def test_touch_records_the_league_and_warms_it_once_per_debounce_window(monkeypatch):
    warmed = []
    monkeypatch.setattr(league_prewarm, "prewarm_league", lambda *a: warmed.append(a))
    assert league_prewarm.touch("L1", "Dynasty", "x.db", background=False) is True
    assert league_prewarm.touch("L1", "Dynasty", "x.db", background=False) is False  # debounced
    assert league_prewarm.touch("L1", "Redraft", "x.db", background=False) is True
    assert warmed == [("L1", "Dynasty", "x.db"), ("L1", "Redraft", "x.db")]
    assert set(league_prewarm.recent_leagues()) == {("L1", "Dynasty"), ("L1", "Redraft")}


def test_recent_leagues_only_returns_the_active_window_most_recent_first():
    league_prewarm.record_active("OLD", "Dynasty", now=1_000.0)
    league_prewarm.record_active("MID", "Dynasty", now=900_000.0)
    league_prewarm.record_active("NEW", "Dynasty", now=1_000_000.0)
    got = league_prewarm.recent_leagues(within=200_000, now=1_000_100.0)
    assert got == [("NEW", "Dynasty"), ("MID", "Dynasty")]


def test_warm_recent_warms_each_active_league(monkeypatch):
    warmed = []
    monkeypatch.setattr(league_prewarm, "prewarm_league", lambda *a: warmed.append(a))
    league_prewarm.record_active("L1", "Dynasty")
    league_prewarm.record_active("L2", "Dynasty")
    assert league_prewarm.warm_recent("x.db") == 2
    assert {w[0] for w in warmed} == {"L1", "L2"}


def test_only_one_worker_wins_each_scheduled_tick(monkeypatch):
    warmed = []
    monkeypatch.setattr(league_prewarm, "prewarm_league", lambda *a: warmed.append(a))
    league_prewarm.record_active("L1", "Dynasty")
    assert league_prewarm._tick("x.db", 90.0) == 1
    assert league_prewarm._tick("x.db", 90.0) == 0  # another worker, same interval
    assert len(warmed) == 1


def test_a_failing_step_never_raises_and_does_not_stop_the_others(monkeypatch):
    calls = []
    monkeypatch.setattr(
        league_prewarm.league_value_settings, "build_valued_players_frame_cached", lambda **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    monkeypatch.setattr(league_prewarm.league_rankings, "build_league_summary_and_draft_capital_cached", lambda **k: calls.append("summary"))
    monkeypatch.setattr(league_prewarm.league_rankings, "build_league_rankings_frame_cached", lambda **k: calls.append("rankings"))
    league_prewarm.prewarm_league("L1", "Dynasty", "x.db")
    assert calls == ["summary", "rankings"]


def test_disabled_under_tests_by_default(monkeypatch):
    monkeypatch.undo()
    assert league_prewarm.touch("L1", "Dynasty", "x.db") is False


def test_redis_down_is_fail_open(monkeypatch):
    class Boom:
        def __getattr__(self, name):
            def _raise(*a, **k):
                raise redis_cache.RedisError("down")

            return _raise

    redis_cache.set_redis_client_for_testing(Boom())
    assert league_prewarm.recent_leagues() == []
    league_prewarm.record_active("L1", "Dynasty")  # no raise
    assert league_prewarm._tick("x.db", 90.0) == 0


class _Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_memo_serves_stale_then_refreshes_in_the_background():
    clock = _Clock()
    memo = derived_cache.Memo("t", ttl_seconds=10, stale_ttl_seconds=100, clock=clock)
    calls, done = [], threading.Event()

    def compute():
        calls.append(1)
        done.set()
        return {"n": len(calls)}

    assert memo.get_or_compute("k", compute) == {"n": 1}
    clock.now = 50  # past fresh, within stale
    done.clear()
    assert memo.get_or_compute("k", compute) == {"n": 1}  # stale value returned at once
    assert done.wait(5)
    for _ in range(200):  # the refresh stores its result just after compute returns
        if memo.get_or_compute("k", compute) == {"n": 2}:
            break
        threading.Event().wait(0.01)
    assert memo.get_or_compute("k", compute) == {"n": 2}


def test_memo_past_the_stale_window_recomputes_synchronously_and_other_keys_never_see_it():
    clock = _Clock()
    memo = derived_cache.Memo("t", ttl_seconds=10, stale_ttl_seconds=100, clock=clock)
    assert memo.get_or_compute("a", lambda: "A1") == "A1"
    clock.now = 500
    assert memo.get_or_compute("a", lambda: "A2") == "A2"
    assert memo.get_or_compute("b", lambda: "B") == "B"  # a different (changed-input) key is always a miss


def test_memo_without_stale_ttl_is_unchanged():
    clock = _Clock()
    memo = derived_cache.Memo("t", ttl_seconds=10, clock=clock)
    memo.get_or_compute("k", lambda: 1)
    clock.now = 11
    assert memo.get_or_compute("k", lambda: 2) == 2
