import numpy as np
import pandas as pd

from modules import rankings


def test_name_key_strips_suffix_punctuation_accents():
    base = rankings._normalize_name("Kenneth Walker")
    assert rankings._normalize_name("Kenneth Walker III") == base
    assert rankings._normalize_name("Brian Thomas Jr.") == rankings._normalize_name("Brian Thomas")
    assert rankings._normalize_name("Ja'Marr Chase") == "jamarrchase"
    assert rankings._normalize_name("José Alvarado, Sr.") == rankings._normalize_name("Jose Alvarado")
    assert rankings._normalize_name("V") == "v"


def test_teamless_veteran_value_capped_but_rookie_and_market_backed_kept():
    df = pd.DataFrame(
        {
            "team": ["", "", "", "KC"],
            "years_exp": [12, 0, 12, 12],
            "fantasycalc_value": [0, 0, 500, 0],
            "value": [7317.0, 7317.0, 7317.0, 7317.0],
        }
    )
    out = rankings._cap_teamless_veteran_values(df)
    assert out.loc[0, "value"] == rankings.TEAMLESS_VETERAN_VALUE_CAP
    assert out.loc[1, "value"] == 7317.0
    assert out.loc[2, "value"] == 7317.0
    assert out.loc[3, "value"] == 7317.0


def test_injury_discount_is_age_aware():
    young = rankings.injury_multiplier_for_age("Inactive", "IR", 23)
    old = rankings.injury_multiplier_for_age("Inactive", "IR", 34)
    assert young > old
    assert rankings.injury_multiplier_for_age("Inactive", "IR", None) == rankings.injury_multiplier("Inactive", "IR")
    assert rankings.injury_multiplier_for_age("Active", "", 30) == 1.0


def test_null_age_is_neutral_and_not_sentinel():
    assert rankings.age_multiplier("WR", None) == 1.0
    assert rankings.age_multiplier("WR", 99) == 1.0
    frame = pd.DataFrame(
        {
            "age": [None, 25.0],
            "opportunity_label": ["", ""],
            "opportunity_explanation": ["", ""],
            "workload_trend": ["", ""],
            "opportunity_score": [0, 0],
        }
    )
    rankings._normalize_opportunity_inputs(frame)
    assert pd.isna(frame.loc[0, "age"])


def _season_frame(n=20, boost_idx=None):
    market = np.linspace(9000, 1000, n)
    return pd.DataFrame(
        {
            "position": ["WR"] * n,
            "games_played": [8] * n,
            "ppg": list(np.linspace(20, 5, n)),
        }
    ), pd.Series(market)


def test_in_season_adjustment_bounded_and_directional():
    frame, market = _season_frame()
    # worst-market player is the best producer
    frame.loc[n_last := len(frame) - 1, "ppg"] = 30.0
    composite = market * 0.6
    risk = pd.Series(1.0, index=frame.index)
    adj = rankings._in_season_production_adjustment(frame, market, composite, risk)
    assert adj.iloc[n_last] > 0
    bound = rankings.IN_SEASON_MAX_SWING * composite.clip(lower=rankings.IN_SEASON_SWING_FLOOR)
    assert (adj.abs() <= bound + 1e-6).all()


def test_in_season_adjustment_grows_with_games_and_ignores_small_samples():
    frame, market = _season_frame()
    frame.loc[len(frame) - 1, "ppg"] = 30.0
    composite = market * 0.6
    risk = pd.Series(1.0, index=frame.index)
    frame["games_played"] = 3
    low = rankings._in_season_production_adjustment(frame, market, composite, risk).iloc[-1]
    frame["games_played"] = 14
    high = rankings._in_season_production_adjustment(frame, market, composite, risk).iloc[-1]
    assert 0 < low <= high
    frame["games_played"] = 2
    assert rankings._in_season_production_adjustment(frame, market, composite, risk).abs().sum() == 0
    small = frame.head(5).assign(games_played=10)
    assert rankings._in_season_production_adjustment(small, market.head(5), composite.head(5), risk.head(5)).abs().sum() == 0


def test_missing_ppg_derived_from_points_and_games():
    frame = pd.DataFrame(
        {"games_played": [4, 0, 3], "fantasy_points_ppr": [40.0, 0.0, None], "ppg": [None, None, None]}
    )
    out = rankings._fill_missing_ppg(frame)
    assert out.loc[0, "ppg"] == 10.0
    assert pd.isna(out.loc[1, "ppg"]) and pd.isna(out.loc[2, "ppg"])
