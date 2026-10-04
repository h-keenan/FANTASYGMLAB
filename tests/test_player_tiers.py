"""modules.player_tiers.assign_player_tiers — percentile-based tier labels,
and the role-blocked tier cap.

Regression coverage for the Chimere Dike "STARTER" tag bug report: a
player with a high long-horizon value/dynasty score (draft capital, market
hype) but no live current role — rankings.py's own
``workload_trend == "Blocked"`` signal, the same column
modules.waivers_ui.rank_priority_add_candidates already gates Priority Adds
on for the identical reason — must never show a tier at or above "Starter".
"""

from __future__ import annotations

import pandas as pd

from modules import player_tiers


def _row(**kwargs):
    base = {
        "player_id": "p1",
        "dynasty_score": 7200,
        "value_score": 7200,
        "market_score": 8000,
        "scarcity_score": 5000,
    }
    base.update(kwargs)
    return base


def test_blocked_role_player_is_capped_below_starter_despite_high_value_score():
    df = pd.DataFrame(
        [
            _row(player_id="blocked-high-value", workload_trend="Blocked"),
            _row(player_id="healthy-same-score", workload_trend="Stable"),
        ]
    )

    tiered = player_tiers.assign_player_tiers(df, primary_score_field="dynasty_score")
    by_id = tiered.set_index("player_id")

    # Identical dynasty/value/market/scarcity scores, but the blocked-role
    # player must land at or below the cap while the healthy player (same
    # score) keeps the tier the percentile math actually earned.
    assert by_id.loc["healthy-same-score", "player_tier"] not in {
        player_tiers.BLOCKED_ROLE_TIER_CAP,
        "Developmental",
    }
    assert by_id.loc["blocked-high-value", "player_tier"] == player_tiers.BLOCKED_ROLE_TIER_CAP
    assert by_id.loc["blocked-high-value", "dynasty_tier"] == player_tiers.BLOCKED_ROLE_TIER_CAP


def test_blocked_role_cap_never_promotes_a_lower_tier():
    """The cap only ever pulls a tier DOWN to "Depth" — it must never bump
    a genuinely low-percentile blocked player UP into "Depth". A pool of
    high-scoring distractor rows is included so the two rows under test
    actually land at a low percentile (percentile rank is relative to the
    rest of the pool, not an absolute score threshold)."""

    distractors = [
        _row(player_id=f"distractor-{i}", dynasty_score=9000, value_score=9000, market_score=9000, scarcity_score=9000)
        for i in range(8)
    ]
    rows = distractors + [
        _row(
            player_id="low-value-blocked",
            dynasty_score=50,
            value_score=50,
            market_score=10,
            scarcity_score=0,
            workload_trend="Blocked",
        ),
        _row(
            player_id="low-value-healthy",
            dynasty_score=50,
            value_score=50,
            market_score=10,
            scarcity_score=0,
            workload_trend="Stable",
        ),
    ]
    df = pd.DataFrame(rows)

    tiered = player_tiers.assign_player_tiers(df, primary_score_field="dynasty_score")
    by_id = tiered.set_index("player_id")

    healthy_tier = by_id.loc["low-value-healthy", "player_tier"]
    assert healthy_tier == "Developmental"
    # The blocked twin, scored identically, must land at the same low tier
    # the percentile math actually earned — not get bumped up to the
    # "Depth" cap, which only ever pulls a tier DOWN.
    assert by_id.loc["low-value-blocked", "player_tier"] == healthy_tier


def test_no_workload_trend_column_is_unaffected():
    """Older/internal callers that never attach ``workload_trend`` keep the
    exact prior percentile-only behavior — the cap is additive, not a
    required column."""

    df = pd.DataFrame([_row(player_id="p1"), _row(player_id="p2", dynasty_score=100, value_score=100)])

    tiered = player_tiers.assign_player_tiers(df, primary_score_field="dynasty_score")

    assert "player_tier" in tiered.columns
    assert tiered.set_index("player_id").loc["p1", "player_tier"] not in {None, ""}


def test_non_blocked_workload_trend_values_are_never_capped():
    df = pd.DataFrame(
        [
            _row(player_id="rising", workload_trend="Rising"),
            _row(player_id="cooling", workload_trend="Cooling"),
            _row(player_id="fragile", workload_trend="Fragile"),
            _row(player_id="contingent", workload_trend="Contingent"),
        ]
    )

    tiered = player_tiers.assign_player_tiers(df, primary_score_field="dynasty_score")
    by_id = tiered.set_index("player_id")

    for player_id in ("rising", "cooling", "fragile", "contingent"):
        assert by_id.loc[player_id, "player_tier"] != player_tiers.BLOCKED_ROLE_TIER_CAP
