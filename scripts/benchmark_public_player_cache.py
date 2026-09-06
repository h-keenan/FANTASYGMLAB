"""Sanitized CI/local benchmark for the canonical public-player cache."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import public_player_snapshot, rankings


EQUIVALENCE_FIELDS = [
    "player_id",
    "name",
    "position",
    "team",
    "age",
    "active",
    "status",
    "fantasy_positions",
    "is_current_fantasy_eligible",
    "dynasty_score",
    "value_score",
    "market_score",
    "injury_status",
    "injury_level",
]


def _elapsed_call():
    started = time.perf_counter()
    frame = rankings.load_players("data/players.db")
    return frame, (time.perf_counter() - started) * 1000


def main() -> None:
    timings = []

    def capture_timing(label, elapsed_ms, *, category="app", result_size=None):
        timings.append(
            {
                "operation": str(label),
                "duration_ms": round(float(elapsed_ms), 1),
                "category": str(category),
            }
        )
        return timings[-1]

    public_player_snapshot.invalidate_public_player_snapshot("data/players.db")
    rankings.clear_public_player_cache()
    with patch("modules.performance.record_timing", side_effect=capture_timing):
        built, snapshot_build_ms = _elapsed_call()
        snapshot_build_operations = list(timings)
        timings.clear()
        rankings.clear_public_player_cache()
        cold, cold_ms = _elapsed_call()
        snapshot_load_operations = list(timings)
        timings.clear()
        warm, warm_ms = _elapsed_call()
    fields = [field for field in EQUIVALENCE_FIELDS if field in cold.columns]
    def comparable(frame):
        result = frame[fields].reset_index(drop=True).copy()
        for column in result.columns:
            result[column] = result[column].where(result[column].notna(), pd.NA)
        return result
    pd.testing.assert_frame_equal(
        comparable(built),
        comparable(cold),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        comparable(cold),
        comparable(warm),
        check_dtype=False,
    )
    data_path, metadata_path = public_player_snapshot.snapshot_paths("data/players.db")
    payload = {
        "benchmark": "public_player_cache",
        "environment": "ci_or_local_not_render_production",
        "snapshot_build_ms": round(snapshot_build_ms, 1),
        "cold_ms": round(cold_ms, 1),
        "warm_ms": round(warm_ms, 1),
        "snapshot_size_bytes": int(data_path.stat().st_size + metadata_path.stat().st_size),
        "row_count": int(len(warm)),
        "memory_mb": round(
            int(warm.memory_usage(index=True, deep=True).sum()) / (1024 * 1024),
            2,
        ),
        "equivalent": True,
        "snapshot_build_operations": sorted(
            snapshot_build_operations,
            key=lambda item: item["duration_ms"],
            reverse=True,
        )[:5],
        "snapshot_load_operations": sorted(
            [
                item
                for item in snapshot_load_operations
                if item["operation"] != "public_player_cache_retrieval"
            ],
            key=lambda item: item["duration_ms"],
            reverse=True,
        )[:5],
    }
    print("PUBLIC_PLAYER_CACHE_BENCHMARK " + json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
