"""Top-5 presentation ownership contracts after #269 follow-up."""

from pathlib import Path

from modules import league_display


ROOT = Path(__file__).resolve().parents[1]


def test_format_score_and_rank_edge_cases():
    assert league_display._format_score(None) == "0"
    assert league_display._format_score(float("nan")) == "0"
    assert league_display._format_score(0) == "0"
    assert league_display._format_score(12) == "12"
    assert league_display._format_score(12.6) == "13"
    assert league_display._format_score(1234.4) == "1,234"
    assert league_display._format_rank(None) == "N/A"
    assert league_display._format_rank(float("nan")) == "N/A"
    assert league_display._format_rank(0) == "N/A"
    assert league_display._format_rank(-1) == "N/A"
    assert league_display._format_rank(1) == "#1"
    assert league_display._format_rank(12.4) == "#12"
