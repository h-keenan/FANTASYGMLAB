from __future__ import annotations

import os
import sqlite3

import pandas as pd

from modules import rankings
from modules.valuation_authority import VALUATION_AUTHORITY_CONTRACT_VERSION


def _tiny_inputs(tmp_path, monkeypatch):
    sleeper = tmp_path / "sleeper_players.json"
    sleeper.write_text('{"1": {"player_id": "1"}}', encoding="utf-8")
    fantasycalc = tmp_path / "fantasycalc_values.csv"
    fantasycalc.write_text("name,value\nA,1\n", encoding="utf-8")
    stats = tmp_path / "season_stats.json"
    stats.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(rankings.sleeper_module, "PLAYERS_CACHE_PATH", str(sleeper))
    monkeypatch.setattr(rankings, "FANTASYCALC_CACHE_PATH", str(fantasycalc))
    monkeypatch.setattr(
        rankings.sleeper_module,
        "PLAYER_STATS_CACHE_TEMPLATE",
        str(stats),
    )
    monkeypatch.setattr(rankings.sleeper_module, "default_player_stats_season", lambda: "2026")
    return sleeper, fantasycalc, stats


def _prepared_db(tmp_path) -> str:
    path = tmp_path / "players.db"
    frame = pd.DataFrame(
        [
            {
                "player_id": "1",
                "name": "Current Player",
                "position": "WR",
                "is_current_fantasy_eligible": True,
                "valuation_authority_status": "canonical_provider_backed",
                "score": 5000,
                "dynasty_score": 5000,
                "value_score": 5000,
            }
        ]
    )
    with sqlite3.connect(path) as connection:
        frame.to_sql("players", connection, index=False)
        rankings._write_player_universe_cache_metadata(connection, db_path=str(path))
    return str(path)


def test_mtime_only_drift_does_not_invalidate_prepared_universe(tmp_path, monkeypatch):
    sleeper, _fantasycalc, _stats = _tiny_inputs(tmp_path, monkeypatch)
    db_path = _prepared_db(tmp_path)
    assert rankings._player_universe_cache_is_current(db_path) is True

    stat = sleeper.stat()
    os.utime(sleeper, ns=(stat.st_atime_ns, stat.st_mtime_ns + 8_000_000_000))
    report = rankings._player_universe_cache_currency_report(db_path)
    assert report["current"] is True
    assert report["reason"] == "validated"


def test_content_change_invalidates_prepared_universe(tmp_path, monkeypatch):
    sleeper, _fantasycalc, _stats = _tiny_inputs(tmp_path, monkeypatch)
    db_path = _prepared_db(tmp_path)
    sleeper.write_text('{"1": {"player_id": "1"}, "2": {"player_id": "2"}}', encoding="utf-8")
    report = rankings._player_universe_cache_currency_report(db_path)
    assert report["current"] is False
    assert report["reason"] == "sleeper_universe_mismatch"


def test_stale_artifact_does_not_take_validated_fast_path(tmp_path, monkeypatch):
    _tiny_inputs(tmp_path, monkeypatch)
    db_path = _prepared_db(tmp_path)
    monkeypatch.setattr(
        rankings,
        "_player_universe_cache_currency_report",
        lambda _p: {"current": False, "reason": "canonical_inputs_mismatch"},
    )
    monkeypatch.setattr(rankings, "_load_players_from_snapshot", lambda *_a, **_k: None)

    def _without_snapshot(_path):
        with sqlite3.connect(db_path) as connection:
            return pd.read_sql_query("SELECT * FROM players", connection)

    monkeypatch.setattr(rankings, "_load_players_without_snapshot", _without_snapshot)
    monkeypatch.setattr(
        "modules.structured_player_refresh.refresh_structured_player_state_from_disk",
        lambda frame, **_k: frame,
    )
    rankings.clear_public_player_cache()
    loaded = rankings.load_players(db_path)
    assert loaded.attrs["public_player_load_path"] == "sqlite_reconcile"
    assert loaded.attrs["public_player_currency_reason"] == "canonical_inputs_mismatch"


def test_valid_prepared_artifact_is_validated_sqlite_read(tmp_path, monkeypatch):
    _tiny_inputs(tmp_path, monkeypatch)
    db_path = _prepared_db(tmp_path)
    monkeypatch.setattr(
        "modules.structured_player_refresh.refresh_structured_player_state_from_disk",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("reconciliation must not run")),
    )
    rankings.clear_public_player_cache()
    loaded = rankings.load_players(db_path)
    assert loaded.attrs["public_player_load_path"] == "metadata_current_sqlite"
    assert tuple(loaded["player_id"]) == ("1",)


def test_valuation_authority_mismatch_is_a_runtime_reconcile_condition(tmp_path, monkeypatch):
    _tiny_inputs(tmp_path, monkeypatch)
    db_path = _prepared_db(tmp_path)
    with sqlite3.connect(db_path) as connection:
        payload = rankings._player_universe_metadata_payload()
        payload["valuation_authority"] = "valuation-authority-stale"
        pd.DataFrame([payload]).to_sql(
            rankings.PLAYER_CACHE_METADATA_TABLE,
            connection,
            if_exists="replace",
            index=False,
        )
    report = rankings._player_universe_cache_currency_report(db_path)
    assert report["current"] is False
    assert report["reason"] == "valuation_authority_mismatch"
    assert VALUATION_AUTHORITY_CONTRACT_VERSION != "valuation-authority-stale"


def test_prepare_script_stamps_content_addressed_metadata():
    source = open("scripts/prepare_public_player_cache.py", encoding="utf-8").read()
    assert "_write_player_universe_cache_metadata" in source
    assert "Content-addressed metadata" in source
    assert "metadata_current_sqlite" in source
