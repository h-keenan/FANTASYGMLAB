"""modules.player_search: matching over the full valued pool, no value cutoff."""

from __future__ import annotations

import pandas as pd

from modules import player_search


def _pool() -> pd.DataFrame:
    rows = [
        ("1", "Josh Allen", "QB", "BUF", 9000),
        ("2", "Josh Allen", "LB", "JAX", 300),
        ("3", "Carson Beck", "QB", "ARI", 156),
        ("4", "Amon-Ra St. Brown", "WR", "DET", 8000),
        ("5", "Marvin Harrison Jr.", "WR", "ARI", 7000),
        ("6", "D'Andre Swift", "RB", "CHI", 3000),
    ]
    return pd.DataFrame(rows, columns=["player_id", "name", "position", "team", "dynasty_score"])


def _names(df: pd.DataFrame) -> list[str]:
    return list(df["player_id"])


def test_low_value_player_is_found_not_dropped():
    out = player_search.search_ranked_players(_pool(), "carson beck", score_field="dynasty_score")
    assert _names(out) == ["3"]


def test_partial_reversed_and_team_tokens_match():
    pool = _pool()
    assert _names(player_search.search_ranked_players(pool, "beck", score_field="dynasty_score")) == ["3"]
    assert _names(player_search.search_ranked_players(pool, "beck carson", score_field="dynasty_score")) == ["3"]
    assert _names(player_search.search_ranked_players(pool, "carson ari", score_field="dynasty_score")) == ["3"]


def test_punctuation_and_suffix_insensitive():
    pool = _pool()
    assert _names(player_search.search_ranked_players(pool, "amon ra st brown", score_field="dynasty_score")) == ["4"]
    assert _names(player_search.search_ranked_players(pool, "marvin harrison", score_field="dynasty_score")) == ["5"]
    assert _names(player_search.search_ranked_players(pool, "dandre swift", score_field="dynasty_score")) == ["6"]


def test_same_name_ordered_by_value_and_position_filter():
    pool = _pool()
    assert _names(player_search.search_ranked_players(pool, "josh allen", score_field="dynasty_score")) == ["1", "2"]
    assert _names(player_search.search_ranked_players(pool, "josh allen", score_field="dynasty_score", position="LB")) == ["2"]


def test_exact_beats_prefix_beats_value():
    pool = pd.DataFrame(
        [("1", "Josh Allen Jr", "WR", "NYJ", 9000), ("2", "Josh", "RB", "NYJ", 1)],
        columns=["player_id", "name", "position", "team", "dynasty_score"],
    )
    assert _names(player_search.search_ranked_players(pool, "josh", score_field="dynasty_score")) == ["2", "1"]


def test_empty_query_and_empty_pool_return_nothing():
    assert player_search.search_ranked_players(_pool(), "  ", score_field="dynasty_score").empty
    assert player_search.search_ranked_players(pd.DataFrame(), "x", score_field="dynasty_score").empty
