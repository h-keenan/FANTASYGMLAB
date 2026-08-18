"""Core valuation methodology + calibration harnesses.

Locks controlled scenario ordering, monotonicity, age curves, injury
double-count fixes, and cross-surface score_field consistency — without
rewriting football methodology or league-format multipliers.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import rankings
from modules import team_eval
from modules import trade_ideas


ROOT = Path(__file__).resolve().parents[1]
AGES = (20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34)
POSITIONS = ("QB", "RB", "WR", "TE")


def _composite_score(
    *,
    market: float,
    position: str,
    age: float,
    role: float,
    opportunity: float,
    risk: float = 1.0,
    replacement: float = 2500.0,
    production: float | None = None,
    games_played: float | None = None,
    targets: float | None = None,
    receptions: float | None = None,
    rush_attempts: float | None = None,
    pass_attempts: float | None = None,
    years_exp: float | None = None,
) -> float:
    """Deterministic replica of apply_valuation_model's composite math."""

    age_curve = market * rankings.age_multiplier(position, age)
    scarcity = max(
        0.0,
        market - replacement,
    ) * rankings.POSITION_SCARCITY_MULTIPLIER.get(position, 1.0)
    if production is None:
        production = rankings.production_usage_score(
            position=position,
            market_score=market,
            games_played=games_played,
            targets=targets,
            receptions=receptions,
            rush_attempts=rush_attempts,
            pass_attempts=pass_attempts,
            years_exp=years_exp,
        )["production_score"]
    composite = (
        market * rankings.COMPOSITE_WEIGHT_MARKET
        + age_curve * rankings.COMPOSITE_WEIGHT_AGE
        + float(production) * rankings.COMPOSITE_WEIGHT_PRODUCTION
        + scarcity * rankings.COMPOSITE_WEIGHT_SCARCITY
        + role * rankings.COMPOSITE_WEIGHT_ROLE
        + opportunity * rankings.COMPOSITE_WEIGHT_OPPORTUNITY
    )
    return composite * risk


def test_canonical_composite_weights_documented():
    source = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    assert "COMPOSITE_WEIGHT_MARKET = 0.44" in source
    assert "COMPOSITE_WEIGHT_AGE = 0.18" in source
    assert "COMPOSITE_WEIGHT_PRODUCTION = 0.12" in source
    assert "COMPOSITE_WEIGHT_SCARCITY = 0.10" in source
    assert "COMPOSITE_WEIGHT_ROLE = 0.06" in source
    assert "COMPOSITE_WEIGHT_OPPORTUNITY = 0.10" in source
    assert abs(
        rankings.COMPOSITE_WEIGHT_MARKET
        + rankings.COMPOSITE_WEIGHT_AGE
        + rankings.COMPOSITE_WEIGHT_PRODUCTION
        + rankings.COMPOSITE_WEIGHT_SCARCITY
        + rankings.COMPOSITE_WEIGHT_ROLE
        + rankings.COMPOSITE_WEIGHT_OPPORTUNITY
        - 1.0
    ) < 1e-9
    assert 'df["news_factor"] = 0.0' in source


def test_age_multiplier_continuous_and_position_aware():
    # Continuous interpolation — adjacent integer ages move smoothly.
    for pos in POSITIONS:
        prev = rankings.age_multiplier(pos, AGES[0])
        for age in AGES[1:]:
            curr = rankings.age_multiplier(pos, age)
            assert abs(curr - prev) <= 0.13, (pos, age, prev, curr)
            prev = curr
    # Fractional ages interpolate between integers.
    mid = rankings.age_multiplier("RB", 27.5)
    lo = rankings.age_multiplier("RB", 27)
    hi = rankings.age_multiplier("RB", 28)
    assert min(lo, hi) <= mid <= max(lo, hi)
    # Peak windows: young RB/WR premium; QB stays elevated longer.
    assert rankings.age_multiplier("RB", 22) > rankings.age_multiplier("RB", 30)
    assert rankings.age_multiplier("QB", 32) > rankings.age_multiplier("RB", 32)
    rb_curve = [rankings.age_multiplier("RB", age) for age in AGES]
    assert all(rb_curve[i] >= rb_curve[i + 1] for i in range(len(rb_curve) - 1))


