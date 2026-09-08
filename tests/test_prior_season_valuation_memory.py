"""Prior-season valuation memory + sample-confidence blending harnesses."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("committed_fantasycalc")

import time
from pathlib import Path

import pandas as pd

from modules import news_signal
from modules import rankings
from modules import sleeper


ROOT = Path(__file__).resolve().parents[1]


def _score_row(**kwargs):
    base = {
        "player_id": kwargs.get("player_id", "p1"),
        "name": kwargs.get("name", "Player"),
        "position": kwargs.get("position", "RB"),
        "team": kwargs.get("team", "KC"),
        "age": kwargs.get("age", 25),
        "value": kwargs.get("value", 6500),
        "search_rank": kwargs.get("search_rank", 40),
        "status": kwargs.get("status", "Active"),
        "injury_status": kwargs.get("injury_status", ""),
        "years_exp": kwargs.get("years_exp", 4),
        "depth_chart_position": kwargs.get("depth_chart_position", "RB1"),
        "depth_chart_order": kwargs.get("depth_chart_order", 1),
    }
    for key, value in kwargs.items():
        if key not in base:
            base[key] = value
    return rankings.apply_valuation_model(pd.DataFrame([base])).iloc[0]


def test_season_resolver_boundaries():
    cases = [
        ((2026, 1, 15), 2025, 2024),
        ((2026, 3, 1), 2025, 2024),
        ((2026, 8, 15), 2025, 2024),
        ((2026, 9, 1), 2026, 2025),
        ((2026, 11, 20), 2026, 2025),
        ((2026, 12, 31), 2026, 2025),
        ((2025, 9, 10), 2025, 2024),
        ((2025, 2, 1), 2024, 2023),
    ]
    for parts, current, prior in cases:
        now = time.struct_time((parts[0], parts[1], parts[2], 12, 0, 0, 0, 0, -1))
        assert sleeper.default_player_stats_season(now) == current
        assert sleeper.prior_player_stats_season(now) == prior


def test_prior_ttl_longer_than_active_in_season():
    nov = time.struct_time((2026, 11, 1, 12, 0, 0, 0, 0, -1))
    active = sleeper.default_player_stats_season(nov)
    prior = sleeper.prior_player_stats_season(nov)
    assert sleeper._player_stats_cache_ttl(active, nov) == sleeper.PLAYER_STATS_CACHE_TTL_SECONDS
    assert sleeper._player_stats_cache_ttl(prior, nov) == sleeper.PRIOR_PLAYER_STATS_CACHE_TTL_SECONDS


def test_attach_keeps_prior_separate_and_joins_by_player_id():
    players = pd.DataFrame(
        [
            {"player_id": "111", "name": "Same Id New Team", "team": "DAL"},
            {"player_id": "222", "name": "No Prior", "team": "CHI"},
            {"player_id": "333", "name": "Rookie", "team": "NYJ"},
        ]
    )
    current = {
        "111": {"stats_season": 2025, "games_played": 2, "rush_attempts": 30, "targets": 4},
        "222": {"stats_season": 2025, "games_played": 2, "rush_attempts": 10, "targets": 1},
    }
    prior = {
        "111": {
            "stats_season": 2024,
            "games_played": 16,
            "rush_attempts": 280,
            "targets": 40,
            "snap_share": 0.7,
        }
    }
    joined = rankings.attach_player_stats(players, current, prior_stats=prior)
    row = joined.set_index("player_id")
    assert row.loc["111", "games_played"] == 2
    assert row.loc["111", "prior_games_played"] == 16
    assert row.loc["111", "prior_season"] == 2024
    assert row.loc["111", "stats_season"] == 2025
    assert pd.isna(row.loc["222", "prior_games_played"])
    assert pd.isna(row.loc["333", "games_played"])
    assert pd.isna(row.loc["333", "prior_games_played"])


def test_prior_weight_decay_with_current_sample():
    # Guard=1, prior_conf=1 → weight = (1 - c)
    assert rankings.prior_evidence_weight(0.0, 1.0, 1.0) == 1.0
    assert abs(rankings.prior_evidence_weight(0.25, 1.0, 1.0) - 0.75) < 1e-9
    assert abs(rankings.prior_evidence_weight(0.5, 1.0, 1.0) - 0.5) < 1e-9
    assert abs(rankings.prior_evidence_weight(0.75, 1.0, 1.0) - 0.25) < 1e-9
    assert rankings.prior_evidence_weight(1.0, 1.0, 1.0) == 0.0


def test_strong_vs_weak_prior_same_sparse_current():
    strong = rankings.production_usage_score(
        position="RB",
        market_score=6000,
        games_played=2,
        rush_attempts=24,
        targets=4,
        prior_games_played=16,
        prior_rush_attempts=300,
        prior_targets=50,
        depth_chart_slot=1,
        years_exp=4,
    )
    weak = rankings.production_usage_score(
        position="RB",
        market_score=6000,
        games_played=2,
        rush_attempts=24,
        targets=4,
        prior_games_played=16,
        prior_rush_attempts=40,
        prior_targets=5,
        depth_chart_slot=1,
        years_exp=4,
    )
    assert strong["production_score"] > weak["production_score"]
    assert strong["production_fallback"] == "current_plus_prior"


def test_full_current_sample_ignores_conflicting_prior():
    sparse = rankings.production_usage_score(
        position="WR",
        market_score=6000,
        games_played=2,
        targets=18,
        receptions=10,
        prior_games_played=16,
        prior_targets=40,
        prior_receptions=20,
        depth_chart_slot=1,
    )
    full = rankings.production_usage_score(
        position="WR",
        market_score=6000,
        games_played=8,
        targets=72,
        receptions=40,
        prior_games_played=16,
        prior_targets=40,
        prior_receptions=20,
        depth_chart_slot=1,
    )
    assert full["production_fallback"] in {"current_only", "current_plus_prior"}
    # At full sample prior weight is ~0 so conflicting weak prior cannot dominate.
    assert rankings.prior_evidence_weight(1.0, 1.0, 1.0) == 0.0
    assert float(full["production_confidence"]) >= float(sparse["production_confidence"])


def test_demoted_starter_prior_does_not_inflate_like_starter():
    demoted = rankings.production_usage_score(
        position="RB",
        market_score=5000,
        games_played=2,
        rush_attempts=10,
        targets=2,
        prior_games_played=16,
        prior_rush_attempts=300,
        prior_targets=40,
        depth_chart_slot=3,
        years_exp=5,
    )
    still_starter = rankings.production_usage_score(
        position="RB",
        market_score=5000,
        games_played=2,
        rush_attempts=10,
        targets=2,
        prior_games_played=16,
        prior_rush_attempts=300,
        prior_targets=40,
        depth_chart_slot=1,
        years_exp=5,
    )
    assert still_starter["production_score"] > demoted["production_score"]
    assert rankings.role_continuity_guard(3, 0.8) < rankings.role_continuity_guard(1, 0.8)


def test_promoted_backup_not_suppressed_by_weak_prior():
    promoted = rankings.production_usage_score(
        position="WR",
        market_score=5500,
        games_played=2,
        targets=20,
        receptions=12,
        prior_games_played=14,
        prior_targets=30,
        prior_receptions=18,
        depth_chart_slot=1,
        years_exp=3,
    )
    # Weak prior quality with starter slot → low guard; current sparse rates still count.
    assert rankings.role_continuity_guard(1, 0.2) == 0.20
    assert promoted["production_score"] > rankings.PRODUCTION_NEUTRAL_ANCHOR


def test_rookie_no_prior_stays_neutral():
    rookie = rankings.production_usage_score(
        position="WR",
        market_score=8000,
        games_played=None,
        years_exp=0,
        depth_chart_slot=1,
    )
    assert rookie["production_score"] == rankings.PRODUCTION_NEUTRAL_ANCHOR
    assert rookie["production_confidence"] == 0.0
    assert "rookie" in rookie["production_explanation"]


def test_zero_current_gp_uses_prior_only_capped():
    prior_only = rankings.production_usage_score(
        position="RB",
        market_score=6000,
        games_played=0,
        prior_games_played=16,
        prior_rush_attempts=280,
        prior_targets=45,
        depth_chart_slot=1,
        years_exp=6,
    )
    assert prior_only["production_fallback"] == "prior_only"
    assert 0.0 < prior_only["production_confidence"] <= rankings.PRIOR_ONLY_CONFIDENCE_CAP
    assert prior_only["production_score"] > rankings.PRODUCTION_NEUTRAL_ANCHOR


def test_missing_prior_fail_neutral_matches_current_only_path():
    with_missing = rankings.production_usage_score(
        position="TE",
        market_score=4000,
        games_played=4,
        targets=28,
        receptions=18,
        prior_games_played=None,
        depth_chart_slot=1,
    )
    assert with_missing["production_fallback"] == "current_only"


def test_opportunity_remains_current_owned_not_prior():
    # Same current role/usage; prior differs — opportunity should match.
    a = _score_row(
        player_id="a",
        games_played=2,
        rush_attempts=30,
        targets=4,
        snap_share=0.55,
        prior_games_played=16,
        prior_rush_attempts=300,
        prior_targets=50,
        depth_chart_position="RB1",
        depth_chart_order=1,
    )
    b = _score_row(
        player_id="b",
        games_played=2,
        rush_attempts=30,
        targets=4,
        snap_share=0.55,
        prior_games_played=16,
        prior_rush_attempts=40,
        prior_targets=5,
        depth_chart_position="RB1",
        depth_chart_order=1,
    )
    assert int(a["opportunity_score"]) == int(b["opportunity_score"])
    assert float(a["production_score"]) > float(b["production_score"])


def test_injured_veteran_not_quadruple_punished_vs_risk():
    healthy = _score_row(
        player_id="h",
        value=7000,
        status="Active",
        injury_status="",
        games_played=4,
        rush_attempts=60,
        targets=10,
        prior_games_played=16,
        prior_rush_attempts=280,
        prior_targets=40,
        depth_chart_position="RB1",
        depth_chart_order=1,
    )
    injured = _score_row(
        player_id="i",
        value=7000,
        status="Injured Reserve",
        injury_status="Torn ACL",
        games_played=4,
        rush_attempts=60,
        targets=10,
        prior_games_played=16,
        prior_rush_attempts=280,
        prior_targets=40,
        depth_chart_position="RB1",
        depth_chart_order=1,
    )
    # Production rates + prior stabilization should not collapse independently of risk.
    assert float(injured["production_score"]) > 4500
    assert float(injured["score"]) < float(healthy["score"])
    assert float(injured["risk_multiplier"]) < float(healthy["risk_multiplier"])


def test_team_change_same_player_id_keeps_prior():
    players = pd.DataFrame([{"player_id": "999", "name": "Traveler", "team": "SF"}])
    current = {"999": {"stats_season": 2025, "games_played": 1, "targets": 7, "receptions": 4}}
    prior = {"999": {"stats_season": 2024, "games_played": 15, "targets": 120, "receptions": 75}}
    joined = rankings.attach_player_stats(players, current, prior_stats=prior).iloc[0]
    assert joined["prior_games_played"] == 15
    assert joined["team"] == "SF"


def test_news_firewall_still_holds():
    row = _score_row(
        games_played=2,
        rush_attempts=28,
        targets=5,
        prior_games_played=15,
        prior_rush_attempts=250,
        prior_targets=35,
    )
    before = float(row["score"])
    news_signal.classify_article("Star RB dominates with 25 touches")
    assert float(row["news_factor"]) == 0.0
    assert float(row["score"]) == before


def test_get_prior_season_failure_is_fail_neutral(monkeypatch):
    monkeypatch.setattr(
        sleeper,
        "get_season_player_stats",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert sleeper.get_prior_season_player_stats() == {}
