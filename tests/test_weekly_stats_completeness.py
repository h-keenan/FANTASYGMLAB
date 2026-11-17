"""Weekly stats: confirmed-inactive weeks are kept distinct from missing data, and a partial
rebuild is detected (manifest) and retried instead of persisting as complete."""

from __future__ import annotations

import json
import os

import pytest

from modules import sleeper


def _payloads():
    return [
        (1, {"12492": {"gp": 1, "pts_ppr": 8.2, "off_snp": 30, "tm_off_snp": 60}}),
        (2, {"12492": {"gp": 1, "pts_ppr": 1.6, "off_snp": 41, "tm_off_snp": 60}}),
        # Weeks 3-4: Sleeper lists him (gms_active) but he has no gp: a healthy scratch.
        (3, {"12492": {"gms_active": 1.0, "pos_rank_ppr": 999.0}}),
        (4, {"12492": {"gms_active": 1.0, "pos_rank_ppr": 999.0}}),
        (5, {"12492": {"gp": 1, "pts_ppr": 15.6, "off_snp": 51, "tm_off_snp": 60}}),
        (6, {}),  # bye: no entry at all
    ]


def test_aggregate_records_confirmed_inactive_weeks_but_not_byes():
    agg = sleeper._aggregate_player_week_stats(_payloads(), 2026, retain_weekly=True)
    rec = agg["12492"]
    assert rec["inactive_weeks"] == [3, 4]
    assert [r["week"] for r in rec["weekly"]] == [1, 2, 5]
    assert 6 not in rec["inactive_weeks"]


@pytest.fixture
def stats_files(tmp_path, monkeypatch):
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "sleeper_player_stats_{season}.json"))
    monkeypatch.setattr(sleeper, "expected_stats_weeks", lambda season: 5)
    monkeypatch.setattr(sleeper, "_player_stats_cache_ttl", lambda season, now=None: 3600)
    sleeper._season_stats_memo.clear()
    sleeper._season_stats_fallback.clear()
    sleeper._stats_rebuild_attempted_at.clear()
    return tmp_path


def test_partial_rebuild_is_flagged_and_retried_not_trusted(stats_files, monkeypatch):
    # Weeks 3 and 4 fail on the first build (timeouts): the old code wrote this as "fresh".
    calls = []

    def fetch(season, weeks):
        calls.append(list(weeks))
        return [p for p in _payloads() if p[0] in (1, 2, 5) or len(calls) > 1]

    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", fetch)
    sleeper.get_season_player_stats(2026, max_week=5)
    report = sleeper.season_stats_completeness(2026)
    assert report["status"] == "incomplete" and report["missing_weeks"] == [3, 4]

    # Within the retry window a request is served from the file without hammering the provider.
    sleeper.get_season_player_stats(2026, max_week=5)
    assert len(calls) == 1
    # After the window it refetches and the manifest becomes complete.
    sleeper._stats_rebuild_attempted_at.clear()
    sleeper.get_season_player_stats(2026, max_week=5)
    assert len(calls) == 2
    assert sleeper.season_stats_completeness(2026)["status"] == "complete"


def test_worse_rebuild_never_replaces_a_more_complete_cache(stats_files, monkeypatch):
    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", lambda s, w: _payloads())
    sleeper.get_season_player_stats(2026, max_week=5)
    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", lambda s, w: _payloads()[:1])
    sleeper.get_season_player_stats(2026, refresh=True, max_week=5)
    path = sleeper.PLAYER_STATS_CACHE_TEMPLATE.format(season=2026)
    with open(path) as handle:
        assert len(json.load(handle)["12492"]["weekly"]) == 3
    assert sleeper.season_stats_completeness(2026)["status"] == "complete"


def test_legacy_cache_without_manifest_is_unverified_not_refetched(stats_files, monkeypatch):
    path = sleeper.PLAYER_STATS_CACHE_TEMPLATE.format(season=2026)
    with open(path, "w") as handle:
        json.dump({"1": {"fantasy_points_ppr": 1.0, "weekly": [{"week": 1, "games_played": 1}]}}, handle)
    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", lambda s, w: pytest.fail("must not refetch"))
    sleeper.get_season_player_stats(2026)
    assert sleeper.season_stats_completeness(2026)["status"] == "unverified"
    assert not os.path.exists(sleeper.stats_manifest_path(path))
