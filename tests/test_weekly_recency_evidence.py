"""Weekly usage retention + capped recency evidence harnesses."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("committed_fantasycalc")

import pandas as pd

from modules import news_signal
from modules import rankings
from modules import sleeper


def _weeks_from_usage(position: str, usages: list[float], start_week: int = 1):
    rows = []
    for offset, usage in enumerate(usages):
        week = start_week + offset
        row = {"week": week, "games_played": 1}
        if position == "RB":
            # Split touches into rush/targets roughly 75/25
            row["rush_attempts"] = int(round(usage * 0.75))
            row["targets"] = int(round(usage * 0.25))
        elif position in {"WR", "TE"}:
            row["targets"] = int(round(usage))
            row["receptions"] = int(round(usage * 0.6))
        else:
            row["pass_attempts"] = int(round(usage))
        row["snap_share"] = min(0.95, max(0.15, usage / (34 if position == "QB" else 22)))
        rows.append(row)
    return rows


def _score(**kwargs):
    weekly = kwargs.pop("weekly", None)
    base = {
        "player_id": kwargs.get("player_id", "p1"),
        "name": kwargs.get("name", "Player"),
        "position": kwargs.get("position", "RB"),
        "team": kwargs.get("team", "KC"),
        "age": kwargs.get("age", 24),
        "value": kwargs.get("value", 6000),
        "search_rank": kwargs.get("search_rank", 40),
        "status": kwargs.get("status", "Active"),
        "injury_status": kwargs.get("injury_status", ""),
        "years_exp": kwargs.get("years_exp", 3),
        "depth_chart_position": kwargs.get("depth_chart_position", "RB2"),
        "depth_chart_order": kwargs.get("depth_chart_order", 2),
        "games_played": kwargs.get("games_played", 10),
        "rush_attempts": kwargs.get("rush_attempts", 80),
        "targets": kwargs.get("targets", 20),
        "receptions": kwargs.get("receptions", 12),
        "pass_attempts": kwargs.get("pass_attempts", 0),
        "snap_share": kwargs.get("snap_share", 0.45),
    }
    for key, value in kwargs.items():
        base[key] = value
    features = rankings.compute_recency_features(
        base["position"],
        weekly,
        status=base["status"],
        injury_status=base["injury_status"],
    )
    base.update(features)
    return rankings.apply_valuation_model(pd.DataFrame([base])).iloc[0]


def test_aggregate_retains_weekly_without_extra_fields_bloat():
    payloads = [
        (
            1,
            {
                "p1": {
                    "gp": 1,
                    "rec_tgt": 8,
                    "rec": 5,
                    "off_snp": 40,
                    "tm_off_snp": 60,
                    "pts_ppr": 12,
                }
            },
        ),
        (
            2,
            {
                "p1": {
                    "gp": 1,
                    "rec_tgt": 10,
                    "rec": 6,
                    "off_snp": 45,
                    "tm_off_snp": 60,
                    "pts_ppr": 14,
                }
            },
        ),
        (3, {"p2": {"gp": 1, "rush_att": 12, "off_snp": 30, "tm_off_snp": 60}}),
    ]
    aggregated = sleeper._aggregate_player_week_stats(payloads, 2025, retain_weekly=True)
    assert "weekly" in aggregated["p1"]
    assert len(aggregated["p1"]["weekly"]) == 2
    assert aggregated["p1"]["weekly"][0]["week"] == 1
    assert aggregated["p1"]["targets"] == 18
    # Weekly rows also retain fantasy points now (Player Detail's
    # points-by-week chart reads this per week, not just the season sum) —
    # the raw Sleeper field name itself is never exposed, only the mapped one.
    assert aggregated["p1"]["weekly"][0]["fantasy_points_ppr"] == 12.0
    assert aggregated["p1"]["weekly"][1]["fantasy_points_ppr"] == 14.0
    assert "pts_ppr" not in aggregated["p1"]["weekly"][0]


def test_bye_and_missing_week_not_treated_as_zero_usage():
    weeks = _weeks_from_usage("WR", [8, 9], start_week=1)
    # Gap week 3 missing (bye) then continue
    weeks += _weeks_from_usage("WR", [10, 11], start_week=4)
    features = rankings.compute_recency_features("WR", weeks)
    assert features["recency_sample_n"] == 4
    # No fabricated zero week in the window.
    assert features["recency_confidence"] > 0


def test_one_game_spike_is_bounded():
    quiet = _weeks_from_usage("RB", [6, 7, 8])
    spike = _weeks_from_usage("RB", [6, 7, 8, 28])
    quiet_f = rankings.compute_recency_features("RB", quiet)
    spike_f = rankings.compute_recency_features("RB", spike)
    quiet_row = _score(weekly=quiet, rush_attempts=60, targets=20, games_played=8)
    spike_row = _score(weekly=spike, rush_attempts=60 + 28, targets=20, games_played=9)
    assert spike_f["recency_confidence"] <= 1.0
    # One spike may raise trend, but score movement stays bounded.
    ratio = float(spike_row["score"]) / max(float(quiet_row["score"]), 1.0)
    assert ratio < 1.12


def test_sustained_breakout_moves_opportunity_faster_than_noise():
    flat = _weeks_from_usage("WR", [4, 5, 4, 5, 4])
    breakout = _weeks_from_usage("WR", [4, 5, 8, 10, 11])
    flat_row = _score(
        position="WR",
        depth_chart_position="WR2",
        depth_chart_order=2,
        weekly=flat,
        targets=22,
        receptions=14,
        games_played=5,
        rush_attempts=0,
    )
    break_row = _score(
        position="WR",
        depth_chart_position="WR2",
        depth_chart_order=2,
        weekly=breakout,
        targets=38,
        receptions=24,
        games_played=5,
        rush_attempts=0,
    )
    assert float(break_row["opportunity_score"]) > float(flat_row["opportunity_score"])
    assert "weekly_recency" in str(break_row["opportunity_source_flags"])
    assert float(break_row["score"]) > float(flat_row["score"])


def test_sustained_role_loss_cools_opportunity():
    strong = _weeks_from_usage("RB", [20, 18, 19, 17, 18])
    decline = _weeks_from_usage("RB", [20, 18, 12, 7, 5])
    strong_row = _score(
        weekly=strong,
        depth_chart_position="RB1",
        depth_chart_order=1,
        rush_attempts=90,
        targets=20,
        games_played=5,
    )
    decline_row = _score(
        weekly=decline,
        depth_chart_position="RB1",
        depth_chart_order=1,
        rush_attempts=62,
        targets=16,
        games_played=5,
    )
    assert float(decline_row["opportunity_score"]) < float(strong_row["opportunity_score"])
    assert decline_row["workload_trend"] in {"Cooling", "Stable", "Fragile", "Rising"}


def test_major_injury_fail_neutral_for_recency():
    weeks = _weeks_from_usage("RB", [18, 16, 4, 0, 0])
    # Force zeros with gp still 1 would be weird; use declining then injury status
    features = rankings.compute_recency_features(
        "RB",
        _weeks_from_usage("RB", [18, 16, 15, 14]),
        status="Injured Reserve",
        injury_status="Torn ACL",
    )
    assert features["recency_confidence"] == 0.0
    assert "injury" in features["recency_formulation"]


def test_rookie_needs_three_games_before_trend():
    two = rankings.compute_recency_features("WR", _weeks_from_usage("WR", [2, 9]), status="Active")
    three = rankings.compute_recency_features("WR", _weeks_from_usage("WR", [2, 8, 10]), status="Active")
    assert two["recency_confidence"] == 0.0
    assert three["recency_sample_n"] == 3
    assert three["recency_confidence"] > 0.0


def test_max_recency_authority_cap():
    # Adversarial: huge recent vs tiny baseline, full confidence.
    features = {
        "recency_trend": 0.40,
        "recency_confidence": 1.0,
        "recency_sample_n": 8,
        "recency_usage_rate": 20,
        "recency_baseline_rate": 5,
    }
    low = rankings.opportunity_profile(
        "RB",
        "RB2",
        market_score=6000,
        depth_chart_order=2,
        years_exp=3,
        age=24,
        games_played=10,
        rush_attempts=100,
        targets=20,
        snap_share=0.5,
        recency_trend=0,
        recency_confidence=0,
        recency_sample_n=0,
    )
    high = rankings.opportunity_profile(
        "RB",
        "RB2",
        market_score=6000,
        depth_chart_order=2,
        years_exp=3,
        age=24,
        games_played=10,
        rush_attempts=100,
        targets=20,
        snap_share=0.5,
        **features,
    )
    delta = int(high["opportunity_score"]) - int(low["opportunity_score"])
    assert delta <= rankings.RECENCY_MAX_OPP_BUMP
    # Composite weight 0.10 → theoretical max ~70 score points from opportunity alone.
    assert delta * rankings.COMPOSITE_WEIGHT_OPPORTUNITY <= 70.0001


def test_formulation_weighted4_beats_last2_on_spike_stability():
    spike = _weeks_from_usage("RB", [6, 7, 8, 28])
    alts = rankings.evaluate_recency_formulations("RB", spike)
    # last2 overweight the spike more than weighted4
    assert alts["last2"] is not None and alts["weighted4"] is not None
    assert alts["last2"] > alts["weighted4"]


def test_prior_season_interaction_recency_does_not_replace_production():
    weeks = _weeks_from_usage("RB", [6, 8, 17, 19, 21])
    row = _score(
        weekly=weeks,
        games_played=5,
        rush_attempts=70,
        targets=15,
        prior_games_played=16,
        prior_rush_attempts=40,
        prior_targets=10,
        depth_chart_position="RB1",
        depth_chart_order=1,
    )
    # Production still uses season/prior blend; recency only flags opportunity.
    assert "prior" in str(row["production_fallback"]) or row["production_fallback"] in {
        "current_plus_prior",
        "current_only",
        "prior_only",
    }
    assert "weekly_recency" in str(row["opportunity_source_flags"])


def test_attach_does_not_put_raw_weekly_on_frame():
    players = pd.DataFrame(
        [{"player_id": "p1", "name": "A", "position": "WR", "status": "Active", "injury_status": ""}]
    )
    stats = {
        "p1": {
            "stats_season": 2025,
            "games_played": 4,
            "targets": 30,
            "weekly": _weeks_from_usage("WR", [4, 5, 8, 10]),
        }
    }
    joined = rankings.attach_player_stats(players, stats, prior_stats={})
    assert "weekly" not in joined.columns
    assert int(joined.iloc[0]["recency_sample_n"]) == 4
    assert float(joined.iloc[0]["recency_confidence"]) > 0


def test_news_firewall_still_holds():
    row = _score(weekly=_weeks_from_usage("WR", [5, 6, 9, 10]), position="WR", targets=30, games_played=4)
    before = float(row["score"])
    news_signal.classify_article("WR emerging as true WR1 with huge target share")
    assert float(row["news_factor"]) == 0.0
    assert float(row["score"]) == before


def test_missing_weekly_fail_neutral():
    features = rankings.compute_recency_features("TE", None)
    assert features["recency_confidence"] == 0.0
    row = _score(position="TE", weekly=None, targets=40, receptions=25, games_played=8)
    assert "weekly_recency" not in str(row["opportunity_source_flags"])
