"""Round 4 stale-while-revalidate: fresh hit, stale hit + background refresh, fingerprint change = synchronous recompute (never stale
across a changed input), refresh failure keeps the stale entry, and the valued frame is identical whether served fresh, stale or
recomputed. tests/conftest.py points modules.redis_cache at a fresh fakeredis per test."""

from __future__ import annotations

import pandas as pd
import pytest

from modules import derived_cache, league_value_settings, redis_cache, swr_cache


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture()
def refreshes(monkeypatch):
    """Capture background refreshes instead of spawning threads; run them on demand."""

    queued: list = []
    monkeypatch.setattr(swr_cache, "_spawn_refresh", queued.append)
    swr_cache._inflight.clear()
    swr_cache._failed_until.clear()
    return queued


def _call(key, compute, clock, fresh=120, stale=3600):
    return swr_cache.redis_swr_cache(cache_key=key, fresh_ttl_seconds=fresh, stale_ttl_seconds=stale, compute=compute, clock=clock)


def test_fresh_hit_does_not_recompute_or_refresh(refreshes):
    clock, calls = Clock(), []
    compute = lambda: calls.append(1) or {"n": len(calls)}
    assert _call("k", compute, clock) == {"n": 1}
    clock.now += 119
    assert _call("k", compute, clock) == {"n": 1}
    assert len(calls) == 1 and refreshes == []


def test_stale_hit_is_served_instantly_then_refreshed_in_the_background(refreshes):
    clock, calls = Clock(), []
    compute = lambda: calls.append(1) or {"n": len(calls)}
    _call("k", compute, clock)
    clock.now += 500
    assert _call("k", compute, clock) == {"n": 1}  # stale value, no recompute on the request path
    assert len(calls) == 1 and len(refreshes) == 1
    assert _call("k", compute, clock) == {"n": 1}  # still stale until the refresh lands; one refresh only
    assert len(refreshes) == 1
    refreshes.pop()()  # the background worker runs
    assert len(calls) == 2
    assert _call("k", compute, clock) == {"n": 2} and len(refreshes) == 0  # fresh again


def test_changed_fingerprint_is_a_synchronous_recompute_never_the_stale_value(refreshes):
    clock = Clock()
    key = lambda fp: redis_cache.build_cache_key("t", "league", fp)
    assert _call(key("A"), lambda: "value-for-A", clock) == "value-for-A"
    clock.now += 500  # A is stale, but B is a different input
    assert _call(key("B"), lambda: "value-for-B", clock) == "value-for-B"
    assert refreshes == []
    assert _call(key("A"), lambda: "value-for-A2", clock) == "value-for-A"  # A itself is still served stale, as designed


def test_failed_refresh_keeps_the_stale_entry_and_backs_off(refreshes):
    clock = Clock()
    _call("k", lambda: "good", clock)
    clock.now += 500

    def boom():
        raise RuntimeError("upstream down")

    assert _call("k", boom, clock) == "good"
    refreshes.pop()()
    assert _call("k", boom, clock) == "good"
    assert refreshes == []  # backed off, no thrash
    clock.now += 31
    _call("k", boom, clock)
    assert len(refreshes) == 1


def test_only_one_worker_refreshes_a_key(refreshes):
    clock = Clock()
    _call("k", lambda: 1, clock)
    clock.now += 500
    client = redis_cache.get_redis_client()
    client.set("lock:k", b"other-worker", nx=True, px=5000)
    calls = []
    assert _call("k", lambda: calls.append(1) or 2, clock) == 1
    refreshes.pop()()
    assert calls == []  # the lock holder, not this worker, recomputes


def test_disabled_falls_back_to_a_plain_ttl_cache(monkeypatch, refreshes):
    monkeypatch.setattr(swr_cache, "ENABLED", False)
    calls = []
    compute = lambda: calls.append(1) or len(calls)
    assert _call("k", compute, Clock()) == 1
    assert _call("k", compute, Clock()) == 1
    assert refreshes == []


def _pool(n=3):
    return pd.DataFrame({"player_id": [str(i) for i in range(n)], "dynasty_score": [100.0 * (i + 1) for i in range(n)]})


def _patch_inputs(monkeypatch, league, builds):
    monkeypatch.setattr(league_value_settings.sleeper, "get_league", lambda league_id: dict(league))
    monkeypatch.setattr(league_value_settings.rankings, "public_player_source_fingerprint", lambda path: (("sqlite", True, 1, 1),))
    monkeypatch.setattr(league_value_settings.rankings, "reconciled_valuation_cache_versions", lambda: ())
    monkeypatch.setattr(
        league_value_settings, "_build_valued_players_frame_cached", lambda *a: builds.append(a) or _pool(len(builds) + 2)
    )


def _frame(clock):
    # The front door reads the wall clock through redis_swr_cache's default; drive it via the module's clock param.
    return league_value_settings.build_valued_players_frame_cached(league_id="L1", lens="Dynasty", players_db_path="x.db")


def test_valued_frame_is_stale_served_then_refreshed_and_a_changed_league_recomputes(monkeypatch, refreshes):
    clock, builds = Clock(), []
    real = swr_cache.redis_swr_cache
    monkeypatch.setattr(swr_cache, "redis_swr_cache", lambda **kw: real(**kw, clock=clock))
    league = {"league_id": "L1", "scoring_settings": {"rec": 1.0}}
    _patch_inputs(monkeypatch, league, builds)

    first = _frame(clock)
    assert len(builds) == 1
    clock.now += 600
    stale = _frame(clock)
    assert len(builds) == 1 and len(refreshes) == 1
    pd.testing.assert_frame_equal(first, stale)  # identical result, served instantly
    assert league_value_settings.valued_players_frame_cache_key(stale)  # still tagged for downstream memos

    refreshes.pop()()
    assert len(builds) == 2
    pd.testing.assert_frame_equal(_frame(clock), _pool(4))

    league["scoring_settings"] = {"rec": 0.5}  # a real settings change: different fingerprint, never the stale frame
    changed = _frame(clock)
    assert len(builds) == 3
    pd.testing.assert_frame_equal(changed, _pool(5))


def test_players_data_change_is_a_different_key(monkeypatch, refreshes):
    clock, builds = Clock(), []
    real = swr_cache.redis_swr_cache
    monkeypatch.setattr(swr_cache, "redis_swr_cache", lambda **kw: real(**kw, clock=clock))
    _patch_inputs(monkeypatch, {"league_id": "L1"}, builds)
    _frame(clock)
    monkeypatch.setattr(league_value_settings.rankings, "public_player_source_fingerprint", lambda path: (("sqlite", True, 2, 2),))
    _frame(clock)
    assert len(builds) == 2 and refreshes == []


def test_unfingerprintable_league_falls_back_to_the_clock_bucket(monkeypatch):
    monkeypatch.setattr(league_value_settings.sleeper, "get_league", lambda league_id: {"x": object()})
    monkeypatch.setattr(league_value_settings.rankings, "public_player_source_fingerprint", lambda path: ())
    monkeypatch.setattr(league_value_settings.rankings, "reconciled_valuation_cache_versions", lambda: ())
    assert league_value_settings._valued_players_inputs_fingerprint("L1", "x.db").startswith("bucket:")
    assert derived_cache.Unfingerprintable
