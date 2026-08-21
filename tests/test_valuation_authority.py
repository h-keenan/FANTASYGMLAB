from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from modules import rankings, structured_player_refresh, trade_analyzer_assembly, trade_analyzer_builder
from modules.player_eligibility import filter_current_fantasy_players
from modules.valuation_authority import (
    MODEL_DERIVED,
    PROVIDER_BACKED,
    RECONCILED_UNMODELED,
    annotate_valuation_authority,
)


def _persisted() -> pd.DataFrame:
    with sqlite3.connect("data/players.db") as connection:
        return pd.read_sql_query("SELECT * FROM players", connection)


def _inventory() -> dict:
    return json.loads(Path("data/sleeper_players.json").read_text(encoding="utf-8"))


def test_normal_provider_backed_player_keeps_canonical_score_and_provenance():
    source = _persisted()
    original = source.loc[source["name"].eq("Davante Adams")].iloc[0]
    annotated = annotate_valuation_authority(source)
    row = annotated.loc[annotated["name"].eq("Davante Adams")].iloc[0]

    assert float(row["fantasycalc_value"]) > 0
    assert row["valuation_authority_status"] == PROVIDER_BACKED
    assert bool(row["valuation_is_authoritative"]) is True
    assert int(row["score"]) == int(original["score"])


def test_canonical_model_result_without_provider_row_remains_authoritative():
    row = pd.DataFrame(
        [{
            "player_id": "modeled",
            "fantasycalc_value": 0,
            "valuation_blend": "Sleeper rank + age/VORP/role (market unavailable)",
            "role_score": 3100,
            "opportunity_label": "Starter",
            "score": 2200,
            "dynasty_score": 2200,
            "value_score": 2200,
            "market_score": 1800,
        }]
    )
    result = annotate_valuation_authority(row).iloc[0]

    assert result["valuation_authority_status"] == MODEL_DERIVED
    assert bool(result["valuation_is_authoritative"]) is True
    assert int(result["score"]) == 2200


def test_actual_keenan_cached_provider_value_runs_canonical_local_model():
    with patch(
        "modules.fantasycalc.requests.get",
        side_effect=AssertionError("cached reconciliation must not call FantasyCalc"),
    ), patch(
        "modules.sleeper.requests.get",
        side_effect=AssertionError("cached reconciliation must not call Sleeper"),
    ):
        frame = structured_player_refresh.refresh_structured_player_state(_persisted(), _inventory())
    current = filter_current_fantasy_players(frame, surface="valuation_authority_test")
    row = current.loc[current["name"].eq("Keenan Allen")].iloc[0]
    persisted = _persisted()
    normal_before = persisted.loc[persisted["name"].eq("Davante Adams")].iloc[0]
    normal_after = frame.loc[frame["name"].eq("Davante Adams")].iloc[0]

    assert float(row["fantasycalc_value"]) == 222.0
    assert row["valuation_authority_status"] == PROVIDER_BACKED
    assert row["valuation_authority_source"] == "fantasycalc_plus_canonical_model"
    assert int(row["value_score"]) == 1060
    assert int(row["value_score"]) != 6417
    assert bool(row["valuation_trade_eligible"]) is True
    assert int(normal_after["value_score"]) == int(normal_before["value_score"])

    asset = trade_analyzer_assembly.player_asset_from_mapping(row.to_dict())
    assert trade_analyzer_builder.valid_package_assets([asset]) == [asset]


def test_reconciled_player_without_cached_provider_support_remains_unmodeled(tmp_path, monkeypatch):
    empty_cache = tmp_path / "fantasycalc.csv"
    pd.DataFrame(columns=["name", "position", "team", "value"]).to_csv(empty_cache, index=False)
    monkeypatch.setattr(rankings, "FANTASYCALC_CACHE_PATH", str(empty_cache))
    unsupported = {
        "player_id": "active-no-local-evidence",
        "full_name": "Active No Evidence",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "active": True,
        "status": "Active",
        "search_rank": None,
        "age": 25,
        "years_exp": 3,
        "news_updated": 1787350000000,
    }

    with patch("modules.fantasycalc.requests.get", side_effect=AssertionError("network")):
        frame = structured_player_refresh.refresh_structured_player_state(
            _persisted(), {str(unsupported["player_id"]): unsupported}
        )
    row = frame.loc[frame["name"].eq("Active No Evidence")].iloc[0]

    assert row["valuation_authority_status"] == RECONCILED_UNMODELED
    assert int(row["value_score"]) == 0
    asset = trade_analyzer_assembly.player_asset_from_mapping(row.to_dict())
    assert trade_analyzer_builder.valid_package_assets([asset]) == []


def test_retired_player_remains_outside_actionable_universe():
    frame = structured_player_refresh.refresh_structured_player_state(_persisted(), _inventory())
    current = filter_current_fantasy_players(frame, surface="valuation_authority_test")

    assert "Keenan Allen" in current["name"].tolist()
    assert "Ben Roethlisberger" not in current["name"].tolist()


def test_legacy_analyzer_assets_remain_compatible_but_explicit_unmodeled_is_rejected():
    legacy = {"asset_type": "player", "player_id": "normal", "score": 1000}
    unmodeled = {
        "asset_type": "player",
        "player_id": "pending",
        "score": 6417,
        "valuation_trade_eligible": False,
    }

    assert trade_analyzer_builder.valid_package_assets([legacy]) == [legacy]
    assert trade_analyzer_builder.valid_package_assets([unmodeled]) == []
