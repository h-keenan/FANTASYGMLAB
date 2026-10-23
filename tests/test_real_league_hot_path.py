"""Real-league Dashboard and Trade Hub modal hot-path contracts."""

from pathlib import Path

import pandas as pd

from modules import hot_path_profile
from modules import prepared_player_frame


ROOT = Path(__file__).resolve().parents[1]


def test_hot_path_profile_ranks_top_spans_with_percentages():
    hot_path_profile.begin("fixture")
    hot_path_profile.record("slow", 800.0, cache_status="miss")
    hot_path_profile.record("fast", 200.0, cache_status="hit")
    payload = hot_path_profile.report(top_n=10)
    assert payload["span_sum_ms"] == 1000.0
    assert payload["top"][0]["name"] == "slow"
    assert "unaccounted_ms" in payload
    assert "python_complete_ms" in payload
    assert payload["top"][0]["pct_of_wall"] > 0
    assert payload["top"][1]["name"] == "fast"
