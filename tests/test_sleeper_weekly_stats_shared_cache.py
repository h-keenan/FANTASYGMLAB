"""Season weekly stats go through the shared single-flight cache and degrade gracefully without a disk cache."""

from __future__ import annotations

import threading
import time

import pytest

from modules import sleeper, sleeper_cache


def _struct(year, month, day):
    return time.struct_time((year, month, day, 12, 0, 0, 0, 0, -1))


def test_weekly_stats_ttl_completed_long_current_short_prior_longest():
    mid_season = _struct(2026, 11, 10)  # NFL week ~10
    assert sleeper.weekly_stats_ttl(2026, 3, mid_season) == sleeper.WEEKLY_STATS_COMPLETED_TTL_SECONDS
    assert sleeper.weekly_stats_ttl(2026, 18, mid_season) == sleeper.WEEKLY_STATS_CURRENT_WEEK_TTL_SECONDS
    assert sleeper.weekly_stats_ttl(2025, 18, mid_season) == sleeper.WEEKLY_STATS_PRIOR_SEASON_TTL_SECONDS
    offseason = _struct(2027, 3, 1)  # active season is still 2026 and finished
    assert sleeper.weekly_stats_ttl(2026, 18, offseason) == sleeper.WEEKLY_STATS_COMPLETED_TTL_SECONDS
    assert (
        sleeper.WEEKLY_STATS_CURRENT_WEEK_TTL_SECONDS
        < sleeper.WEEKLY_STATS_COMPLETED_TTL_SECONDS
        < sleeper.WEEKLY_STATS_PRIOR_SEASON_TTL_SECONDS
    )


def test_concurrent_cold_fetches_hit_sleeper_once_per_week(monkeypatch):
    calls = []
    lock = threading.Lock()

    def fake(label, url, timeout=0):
        with lock:
            calls.append(url)
        time.sleep(0.02)
        return {"p": {"pts": 1}}

    monkeypatch.setattr(sleeper, "_request_json", fake)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(sleeper._fetch_weekly_stat_payloads(2025, range(1, 19))))
        for _ in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 18 and len(set(calls)) == 18
    assert all(len(r) == 18 for r in results)
    # A later caller is served from the shared cache with no upstream call.
    sleeper._fetch_weekly_stat_payloads(2025, range(1, 19))
    assert len(calls) == 18


def test_failed_week_is_not_cached_as_success(monkeypatch):
    seq = iter([None, {"p": {}}])

    monkeypatch.setattr(sleeper, "_request_json", lambda label, url, timeout=0: next(seq))
    assert sleeper._fetch_weekly_stat_payloads(2025, [3]) == []
    sleeper_cache.reset_for_tests()  # clear the short negative cache
    assert sleeper._fetch_weekly_stat_payloads(2025, [3]) == [(3, {"p": {}})]


def test_large_payloads_stay_out_of_long_lived_local_store(monkeypatch):
    monkeypatch.setattr(sleeper_cache, "_redis", lambda: None)
    sleeper_cache.shared_json("u://big", ttl=60, fetch=lambda: {"x": 1}, large=True)
    assert sleeper_cache._local == {}
    assert len(sleeper_cache._local_large) == 1
    key = sleeper_cache.cache_key("u://big")
    monkeypatch.setattr(sleeper_cache, "LARGE_LOCAL_SECONDS", -1.0)
    assert sleeper_cache._get_entry(key) is None


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _fake_aggregate(monkeypatch, counter):
    def fake_fetch(season, weeks):
        counter.append(1)
        return [(1, {"p1": {"gp": 1, "pts_ppr": 12.0, "rec": 4}})]

    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", fake_fetch)


def test_unwritable_disk_cache_builds_once_and_serves_from_memory(tmp_cwd, monkeypatch):
    builds = []
    _fake_aggregate(monkeypatch, builds)

    def boom(*a, **k):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(sleeper.os, "replace", boom)
    first = sleeper.get_season_player_stats(2025, retain_weekly=True)
    second = sleeper.get_season_player_stats(2025, retain_weekly=True)
    assert first and second is first
    assert len(builds) == 1
    # readers that never fetch also see the in-memory build
    assert sleeper.cached_season_weekly_map(2025).get("p1")
    assert sleeper.cached_season_player_weekly("p1", 2025)


def test_concurrent_cold_builds_are_single_flight(tmp_cwd, monkeypatch):
    builds = []

    def slow_fetch(season, weeks):
        builds.append(1)
        time.sleep(0.15)
        return [(1, {"p1": {"gp": 1, "pts_ppr": 12.0}})]

    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", slow_fetch)
    out = []
    threads = [threading.Thread(target=lambda: out.append(sleeper.get_season_player_stats(2025))) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(builds) == 1 and len(out) == 5 and all(o for o in out)


def test_season_weekly_map_self_heals_missing_disk_cache(tmp_cwd, monkeypatch):
    builds = []
    _fake_aggregate(monkeypatch, builds)
    assert sleeper.cached_season_weekly_map(2025) == {}  # never fetches
    assert builds == []
    healed = sleeper.season_weekly_map(2025)
    assert healed.get("p1") and len(builds) == 1
    assert sleeper.season_weekly_map(2025).get("p1") and len(builds) == 1
