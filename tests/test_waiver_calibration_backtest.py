"""Guards that the waiver calibration backtest evaluates the constants production ships."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import waiver_calibration_backtest as bt  # noqa: E402
from modules import faab, rankings  # noqa: E402


def _stat_row(points):
    return {"weekly": [{"week": i + 1, "fantasy_points_ppr": p, "games_played": 1} for i, p in enumerate(points)]}


def test_breakout_flag_matches_production_breakout_catalyst():
    flag = bt.breakout_flag(faab.BREAKOUT_MIN_POINTS, faab.BREAKOUT_MIN_JUMP, faab.BREAKOUT_MIN_RATIO)
    cases = [
        [6, 7, 5, 22],      # clear breakout
        [6, 7, 5, 11],      # under the 12-point floor
        [14, 15, 13, 24],   # jump +10 but ratio < 1.8
        [3, 2, 4, 13],      # floor, jump and ratio all met
        [10, 10, 10, 19],   # ratio 1.9, jump 9 -> flagged
    ]
    for pts in cases:
        prod = faab.breakout_catalyst(_stat_row(pts), current_week=len(pts) + 1) is not None
        assert flag({"pts": [float(p) for p in pts]}) is prod, pts


def test_backtest_recency_formulation_matches_rankings_constants():
    assert rankings.RECENCY_WINDOW == 4
    weights = rankings.RECENCY_WEIGHTS
    assert abs(weights[1] / weights[0] - 0.75) < 1e-9
    assert rankings.RECENCY_TREND_CLIP == 0.40
