"""Contracts for RC performance audit engineering optimizations."""

from pathlib import Path

from modules.rankings import _injury_level_cached, injury_level


ROOT = Path(__file__).resolve().parents[1]


def test_injury_level_cache_preserves_classification_and_hits():
    _injury_level_cached.cache_clear()
    assert injury_level("Out", "Questionable") == injury_level("out", "questionable")
    assert injury_level("IR", "") == "major"
    assert injury_level("Active", "") == "healthy"
    info = _injury_level_cached.cache_info()
    assert info.hits >= 1
    assert info.misses >= 1
