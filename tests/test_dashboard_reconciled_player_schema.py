from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from modules import structured_player_refresh, trade_ideas
from modules.player_eligibility import filter_current_fantasy_players


def _inventory() -> dict:
    return json.loads(Path("data/sleeper_players.json").read_text(encoding="utf-8"))


def _persisted_frame() -> pd.DataFrame:
    with sqlite3.connect("data/players.db") as connection:
        return pd.read_sql_query("SELECT * FROM players", connection)


def test_reconciled_rows_use_persisted_schema_safe_nulls():
    reconciled = structured_player_refresh.refresh_structured_player_state(
        _persisted_frame(),
        _inventory(),
    )
    crash_rows = reconciled.loc[
        reconciled["name"].isin(
            ("Tyreek Hill", "Joe Mixon", "Najee Harris", "Darren Waller")
        )
    ]

    assert len(crash_rows) == 4
    assert crash_rows["opportunity_label"].notna().all()
    assert crash_rows["valuation_authority_status"].eq("canonical_provider_backed").all()
    assert all(
        value is not pd.NA
        for _, row in crash_rows.iterrows()
        for value in row.tolist()
    )


def test_dashboard_game_plan_trade_shape_accepts_reconciled_players():
    """Exercise the real Dashboard trade-shape path that crashed after #375."""

    reconciled = structured_player_refresh.refresh_structured_player_state(
        _persisted_frame(),
        _inventory(),
    )
    partner_team = reconciled.loc[
        reconciled["name"].isin(
            ("Tyreek Hill", "Joe Mixon", "Najee Harris", "Darren Waller")
        )
    ].copy()
    metrics = {
        "strategy": "competitive",
        "mode": "competitive",
        "strengths": [],
        "weaknesses": [],
    }

    with patch.object(trade_ideas, "get_team_vs_league", return_value=metrics):
        shape = trade_ideas._build_team_shape(
            pd.DataFrame(),
            2,
            partner_team,
            score_field="value_score",
            league_settings={},
        )

    assert shape["injured_count"] == 4
    assert shape["health_flag"] == "Injury Crisis"


def test_reconciled_universe_keeps_current_and_excludes_retired_players():
    reconciled = structured_player_refresh.refresh_structured_player_state(
        _persisted_frame(),
        _inventory(),
    )
    current = filter_current_fantasy_players(
        reconciled,
        surface="prepared_player_frame",
    )

    assert "Keenan Allen" in current["name"].tolist()
    assert "Ben Roethlisberger" not in current["name"].tolist()