def test_age_curve_adjacent_steps_bounded():
    """Adjacent integer ages should not jump more than the continuous-curve bound."""

    for pos in POSITIONS:
        prev = rankings.age_multiplier(pos, AGES[0])
        for age in AGES[1:]:
            curr = rankings.age_multiplier(pos, age)
            assert abs(curr - prev) <= 0.13, (pos, age, prev, curr)
            prev = curr


def test_holding_market_constant_age_alone_changes_value():
    market = 7000.0
    for pos in POSITIONS:
        scores = [
            _composite_score(
                market=market,
                position=pos,
                age=age,
                role=8500,
                opportunity=7600,
            )
            for age in AGES
        ]
        # Younger should not be strictly worse than older at same market.
        assert scores[0] >= scores[-1]
        if pos == "RB":
            assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


def test_injury_monotonicity_risk_and_availability():
    statuses = [
        ("Active", ""),
        ("Active", "Questionable"),
        ("Active", "Doubtful"),
        ("Injured Reserve", "Torn ACL"),
    ]
    dynasty = [
        rankings.risk_multiplier(status, "KC", 40, injury)
        for status, injury in statuses
    ]
    current = [
        rankings.current_availability_multiplier(status, "KC", 40, injury)
        for status, injury in statuses
    ]
    assert all(dynasty[i] >= dynasty[i + 1] for i in range(len(dynasty) - 1))
    assert all(current[i] >= current[i + 1] for i in range(len(current) - 1))
    # Temporary/season absence must crush current harder than long-term dynasty risk.
    assert current[-1] < dynasty[-1]
    assert dynasty[-1] == 0.68
    assert current[-1] == 0.42


def test_worse_injury_does_not_raise_composite():
    base = dict(market=6500.0, position="WR", age=25.0, role=8500.0, opportunity=7600.0)
    healthy = _composite_score(**base, risk=rankings.risk_multiplier("Active", "KC", 20, ""))
    major = _composite_score(
        **base,
        risk=rankings.risk_multiplier("Injured Reserve", "KC", 20, "Torn ACL"),
    )
    assert major < healthy


def test_opportunity_starter_injury_not_double_haircut():
    healthy = rankings.opportunity_profile(
        "RB",
        depth_chart_position="RB",
        market_score=6000,
        depth_chart_order=1,
        years_exp=3,
        age=24,
        status="Active",
        injury_status="",
    )
    major = rankings.opportunity_profile(
        "RB",
        depth_chart_position="RB",
        market_score=6000,
        depth_chart_order=1,
        years_exp=3,
        age=24,
        status="Injured Reserve",
        injury_status="Torn ACL",
    )
    assert healthy["opportunity_label"] == "Elite Opportunity"
    assert major["opportunity_label"] == "Starter At Risk"
    # Score is the Starter At Risk base (6600), not 6600*0.82.
    assert major["opportunity_score"] == 6600
    assert major["opportunity_score"] < healthy["opportunity_score"]
    assert "injury_overlay" in major["opportunity_source_flags"]


def test_lineup_uses_active_score_field_not_hardcoded_current():
    frame = pd.DataFrame(
        [
            {
                "player_id": "young",
                "name": "Young RB",
                "position": "RB",
                "dynasty_score": 9000,
                "value_score": 1000,
            },
            {
                "player_id": "old",
                "name": "Old RB",
                "position": "RB",
                "dynasty_score": 2000,
                "value_score": 8000,
            },
            {
                "player_id": "qb",
                "name": "QB",
                "position": "QB",
                "dynasty_score": 5000,
                "value_score": 5000,
            },
        ]
    )
    dynasty_lineup = team_eval.suggest_optimal_lineup(
        frame, {"QB": 1, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "K": 0}, score_field="dynasty_score"
    )
    current_lineup = team_eval.suggest_optimal_lineup(
        frame, {"QB": 1, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "K": 0}, score_field="value_score"
    )
    dynasty_rb = dynasty_lineup[
        (dynasty_lineup["position"] == "RB") & dynasty_lineup["suggested_starter"]
    ].iloc[0]["player_id"]
    current_rb = current_lineup[
        (current_lineup["position"] == "RB") & current_lineup["suggested_starter"]
    ].iloc[0]["player_id"]
    assert dynasty_rb == "young"
    assert current_rb == "old"


