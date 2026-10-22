"""Regression (logic audit 2026-10): modules.rankings stores age 99.0 for a
player with no birth date (212 rows in the audited players.db, mostly UDFA
rookies). Averaging that placeholder made one such player add years to a
roster's average age: a rebuilding team receiving a rookie for free got
the maximum "pushes the roster older" age penalty (-2)."""

from __future__ import annotations

import pandas as pd

from modules import trade_analyzer_fit, trade_ideas
from modules.team_eval import known_player_ages


def _row(pid, position, score, age):
    return {
        "player_id": pid,
        "name": pid,
        "position": position,
        "age": age,
        "value_score": score,
        "dynasty_score": score,
        "status": "Active",
        "injury_status": "",
        "team": "DET",
    }


def _asset(row):
    return {"asset_type": "player", "score": row["dynasty_score"], **row}


def test_known_player_ages_drops_placeholder_and_missing():
    ages = known_player_ages([24.0, 99.0, None, float("nan"), 31, 0])
    assert sorted(ages.tolist()) == [24.0, 31.0]


def test_receiving_unknown_age_rookie_does_not_age_a_rebuilding_roster():
    roster = pd.DataFrame(
        [
            _row("qb", "QB", 5000, 24),
            _row("rb1", "RB", 4000, 23),
            _row("rb2", "RB", 3500, 25),
            _row("wr1", "WR", 4500, 22),
            _row("wr2", "WR", 3000, 24),
            _row("wr3", "WR", 2500, 23),
            _row("te", "TE", 2000, 25),
        ]
    )
    rookie = _row("udfa", "RB", 800, 99.0)
    pool = pd.concat([roster, pd.DataFrame([rookie])], ignore_index=True)
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        my_team_df=roster,
        all_players_df=pool,
        send_assets=[],
        receive_assets=[_asset(rookie)],
        metrics=None,
        strategy="rebuild",
        lineup_settings=None,
        score_field="dynasty_score",
    )
    assert fit["component_scores"]["age"] == 0
    assert "pushes the roster older" not in fit["strategy_summary"]


def test_trade_idea_side_age_ignores_placeholder():
    assets = [
        {"asset_type": "player", "age": 24.0},
        {"asset_type": "player", "age": 99.0},
    ]
    assert trade_ideas._asset_avg_age(assets) == 24.0
