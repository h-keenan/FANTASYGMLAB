from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading
import time

import pandas as pd

from modules import players_refresh_flight, rankings


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "1",
                "name": "Current Player",
                "position": "WR",
                "is_current_fantasy_eligible": True,
                "valuation_authority_status": "canonical_provider_backed",
                "score": 5000,
                "dynasty_score": 5000,
                "value_score": 5000,
            }
        ]
    )


def _metadata_current_db(tmp_path) -> str:
    path = tmp_path / "players.db"
    with sqlite3.connect(path) as connection:
        _frame().to_sql("players", connection, index=False)
        rankings._write_player_universe_cache_metadata(connection, db_path=str(path))
    return str(path)


def test_valid_prepared_disk_snapshot_uses_metadata_current_fast_path(tmp_path, monkeypatch):
    db_path = _metadata_current_db(tmp_path)
    monkeypatch.setattr(
        "modules.structured_player_refresh.refresh_structured_player_state_from_disk",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("reconciliation must not run")),
    )
    rankings.clear_public_player_cache()
    result = rankings.load_players(db_path)
    assert tuple(result["player_id"]) == ("1",)
    assert result.attrs["public_player_load_path"] == "metadata_current_sqlite"
    assert result.attrs["public_player_cache_status"] == "miss"


def test_two_concurrent_sessions_single_flight_one_public_build(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    build_count = 0
    build_guard = threading.Lock()

    def slow_build(_db_path):
        nonlocal build_count
        with build_guard:
            build_count += 1
        entered.set()
        assert release.wait(2)
        frame = _frame()
        frame.attrs["public_player_load_path"] = "fixture"
        return frame

    monkeypatch.setattr(rankings, "public_player_source_fingerprint", lambda _p: (("fixture", True, 1, 1),))
    monkeypatch.setattr(rankings, "_load_players_uncached", slow_build)
    rankings.clear_public_player_cache()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(rankings.load_players, "fixture.db")
        assert entered.wait(1)
        second = pool.submit(rankings.load_players, "fixture.db")
        time.sleep(0.05)
        assert not first.done() and not second.done()
        release.set()
        first_frame = first.result(timeout=2)
        second_frame = second.result(timeout=2)
    assert build_count == 1
    assert tuple(first_frame["player_id"]) == tuple(second_frame["player_id"]) == ("1",)


def test_background_refresh_does_not_block_valid_foreground_cache(monkeypatch):
    release = threading.Event()
    entered = threading.Event()
    state = {"pending": True}
    players_refresh_flight.reset_process_refresh_state_for_tests()

    def background_build(_db_path, refresh=False):
        assert refresh is True
        entered.set()
        assert release.wait(2)
        return _frame()

    result = players_refresh_flight.schedule_deferred_players_refresh(
        db_path="fixture.db",
        build_players_table_fn=background_build,
        session_state=state,
        pending_key="pending",
        background=True,
    )
    assert result["role"] == "refresh_owner"
    assert entered.wait(1)

    monkeypatch.setattr(rankings, "public_player_source_fingerprint", lambda _p: (("warm", True, 1, 1),))
    monkeypatch.setattr(rankings, "_load_players_uncached", lambda _p: _frame())
    rankings.clear_public_player_cache()
    rankings.load_players("fixture.db")
    with ThreadPoolExecutor(max_workers=1) as pool:
        foreground = pool.submit(rankings.load_players, "fixture.db")
        foreground_frame = foreground.result(timeout=1)
    assert tuple(foreground_frame["player_id"]) == ("1",)
    assert players_refresh_flight.refresh_in_flight()
    release.set()
    assert players_refresh_flight.wait_for_refresh(timeout_s=2)
    assert players_refresh_flight.provider_refresh_call_count() == 1


def test_render_build_prepares_cache_before_web_process():
    render = open("render.yaml", encoding="utf-8").read()
    web_service = render.split("- type: web", 1)[1].split("- type: web", 1)[0]
    assert "python scripts/prepare_public_player_cache.py" in web_service