def test_my_team_boards_consume_score_field_parameter():
    source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    workspace = source.split("def render_my_team_workspace", 1)[1]
    assert workspace.count("score_field=score_field") >= 7
    assert 'score_field="value_score"' not in workspace


def test_production_vs_upside_controlled_profiles():
    """Market is the production proxy; youth alone must not dominate elite producers."""

    elite_veteran = _composite_score(
        market=8200, position="WR", age=29, role=8500, opportunity=9200
    )
    elite_young = _composite_score(
        market=8200, position="WR", age=23, role=8500, opportunity=9200
    )
    young_bench = _composite_score(
        market=2200, position="WR", age=21, role=3300, opportunity=3000
    )
    rookie_capital = _composite_score(
        market=4800, position="WR", age=21, role=4200, opportunity=4000
    )
    mid_starter = _composite_score(
        market=5200, position="WR", age=27, role=8500, opportunity=7600
    )
    aging_decline = _composite_score(
        market=3500, position="WR", age=32, role=5600, opportunity=4200
    )

    assert elite_young > elite_veteran
    assert elite_veteran > mid_starter > aging_decline
    assert elite_veteran > young_bench
    assert elite_veteran > rookie_capital
    assert rookie_capital > young_bench
    assert mid_starter > aging_decline


def test_positional_same_market_scarcity_order():
    market = 6000.0
    replacement = 2500.0
    scarcity = {
        pos: max(0.0, market - replacement)
        * rankings.POSITION_SCARCITY_MULTIPLIER.get(pos, 1.0)
        for pos in POSITIONS
    }
    assert scarcity["TE"] > scarcity["RB"] > scarcity["WR"] > scarcity["QB"]
    assert rankings.POSITION_SCARCITY_MULTIPLIER["RB"] > rankings.POSITION_SCARCITY_MULTIPLIER["WR"]
    assert rankings.POSITION_SCARCITY_MULTIPLIER["TE"] > rankings.POSITION_SCARCITY_MULTIPLIER["WR"]
    assert rankings.POSITION_SCARCITY_MULTIPLIER["QB"] < rankings.POSITION_SCARCITY_MULTIPLIER["WR"]

    # Same market + mid-career age: scarcity order TE > WR > QB survives continuous curves.
    by_pos = {
        pos: _composite_score(
            market=market,
            position=pos,
            age=26,
            role=8500,
            opportunity=7600,
            replacement=replacement,
        )
        for pos in ("WR", "TE", "QB")
    }
    assert by_pos["TE"] > by_pos["WR"] > by_pos["QB"]


def test_better_market_does_not_lower_value():
    low = _composite_score(market=4000, position="RB", age=24, role=7600, opportunity=7600)
    high = _composite_score(market=7000, position="RB", age=24, role=7600, opportunity=7600)
    assert high > low


def test_stronger_role_does_not_lower_value():
    weak = _composite_score(market=5000, position="WR", age=24, role=3300, opportunity=4200)
    strong = _composite_score(market=5000, position="WR", age=24, role=8500, opportunity=7600)
    assert strong > weak


def test_scenario_ordering_profiles_by_component_scores():
    market = 7000.0
    young_bellcow = _composite_score(
        market=market, position="RB", age=23, role=8500, opportunity=9200
    )
    older_bellcow = _composite_score(
        market=market, position="RB", age=29, role=8500, opportunity=9200
    )
    young_committee = _composite_score(
        market=market * 0.75, position="RB", age=23, role=5600, opportunity=5600
    )
    backup = _composite_score(
        market=market * 0.35, position="RB", age=24, role=3600, opportunity=3200
    )
    assert young_bellcow > older_bellcow > young_committee > backup

    young_wr = _composite_score(market=market, position="WR", age=22, role=8500, opportunity=9200)
    aging_wr = _composite_score(market=market, position="WR", age=31, role=8500, opportunity=9200)
    assert young_wr > aging_wr

    qb_drop = _composite_score(
        market=market, position="QB", age=24, role=8500, opportunity=9200
    ) - _composite_score(market=market, position="QB", age=34, role=8500, opportunity=9200)
    rb_drop = _composite_score(
        market=market, position="RB", age=24, role=8500, opportunity=9200
    ) - _composite_score(market=market, position="RB", age=34, role=8500, opportunity=9200)
    assert rb_drop > qb_drop


