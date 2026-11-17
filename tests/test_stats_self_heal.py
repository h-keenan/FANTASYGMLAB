"""Boot-time weekly-stats self-heal, run against a temp cache dir (never data/)."""

import json

import pytest

from modules import sleeper, stats_self_heal
from modules.file_lock import ExclusiveFileLock


def _payload(week):
    return (week, {str(i): {"gp": 1, "pts_ppr": 1.0} for i in range(200)})


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "stats" / "sleeper_player_stats_{season}.json"))
    monkeypatch.setattr(sleeper, "expected_stats_weeks", lambda season: 4)
    monkeypatch.setattr(sleeper, "default_player_stats_season", lambda *a, **k: 2026)
    monkeypatch.setattr(sleeper, "_player_stats_cache_ttl", lambda season, now=None: 3600)
    sleeper._season_stats_memo.clear()
    sleeper._season_stats_fallback.clear()
    sleeper._stats_rebuild_attempted_at.clear()
    return tmp_path / "stats"


def _fetcher(monkeypatch, ok_weeks, calls):
    def fetch(season, weeks):
        calls.append((season, list(weeks)))
        return [_payload(w) for w in weeks if w in ok_weeks]

    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", fetch)


def _heal(**kw):
    sleeps = []
    out = stats_self_heal.self_heal(sleep=sleeps.append, **kw)
    return out, sleeps


def test_missing_season_is_backfilled_from_an_empty_dir(cache, monkeypatch):
    calls = []
    _fetcher(monkeypatch, {1, 2, 3, 4}, calls)
    out, _ = _heal()
    assert out["state"] == "ok"
    assert [e["result"] for e in out["seasons"]] == ["healed", "healed"]
    assert sleeper.season_stats_completeness(2026)["status"] == "complete"
    assert sleeper.season_stats_completeness(2025)["status"] == "complete"
    assert stats_self_heal.read_status()["state"] == "ok"


def test_partial_weeks_are_refetched(cache, monkeypatch):
    _fetcher(monkeypatch, {1, 2}, [])
    sleeper.get_season_player_stats(2026, max_week=4)
    assert sleeper.season_stats_completeness(2026)["missing_weeks"] == [3, 4]
    calls = []
    _fetcher(monkeypatch, {1, 2, 3, 4}, calls)
    out, _ = _heal(seasons=[2026])
    assert out["seasons"][0]["result"] == "healed"
    assert sleeper.season_stats_completeness(2026)["status"] == "complete"


def test_complete_cache_is_a_noop(cache, monkeypatch):
    _fetcher(monkeypatch, {1, 2, 3, 4}, [])
    sleeper.get_season_player_stats(2026, max_week=4)
    calls = []
    _fetcher(monkeypatch, {1, 2, 3, 4}, calls)
    out, sleeps = _heal(seasons=[2026])
    assert out["state"] == "ok" and out["seasons"][0]["result"] == "complete"
    assert calls == [] and sleeps == []


def test_lock_contention_skips_without_touching_sleeper(cache, monkeypatch):
    calls = []
    _fetcher(monkeypatch, {1, 2, 3, 4}, calls)
    cache.mkdir(parents=True)
    with ExclusiveFileLock(str(cache / stats_self_heal.LOCK_FILENAME)) as held:
        assert held.acquired
        out, _ = _heal(seasons=[2026])
    assert out["state"] == "skipped_locked"
    assert calls == []


def test_sleeper_failure_backs_off_and_does_not_crash(cache, monkeypatch):
    attempts = []

    def boom(season, weeks):
        attempts.append(season)
        raise RuntimeError("sleeper down")

    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", boom)
    out, sleeps = _heal(seasons=[2026], backoff_seconds=(1.0, 2.0))
    assert out["state"] == "incomplete"
    assert len(attempts) == 3 and sleeps == [1.0, 2.0]
    assert out["seasons"][0]["error"] == "RuntimeError"
    status = json.loads((cache / stats_self_heal.STATUS_FILENAME).read_text())
    assert status["state"] == "incomplete"


def test_freshness_report_surfaces_self_heal(cache, monkeypatch):
    from modules import data_freshness

    _fetcher(monkeypatch, {1, 2, 3, 4}, [])
    _heal(seasons=[2026])
    row = data_freshness.weekly_stats_row(0.0, True)
    assert row["self_heal"]["state"] == "ok" and "self-heal ok" in row["detail"]


def test_start_background_is_a_noop_under_pytest():
    assert stats_self_heal.start_background() is None
