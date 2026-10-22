"""Invariant: every idea Trade Hub surfaces grades at least FAIR in the Trade Analyzer.

Runs the real (unmocked) Hub engine on scripts/profile_trade_hub.py's
synthetic 1QB and Superflex leagues the way production does
(trade_hub_engine.apply_strategy_age_curve, then trade_ideas'
build path, then Trust enforcement), and grades every surfaced idea
independently through the mobile / web-next Trade Analyzer path:
assets rebuilt from the strategy-adjusted pool with
trade_analyzer_assembly.player_asset_from_mapping, then
trade_analyzer_fit.evaluate_trade_analyzer_fit and
trade_offer_analyzer.decide_offer_verdict.
"""

from __future__ import annotations

import pytest

from modules import trade_analyzer_fit, trade_ideas, trade_offer_analyzer
from modules.trade_analyzer_assembly import player_asset_from_mapping
from modules.trade_hub_engine import (
    apply_strategy_age_curve,
    strategy_adjusted_pick_score_multiplier,
)
from modules.trust_enforcement import enforce_trade_board
from scripts.profile_trade_hub import FixtureSpec, _trust_context, build_fixture

SCORE_FIELD = "value_score"


def _surfaced_ideas(fixture, strategy):
    pool = apply_strategy_age_curve(fixture["players"], strategy, SCORE_FIELD)
    raw = trade_ideas._build_trade_ideas_impl(
        pool,
        "fixture-league",
        fixture["summary"],
        1,
        [],
        [],
        {},
        max_ideas=8,
        score_field=SCORE_FIELD,
        pick_score_multiplier=strategy_adjusted_pick_score_multiplier(1.0, strategy),
        team_strategy=strategy,
        league_settings=fixture["settings"],
        draft_status={"draft_year": 2026, "current_year_picks_active": True},
        adapter=fixture["adapter"],
    )
    board = enforce_trade_board(raw, **_trust_context(fixture, raw))
    return pool, list(board.recommendations)


def _analyzer_verdict(fixture, pool, strategy, idea):
    rows = {str(row["player_id"]): row for row in pool.to_dict("records")}

    def rebuild(assets):
        rebuilt = []
        for asset in assets or ():
            if asset.get("asset_type") == "player":
                rebuilt.append(player_asset_from_mapping(rows[str(asset["player_id"])], score_field=SCORE_FIELD))
            else:
                rebuilt.append(dict(asset))
        return rebuilt

    send = rebuild(idea["send_assets"])
    receive = rebuild(idea["receive_assets"])
    my_team_df = pool[pool["player_id"].isin(fixture["rosters"][0]["players"])]
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        my_team_df=my_team_df,
        all_players_df=pool,
        send_assets=send,
        receive_assets=receive,
        metrics=None,
        strategy=strategy,
        lineup_settings=fixture["settings"],
        score_field=SCORE_FIELD,
    )
    assert fit and fit.get("available")
    return trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)


@pytest.mark.parametrize(
    ("spec", "current_week"),
    (
        (FixtureSpec("8-team-1qb", 8, 22, "1QB", strategy="contender"), 8),
        (FixtureSpec("8-team-1qb", 8, 22, "1QB", strategy="rebuild"), 8),
        (FixtureSpec("8-team-1qb", 8, 22, "1QB", strategy="retool"), 0),
        (FixtureSpec("8-team-superflex", 8, 26, "Superflex", strategy="contender"), 8),
        (FixtureSpec("8-team-superflex", 8, 26, "Superflex", strategy="rebuild"), 0),
        (FixtureSpec("12-team-superflex", 12, 28, "Superflex", strategy="retool"), 8),
    ),
    ids=lambda value: value.label + "-" + value.strategy if isinstance(value, FixtureSpec) else f"week{value}",
)
def test_every_surfaced_hub_idea_grades_at_least_fair_in_the_analyzer(spec, current_week):
    fixture = build_fixture(spec)
    fixture["settings"] = dict(fixture["settings"], current_week=current_week)

    pool, ideas = _surfaced_ideas(fixture, spec.strategy)

    assert ideas, "the synthetic league should still produce Hub ideas"
    failures = []
    for idea in ideas:
        verdict = _analyzer_verdict(fixture, pool, spec.strategy, idea)
        # Hub's own gate recorded the same verdict on the idea.
        assert idea.get("analyzer_verdict") == verdict.ui_verdict
        if verdict.ui_verdict not in {"FAIR", "ACCEPT"}:
            failures.append((idea.get("my_player"), idea.get("their_player"), verdict.band, verdict.value_delta))
    assert not failures, failures
