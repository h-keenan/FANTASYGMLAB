from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app
from modules import league_history
from modules import player_state_authority
from modules import rankings
from modules import structured_player_refresh
from modules.player_asset_explorer_ui import filter_player_results, ranked_player_frame
from modules.player_eligibility import player_eligibility


def _inventory() -> dict:
    return json.loads(Path("data/sleeper_players.json").read_text(encoding="utf-8"))


def _actual_record(full_name: str) -> dict:
    matches = [
        dict(record)
        for record in _inventory().values()
        if str(record.get("full_name") or "").casefold() == full_name.casefold()
    ]
    assert len(matches) == 1
    return matches[0]


def _persisted_frame() -> pd.DataFrame:
    with sqlite3.connect("data/players.db") as connection:
        return pd.read_sql_query("SELECT * FROM players", connection)


def _reconciled_frame() -> pd.DataFrame:
    return structured_player_refresh.refresh_structured_player_state(
        _persisted_frame(),
        _inventory(),
    )


def test_actual_keenan_survives_current_player_universe_reconciliation():
    keenan = _actual_record("Keenan Allen")
    frame = _reconciled_frame()
    row = frame.loc[frame["player_id"].astype(str).eq(str(keenan["player_id"]))]

    assert player_eligibility(keenan)["eligible"] is True
    assert len(row) == 1
    assert bool(row.iloc[0]["is_current_fantasy_eligible"]) is True


def test_query_keenan_returns_actual_player_with_default_explorer_filters():
    frame = player_state_authority.current_player_pool(
        _reconciled_frame(),
        surface="player_asset_explorer",
    )
    searched = app.search_trade_assets(
        frame,
        [],
        "Keenan",
        asset_filter="All",
        limit=60,
    )
    players = searched.loc[searched["asset_type"].eq("player")].copy()
    visible = filter_player_results(
        players,
        age_filter="All ages",
        status_filter="All statuses",
        availability_filter="All availability",
        rostered_player_ids=set(),
        is_injury_status=rankings.is_injury_status,
    )

    assert "Keenan Allen" in visible["name"].tolist()


def test_active_unsigned_cached_market_value_remains_globally_searchable():
    keenan = _actual_record("Keenan Allen")
    persisted = _persisted_frame()
    inventory = {str(keenan["player_id"]): keenan}
    frame = structured_player_refresh.refresh_structured_player_state(
        persisted,
        inventory,
    )
    row = frame.loc[frame["player_id"].astype(str).eq(str(keenan["player_id"]))]

    assert len(row) == 1
    assert float(row.iloc[0]["fantasycalc_value"]) == 222.0
    assert float(row.iloc[0]["value_score"]) == 1060.0
    assert row.iloc[0]["valuation_authority_status"] == "canonical_provider_backed"
    assert bool(row.iloc[0]["valuation_is_authoritative"]) is True


def test_actual_ben_is_absent_from_current_trade_and_waiver_pools():
    ben = _actual_record("Ben Roethlisberger")
    frame = _reconciled_frame()
    current = player_state_authority.current_player_pool(
        frame,
        surface="trade_search_pool",
    )
    waivers = player_state_authority.transaction_available_player_pool(
        frame,
        {},
        surface="waiver_free_agents",
    )

    assert player_eligibility(ben)["eligible"] is False
    assert str(ben["player_id"]) not in current["player_id"].astype(str).tolist()
    assert str(ben["player_id"]) not in waivers["player_id"].astype(str).tolist()


def test_historical_identity_lookup_still_resolves_retired_player():
    ben = _actual_record("Ben Roethlisberger")
    lookup = league_history.player_lookup_from_rows([ben])

    assert lookup[str(ben["player_id"])]["name"] == "Ben Roethlisberger"


def test_roster_browser_uses_membership_without_deleting_global_identity():
    keenan = _actual_record("Keenan Allen")
    frame = player_state_authority.current_player_pool(
        _reconciled_frame(),
        surface="trade_search_pool",
    )
    global_result = app.player_search_results(frame, "Keenan", limit=8)
    roster_result = app.player_search_results(
        frame,
        "Keenan",
        owned_player_ids={"not-keenan"},
        only_owned=True,
        limit=8,
    )

    assert str(keenan["player_id"]) in global_result["player_id"].astype(str).tolist()
    assert roster_result.empty


def test_ranked_explorer_source_retains_reconciled_current_identity():
    keenan = _actual_record("Keenan Allen")
    current = player_state_authority.current_player_pool(
        _reconciled_frame(),
        surface="prepared_player_frame",
    )
    ranked = ranked_player_frame(current, "value_score")

    assert str(keenan["player_id"]) in ranked["player_id"].astype(str).tolist()


def test_public_cache_fingerprint_depends_on_eligibility_contract(monkeypatch):
    before = rankings.public_player_source_fingerprint("data/players.db")
    monkeypatch.setattr(rankings, "PLAYER_ELIGIBILITY_CONTRACT_VERSION", "next-contract")
    after = rankings.public_player_source_fingerprint("data/players.db")

    assert before != after
    assert any(item[0] == "player_eligibility_contract" for item in before)


def test_actual_load_players_path_reconciles_missing_identity(tmp_path):
    keenan = _actual_record("Keenan Allen")
    db_path = tmp_path / "players.db"
    shutil.copyfile("data/players.db", db_path)
    rankings.clear_public_player_cache()

    with patch(
        "modules.sleeper.requests.get",
        side_effect=AssertionError("player reconciliation must remain disk-only"),
    ), patch(
        "modules.fantasycalc.requests.get",
        side_effect=AssertionError("player reconciliation must remain disk-only"),
    ):
        loaded = rankings.load_players(str(db_path))

    assert str(keenan["player_id"]) in loaded["player_id"].astype(str).tolist()
    assert rankings._player_universe_cache_is_current(str(db_path)) is True


def test_persisted_universe_metadata_invalidates_when_contract_changes(tmp_path, monkeypatch):
    db_path = tmp_path / "players.db"
    shutil.copyfile("data/players.db", db_path)
    rankings.clear_public_player_cache()
    rankings.load_players(str(db_path))
    assert rankings._player_universe_cache_is_current(str(db_path)) is True

    monkeypatch.setattr(rankings, "PLAYER_ELIGIBILITY_CONTRACT_VERSION", "future-contract")

    assert rankings._player_universe_cache_is_current(str(db_path)) is False
