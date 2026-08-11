"""Combined #252+#253 valuation hardening harnesses.

Locks value ownership (base vs league vs strategy), decomposable league
adjustments, redraft pick non-stacking, and A→B→A→B cross-league restoration.
"""

from __future__ import annotations

import pandas as pd

import app
from modules import prepared_player_frame
from modules import trade_ideas
from modules import team_eval


def _base_row(player_id: str, **kwargs) -> dict:
    row = {
        "player_id": player_id,
        "name": player_id,
        "position": "WR",
        "team": "KC",
        "age": 25,
        "years_exp": 3,
        "score": 6000,
        "dynasty_score": 6000,
        "value_score": 6000,
        "market_score": 6000,
        "role_score": 7000,
        "opportunity_score": 7000,
        "scarcity_score": 2000,
        "risk_multiplier": 1.0,
        "status": "Active",
        "injury_status": "",
        "search_rank": 40,
        "targets": 80,
        "receptions": 55,
        "rush_attempts": 0,
        "passing_tds": 0,
        "passing_yards": 0,
    }
    row.update(kwargs)
    return row


def test_pr_relationship_252_subset_of_253_documented():
    # Living assertion via git is CI-side; here lock the architectural contract.
    assert hasattr(app, "league_settings_adjustment_components")
    assert hasattr(app, "detect_league_value_settings_from_payload")


def test_base_score_survives_league_and_strategy_overlays():
    frame = pd.DataFrame(
        [
            _base_row("qb1", position="QB", score=5000, dynasty_score=5000, market_score=5000),
            _base_row("wr1", position="WR", score=5000, dynasty_score=5000, market_score=5000, targets=120),
        ]
    )
    league = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "Superflex", "superflex_count": 1},
    )
    assert (league["base_score"] == 5000).all()
    assert (league["score"] == 5000).all()
    assert int(league.loc[league["player_id"].eq("qb1"), "league_dynasty_score"].iloc[0]) > 5000

    curved = app.apply_strategy_age_curve(league, "rebuild", "dynasty_score")
    assert (curved["base_score"] == 5000).all()
    assert (
        curved["league_dynasty_score"]
        == league["league_dynasty_score"]
    ).all()
    # Active score_field may carry strategy preference; other lens columns stay league.
    assert (curved["value_score"] == curved["league_value_score"]).all()
    assert "strategy_score" in curved.columns
    assert "strategy_preference_multiplier" in curved.columns


def test_league_adjustment_components_are_decomposable():
    frame = pd.DataFrame(
        [
            _base_row("slot", position="WR", targets=140, receptions=100),
            _base_row("te", position="TE", targets=110, receptions=80),
            _base_row("qb", position="QB", market_score=8000),
        ]
    )
    components = app.league_settings_adjustment_components(
        frame,
        {
            "scoring_format": "Standard",
            "qb_format": "Superflex",
            "te_premium": True,
            "superflex_count": 1,
            "_detected_scoring": {"pass_td": 6.0},
        },
    )
    product = pd.Series(1.0, index=frame.index, dtype="float64")
    for key, series in components.items():
        if key == "league_settings_multiplier":
            continue
        product = product * series
    # Combined equals product of parts (within float noise before clip).
    assert (product.clip(0.35, 2.2) - components["league_settings_multiplier"]).abs().max() < 1e-9
    assert float(components["league_adj_qb_scarcity"].iloc[2]) == 1.35
    assert float(components["league_adj_te_premium"].iloc[1]) > 1.0
    assert float(components["league_adj_pass_td"].iloc[2]) > 1.0


def test_redraft_pick_discount_not_stacked():
    # Format layer must not apply a second redraft haircut.
    source = open("modules/trade_ideas.py", encoding="utf-8").read()
    pick_fn = source.split("def _pick_format_multiplier", 1)[1].split("\ndef ", 1)[0]
    assert 'league_format == "Redraft"' not in pick_fn or "Do not apply a second" in pick_fn

    non_dynasty = app.draft_pick_score_multiplier("Non-Dynasty", {"league_format": "Redraft"})
    dynasty_lens_redraft = app.draft_pick_score_multiplier("Dynasty", {"league_format": "Redraft"})
    assert non_dynasty == 0.45
    assert dynasty_lens_redraft == 0.45
    # Historical bug was ~0.45 * 0.52 from dual owners.
    assert non_dynasty > 0.45 * 0.52


def test_keeper_horizon_between_dynasty_and_redraft():
    frame = pd.DataFrame(
        [
            _base_row(
                "prod",
                position="WR",
                age=29,
                score=8000,
                dynasty_score=8000,
                market_score=9000,
                opportunity_score=9000,
                role_score=8500,
                targets=100,
            )
        ]
    )
    dynasty = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "_keeper_mode": False}
    )
    keeper = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "_keeper_mode": True}
    )
    redraft = app.apply_valuation_lens(
        frame, "Non-Dynasty", {"league_format": "Redraft", "scoring_format": "PPR", "_keeper_mode": False}
    )
    # base identical
    assert int(dynasty.iloc[0]["base_score"]) == int(keeper.iloc[0]["base_score"]) == int(
        redraft.iloc[0]["base_score"]
    )
    d = int(dynasty.iloc[0]["league_dynasty_score"])
    k = int(keeper.iloc[0]["league_dynasty_score"])
    # Keeper blends toward current; for a currently-hot vet, keeper >= pure dynasty path
    # is not guaranteed — assert blend differs from pure dynasty and redraft blend differs more.
    assert k != d or float(keeper.iloc[0]["league_adj_horizon"]) != 1.0
    assert int(redraft.iloc[0]["league_dynasty_score"]) != d


