"""Valuation signal quality + market-independence harnesses."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import news_signal
from modules import rankings


ROOT = Path(__file__).resolve().parents[1]


def _score_row(**kwargs):
    base = {
        "player_id": kwargs.get("player_id", "p1"),
        "name": kwargs.get("name", "Player"),
        "position": kwargs.get("position", "RB"),
        "team": kwargs.get("team", "KC"),
        "age": kwargs.get("age", 24),
        "value": kwargs.get("value", 6500),
        "search_rank": kwargs.get("search_rank", 40),
        "status": kwargs.get("status", "Active"),
        "injury_status": kwargs.get("injury_status", ""),
        "years_exp": kwargs.get("years_exp", 3),
        "depth_chart_position": kwargs.get("depth_chart_position", "RB1"),
        "depth_chart_order": kwargs.get("depth_chart_order", 1),
    }
    for key in (
        "games_played",
        "targets",
        "receptions",
        "rush_attempts",
        "rushing_yards",
        "pass_attempts",
    ):
        if key in kwargs:
            base[key] = kwargs[key]
    return rankings.apply_valuation_model(pd.DataFrame([base])).iloc[0]


def test_recency_explicitly_unsupported():
    assert rankings.recency_supported_by_available_data() is False


def test_production_fallback_is_neutral_not_market():
    miss = rankings.production_usage_score(
        position="WR", market_score=9000, games_played=0, years_exp=0
    )
    assert miss["production_score"] == rankings.PRODUCTION_NEUTRAL_ANCHOR
    assert miss["production_fallback"] == "neutral_anchor"
    assert "market" not in miss["production_explanation"] or "neutral" in miss["production_explanation"]


def test_opportunity_does_not_use_market_inference_for_unknown_depth():
    profile = rankings.opportunity_profile(
        "WR",
        depth_chart_position="",
        market_score=9000,
        depth_chart_order=None,
        years_exp=4,
        age=26,
    )
    assert "market_inference" not in profile["opportunity_source_flags"]
    assert profile["opportunity_fallback"] == "neutral_anchor"
    assert profile["opportunity_score"] == int(rankings.OPPORTUNITY_NEUTRAL_ANCHOR)


def test_depth_starter_opportunity_independent_of_market():
    low = rankings.opportunity_profile(
        "RB", "RB1", market_score=1500, depth_chart_order=1, years_exp=3, age=24
    )
    high = rankings.opportunity_profile(
        "RB", "RB1", market_score=9000, depth_chart_order=1, years_exp=3, age=24
    )
    assert low["opportunity_label"] == high["opportunity_label"] == "Elite Opportunity"
    assert low["opportunity_score"] == high["opportunity_score"]


def test_usage_can_move_opportunity_without_changing_depth():
    low = rankings.opportunity_profile(
        "RB",
        "RB2",
        market_score=5000,
        depth_chart_order=2,
        years_exp=3,
        age=24,
        games_played=14,
        rush_attempts=70,
        targets=10,
    )
    high = rankings.opportunity_profile(
        "RB",
        "RB2",
        market_score=5000,
        depth_chart_order=2,
        years_exp=3,
        age=24,
        games_played=14,
        rush_attempts=250,
        targets=45,
    )
    assert high["opportunity_score"] > low["opportunity_score"]
    assert "season_usage_rates" in high["opportunity_source_flags"]


def test_same_market_workload_divergence_is_material_and_bounded():
    bell = _score_row(
        player_id="a",
        value=6200,
        rush_attempts=300,
        targets=40,
        games_played=15,
        depth_chart_position="RB1",
        depth_chart_order=1,
    )
    committee = _score_row(
        player_id="b",
        value=6200,
        rush_attempts=90,
        targets=15,
        games_played=15,
        depth_chart_position="RB2",
        depth_chart_order=2,
    )
    assert float(bell["score"]) > float(committee["score"])
    # Bounded: not a total collapse of market ordering.
    assert float(bell["score"]) / max(float(committee["score"]), 1) < 1.55


def test_same_market_wr_target_divergence():
    heavy = _score_row(
        player_id="w1",
        position="WR",
        value=6000,
        depth_chart_position="WR1",
        depth_chart_order=1,
        games_played=15,
        targets=150,
        receptions=95,
    )
    light = _score_row(
        player_id="w2",
        position="WR",
        value=6000,
        depth_chart_position="WR2",
        depth_chart_order=2,
        games_played=15,
        targets=55,
        receptions=30,
    )
    assert float(heavy["score"]) > float(light["score"])


def test_qb_starter_vs_backup_same_market():
    starter = _score_row(
        player_id="q1",
        position="QB",
        value=5500,
        depth_chart_position="QB1",
        depth_chart_order=1,
        games_played=16,
        pass_attempts=560,
        rushing_yards=200,
    )
    backup = _score_row(
        player_id="q2",
        position="QB",
        value=5500,
        depth_chart_position="QB2",
        depth_chart_order=2,
        games_played=4,
        pass_attempts=40,
        rushing_yards=10,
    )
    assert float(starter["score"]) > float(backup["score"])


def test_rookies_not_penalized_relative_to_each_other_for_missing_production():
    elite = _score_row(
        player_id="r1",
        name="Elite Rookie",
        value=8000,
        age=21,
        years_exp=0,
        depth_chart_position="WR1",
        depth_chart_order=1,
        position="WR",
    )
    late = _score_row(
        player_id="r2",
        name="Late Rookie",
        value=2500,
        age=22,
        years_exp=0,
        depth_chart_position="WR3",
        depth_chart_order=3,
        position="WR",
    )
    assert float(elite["production_score"]) == rankings.PRODUCTION_NEUTRAL_ANCHOR
    assert float(late["production_score"]) == rankings.PRODUCTION_NEUTRAL_ANCHOR
    assert float(elite["score"]) > float(late["score"])


def test_injured_rate_sample_not_triple_punished_vs_risk_only():
    healthy = _score_row(
        player_id="i1",
        value=7000,
        status="Active",
        injury_status="",
        games_played=8,
        targets=72,
        receptions=45,
        position="WR",
        depth_chart_position="WR1",
        depth_chart_order=1,
    )
    injured = _score_row(
        player_id="i2",
        value=7000,
        status="Injured Reserve",
        injury_status="Torn ACL",
        games_played=4,
        targets=36,
        receptions=22,
        position="WR",
        depth_chart_position="WR1",
        depth_chart_order=1,
    )
    # Similar per-game rates → production should not collapse independently of risk.
    assert float(injured["production_score"]) > 4500
    assert float(injured["score"]) < float(healthy["score"])
    assert float(injured["risk_multiplier"]) < float(healthy["risk_multiplier"])


def test_news_still_cannot_mutate_scores():
    row = _score_row(value=6000, games_played=10, rush_attempts=180, targets=25)
    before = float(row["score"])
    news_signal.classify_article("Player ruled out torn ACL season ending")
    assert float(row["score"]) == before
    assert float(row["news_factor"]) == 0.0


def test_effective_market_linkage_drops_with_usage_confidence():
    low = _score_row(value=6000, years_exp=0)  # no stats
    high = _score_row(
        value=6000,
        games_played=15,
        rush_attempts=280,
        targets=40,
        years_exp=4,
    )
    # With neutral production fallback, linkage is similar; usage should still
    # reduce opportunity market flags and keep overall linkage bounded.
    assert float(high["effective_market_linkage"]) <= float(low["effective_market_linkage"]) + 0.01
    assert float(high["effective_market_linkage"]) < 0.80
    assert float(low["effective_market_linkage"]) < 0.80
    assert "season_usage_rates" in str(high["opportunity_source_flags"])


def test_weights_sum_and_independent_block_material():
    total = (
        rankings.COMPOSITE_WEIGHT_MARKET
        + rankings.COMPOSITE_WEIGHT_AGE
        + rankings.COMPOSITE_WEIGHT_PRODUCTION
        + rankings.COMPOSITE_WEIGHT_SCARCITY
        + rankings.COMPOSITE_WEIGHT_ROLE
        + rankings.COMPOSITE_WEIGHT_OPPORTUNITY
    )
    assert abs(total - 1.0) < 1e-9
    independent = (
        rankings.COMPOSITE_WEIGHT_PRODUCTION
        + rankings.COMPOSITE_WEIGHT_ROLE
        + rankings.COMPOSITE_WEIGHT_OPPORTUNITY
    )
    assert independent >= 0.28