def test_pick_value_monotonic_by_round_and_years_out():
    settings = {"qb_format": "1QB", "scoring_format": "PPR", "league_size": 12}
    # Weakest team → early pick projection.
    summary = pd.DataFrame(
        {
            "roster_id": [1, 2, 3, 4],
            "total_score": [9000, 7000, 5000, 3000],
        }
    )

    def score(season: int, round_no: int) -> int:
        return int(
            trade_ideas._pick_value_components(
                season,
                round_no,
                4,
                summary,
                league_settings=settings,
            )["score"]
        )

    assert score(2027, 1) > score(2027, 2) > score(2027, 3) > score(2027, 4)
    assert score(2027, 1) > score(2028, 1) > score(2029, 1)
    assert trade_ideas._round_tier_base_value(1, "early") > trade_ideas._round_tier_base_value(
        1, "mid"
    )
    assert trade_ideas._round_tier_base_value(1, "mid") > trade_ideas._round_tier_base_value(
        1, "late"
    )


def test_better_draft_capital_does_not_lower_pick_value():
    assert trade_ideas._round_tier_base_value(1, "early") > trade_ideas._round_tier_base_value(
        2, "early"
    )
    assert trade_ideas._round_tier_base_value(2, "early") > trade_ideas._round_tier_base_value(
        3, "early"
    )


def test_dead_age_adjustment_not_used_in_composite():
    source = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    assert "age_multiplier(" in source
    assert 'df["age_curve_score"]' in source
    model = source.split("def apply_valuation_model", 1)[1].split("\ndef ", 1)[0]
    assert "age_adjustment" not in model


def test_strategy_age_curve_is_overlay_not_rankings_owner():
    """Strategy may reweight recommendation boards; rankings.py owns universal talent."""

    rankings_src = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    app_src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def apply_strategy_age_curve" not in rankings_src
    assert "def apply_strategy_age_curve" in app_src
    assert "def apply_valuation_model" in rankings_src


def test_rookie_years_exp_does_not_bypass_market_in_composite_formula():
    """NFL evidence proxy is market_score; years_exp only shapes opportunity labels."""

    source = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    role = source.split("def apply_role_and_opportunity", 1)[1].split("\ndef ", 1)[0]
    compose = source.split("def compose_composite_score", 1)[1].split("\ndef ", 1)[0]
    assert "years_exp" in role  # opportunity_profile / production input
    assert "COMPOSITE_WEIGHT_MARKET" in compose
    assert "years_exp" not in compose.split("composite = (", 1)[1].split(")", 1)[0]


def test_role_adjusted_lineup_does_not_clobber_canonical_value_score():
    """Role weights are a lineup overlay — canonical value_score must remain intact."""

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'my_team_df["role_adjusted_score"] = adjusted_scores' in source
    assert 'score_field="role_adjusted_score"' in source
    # Legacy clobber path must not remain on Game Plan / My Team role loops.
    assert 'my_team_df["value_score"] = adjusted_scores' not in source


def test_market_weight_dominates_but_football_components_can_move_order():
    """Adversarial: high market + poor role/opp vs lower market + elite role."""

    high_market_buried = _composite_score(
        market=7500, position="WR", age=24, role=1600, opportunity=1600
    )
    lower_market_starter = _composite_score(
        market=6200, position="WR", age=24, role=8500, opportunity=9200
    )
    # Market weight is large, but role+opportunity can still close gaps for near peers.
    assert abs(high_market_buried - lower_market_starter) / max(high_market_buried, 1) < 0.25
    # Extreme market still wins when football gap is not huge.
    elite_market = _composite_score(
        market=9500, position="WR", age=24, role=1600, opportunity=1600
    )
    assert elite_market > lower_market_starter
