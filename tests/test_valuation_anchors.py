import pandas as pd
import pytest

from modules import league_value_settings as lvs
from modules import rankings, valuation_anchors as va

ONE_QB = {"league_size": 12, "qb_count": 1, "superflex_count": 0, "rb_count": 2, "wr_count": 2, "te_count": 1, "regular_flex_count": 1}
SUPERFLEX = {**ONE_QB, "superflex_count": 1}


def _pool(n_qb=30):
    rows = [
        {
            "player_id": f"qb{i}", "position": "QB", "age": 27, "market_score": 9000 - i * 250,
            "role_score": 8500, "opportunity_score": 8800, "production_score": 5000, "scarcity_score": 0,
            "risk_multiplier": 1.0, "dynasty_score": 6000, "value_score": 6000, "score": 6000,
        }
        for i in range(n_qb)
    ]
    rows.append({
        "player_id": "depth", "position": "WR", "age": 25, "market_score": 0,
        "role_score": 3800, "opportunity_score": 2800, "production_score": 2200, "scarcity_score": 0,
        "risk_multiplier": 1.0, "dynasty_score": 900, "value_score": 900, "score": 900,
    })
    return pd.DataFrame(rows)


def test_constants_match_the_composite():
    assert va.ROLE_WEIGHT == rankings.COMPOSITE_WEIGHT_ROLE
    assert va.OPPORTUNITY_WEIGHT == rankings.COMPOSITE_WEIGHT_OPPORTUNITY
    assert va.PRODUCTION_WEIGHT == rankings.COMPOSITE_WEIGHT_PRODUCTION
    assert va.PRODUCTION_NEUTRAL == rankings.PRODUCTION_NEUTRAL_ANCHOR
    assert va.OPPORTUNITY_NEUTRAL == rankings.OPPORTUNITY_NEUTRAL_ANCHOR


def test_demand_follows_league_format():
    assert va.starting_demand_by_position(ONE_QB)["QB"] == 12
    assert va.starting_demand_by_position(SUPERFLEX)["QB"] == 24


def test_non_starting_qb_loses_the_saturated_anchor_credit_smoothly():
    adj = va.starting_demand_adjustment(_pool(), ONE_QB)
    qb = adj.iloc[:30]
    assert (qb.iloc[:12] == 0).all()  # starters keep full credit
    full = -(0.06 * (8500 - 3800) + 0.10 * (8800 - 2800))
    assert qb.iloc[15] == pytest.approx(full * 4 / 6, abs=1)  # rank 16 of demand 12: two thirds faded
    assert full - 1 <= qb.iloc[29] <= full + 1  # beyond 1.5x demand: whole credit gone (~1,000+)
    assert list(qb) == sorted(qb, reverse=True)  # monotone, no cliff
    assert adj.iloc[30] == 0  # a WR with neutral anchors has no above-neutral credit to lose


def test_superflex_keeps_the_qb19_credit():
    assert (va.starting_demand_adjustment(_pool(), SUPERFLEX).iloc[:24] == 0).all()  # QB19 starts in Superflex


def test_no_market_floor_only_for_evidence_free_players():
    adj = va.no_market_floor_adjustment(_pool())
    assert adj.iloc[30] == pytest.approx(-(0.12 * 2200 + 0.10 * 2800))
    assert (adj.iloc[:30] == 0).all()
    pool = _pool()
    pool.loc[30, "production_score"] = 3100  # real production evidence keeps its credit
    assert va.no_market_floor_adjustment(pool).iloc[30] == pytest.approx(-0.10 * 2800)


def test_flags_default_off_and_cache_key_untouched(monkeypatch):
    monkeypatch.delenv(va.STARTING_DEMAND_ENV_KEY, raising=False)
    monkeypatch.delenv(va.NO_MARKET_FLOOR_ENV_KEY, raising=False)
    assert not va.starting_demand_enabled() and not va.no_market_floor_enabled()
    assert va.fingerprint_parts() == ()
    monkeypatch.setenv(va.STARTING_DEMAND_ENV_KEY, "1")
    assert va.fingerprint_parts() == ("role_demand=1",)


def test_lens_applies_both_adjustments_only_when_flagged(monkeypatch):
    monkeypatch.delenv(va.STARTING_DEMAND_ENV_KEY, raising=False)
    monkeypatch.delenv(va.NO_MARKET_FLOOR_ENV_KEY, raising=False)
    off = lvs.apply_valuation_lens(_pool(), lvs.LENS_DYNASTY, dict(ONE_QB))
    monkeypatch.setenv(va.STARTING_DEMAND_ENV_KEY, "1")
    monkeypatch.setenv(va.NO_MARKET_FLOOR_ENV_KEY, "1")
    on = lvs.apply_valuation_lens(_pool(), lvs.LENS_DYNASTY, dict(ONE_QB))
    qb = on.set_index("player_id")
    base = off.set_index("player_id")
    assert qb.loc["qb0", "dynasty_score"] == base.loc["qb0", "dynasty_score"]
    assert qb.loc["qb29", "dynasty_score"] < base.loc["qb29", "dynasty_score"]
    assert qb.loc["depth", "dynasty_score"] < base.loc["depth", "dynasty_score"]
    # The canonical base score is never rewritten by league math.
    assert (on["base_score"].values == off["base_score"].values).all()
