"""Early-1st top end of the pick value model (trade-advice pick audit)."""

from __future__ import annotations

import pandas as pd

from modules import trade_ideas

KEY = trade_ideas.EARLY_FIRST_TOP_END_ENV_KEY


def _early_first(round_num=1):
    ctx = {"slot_percentile": 1.0, "tier_bucket": "early"}
    return trade_ideas.pick_value_components(
        2027, round_num, 1, pd.DataFrame(), None, team_context=ctx, next_draft_year=2027
    )


def test_flag_defaults_on_and_can_be_switched_off(monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    assert trade_ideas.early_first_top_end_enabled() is True
    for off in ("0", "false", "no", "off"):
        monkeypatch.setenv(KEY, off)
        assert trade_ideas.early_first_top_end_enabled() is False


def test_early_first_is_raised_toward_market_and_nothing_else_moves(monkeypatch):
    monkeypatch.setenv(KEY, "0")
    old_r1, old_r2 = _early_first(1)["score"], _early_first(2)["score"]
    monkeypatch.delenv(KEY, raising=False)
    new_r1, new_r2 = _early_first(1)["score"], _early_first(2)["score"]
    assert new_r1 > old_r1 * 1.08  # early probability mass takes the higher base
    assert new_r1 < old_r1 * 1.20  # but it is a calibrated lift, not a rewrite
    assert new_r2 == old_r2  # round 2 untouched


def test_mid_and_late_firsts_are_unchanged(monkeypatch):
    def score(pct, bucket):
        ctx = {"slot_percentile": pct, "tier_bucket": bucket}
        return trade_ideas.pick_value_components(2027, 1, 1, pd.DataFrame(), None, team_context=ctx, next_draft_year=2027)

    monkeypatch.setenv(KEY, "0")
    off = (score(0.5, "mid")["base_score"], score(0.0, "late")["base_score"])
    monkeypatch.delenv(KEY, raising=False)
    on = (score(0.5, "mid")["base_score"], score(0.0, "late")["base_score"])
    # Neighbouring buckets carry a little early probability mass, so the lift is small and bounded.
    assert off[0] <= on[0] <= off[0] * 1.07
    assert off[1] <= on[1] <= off[1] * 1.01
