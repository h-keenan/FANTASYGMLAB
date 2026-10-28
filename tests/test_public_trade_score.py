"""Audit C2: the public Analyzer prices trades with the app's age-curved value."""

from unittest.mock import patch

import pandas as pd

from modules import external_interesting_trades, league_value_settings, public_dynasty_values, trade_hub_engine


def _frame():
    rows = []
    for idx, (pos, base, age) in enumerate([("WR", 9000, 22), ("WR", 8900, 33), ("RB", 8000, 24), ("QB", 7000, 36)]):
        rows.append(
            {
                "player_id": str(8000 + idx), "name": f"P{idx}", "position": pos, "team": "KC", "age": age,
                "years_exp": 3, "status": "Active", "injury_status": None, "search_rank": 10 + idx,
                "score": base, "dynasty_score": base, "value_score": base, "market_score": base,
                "role_score": base, "opportunity_score": base, "scarcity_score": base,
                "risk_multiplier": 1.0, "workload_trend": "Stable",
            }
        )
    return pd.DataFrame(rows)


def _board(fmt="1qb"):
    with patch("modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kw: df):
        return public_dynasty_values.build_public_dynasty_values(_frame(), fmt)


def test_public_board_carries_the_age_curved_trade_score_next_to_the_ranking_score():
    board = _board()
    assert board["trade_strategy"] == trade_hub_engine.DEFAULT_ANALYZER_STRATEGY
    rows = {r["name"]: r for r in board["players"]}
    assert all("trade_score" in r for r in rows.values())
    # Rankings stay un-curved; the curve moves the old player down relative to the young one.
    assert rows["P0"]["score"] > rows["P1"]["score"]
    assert (rows["P0"]["trade_score"] - rows["P1"]["trade_score"]) > (rows["P0"]["score"] - rows["P1"]["score"])


def test_public_trade_score_equals_what_the_signed_in_pipeline_prices():
    board = _board()
    settings = public_dynasty_values.settings_for_format("1qb")
    with patch("modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kw: df):
        valued = league_value_settings.apply_valuation_lens(_frame(), "Dynasty", settings)
    field = league_value_settings.valuation_score_field("Dynasty")
    expected = trade_hub_engine.apply_strategy_age_curve(valued, external_interesting_trades.STRATEGY, field)
    by_id = {str(r["player_id"]): int(round(float(r[field]))) for _, r in expected.iterrows()}
    for row in board["players"]:
        assert row["trade_score"] == by_id[row["player_id"]]


def test_one_neutral_strategy_constant_for_every_surface():
    assert external_interesting_trades.STRATEGY == trade_hub_engine.DEFAULT_ANALYZER_STRATEGY
    from services import mobile_api_service

    assert mobile_api_service.TradeAnalyzerRequest().strategy == trade_hub_engine.DEFAULT_ANALYZER_STRATEGY
