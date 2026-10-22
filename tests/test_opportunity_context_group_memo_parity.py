"""enrich_opportunity_context (per-group memo) must equal the original
implementation (_enrich_opportunity_context_full) exactly."""

import random

import numpy as np
import pandas as pd
import pytest

from modules import rankings

LABELS = [
    "Elite Opportunity",
    "Strong Opportunity",
    "Starter At Risk",
    "Backup With Upside",
    "Handcuff",
    "Committee Back",
    "Buried Depth",
    "Unknown",
    "",
    None,
]
TRENDS = ["Stable", "Rising", "Fragile", "Unknown", None]
STATUSES = ["Active", "Inactive", "Injured Reserve", "Practice Squad", None, ""]
INJURIES = ["Out", "Doubtful", "Questionable", "IR", "NA", None, "", "Hamstring"]
FLAGS = ["", "depth_chart", "depth_chart|snap_share", None, "team_competition"]


def _frame(seed: int, n: int = 400, *, optional: bool = True) -> pd.DataFrame:
    rng = random.Random(seed)
    teams = [f"T{i}" for i in range(14)] + ["", None]
    rows = []
    for i in range(n):
        rows.append(
            {
                "player_id": str(i),
                "team": rng.choice(teams),
                "position": rng.choice(["QB", "RB", "WR", "TE", "rb"]),
                "opportunity_label": rng.choice(LABELS),
                "opportunity_explanation": rng.choice(["", "Some text.", "Other text", None]),
                "workload_trend": rng.choice(TRENDS),
                "opportunity_score": rng.choice([None, 0, 3000, 6500, 9800, 10000]),
                "opportunity_confidence": rng.choice([None, 0, 50, 70, 99]),
                "opportunity_source_flags": rng.choice(FLAGS),
                "market_score": rng.choice([None, 0.0, 10.5, 40.0, 55.0, 55.0, 80.25]),
                "depth_chart_slot": rng.choice([None, 0, 1, 1, 2, 3, 4]),
                "depth_chart_order": rng.choice([None, 0, 1, 2]),
                "years_exp": rng.choice([None, 0, 1, 2, 5, 9]),
                "age": rng.choice([None, 21, 23.5, 24, 27, 31]),
                "projected_starter": rng.choice([True, False, None]),
                "status": rng.choice(STATUSES),
                "injury_status": rng.choice(INJURIES),
            }
        )
    df = pd.DataFrame(rows)
    if not optional:
        df = df.drop(columns=["projected_starter", "status", "injury_status"])
    return df


def _assert_same(a: pd.DataFrame, b: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(a, b, check_exact=True, check_dtype=True)
    assert a.to_json(orient="split") == b.to_json(orient="split")


@pytest.fixture(autouse=True)
def _fresh_memo():
    rankings.clear_opportunity_group_memo()
    yield
    rankings.clear_opportunity_group_memo()


@pytest.mark.parametrize("seed", range(8))
def test_matches_original_cold_and_warm(seed):
    df = _frame(seed)
    expected = rankings._enrich_opportunity_context_full(df)
    _assert_same(rankings.enrich_opportunity_context(df), expected)
    # second call is served from the memo and must still be identical
    _assert_same(rankings.enrich_opportunity_context(df), expected)
    assert rankings.opportunity_group_memo_stats()["hits"] > 0


def test_matches_original_without_optional_columns():
    df = _frame(3, optional=False)
    _assert_same(
        rankings.enrich_opportunity_context(df),
        rankings._enrich_opportunity_context_full(df),
    )


def test_does_not_mutate_input_and_handles_empty():
    df = _frame(1, 50)
    before = df.copy()
    rankings.enrich_opportunity_context(df)
    pd.testing.assert_frame_equal(df, before)
    empty = df.iloc[0:0]
    assert rankings.enrich_opportunity_context(empty) is empty
    nocols = df.drop(columns=["team"])
    pd.testing.assert_frame_equal(
        rankings.enrich_opportunity_context(nocols),
        rankings._enrich_opportunity_context_full(nocols),
    )


def test_non_default_and_duplicate_index_fall_back_identically():
    df = _frame(5, 120)
    shuffled = df.sample(frac=1.0, random_state=1)
    _assert_same(
        rankings.enrich_opportunity_context(shuffled),
        rankings._enrich_opportunity_context_full(shuffled),
    )
    dup = df.copy()
    dup.index = [i // 2 for i in range(len(dup))]
    # the original cannot handle duplicate labels; the fast path defers to it
    with pytest.raises(ValueError):
        rankings._enrich_opportunity_context_full(dup)
    with pytest.raises(ValueError):
        rankings.enrich_opportunity_context(dup)


def test_incremental_refresh_recomputes_only_changed_groups():
    df = _frame(7, 600)
    rankings.enrich_opportunity_context(df)
    stats = rankings.opportunity_group_memo_stats()
    groups = stats["misses"]
    assert groups > 5
    changed = df.copy()
    row = changed.index[changed["team"] == "T1"][0]
    changed.loc[row, "injury_status"] = "Out"
    changed.loc[row, "status"] = "Inactive"
    expected = rankings._enrich_opportunity_context_full(changed)
    before = rankings.opportunity_group_memo_stats()
    _assert_same(rankings.enrich_opportunity_context(changed), expected)
    after = rankings.opportunity_group_memo_stats()
    assert after["misses"] - before["misses"] <= 1
    assert after["hits"] - before["hits"] >= groups - 2


def test_every_input_change_invalidates():
    base = _frame(11, 300)
    rankings.enrich_opportunity_context(base)
    for col, value in [
        ("market_score", 99.5),
        ("age", 22),
        ("years_exp", 1),
        ("depth_chart_slot", 3),
        ("projected_starter", True),
        ("opportunity_label", "Backup With Upside"),
        ("workload_trend", "Stable"),
        ("opportunity_score", 1234),
        ("opportunity_confidence", 11),
        ("opportunity_source_flags", "x|y"),
        ("opportunity_explanation", "Changed text."),
        ("status", "Inactive"),
        ("injury_status", "Out"),
    ]:
        changed = base.copy()
        idx = changed.index[changed.groupby(["team", "position"]).cumcount() == 1][0]
        changed.at[idx, col] = value
        _assert_same(
            rankings.enrich_opportunity_context(changed),
            rankings._enrich_opportunity_context_full(changed),
        )


def test_numpy_typed_inputs_match():
    df = _frame(13, 200)
    df["market_score"] = df["market_score"].astype(float).fillna(0.0).astype(np.float32)
    df["depth_chart_slot"] = df["depth_chart_slot"].fillna(0).astype(np.int32)
    _assert_same(
        rankings.enrich_opportunity_context(df),
        rankings._enrich_opportunity_context_full(df),
    )
