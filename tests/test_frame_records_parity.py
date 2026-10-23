import math

import numpy as np
import pandas as pd
import pytest

from modules.frame_records import _fast_dtype, frame_records


def _same(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if a is pd.NA and b is pd.NA:
        return True
    if a is pd.NaT and b is pd.NaT:
        return True
    if isinstance(a, (list, tuple, dict, set)):
        return type(a) is type(b) and a == b
    return type(a) is type(b) and a == b


def _assert_equivalent(frame):
    expected = frame.to_dict("records")
    got = frame_records(frame)
    assert len(got) == len(expected)
    for want_row, got_row in zip(expected, got):
        assert list(want_row) == list(got_row)
        for key in want_row:
            assert _same(want_row[key], got_row[key]), (key, want_row[key], got_row[key])


def _zoo(n=40):
    rng = np.random.default_rng(1)
    return pd.DataFrame(
        {
            "player_id": [str(i) for i in range(n)],
            "f": np.where(rng.random(n) < 0.2, np.nan, rng.random(n)),
            "i": rng.integers(0, 100, n),
            "b": rng.random(n) < 0.5,
            "s": [None if i % 7 == 0 else f"name {i}" for i in range(n)],
            "o": [None if i % 5 == 0 else ([i] if i % 2 else {"k": i}) for i in range(n)],
            "d": pd.to_datetime(["2026-01-01"] * n),
            "dn": [pd.NaT if i % 4 == 0 else pd.Timestamp("2026-02-02") for i in range(n)],
            "ni": pd.array([None if i % 3 == 0 else i for i in range(n)], dtype="Int64"),
            "nb": pd.array([None if i % 3 == 0 else bool(i % 2) for i in range(n)], dtype="boolean"),
            "c": pd.Categorical([["a", "b", None][i % 3] for i in range(n)]),
            "u8": rng.integers(0, 5, n).astype(np.uint8),
            "f32": rng.random(n).astype(np.float32),
            "mixed": [1 if i % 2 else "x" for i in range(n)],
        }
    )


def test_matches_to_dict_records_on_a_dtype_zoo():
    frame = _zoo()
    _assert_equivalent(frame)
    _assert_equivalent(frame.iloc[[3, 1, 30]])
    sliced = frame.iloc[5:8]
    sliced.index = ["x", "y", "z"]
    _assert_equivalent(sliced)


def test_matches_on_empty_one_row_and_duplicate_columns():
    frame = _zoo()
    assert frame_records(frame.iloc[0:0]) == frame.iloc[0:0].to_dict("records") == []
    _assert_equivalent(frame.iloc[:1])
    dup = pd.concat([frame[["player_id", "f"]], frame[["f"]]], axis=1)
    _assert_equivalent(dup)
    assert frame_records(None) == []


def test_player_injury_index_identical_with_either_record_builder(monkeypatch):
    from modules import rankings

    rng = np.random.default_rng(3)
    n = 60
    frame = pd.DataFrame(
        {
            "player_id": [str(i) for i in range(n)],
            "name": [f"Player {i}" for i in range(n)],
            "position": rng.choice(["QB", "RB", "WR", "TE"], n),
            "team": rng.choice(["KC", "SF", None], n),
            "status": rng.choice(["Active", "Inactive", "Injured Reserve", None], n),
            "injury_status": rng.choice(["Out", "Questionable", "Doubtful", None, "IR"], n),
            "news_updated": rng.integers(1_700_000_000_000, 1_800_000_000_000, n),
            "injury_risk_score": np.where(rng.random(n) < 0.3, np.nan, rng.random(n) * 3),
            "value_score": rng.random(n) * 9000,
            "dynasty_score": rng.random(n) * 9000,
            "opportunity_label": rng.choice(["Handcuff", "Backup With Upside", None, "Elite Opportunity"], n),
            "age": rng.integers(21, 35, n),
            "role": rng.choice(["Starter", "core piece", None], n),
        }
    )
    clock = 1_790_000_000.0
    fast = rankings.build_player_injury_index(frame, now=clock)
    monkeypatch.setattr(rankings, "frame_records", lambda f: f.to_dict("records"))
    reference = rankings.build_player_injury_index(frame, now=clock)
    assert repr(fast) == repr(reference)


def test_fast_path_used_for_player_shaped_frames_and_boxes_object_cells():
    n = 30
    frame = pd.DataFrame(
        {
            "player_id": [str(i) for i in range(n)],
            "f": [float(i) if i % 4 else np.nan for i in range(n)],
            "i": list(range(n)),
            "b": [bool(i % 2) for i in range(n)],
            "o": [np.float64(i) if i % 2 else (None if i % 3 else np.int64(i)) for i in range(n)],
        }
    )
    assert all(_fast_dtype(d) for d in frame.dtypes)
    _assert_equivalent(frame)
    _assert_equivalent(frame.iloc[[7, 2]])
    assert all(type(row["o"]) in (float, int, type(None)) for row in frame_records(frame))
