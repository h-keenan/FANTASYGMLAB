"""Helpers of the walk-forward signal experiments (scripts/projection_walkforward_signals.py)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import projection_walkforward_signals as sig  # noqa: E402


def _ext(rows):
    return pd.DataFrame(rows, columns=["season", "week", "pos", "est", "actual", "played"])


def test_tracker_uses_only_earlier_weeks():
    # week 3 has a huge miss; it must not move week 3's own correction, only later weeks'
    ext = _ext([(2022, 1, "WR", 10.0, 10.0, True), (2022, 2, "WR", 10.0, 10.0, True), (2022, 3, "WR", 10.0, 40.0, True),
                (2022, 4, "WR", 10.0, 10.0, True)])
    b = sig.tracker(ext, 4.0, "add", "all")
    assert b[0] == 0.0 and b[2] == pytest.approx(0.0)
    assert b[3] > 0.0


def test_tracker_ignores_players_who_did_not_play():
    ext = _ext([(2022, 1, "WR", 10.0, 0.0, False), (2022, 2, "WR", 10.0, 10.0, True)])
    assert sig.tracker(ext, 4.0, "add", "all")[1] == 0.0


def test_ratio_groups_are_relative_to_base_and_shrunk():
    f = pd.DataFrame({"g": ["none"] * 200 + ["Q"] * 100, "est": [10.0] * 300, "actual": [10.0] * 200 + [8.0] * 100})
    m = sig.fit_ratio_groups(f, ["g"], "none", n0=100.0)
    assert m[("none",)] == pytest.approx(1.0)
    assert m[("Q",)] == pytest.approx(1 + (0.8 - 1) * 100 / 200)


def test_teammate_lost_excludes_the_player_himself():
    f = pd.DataFrame({"season": [2022] * 3, "week": [5] * 3, "team": ["AAA"] * 3, "pos": ["RB"] * 3,
                      "est": [12.0, 6.0, 4.0], "inj": ["D", "none", "none"]})
    assert list(sig.teammate_lost(f)) == [0.0, 12.0, 12.0]


def test_missing_signal_rows_stay_unadjusted():
    f = pd.DataFrame({"pos": ["WR", "WR"], "est": [10.0, 10.0], "inj": ["none", "Q"], "inj_qd": ["none", "Q"],
                      "rank": [np.nan, np.nan], "has_depth": [False, False], "season": [2022, 2022], "week": [5, 5],
                      "team": ["A", "A"]})
    s = sig.Signals(("injqd", "depth"))
    s.inj_mult = {"Q": 0.9}
    out = s.apply(f, "est")
    assert out[0] == 10.0 and out[1] == pytest.approx(9.0)
