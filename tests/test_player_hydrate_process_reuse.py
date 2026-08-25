"""Process reuse of the canonical public-player hydrate frame."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time
from unittest.mock import patch

import pandas as pd

from modules import player_hydrate_stages
from modules import rankings


def _frame(score: int = 100) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "name": "Alpha",
                "position": "WR",
                "dynasty_score": score,
                "value_score": score,
                "is_current_fantasy_eligible": True,
                "valuation_authority_status": "canonical_provider_backed",
                "score": score,
            }
        ]
    )
    frame.attrs["public_player_load_path"] = "fixture"
    return frame


def test_second_session_process_hit_skips_uncached_and_streamlit():
    rankings.clear_public_player_cache()
    calls = {"n": 0}

    def build(_path):
        calls["n"] += 1
        return _frame()

    with (
        patch.object(rankings, "public_player_source_fingerprint", return_value=(("fix", True, 1, 1),)),
        patch.object(rankings, "_load_players_uncached", side_effect=build),
        patch.object(
            rankings,
            "_cached_public_players",
            wraps=rankings._cached_public_players,
        ) as cached,
    ):
        first = rankings.load_players("hydrate-a.db")
        second = rankings.load_players("hydrate-a.db")

    assert calls["n"] == 1
    assert cached.call_count == 1
    assert first.attrs["public_player_cache_status"] == "miss"
    assert second.attrs["public_player_cache_status"] == "process_hit"
    first.loc[0, "dynasty_score"] = -1
    assert int(second.loc[0, "dynasty_score"]) == 100
    names = [row["name"] for row in player_hydrate_stages.recorded()]
    assert "process_frame_copy" in names


def test_source_fingerprint_change_misses_process_store():
    rankings.clear_public_player_cache()
    fingerprints = iter(
        [
            (("fix", True, 1, 1),),
            (("fix", True, 1, 1),),
            (("fix", True, 1, 2),),
        ]
    )

    def fingerprint(_path):
        return next(fingerprints)

    with (
        patch.object(rankings, "public_player_source_fingerprint", side_effect=fingerprint),
        patch.object(
            rankings,
            "_load_players_uncached",
            side_effect=[_frame(100), _frame(200)],
        ) as loader,
    ):
        first = rankings.load_players("hydrate-b.db")
        rankings.load_players("hydrate-b.db")
        changed = rankings.load_players("hydrate-b.db")

    assert loader.call_count == 2
    assert int(first.loc[0, "dynasty_score"]) == 100
    assert int(changed.loc[0, "dynasty_score"]) == 200
    assert changed.attrs["public_player_cache_status"] == "miss"


def test_clear_public_player_cache_drops_process_store():
    rankings.clear_public_player_cache()
    with (
        patch.object(rankings, "public_player_source_fingerprint", return_value=(("fix", True, 9, 9),)),
        patch.object(rankings, "_load_players_uncached", side_effect=[_frame(1), _frame(2)]) as loader,
    ):
        rankings.load_players("hydrate-c.db")
        rankings.load_players("hydrate-c.db")
        rankings.clear_public_player_cache()
        again = rankings.load_players("hydrate-c.db")
    assert loader.call_count == 2
    assert again.attrs["public_player_cache_status"] == "miss"


def test_hydrate_miss_records_exclusive_named_stages():
    rankings.clear_public_player_cache()
    with (
        patch.object(rankings, "public_player_source_fingerprint", return_value=(("fix", True, 3, 3),)),
        patch.object(rankings, "_load_players_uncached", return_value=_frame()),
    ):
        rankings.load_players("hydrate-d.db")
    names = [row["name"] for row in player_hydrate_stages.recorded()]
    assert "streamlit_cache_data" in names


def test_concurrent_first_loads_still_single_flight():
    rankings.clear_public_player_cache()
    entered = threading.Event()
    release = threading.Event()
    builds = {"n": 0}
    lock = threading.Lock()

    def slow(_path):
        with lock:
            builds["n"] += 1
        entered.set()
        assert release.wait(2)
        return _frame()

    with (
        patch.object(rankings, "public_player_source_fingerprint", return_value=(("fix", True, 4, 4),)),
        patch.object(rankings, "_load_players_uncached", side_effect=slow),
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(rankings.load_players, "hydrate-e.db")
            assert entered.wait(1)
            second = pool.submit(rankings.load_players, "hydrate-e.db")
            time.sleep(0.05)
            release.set()
            first.result(timeout=2)
            second.result(timeout=2)
    assert builds["n"] == 1
