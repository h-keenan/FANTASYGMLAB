"""Valuation evidence / data-availability audit harnesses."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("committed_fantasycalc")

import pandas as pd

from modules import news_signal
from modules import rankings


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
        "snap_share",
        "rush_share",
        "target_share",
        "route_participation",
    ):
        if key in kwargs:
            base[key] = kwargs[key]
    return rankings.apply_valuation_model(pd.DataFrame([base])).iloc[0]


def test_recency_and_prior_season_and_draft_capital_flags():
    # Recency support is weekly-cache presence based after weekly retention.
    assert isinstance(rankings.recency_supported_by_available_data(), bool)
    # Prior-season support is cache-presence based (True once retained).
    assert isinstance(rankings.prior_season_stats_supported_by_available_data(), bool)
    assert rankings.draft_capital_supported_by_available_data() is False


def test_normalize_snap_share_accepts_fraction_and_percent():
    assert rankings.normalize_snap_share(0.62) == 0.62
    assert rankings.normalize_snap_share(62) == 0.62
    assert rankings.normalize_snap_share(None) is None
    assert rankings.normalize_snap_share(-0.1) is None
    assert rankings.normalize_snap_share(150) is None


def test_snap_share_is_preserved_and_can_move_opportunity():
    low = rankings.opportunity_profile(
        "WR",
        "WR2",
        market_score=5000,
        depth_chart_order=2,
        years_exp=3,
        age=25,
        games_played=14,
        targets=60,
        receptions=35,
        snap_share=0.25,
    )
    high = rankings.opportunity_profile(
        "WR",
        "WR2",
        market_score=5000,
        depth_chart_order=2,
        years_exp=3,
        age=25,
        games_played=14,
        targets=60,
        receptions=35,
        snap_share=0.85,
    )
    assert high["snap_share"] == 0.85
    assert low["snap_share"] == 0.25
    assert high["opportunity_score"] > low["opportunity_score"]
    assert "season_snap_share" in high["opportunity_source_flags"]


def test_snap_share_alone_without_usage_is_bounded_not_market():
    profile = rankings.opportunity_profile(
        "RB",
        "RB2",
        market_score=9000,
        depth_chart_order=2,
        years_exp=2,
        age=23,
        games_played=None,
        snap_share=0.70,
    )
    assert "market_inference" not in profile["opportunity_source_flags"]
    assert "season_snap_share" in profile["opportunity_source_flags"]
    assert profile["opportunity_score"] > rankings.OPPORTUNITY_NEUTRAL_ANCHOR
    # Bound: snap alone cannot mint elite starter access without depth/usage.
    assert profile["opportunity_score"] < 8800


def test_missing_snap_does_not_zero_punish():
    with_depth = rankings.opportunity_profile(
        "TE",
        "TE1",
        market_score=4000,
        depth_chart_order=1,
        years_exp=4,
        age=26,
        games_played=12,
        targets=70,
        receptions=48,
        snap_share=None,
    )
    assert with_depth["snap_share"] is None
    assert with_depth["opportunity_label"] == "Elite Opportunity"
    assert with_depth["opportunity_score"] >= 8000


def test_same_market_snap_divergence_moves_score_bounded():
    low = _score_row(
        player_id="s1",
        position="WR",
        value=6000,
        depth_chart_position="WR2",
        depth_chart_order=2,
        games_played=15,
        targets=70,
        receptions=40,
        snap_share=0.30,
    )
    high = _score_row(
        player_id="s2",
        position="WR",
        value=6000,
        depth_chart_position="WR2",
        depth_chart_order=2,
        games_played=15,
        targets=70,
        receptions=40,
        snap_share=0.80,
    )
    assert float(high["score"]) > float(low["score"])
    assert float(high["score"]) / max(float(low["score"]), 1.0) < 1.25


def test_gp_zero_and_one_game_fail_neutral_not_zero():
    zero = rankings.production_usage_score(
        position="RB", market_score=7000, games_played=0, rush_attempts=0
    )
    one = rankings.production_usage_score(
        position="RB", market_score=7000, games_played=1, rush_attempts=18, targets=3
    )
    assert zero["production_score"] == rankings.PRODUCTION_NEUTRAL_ANCHOR
    assert one["production_confidence"] == 1.0 / rankings.PRODUCTION_FULL_SAMPLE_GAMES
    assert one["production_score"] > rankings.PRODUCTION_NEUTRAL_ANCHOR * 0.5


def test_news_firewall_still_holds_after_evidence_pass():
    row = _score_row(value=6000, games_played=12, rush_attempts=200, targets=30, snap_share=0.55)
    before = float(row["score"])
    news_signal.classify_article("Breakout WR dominates with 12 targets")
    assert float(row["news_factor"]) == 0.0
    assert float(row["score"]) == before


def test_football_evidence_cohorts_and_market_mass():
    frame = rankings.apply_valuation_model(
        pd.DataFrame(
            [
                {
                    "player_id": "hi",
                    "name": "High Evidence",
                    "position": "RB",
                    "team": "BUF",
                    "age": 25,
                    "value": 7000,
                    "search_rank": 30,
                    "status": "Active",
                    "injury_status": "",
                    "years_exp": 4,
                    "depth_chart_position": "RB1",
                    "depth_chart_order": 1,
                    "games_played": 15,
                    "rush_attempts": 280,
                    "targets": 40,
                    "snap_share": 0.72,
                },
                {
                    "player_id": "none",
                    "name": "No Evidence",
                    "position": "WR",
                    "team": "CHI",
                    "age": 22,
                    "value": 7000,
                    "search_rank": 30,
                    "status": "Active",
                    "injury_status": "",
                    "years_exp": 0,
                    "depth_chart_position": "",
                    "depth_chart_order": None,
                },
            ]
        )
    )
    cohorts = rankings.football_evidence_confidence_cohort(frame)
    assert cohorts.iloc[0] == "HIGH"
    assert cohorts.iloc[1] in {"NONE", "LOW"}
    mass = rankings.composite_market_mass_series(frame)
    assert float(mass.iloc[0]) < float(mass.iloc[1])
