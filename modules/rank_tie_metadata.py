"""Shared tie-detection metadata for dense-rank columns.

Split out of modules/league_rankings.py so modules/team_eval.py (which
league_rankings.py itself imports from) can use the exact same helper
without creating a circular import between the two modules.
"""

from __future__ import annotations

import pandas as pd


def add_rank_tie_metadata(df: pd.DataFrame, rank_columns: list[str]) -> pd.DataFrame:
    """Add `<col>_tie_count` (int, how many rows share that exact rank value
    — 1 when unique) and `<col>_tied` (bool, True when tie_count >= 2) for
    every column name in `rank_columns` that exists in `df`.

    The rank columns themselves are already correct: they're built with
    `Series.rank(method="dense", ...)`, so ties already share one identical
    integer rank. What's missing is display metadata — today the UI renders
    a bare "#4" whether that rank is unique to one team or shared by
    several, which reads as more precise than it is. This is computed once
    here so every consumer (mobile API responses, web rendering) can show
    "T4" (tied) vs "#4" (unique) without each one re-deriving tie state
    independently.

    Safe on an empty frame or a league where every row shares one rank
    (tie_count == len(df) for all rows, tied True for all) — both are
    ordinary inputs, not error cases.
    """

    if df.empty:
        return df
    df = df.copy()
    for column in rank_columns:
        if column not in df.columns:
            continue
        tie_count_col = f"{column}_tie_count"
        tied_col = f"{column}_tied"
        counts = df[column].value_counts(dropna=True)
        df[tie_count_col] = df[column].map(counts).fillna(1).astype(int)
        df[tied_col] = df[tie_count_col] > 1
    return df
