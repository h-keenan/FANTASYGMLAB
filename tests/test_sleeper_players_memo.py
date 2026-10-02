"""modules.sleeper.get_players(): in-process memo on top of the disk cache.

Before this fix, a disk-cache hit (the common case — PLAYERS_CACHE_TTL_SECONDS
is 5 minutes) still re-parsed the entire on-disk JSON file (~16MB in
production) on every single call, with no in-process memoization at all.
Several hot mobile-API endpoints (/v1/players, matchup, my-team, schedule)
call get_players() once or more per request, so this was real repeated
work for identical data. These tests pin the fix: a process-wide memo keyed
by the cache file's mtime, so the JSON is only actually parsed once per real
file change, not once per call.
"""

from __future__ import annotations

import json
import os
import time
from unittest.mock import Mock, patch

import pytest

from modules import sleeper


@pytest.fixture(autouse=True)
def _reset_players_memo():
    sleeper._players_memo = None
    sleeper._players_memo_mtime_ns = -1
    yield
    sleeper._players_memo = None
    sleeper._players_memo_mtime_ns = -1


def _write_players_cache(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def test_repeated_calls_within_same_file_state_parse_disk_only_once(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write_players_cache(cache_path, {"1": {"full_name": "Player One"}})

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        real_open = open

        call_count = {"n": 0}

        def counting_open(path, *args, **kwargs):
            if path == cache_path and "r" in (args[0] if args else kwargs.get("mode", "r")):
                call_count["n"] += 1
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=counting_open):
            first = sleeper.get_players()
            second = sleeper.get_players()
            third = sleeper.get_players()

    assert first == second == third == {"1": {"full_name": "Player One"}}
    # Only the very first call should have actually opened/parsed the file;
    # the next two must be served from the in-process memo.
    assert call_count["n"] == 1


def test_returns_same_object_across_calls_not_a_fresh_parse(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write_players_cache(cache_path, {"1": {"full_name": "Player One"}})

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        first = sleeper.get_players()
        second = sleeper.get_players()

    assert first is second


def test_file_rewrite_invalidates_the_memo(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write_players_cache(cache_path, {"1": {"full_name": "Stale"}})

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        first = sleeper.get_players()
        assert first["1"]["full_name"] == "Stale"

        # Simulate a real background refresh rewriting the on-disk cache
        # (ensure the mtime actually advances on fast filesystems/clocks).
        time.sleep(0.01)
        _write_players_cache(cache_path, {"1": {"full_name": "Fresh"}})
        os.utime(cache_path, None)

        second = sleeper.get_players()
        assert second["1"]["full_name"] == "Fresh"


def test_refresh_true_bypasses_memo_and_repopulates_it(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write_players_cache(cache_path, {"1": {"full_name": "Old"}})

    response = Mock()
    response.raise_for_status = lambda: None
    response.json.return_value = {"1": {"full_name": "New"}}

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        with patch("modules.sleeper.requests.get", return_value=response):
            result = sleeper.get_players(refresh=True)

        assert result == {"1": {"full_name": "New"}}
        # The memo should now reflect the freshly-fetched data too, so a
        # subsequent non-refresh call (within the TTL) doesn't re-parse disk
        # and serve something stale from before the refresh.
        assert sleeper._players_memo == {"1": {"full_name": "New"}}
