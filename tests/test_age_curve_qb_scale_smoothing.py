import numpy as np
import pandas as pd
import pytest

from modules import league_value_settings as lvs
from modules.trade_hub_engine import apply_strategy_age_curve


def _frame(position, ages, score=5000):
    return pd.DataFrame(
        {
            "position": position,
            "age": [float(a) for a in ages],
            "dynasty_score": score,
            "league_dynasty_score": score,
            "base_score": score,
        }
    )


@pytest.mark.parametrize("strategy", ["contender", "fringe_contender", "retool", "rebuild", "tank"])
@pytest.mark.parametrize("position", ["QB", "RB", "WR", "TE"])
def test_strategy_curve_has_no_large_step_between_adjacent_ages(strategy, position):
    ages = list(range(20, 41))
    out = apply_strategy_age_curve(_frame(position, ages, 10000), strategy, "dynasty_score")
    mult = out["strategy_preference_multiplier"].to_numpy()
    # Old curves jumped up to 0.18 in one year; now every year-step is small.
    assert np.abs(np.diff(mult)).max() <= 0.13, (strategy, position)


def test_rebuild_rb_ramps_instead_of_cliff():
    out = apply_strategy_age_curve(_frame("RB", [26, 27, 28, 29, 30]), "rebuild", "dynasty_score")
    m = out["strategy_preference_multiplier"].tolist()
    assert m[1] == pytest.approx(1.01)
    assert m[2] == pytest.approx(0.91)
    assert m[3] == pytest.approx(0.82)
    assert m[4] == pytest.approx(0.82)


def test_missing_age_is_neutral():
    df = _frame("RB", [28])
    df["age"] = np.nan
    out = apply_strategy_age_curve(df, "tank", "dynasty_score")
    assert out["strategy_preference_multiplier"].iloc[0] == 1.0


def _qb_mult(fmt, score, age):
    df = _frame("QB", [age], score)
    return float(lvs.league_settings_adjustment_components(df, {"qb_format": fmt})["league_adj_qb_scarcity"].iloc[0])


def test_qb_uplift_not_flat_and_ordered_by_tier_and_age():
    assert _qb_mult("Superflex", 5000, 28) == pytest.approx(1.35)
    assert _qb_mult("Superflex", 2000, 28) > _qb_mult("Superflex", 5000, 28) > _qb_mult("Superflex", 9000, 28)
    assert _qb_mult("Superflex", 2000, 38) < _qb_mult("Superflex", 2000, 28)
    assert _qb_mult("2QB", 5000, 28) == pytest.approx(1.55)
    assert _qb_mult("2QB", 5000, 28) > _qb_mult("Superflex", 5000, 28)


def test_qb_uplift_continuous_and_1qb_unchanged():
    vals = [_qb_mult("Superflex", 3000, a) for a in range(30, 42)]
    assert max(abs(np.diff(vals))) < 0.05
    assert _qb_mult("1QB", 3000, 28) == 1.0
    wr = _frame("WR", [26])
    assert lvs.league_settings_adjustment_components(wr, {"qb_format": "Superflex"})["league_adj_qb_scarcity"].iloc[0] == 1.0
