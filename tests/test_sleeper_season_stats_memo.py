"""modules.sleeper.get_season_player_stats(): in-process memo on top of the
disk cache.

Before this fix, a disk-cache hit (the common case — PLAYER_STATS_CACHE_TTL_
SECONDS is 12 hours for the active season, far longer for completed/prior
seasons) still re-parsed the entire on-disk JSON file (~2.3MB/season in
production, confirmed ~20ms of synchronous disk I/O + JSON decode per call
via direct timing against the real cache file) on *every single call*, with
no in-process memoization at all — the same gap get_players() used to have
(see tests/test_sleeper_players_memo.py) before it got a process-wide,
mtime-keyed memo. Several hot mobile-API endpoints call this once per
request (Matchup, Player Detail weekly-stats/schedule/external-projections,
Waivers' defense-strength lookup, Rankings), so this was real repeated work
for identical data. These tests pin the fix: a memo keyed by the cache
file's path and mtime, so the JSON is only actually parsed once per real
file change, not once per call.
"""

from __future__ import annotations

import json
import os
import time
from unittest.mock import patch

import pytest

from modules import sleeper


@pytest.fixture(autouse=True)
def _reset_season_stats_memo():
    sleeper._season_stats_memo.clear()
    sleeper._season_stats_memo_mtime_ns.clear()
    sleeper._season_stats_memo_has_weekly.clear()
    yield
    sleeper._season_stats_memo.clear()
    sleeper._season_stats_memo_mtime_ns.clear()
    sleeper._season_stats_memo_has_weekly.clear()


def _write_stats_cache(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def test_repeated_calls_within_same_file_state_parse_disk_only_once(tmp_path):
    cache_path = str(tmp_path / "sleeper_player_stats_2025.json")
    _write_stats_cache(cache_path, {"1": {"fantasy_points_ppr": 10.0, "weekly": [{"week": 1}]}})

    with patch.object(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "sleeper_player_stats_{season}.json")):
        real_open = open
        call_count = {"n": 0}

        def counting_open(path, *args, **kwargs):
            if path == cache_path and "r" in (args[0] if args else kwargs.get("mode", "r")):
                call_count["n"] += 1
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=counting_open):
            first = sleeper.get_season_player_stats(season=2025, retain_weekly=True)
            second = sleeper.get_season_player_stats(season=2025, retain_weekly=True)
            third = sleeper.get_season_player_stats(season=2025, retain_weekly=True)

    assert first == second == third
    assert first["1"]["fantasy_points_ppr"] == 10.0
    # Only the very first call should have actually opened/parsed the file;
    # the next two must be served from the in-process memo.
    assert call_count["n"] == 1


def test_returns_same_object_across_calls_not_a_fresh_parse(tmp_path):
    cache_path = str(tmp_path / "sleeper_player_stats_2025.json")
    _write_stats_cache(cache_path, {"1": {"fantasy_points_ppr": 10.0, "weekly": [{"week": 1}]}})

    with patch.object(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "sleeper_player_stats_{season}.json")):
        first = sleeper.get_season_player_stats(season=2025, retain_weekly=True)
        second = sleeper.get_season_player_stats(season=2025, retain_weekly=True)

    assert first is second


def test_file_rewrite_invalidates_the_memo(tmp_path):
    cache_path = str(tmp_path / "sleeper_player_stats_2025.json")
    _write_stats_cache(cache_path, {"1": {"fantasy_points_ppr": 10.0, "weekly": [{"week": 1}]}})

    with patch.object(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "sleeper_player_stats_{season}.json")):
        first = sleeper.get_season_player_stats(season=2025, retain_weekly=True)
        assert first["1"]["fantasy_points_ppr"] == 10.0

        # Simulate a real background refresh rewriting the on-disk cache
        # (ensure the mtime actually advances on fast filesystems/clocks).
        time.sleep(0.01)
        _write_stats_cache(cache_path, {"1": {"fantasy_points_ppr": 20.0, "weekly": [{"week": 1}]}})
        os.utime(cache_path, None)

        second = sleeper.get_season_player_stats(season=2025, retain_weekly=True)
        assert second["1"]["fantasy_points_ppr"] == 20.0


def test_distinct_seasons_are_memoized_independently(tmp_path):
    template = str(tmp_path / "sleeper_player_stats_{season}.json")
    _write_stats_cache(
        template.format(season=2025), {"1": {"fantasy_points_ppr": 10.0, "weekly": [{"week": 1}]}}
    )
    _write_stats_cache(
        template.format(season=2024), {"1": {"fantasy_points_ppr": 99.0, "weekly": [{"week": 1}]}}
    )

    with patch.object(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", template):
        current = sleeper.get_season_player_stats(season=2025, retain_weekly=True)
        prior = sleeper.get_season_player_stats(season=2024, retain_weekly=True)

    assert current["1"]["fantasy_points_ppr"] == 10.0
    assert prior["1"]["fantasy_points_ppr"] == 99.0


def test_keep_weekly_true_does_not_serve_a_memo_entry_without_weekly_rows(tmp_path):
    """A cache file with no weekly rows must still trigger the existing
    "active season without weekly rows -> rebuild" path even once memoized,
    not silently serve stale weekly-less data forever."""

    cache_path = str(tmp_path / "sleeper_player_stats_2025.json")
    _write_stats_cache(cache_path, {"1": {"fantasy_points_ppr": 10.0}})  # no "weekly" key

    response_payload = {"player-1": {"pts_ppr": 5}}

    def fake_request_json(label, url, *, timeout=20, max_retries=None):
        return response_payload

    with patch.object(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "sleeper_player_stats_{season}.json")):
        with patch.object(sleeper, "_request_json", side_effect=fake_request_json):
            result = sleeper.get_season_player_stats(season=2025, retain_weekly=True, max_week=1)

    # Rebuilt from the network rather than served stale from the no-weekly
    # cache file (mirrors the pre-memo behavior's own "pass" branch).
    assert "player-1" in result
