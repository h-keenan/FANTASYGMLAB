"""Sanitized CI/local benchmark for the canonical public-player cache."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import rankings


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
    rankings.clear_public_player_cache()
    cold, cold_ms = _elapsed_call()
    warm, warm_ms = _elapsed_call()
    fields = [field for field in EQUIVALENCE_FIELDS if field in cold.columns]
    pd.testing.assert_frame_equal(
        cold[fields].reset_index(drop=True),
        warm[fields].reset_index(drop=True),
        check_dtype=True,
    )
    payload = {
        "benchmark": "public_player_cache",
        "environment": "ci_or_local_not_render_production",
        "cold_ms": round(cold_ms, 1),
        "warm_ms": round(warm_ms, 1),
        "row_count": int(len(warm)),
        "memory_mb": round(
            int(warm.memory_usage(index=True, deep=True).sum()) / (1024 * 1024),
            2,
        ),
        "equivalent": True,
    }
    print("PUBLIC_PLAYER_CACHE_BENCHMARK " + json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
