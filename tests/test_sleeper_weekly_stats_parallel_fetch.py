"""The cold season-stats build fetches its weekly payloads concurrently, with serial-identical output."""

from __future__ import annotations

import threading
import time

from modules import sleeper, sleeper_budget


def _serial_reference(fake, season, weeks):
    out = []
    for week in weeks:
        try:
            payload = fake("sleeper_player_stats_week", f"{sleeper.SLEEPER_BASE}/stats/nfl/regular/{season}/{week}", timeout=20)
        except Exception:
            continue
        if isinstance(payload, dict):
            out.append((week, payload))
    return out


def test_parallel_fetch_matches_serial_loop_including_failures_and_order(monkeypatch):
    def fake(label, url, timeout=0):
        week = int(url.rsplit("/", 1)[1])
        time.sleep(0.03)
        if week == 4:
            raise RuntimeError("boom")
        if week == 7:
            return []  # non-dict payloads are dropped
        return {"p": {"pts": week}}

    monkeypatch.setattr(sleeper, "_request_json", fake)
    expected = _serial_reference(fake, 2026, range(1, 19))
    assert sleeper._fetch_weekly_stat_payloads(2026, range(1, 19)) == expected
    assert [week for week, _ in expected] == [w for w in range(1, 19) if w not in (4, 7)]


def test_parallel_fetch_overlaps_network_latency(monkeypatch):
    seen_threads = set()

    def fake(label, url, timeout=0):
        seen_threads.add(threading.get_ident())
        time.sleep(0.05)
        return {}

    monkeypatch.setattr(sleeper, "_request_json", fake)
    start = time.perf_counter()
    result = sleeper._fetch_weekly_stat_payloads(2026, range(1, 19))
    elapsed = time.perf_counter() - start
    assert len(result) == 18
    assert len(seen_threads) > 1
    assert elapsed < 18 * 0.05 * 0.6  # serial would be >= 0.9 s


def test_parallel_fetch_keeps_caller_budget_context(monkeypatch):
    priorities = []

    def fake(label, url, timeout=0):
        priorities.append(sleeper_budget._priority.get())
        return {}

    monkeypatch.setattr(sleeper, "_request_json", fake)
    token = sleeper_budget._priority.set("free")
    try:
        sleeper._fetch_weekly_stat_payloads(2026, range(1, 7))
    finally:
        sleeper_budget._priority.reset(token)
    assert priorities == ["free"] * 6


def test_get_matchups_for_weeks_matches_per_week_calls_and_overlaps(monkeypatch):
    calls = []

    def fake(league_id, week):
        calls.append(week)
        time.sleep(0.05)
        return [{"matchup_id": week}] if week % 2 else []

    monkeypatch.setattr(sleeper, "get_matchups", fake)
    start = time.perf_counter()
    got = sleeper.get_matchups_for_weeks("L", [*range(1, 15), 3, 5])  # duplicates collapse
    elapsed = time.perf_counter() - start
    assert list(got) == list(range(1, 15))
    assert got == {w: ([{"matchup_id": w}] if w % 2 else []) for w in range(1, 15)}
    assert sorted(calls) == list(range(1, 15))
    assert elapsed < 14 * 0.05 * 0.6
    assert sleeper.get_matchups_for_weeks("L", []) == {}
