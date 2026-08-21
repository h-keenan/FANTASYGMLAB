from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from modules.player_asset_explorer_ui import ranked_player_frame
from modules.player_eligibility import (
    annotate_player_eligibility,
    filter_current_fantasy_players,
    player_eligibility,
)
from modules.rankings import normalize_player_record


NOW = datetime(2026, 8, 21, tzinfo=timezone.utc)
CURRENT_NEWS_MS = int(datetime(2026, 6, 24, tzinfo=timezone.utc).timestamp() * 1000)


def _record(**overrides):
    record = {
        "player_id": "current-veteran",
        "full_name": "Current Veteran",
        "name": "Current Veteran",
        "sport": "nfl",
        "active": True,
        "status": "Active",
        "team": "LAC",
        "team_abbr": "LAC",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "years_exp": 12,
        "age": 33,
        "news_updated": CURRENT_NEWS_MS,
        "fantasycalc_value": 1200,
        "value_score": 1200,
    }
    record.update(overrides)
    return record


def _keenan_record() -> dict:
    inventory = json.loads(
        Path("data/sleeper_players.json").read_text(encoding="utf-8")
    )
    matches = [
        dict(record)
        for record in inventory.values()
        if str(record.get("full_name") or "").casefold() == "keenan allen"
    ]
    assert len(matches) == 1
    return matches[0]


def test_active_veteran_with_valid_team_is_included():
    assert player_eligibility(_record(), now=NOW)["eligible"] is True


def test_active_unsigned_veteran_is_not_excluded_by_missing_team_metadata():
    record = _record(team=None, team_abbr=None, fantasycalc_value=None)

    result = player_eligibility(record, now=NOW)

    assert result["eligible"] is True
    assert result["current_signal"] is True


def test_missing_external_valuation_does_not_remove_active_player():
    players = pd.DataFrame([_record(fantasycalc_value=None, value_score=0)])

    visible = filter_current_fantasy_players(players, now=NOW)

    assert visible["player_id"].tolist() == ["current-veteran"]


def test_explicit_inactive_and_retired_players_remain_excluded():
    players = pd.DataFrame(
        [
            _record(player_id="inactive", active=False),
            _record(player_id="retired", status="Retired"),
        ]
    )

    assert filter_current_fantasy_players(players, now=NOW).empty


def test_malformed_and_non_player_records_remain_excluded():
    players = pd.DataFrame(
        [
            _record(player_id="malformed", position=None, fantasy_positions=None),
            _record(player_id="non-player", position="OL", fantasy_positions=["OL"]),
        ]
    )

    assert filter_current_fantasy_players(players, now=NOW).empty


def test_actual_keenan_fields_pass_without_identity_specific_logic():
    record = _keenan_record()

    result = player_eligibility(record, now=NOW)

    assert record["active"] is True
    assert record["status"] == "Active"
    assert record["team"] is None
    assert record["fantasy_positions"] == ["WR"]
    assert result["eligible"] is True


def test_actual_keenan_survives_normalization_and_prepared_universe_filter():
    record = _keenan_record()
    normalized = normalize_player_record(str(record["player_id"]), record)
    prepared = filter_current_fantasy_players(
        pd.DataFrame([normalized]),
        surface="prepared_player_frame",
        now=NOW,
    )

    assert prepared["player_id"].astype(str).tolist() == [str(record["player_id"])]


def test_unsigned_active_player_remains_discoverable_in_explorer_and_trade_pool():
    eligible = _record(team=None, team_abbr=None, fantasycalc_value=None)
    other = _record(player_id="other", full_name="Other", name="Other", value_score=800)
    annotated = annotate_player_eligibility(pd.DataFrame([eligible, other]), now=NOW)

    explorer = ranked_player_frame(annotated, "value_score")
    trade_pool = filter_current_fantasy_players(
        annotated,
        surface="trade_search_pool",
        now=NOW,
    )

    assert "current-veteran" in explorer["player_id"].tolist()
    assert "current-veteran" in trade_pool["player_id"].tolist()


def test_eligibility_contract_version_invalidates_stored_annotation():
    player = pd.DataFrame([_record(team=None, team_abbr=None, fantasycalc_value=None)])
    stale = annotate_player_eligibility(player, now=NOW)
    stale.loc[:, "is_current_fantasy_eligible"] = False
    stale.loc[:, "trust_validation_fingerprint"] = "legacy-contract-fingerprint"

    refreshed = annotate_player_eligibility(stale, now=NOW)

    assert refreshed["is_current_fantasy_eligible"].tolist() == [True]
    assert refreshed["trust_validation_fingerprint"].iloc[0] != "legacy-contract-fingerprint"
