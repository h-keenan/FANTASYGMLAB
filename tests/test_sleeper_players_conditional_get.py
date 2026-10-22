"""The players dump is re-validated with a conditional GET (ETag / 304).

A 304 must leave the dump file byte- and mtime-identical (its mtime is part of
the public-player fingerprint), yet count as a fresh confirmation for the TTL.
"""

from __future__ import annotations

import json
import os
import time
from unittest.mock import Mock, patch

import pytest

from modules import sleeper, startup_cold_path
from modules import signal_freshness


@pytest.fixture(autouse=True)
def _reset_state():
    def reset():
        sleeper._players_memo = None
        sleeper._players_memo_mtime_ns = -1
        sleeper._players_bg_in_flight = False
        sleeper._players_bg_last_failure_mono = 0.0

    reset()
    yield
    reset()


def _response(payload=None, *, etag="", status=200) -> Mock:
    response = Mock()
    response.status_code = status
    response.raise_for_status = lambda: None
    response.json.return_value = payload
    response.headers = {"ETag": etag} if etag else {}
    return response


def _age(path: str, seconds: float) -> None:
    """Make the dump (and its validation, if any) look `seconds` old."""
    etag = sleeper._read_players_validation(path).get("etag")
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))
    if etag:
        sleeper._write_players_validation(etag, cache_path=path)
        os.utime(sleeper._players_validation_path(path), (stamp, stamp))


def test_304_keeps_dump_untouched_but_counts_as_fresh(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    payload = {"1": {"full_name": "A"}}
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        with patch("modules.sleeper.requests.get", return_value=_response(payload, etag='W/"v1"')) as get:
            assert sleeper.get_players(refresh=True) == payload
        assert get.call_args.kwargs.get("headers") is None
        before = os.stat(cache_path)
        _age(cache_path, sleeper.PLAYERS_CACHE_TTL_SECONDS + 120)
        aged = os.stat(cache_path)
        assert not sleeper._players_cache_is_fresh()
        assert startup_cold_path.sleeper_players_cache_stale(cache_path=cache_path)

        with patch("modules.sleeper.requests.get", return_value=_response(status=304)) as get:
            assert sleeper.get_players(refresh=True) == payload
        assert get.call_args.kwargs["headers"] == {"If-None-Match": 'W/"v1"'}
        after = os.stat(cache_path)
        assert (after.st_mtime_ns, after.st_size) == (aged.st_mtime_ns, aged.st_size)
        assert sleeper._players_cache_is_fresh()
        assert not startup_cold_path.sleeper_players_cache_stale(cache_path=cache_path)
        assert time.time() - signal_freshness.players_cache_synced_at(cache_path) < 30
        assert before.st_size == after.st_size


def test_ttl_still_expires_after_a_304(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        with patch("modules.sleeper.requests.get", return_value=_response({"1": {}}, etag='"a"')):
            sleeper.get_players(refresh=True)
        with patch("modules.sleeper.requests.get", return_value=_response(status=304)):
            sleeper.get_players(refresh=True)
        _age(cache_path, sleeper.PLAYERS_CACHE_TTL_SECONDS + 5)
        assert not sleeper._players_cache_is_fresh()


def test_200_after_a_changed_dump_replaces_file_and_etag(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        with patch("modules.sleeper.requests.get", return_value=_response({"1": {"n": 1}}, etag='"a"')):
            sleeper.get_players(refresh=True)
        _age(cache_path, sleeper.PLAYERS_CACHE_TTL_SECONDS + 5)
        first_mtime = os.stat(cache_path).st_mtime_ns
        with patch("modules.sleeper.requests.get", return_value=_response({"1": {"n": 2}}, etag='"b"')) as get:
            assert sleeper.get_players(refresh=True) == {"1": {"n": 2}}
        assert get.call_args.kwargs["headers"] == {"If-None-Match": '"a"'}
        assert os.stat(cache_path).st_mtime_ns != first_mtime
        with open(cache_path, encoding="utf-8") as handle:
            assert json.load(handle) == {"1": {"n": 2}}
        assert sleeper._read_players_validation()["etag"] == '"b"'


def test_etag_is_not_sent_when_the_dump_was_changed_by_someone_else(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        with patch("modules.sleeper.requests.get", return_value=_response({"1": {}}, etag='"a"')):
            sleeper.get_players(refresh=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump({"1": {"other": True}}, handle)
        with patch("modules.sleeper.requests.get", return_value=_response({"1": {"n": 3}})) as get:
            assert sleeper.get_players(refresh=True) == {"1": {"n": 3}}
        assert get.call_args.kwargs.get("headers") is None


def test_304_with_unreadable_dump_falls_back_to_a_full_download(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        with patch("modules.sleeper.requests.get", return_value=_response({"1": {}}, etag='"a"')):
            sleeper.get_players(refresh=True)
        responses = [_response(status=304), _response({"1": {"n": 9}}, etag='"c"')]
        with patch.object(sleeper, "_read_players_cache_file", return_value=None), patch(
            "modules.sleeper.requests.get", side_effect=responses
        ):
            assert sleeper._download_players() == {"1": {"n": 9}}


def test_stale_validation_of_a_replaced_dump_is_ignored(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path):
        with patch("modules.sleeper.requests.get", return_value=_response({"1": {}}, etag='"a"')):
            sleeper.get_players(refresh=True)
        # dump rewritten by another path; the old validation must not make it look fresh
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump({"1": {"x": 1}}, handle)
        stamp = time.time() - sleeper.PLAYERS_CACHE_TTL_SECONDS - 60
        os.utime(cache_path, (stamp, stamp))
        assert not sleeper._players_cache_is_fresh()
