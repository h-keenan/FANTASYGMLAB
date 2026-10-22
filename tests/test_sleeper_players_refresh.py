"""modules.sleeper.get_players(): atomic, single-flight, background refresh.

The ~16MB players dump used to be rewritten in place (``open(path, "w")``
truncates first), so a concurrent reader could parse an empty/partial file,
and every worker whose request found the 5-minute cache aged downloaded it
again, inline on the request thread.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from modules import sleeper

ROOT = Path(__file__).resolve().parents[1]


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


def _write(path: str, payload: dict, *, age_seconds: float = 0.0) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    if age_seconds:
        stamp = time.time() - age_seconds
        os.utime(path, (stamp, stamp))


def _response(payload: dict) -> Mock:
    response = Mock()
    response.raise_for_status = lambda: None
    response.json.return_value = payload
    return response


def _stale_age() -> float:
    return sleeper.PLAYERS_CACHE_TTL_SECONDS + 60


def test_refresh_replaces_file_atomically_never_truncating_live_file(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write(cache_path, {"1": {"full_name": "Old"}})
    seen_during_write: list[dict] = []
    real_dump = json.dump

    def observing_dump(obj, handle, *args, **kwargs):
        # While the new dump is being serialized, the live path must still
        # hold the complete previous file.
        with open(cache_path, encoding="utf-8") as live:
            seen_during_write.append(json.load(live))
        return real_dump(obj, handle, *args, **kwargs)

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch(
        "modules.sleeper.requests.get", return_value=_response({"1": {"full_name": "New"}})
    ), patch("modules.sleeper.json.dump", side_effect=observing_dump):
        result = sleeper.get_players(refresh=True)

    assert result == {"1": {"full_name": "New"}}
    assert seen_during_write == [{"1": {"full_name": "Old"}}]
    with open(cache_path, encoding="utf-8") as f:
        assert json.load(f) == {"1": {"full_name": "New"}}
    leftovers = [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]
    assert leftovers == []


def test_concurrent_readers_never_see_a_partial_dump(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    big = {str(i): {"full_name": f"Player {i}", "news_updated": i} for i in range(20000)}
    _write(cache_path, big)
    stop = threading.Event()
    errors: list[str] = []
    reads = {"n": 0}

    def reader():
        while not stop.is_set():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    json.load(f)
                reads["n"] += 1
            except ValueError as exc:  # partial / empty file
                errors.append(str(exc))

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch(
        "modules.sleeper.requests.get", return_value=_response(big)
    ):
        threads = [threading.Thread(target=reader) for _ in range(3)]
        for thread in threads:
            thread.start()
        try:
            for _ in range(8):
                sleeper.get_players(refresh=True)
        finally:
            stop.set()
            for thread in threads:
                thread.join()

    assert reads["n"] > 0
    assert errors == []


def test_concurrent_cold_callers_download_once(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    calls = {"n": 0}
    guard = threading.Lock()

    def slow_get(*_args, **_kwargs):
        with guard:
            calls["n"] += 1
        time.sleep(0.3)
        return _response({"1": {"full_name": "Fresh"}})

    results: list[dict] = []
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch(
        "modules.sleeper.requests.get", side_effect=slow_get
    ):
        threads = [
            threading.Thread(target=lambda: results.append(sleeper.get_players()))
            for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert calls["n"] == 1
    assert results == [{"1": {"full_name": "Fresh"}}] * 4


_CHILD = textwrap.dedent(
    """
    import json, os, sys, time
    sys.path.insert(0, {root!r})
    from unittest.mock import Mock
    from modules import sleeper

    cache_path, counter_path = sys.argv[1], sys.argv[2]
    sleeper.PLAYERS_CACHE_PATH = cache_path

    def fake_get(*_a, **_k):
        with open(counter_path, "a") as f:
            f.write(str(os.getpid()) + "\\n")
        time.sleep(0.5)
        response = Mock()
        response.raise_for_status = lambda: None
        response.json.return_value = {{"1": {{"full_name": "Fresh"}}}}
        return response

    sleeper.requests.get = fake_get
    # Line up the workers so they all find the cache aged at the same time.
    while not os.path.exists(cache_path + ".go"):
        time.sleep(0.01)
    print(json.dumps(sleeper.get_players()))
    """
)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="flock is POSIX-only")
def test_worker_processes_share_one_download(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    counter_path = str(tmp_path / "downloads.txt")
    _write(cache_path, {"1": {"full_name": "Old"}}, age_seconds=_stale_age())
    script = tmp_path / "child.py"
    script.write_text(_CHILD.format(root=str(ROOT)))
    env = {key: value for key, value in os.environ.items() if key != "PYTEST_CURRENT_TEST"}
    children = [
        subprocess.Popen(
            [sys.executable, str(script), cache_path, counter_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        for _ in range(4)
    ]
    time.sleep(1.0)
    Path(cache_path + ".go").write_text("")
    outputs = [child.communicate(timeout=120) for child in children]

    assert [child.returncode for child in children] == [0, 0, 0, 0], outputs
    with open(counter_path) as f:
        assert len(f.read().split()) == 1
    for stdout, _stderr in outputs:
        assert json.loads(stdout.strip().splitlines()[-1]) == {"1": {"full_name": "Fresh"}}


def test_background_mode_serves_aged_cache_and_refreshes_once(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write(cache_path, {"1": {"full_name": "Old"}}, age_seconds=_stale_age())
    release = threading.Event()
    calls = {"n": 0}

    def blocked_get(*_args, **_kwargs):
        calls["n"] += 1
        assert release.wait(10)
        return _response({"1": {"full_name": "New"}})

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch.object(
        sleeper, "PLAYERS_BACKGROUND_REFRESH", True
    ), patch("modules.sleeper.requests.get", side_effect=blocked_get):
        started = time.perf_counter()
        served = [sleeper.get_players() for _ in range(5)]
        elapsed = time.perf_counter() - started
        assert served == [{"1": {"full_name": "Old"}}] * 5
        assert elapsed < 2.0  # nobody waited on the (blocked) download
        release.set()
        deadline = time.time() + 10
        while sleeper._players_bg_in_flight and time.time() < deadline:
            time.sleep(0.01)
        assert sleeper.get_players() == {"1": {"full_name": "New"}}

    assert calls["n"] == 1


def test_background_failure_keeps_cache_and_cools_down(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write(cache_path, {"1": {"full_name": "Old"}}, age_seconds=_stale_age())
    calls = {"n": 0}

    def failing_get(*_args, **_kwargs):
        calls["n"] += 1
        raise RuntimeError("sleeper down")

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch.object(
        sleeper, "PLAYERS_BACKGROUND_REFRESH", True
    ), patch("modules.sleeper.requests.get", side_effect=failing_get):
        assert sleeper.get_players() == {"1": {"full_name": "Old"}}
        deadline = time.time() + 10
        while sleeper._players_bg_in_flight and time.time() < deadline:
            time.sleep(0.01)
        for _ in range(5):
            assert sleeper.get_players() == {"1": {"full_name": "Old"}}

    assert calls["n"] == 1
    with open(cache_path, encoding="utf-8") as f:
        assert json.load(f) == {"1": {"full_name": "Old"}}


def test_default_mode_still_refreshes_aged_cache_synchronously(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write(cache_path, {"1": {"full_name": "Old"}}, age_seconds=_stale_age())

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch(
        "modules.sleeper.requests.get", return_value=_response({"1": {"full_name": "New"}})
    ):
        assert sleeper.get_players() == {"1": {"full_name": "New"}}


def test_failed_sync_refresh_falls_back_to_existing_file(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write(cache_path, {"1": {"full_name": "Old"}}, age_seconds=_stale_age())

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch(
        "modules.sleeper.requests.get", side_effect=RuntimeError("down")
    ):
        assert sleeper.get_players() == {"1": {"full_name": "Old"}}
        assert sleeper.get_players(refresh=True) == {"1": {"full_name": "Old"}}


@pytest.mark.parametrize("payload", [{}, [], None, "error"])
def test_empty_or_non_object_dump_never_replaces_a_good_cache(tmp_path, payload):
    cache_path = str(tmp_path / "sleeper_players.json")
    _write(cache_path, {"1": {"full_name": "Old"}}, age_seconds=_stale_age())

    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch(
        "modules.sleeper.requests.get", return_value=_response(payload)
    ):
        assert sleeper.get_players(refresh=True) == {"1": {"full_name": "Old"}}

    with open(cache_path, encoding="utf-8") as f:
        assert json.load(f) == {"1": {"full_name": "Old"}}


def test_empty_dump_without_any_cache_still_returns_empty(tmp_path):
    cache_path = str(tmp_path / "sleeper_players.json")
    with patch.object(sleeper, "PLAYERS_CACHE_PATH", cache_path), patch(
        "modules.sleeper.requests.get", return_value=_response({})
    ):
        assert sleeper.get_players() == {}


def test_mobile_api_lifespan_gate_keeps_tests_synchronous(monkeypatch):
    from services import mobile_api_service as svc

    monkeypatch.setattr(sleeper, "PLAYERS_BACKGROUND_REFRESH", False)
    svc._enable_background_sleeper_players_refresh()
    assert sleeper.PLAYERS_BACKGROUND_REFRESH is False
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("DYNASTYGM_TEST_MODE", raising=False)
    svc._enable_background_sleeper_players_refresh()
    assert sleeper.PLAYERS_BACKGROUND_REFRESH is True
