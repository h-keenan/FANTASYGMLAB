"""ESPN id -> Sleeper id crosswalk (modules.espn_player_crosswalk). No network."""

from __future__ import annotations

import pytest

from modules import espn_player_crosswalk as crosswalk

CSV = (
    "mfl_id,sleeper_id,espn_id,name\n"
    "1,9226,4429160,De'Von Achane\n"
    "2,9493,4426515,Puka Nacua\n"
    "3,NA,123,No Sleeper Id\n"
    "4,555,NA,No ESPN Id\n"
    "5,700,999,Conflict A\n"
    "6,701,999,Conflict B\n"
)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(crosswalk, "DYNASTYPROCESS_PLAYER_IDS_CACHE_PATH", str(tmp_path / "db_playerids.csv"))
    crosswalk.clear_cache()
    yield tmp_path
    crosswalk.clear_cache()


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


def test_fetches_caches_and_drops_missing_and_conflicting_ids(monkeypatch, _isolated_cache):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _Response(CSV.encode())

    monkeypatch.setattr(crosswalk.requests, "get", fake_get)

    sleeper_players = {
        "4881": {"full_name": "Lamar Jackson", "espn_id": 3916387},
        "9226": {"full_name": "De'Von Achane", "espn_id": None},
        # Sleeper disagrees with DynastyProcess for 4426515: dropped.
        "1111": {"full_name": "Wrong Row", "espn_id": "4426515"},
    }
    result = crosswalk.load_espn_crosswalk(sleeper_players)

    assert calls == [crosswalk.DYNASTYPROCESS_PLAYER_IDS_URL]
    assert result == {"3916387": "4881", "4429160": "9226"}
    assert (_isolated_cache / "db_playerids.csv").exists()

    # Served from the on-disk cache on the next process-cache miss.
    crosswalk.clear_cache()
    monkeypatch.setattr(crosswalk.requests, "get", lambda *a, **k: pytest.fail("refetched a fresh cache"))
    assert ("4429160", "9226") in crosswalk.load_dynastyprocess_pairs()


def test_fetch_failure_is_fail_neutral(monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(crosswalk.requests, "get", boom)

    assert crosswalk.load_dynastyprocess_pairs() == []
    assert crosswalk.load_espn_crosswalk({"4881": {"espn_id": "3916387"}}) == {"3916387": "4881"}