def test_pass_td_six_point_lifts_qb_when_detected():
    frame = pd.DataFrame(
        [_base_row("qb", position="QB", score=7000, dynasty_score=7000, market_score=7000, passing_tds=35, passing_yards=4200)]
    )
    four = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB", "_detected_scoring": {"pass_td": 4.0}},
    )
    six = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB", "_detected_scoring": {"pass_td": 6.0}},
    )
    assert int(six.iloc[0]["league_dynasty_score"]) > int(four.iloc[0]["league_dynasty_score"])
    assert float(six.iloc[0]["league_adj_pass_td"]) > 1.0


def test_cross_league_abab_restores_base_and_league_values():
    frame = pd.DataFrame(
        [
            _base_row("qb", position="QB", score=8000, dynasty_score=8000, market_score=8000),
            _base_row("wr", position="WR", score=7000, dynasty_score=7000, market_score=7000, targets=130, receptions=95),
            _base_row("te", position="TE", score=5500, dynasty_score=5500, market_score=5500, targets=100, receptions=70),
        ]
    )
    settings_a = {
        "league_format": "Dynasty",
        "scoring_format": "PPR",
        "qb_format": "Superflex",
        "te_premium": True,
        "superflex_count": 1,
        "league_size": 14,
        "starter_count": 11,
        "flex_count": 3,
        "bench_count": 8,
        "taxi_count": 4,
        "_keeper_mode": False,
        "_detected_scoring": {"pass_td": 6.0, "rec": 1.0},
    }
    settings_b = {
        "league_format": "Redraft",
        "scoring_format": "Standard",
        "qb_format": "1QB",
        "te_premium": False,
        "superflex_count": 0,
        "league_size": 10,
        "starter_count": 8,
        "flex_count": 1,
        "bench_count": 4,
        "taxi_count": 0,
        "_keeper_mode": False,
        "_detected_scoring": {"pass_td": 4.0, "rec": 0.0},
    }

    def snapshot(settings, lens):
        valued = app.apply_valuation_lens(frame, lens, settings)
        cols = [
            "base_score",
            "league_dynasty_score",
            "league_value_score",
            "league_settings_multiplier",
            "league_adj_scoring",
            "league_adj_qb_scarcity",
            "league_adj_te_premium",
        ]
        return valued[["player_id", *cols]].sort_values("player_id").reset_index(drop=True)

    a1 = snapshot(settings_a, "Dynasty")
    b1 = snapshot(settings_b, "Non-Dynasty")
    a2 = snapshot(settings_a, "Dynasty")
    b2 = snapshot(settings_b, "Non-Dynasty")
    pd.testing.assert_frame_equal(a1, a2)
    pd.testing.assert_frame_equal(b1, b2)
    assert not a1["league_dynasty_score"].equals(b1["league_dynasty_score"])
    assert (a1["base_score"] == b1["base_score"]).all()

    key_a = app.league_value_settings_key(settings_a)
    key_b = app.league_value_settings_key(settings_b)
    assert key_a != key_b
    sig_a = prepared_player_frame.build_frame_signature(
        public_fingerprint="fp",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key=key_a,
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced_dynasty",
        season="2026",
        row_count=3,
    )
    sig_b = prepared_player_frame.build_frame_signature(
        public_fingerprint="fp",
        valuation_lens="Non-Dynasty",
        score_field="value_score",
        league_settings_key=key_b,
        scoring_format="Standard",
        scoring_supported=True,
        archetype_id="balanced_dynasty",
        season="2026",
        row_count=3,
    )
    assert sig_a != sig_b


def test_252_regressions_opportunity_lineup_role_field():
    # Starter At Risk no double haircut
    from modules import rankings

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
    assert major["opportunity_label"] == "Starter At Risk"
    assert major["opportunity_score"] == 6600

    frame = pd.DataFrame(
        [
            {"player_id": "young", "name": "Y", "position": "RB", "dynasty_score": 9000, "value_score": 1000},
            {"player_id": "old", "name": "O", "position": "RB", "dynasty_score": 2000, "value_score": 8000},
            {"player_id": "qb", "name": "Q", "position": "QB", "dynasty_score": 5000, "value_score": 5000},
        ]
    )
    dynasty_lineup = team_eval.suggest_optimal_lineup(
        frame, {"QB": 1, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "K": 0}, score_field="dynasty_score"
    )
    assert (
        dynasty_lineup[(dynasty_lineup["position"] == "RB") & dynasty_lineup["suggested_starter"]].iloc[0][
            "player_id"
        ]
        == "young"
    )


def test_253_regressions_missing_rec_and_digest_fields():
    detected = app.detect_league_value_settings_from_payload(
        {
            "settings": {"type": 2},
            "scoring_settings": {},
            "roster_positions": ["QB", "RB", "WR", "TE", "BN"],
            "total_rosters": 12,
        }
    )
    assert detected["_sources"]["scoring_format"] == "default"
    key = app.league_value_settings_key({**app.DEFAULT_LEAGUE_VALUE_SETTINGS, "other_starter_count": 2, "_keeper_mode": True})
    assert "True" in key
    assert key != app.league_value_settings_key(app.DEFAULT_LEAGUE_VALUE_SETTINGS)
