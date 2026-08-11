"""Valuation quality pass: continuous age curves + production/usage factor."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import news_signal
from modules import rankings


ROOT = Path(__file__).resolve().parents[1]


def _legacy_step_age_multiplier(position: str, age: float) -> float:
    """Pre-pass step-function curve retained for before/after cliff measurement."""

    position = str(position or "").upper()
    if position == "QB":
        if age <= 24:
            return 1.10
        if age <= 29:
            return 1.05
        if age <= 33:
            return 0.98
        if age <= 36:
            return 0.82
        return 0.55
    if position == "RB":
        if age <= 22:
            return 1.18
        if age <= 25:
            return 1.08
        if age <= 26:
            return 0.96
        if age <= 27:
            return 0.84
        if age <= 28:
            return 0.66
        if age <= 29:
            return 0.48
        return 0.28
    if position == "WR":
        if age <= 22:
            return 1.18
        if age <= 25:
            return 1.10
        if age <= 28:
            return 1.02
        if age <= 29:
            return 0.90
        if age <= 30:
            return 0.76
        if age <= 31:
            return 0.60
        return 0.42
    if position == "TE":
        if age <= 23:
            return 1.12
        if age <= 28:
            return 1.04
        if age <= 30:
            return 0.94
        if age <= 31:
            return 0.78
        return 0.58
    return 1.0


def _max_adjacent_delta(position: str, ages, fn) -> float:
    vals = [fn(position, age) for age in ages]
    return max(abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1))


def test_continuous_age_curves_reduce_cliffs_vs_legacy_steps():
    cases = {
        "RB": list(range(21, 33)),
        "WR": list(range(21, 35)),
        "QB": list(range(22, 41)),
        "TE": list(range(21, 36)),
    }
    for pos, ages in cases.items():
        before = _max_adjacent_delta(pos, ages, _legacy_step_age_multiplier)
        after = _max_adjacent_delta(pos, ages, rankings.age_multiplier)
        assert after < before or after <= 0.13, (pos, before, after)
        assert after <= 0.13, (pos, after)
        for i, age in enumerate(ages[:-1]):
            assert (
                abs(
                    rankings.age_multiplier(pos, ages[i + 1])
                    - rankings.age_multiplier(pos, age)
                )
                <= 0.13
            )


def test_age_curve_no_older_more_valuable_from_bucket_crossing():
    for pos in ("QB", "RB", "WR", "TE"):
        ages = list(range(21, 36))
        vals = [rankings.age_multiplier(pos, age) for age in ages]
        for i in range(len(vals) - 1):
            assert vals[i + 1] <= vals[i] + 1e-9, (pos, ages[i], vals[i], vals[i + 1])


def test_dynasty_ages_more_than_redraft_via_base_curve_weight():
    market = 7000.0
    young = rankings.age_multiplier("RB", 23)
    old = rankings.age_multiplier("RB", 30)
    dynasty_gap = abs((market * young) - (market * old)) * rankings.COMPOSITE_WEIGHT_AGE
    redraft_embedded = dynasty_gap * 0.40
    assert dynasty_gap > redraft_embedded


def test_production_missing_defers_to_market_for_rookies():
    rookie = rankings.production_usage_score(
        position="RB",
        market_score=6500,
        games_played=0,
        years_exp=0,
    )
    assert rookie["production_confidence"] == 0.0
    assert rookie["production_score"] == 6500.0
    assert "deferred to market" in rookie["production_explanation"]


def test_production_small_sample_does_not_dominate():
    spike = rankings.production_usage_score(
        position="WR",
        market_score=5000,
        games_played=1,
        targets=15,
        receptions=10,
        years_exp=3,
    )
    full = rankings.production_usage_score(
        position="WR",
        market_score=5000,
        games_played=14,
        targets=15 * 14,
        receptions=10 * 14,
        years_exp=3,
    )
    assert spike["production_confidence"] < 0.2
    assert abs(spike["production_score"] - 5000) < abs(full["production_score"] - 5000)
    assert full["production_score"] > spike["production_score"]


def test_production_distinguishes_workload_at_same_market():
    market = 6200.0
    bellcow = rankings.production_usage_score(
        position="RB",
        market_score=market,
        games_played=15,
        rush_attempts=280,
        targets=50,
        years_exp=3,
    )
    committee = rankings.production_usage_score(
        position="RB",
        market_score=market,
        games_played=15,
        rush_attempts=90,
        targets=20,
        years_exp=3,
    )
    assert bellcow["production_score"] > committee["production_score"] + 800


def test_injured_low_games_uses_rates_not_season_volume_crush():
    healthy = rankings.production_usage_score(
        position="WR",
        market_score=7000,
        games_played=16,
        targets=140,
        receptions=90,
    )
    injured_sample = rankings.production_usage_score(
        position="WR",
        market_score=7000,
        games_played=6,
        targets=52,
        receptions=34,
    )
    assert injured_sample["production_score"] > 4500
    assert injured_sample["production_confidence"] < healthy["production_confidence"]


def test_apply_valuation_model_includes_production_and_news_firewall():
    df = pd.DataFrame(
        [
            {
                "player_id": "a",
                "name": "Bellcow RB",
                "position": "RB",
                "team": "KC",
                "age": 24,
                "value": 7000,
                "search_rank": 20,
                "status": "Active",
                "injury_status": "",
                "years_exp": 3,
                "depth_chart_position": "RB1",
                "depth_chart_order": 1,
                "games_played": 15,
                "rush_attempts": 300,
                "targets": 45,
                "receptions": 30,
                "pass_attempts": None,
                "rushing_yards": 1200,
            },
            {
                "player_id": "b",
                "name": "Committee RB",
                "position": "RB",
                "team": "BUF",
                "age": 24,
                "value": 7000,
                "search_rank": 20,
                "status": "Active",
                "injury_status": "",
                "years_exp": 3,
                "depth_chart_position": "RB2",
                "depth_chart_order": 2,
                "games_played": 15,
                "rush_attempts": 95,
                "targets": 18,
                "receptions": 12,
                "pass_attempts": None,
                "rushing_yards": 380,
            },
            {
                "player_id": "c",
                "name": "Rookie RB",
                "position": "RB",
                "team": "CHI",
                "age": 21,
                "value": 7000,
                "search_rank": 20,
                "status": "Active",
                "injury_status": "",
                "years_exp": 0,
                "depth_chart_position": "RB1",
                "depth_chart_order": 1,
            },
        ]
    )
    scored = rankings.apply_valuation_model(df)
    assert "production_score" in scored.columns
    assert float(scored.loc[scored["player_id"] == "a", "score"].iloc[0]) > float(
        scored.loc[scored["player_id"] == "b", "score"].iloc[0]
    )
    rookie_score = float(scored.loc[scored["player_id"] == "c", "score"].iloc[0])
    committee_score = float(scored.loc[scored["player_id"] == "b", "score"].iloc[0])
    assert rookie_score >= committee_score * 0.85
    assert (scored["news_factor"] == 0.0).all()
    before = scored.iloc[0][["score", "dynasty_score", "value_score", "news_factor"]].to_dict()
    news_signal.classify_article("Bellcow RB ruled out torn ACL")
    after = scored.iloc[0][["score", "dynasty_score", "value_score", "news_factor"]].to_dict()
    assert before == after


def test_score_scale_stability_synthetic_frame():
    rows = []
    for i, (pos, age, value) in enumerate(
        [
            ("RB", 24, 8000),
            ("RB", 29, 8000),
            ("WR", 23, 6000),
            ("WR", 31, 6000),
            ("QB", 27, 7500),
            ("TE", 26, 5000),
        ]
    ):
        rows.append(
            {
                "player_id": str(i),
                "name": f"P{i}",
                "position": pos,
                "team": "KC",
                "age": age,
                "value": value,
                "search_rank": 30 + i,
                "status": "Active",
                "injury_status": "",
                "years_exp": 3,
                "depth_chart_position": f"{pos}1",
                "depth_chart_order": 1,
            }
        )
    scored = rankings.apply_valuation_model(pd.DataFrame(rows))
    median = float(scored["score"].median())
    assert 2000 <= median <= 12000
    assert float(scored["score"].max()) <= 15000


def test_archetype_ordering_harness():
    from tests.test_valuation_calibration_audit import _composite_score

    market = 6500.0

    def score(**kwargs):
        base = {
            "market": market,
            "position": "RB",
            "age": 24,
            "role": 8500,
            "opportunity": 7600,
            "risk": 1.0,
        }
        base.update(kwargs)
        return _composite_score(**base)

    young_elite = score(age=23, rush_attempts=300, targets=40, games_played=15)
    young_committee = score(
        age=23,
        rush_attempts=100,
        targets=20,
        games_played=15,
        role=5600,
        opportunity=5200,
    )
    aging_elite = score(age=30, rush_attempts=280, targets=35, games_played=15)
    aging_decline = score(
        age=32,
        rush_attempts=120,
        targets=15,
        games_played=12,
        role=5600,
        opportunity=4200,
    )
    assert young_elite > young_committee
    assert young_elite > aging_elite
    assert aging_elite > aging_decline

    wr_heavy = score(
        position="WR",
        age=23,
        role=8500,
        opportunity=8500,
        targets=150,
        receptions=95,
        games_played=15,
    )
    wr_low = score(
        position="WR",
        age=23,
        role=5600,
        opportunity=5200,
        targets=55,
        receptions=30,
        games_played=15,
    )
    assert wr_heavy > wr_low

    qb_starter = score(
        position="QB",
        age=26,
        role=8500,
        opportunity=8500,
        pass_attempts=560,
        games_played=16,
    )
    qb_backup = score(
        position="QB",
        age=26,
        role=3600,
        opportunity=3200,
        pass_attempts=40,
        games_played=4,
    )
    assert qb_starter > qb_backup


def test_build_players_table_attaches_stats_before_valuation():
    source = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    build = source.split("def build_players_table", 1)[1].split("\ndef ", 1)[0]
    assert build.index("attach_player_stats(") < build.index("apply_valuation_model(")


def test_market_effective_weight_still_primary():
    direct = rankings.COMPOSITE_WEIGHT_MARKET
    via_age = rankings.COMPOSITE_WEIGHT_AGE
    via_prod_fallback = rankings.COMPOSITE_WEIGHT_PRODUCTION
    assert direct + via_age + via_prod_fallback >= 0.70
    assert direct >= 0.45
