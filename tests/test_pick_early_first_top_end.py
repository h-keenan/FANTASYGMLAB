"""Early-1st top end of the pick value model (trade-advice pick audit, flag DYNASTYGM_EARLY_FIRST_TOP_END_V1)."""

from __future__ import annotations

import pandas as pd

from modules import trade_ideas

KEY = trade_ideas.EARLY_FIRST_TOP_END_ENV_KEY


def _value(season: int, round_num: int, pct: float, next_draft_year: int = 2027) -> dict:
    bucket = "early" if pct >= 0.67 else "late" if pct < 0.34 else "mid"
    ctx = {"slot_percentile": pct, "tier_bucket": bucket}
    return trade_ideas.pick_value_components(
        season, round_num, 1, pd.DataFrame(), None, team_context=ctx, next_draft_year=next_draft_year
    )


def test_flag_defaults_on_and_can_be_switched_off(monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    assert trade_ideas.early_first_top_end_enabled() is True
    for off in ("0", "false", "no", "off"):
        monkeypatch.setenv(KEY, off)
        assert trade_ideas.early_first_top_end_enabled() is False


def test_early_first_is_raised_toward_market_and_nothing_else_moves(monkeypatch):
    monkeypatch.setenv(KEY, "0")
    old_r1, old_r2 = _value(2027, 1, 1.0)["score"], _value(2027, 2, 1.0)["score"]
    monkeypatch.delenv(KEY, raising=False)
    new_r1, new_r2 = _value(2027, 1, 1.0)["score"], _value(2027, 2, 1.0)["score"]
    assert old_r1 * 1.08 < new_r1 < old_r1 * 1.20  # a calibrated lift, not a rewrite
    assert new_r2 == old_r2  # round 2 untouched


def test_mid_late_firsts_and_the_future_discount_are_unchanged(monkeypatch):
    monkeypatch.setenv(KEY, "0")
    off = (_value(2027, 1, 0.5)["base_score"], _value(2027, 1, 0.0)["base_score"], _value(2028, 1, 0.5)["future_discount"])
    monkeypatch.delenv(KEY, raising=False)
    on = (_value(2027, 1, 0.5)["base_score"], _value(2027, 1, 0.0)["base_score"], _value(2028, 1, 0.5)["future_discount"])
    # Neighbouring buckets carry a little early probability mass, so the lift is small and bounded.
    assert off[0] <= on[0] <= off[0] * 1.07
    assert off[1] <= on[1] <= off[1] * 1.01
    assert on[2] == off[2] == 0.88
