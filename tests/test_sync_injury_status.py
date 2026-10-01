"""Tests for scripts/sync_injury_status.py's column-patch logic.

Exercises patch_injury_columns() and default_patch_runner() against
throwaway SQLite files created fresh under pytest's tmp_path for every
test -- never the real data/players.db. This follows the same safety rule
the rest of this task operates under: never let test/investigation code
touch the real data/players.db (see this project's safety rule and
tests/test_refresh_and_commit_players_db.py, which does the same for the
full-rebuild cron's commit/push plumbing).
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_injury_status.py"
_spec = importlib.util.spec_from_file_location("sync_injury_status", _MODULE_PATH)
sis = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(sis)


def _make_db(tmp_path: Path, rows: list[tuple]) -> Path:
    """rows: (player_id, status, injury_status, name, value, score)."""

    db_path = tmp_path / "players.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE players ("
        "player_id TEXT, status TEXT, injury_status TEXT, name TEXT, "
        "value REAL, score REAL)"
    )
    conn.executemany(
        "INSERT INTO players (player_id, status, injury_status, name, value, score) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db_path


def _read_all(db_path: Path) -> dict[str, tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT player_id, status, injury_status, name, value, score FROM players"
        )
        return {row[0]: row[1:] for row in cur.fetchall()}
    finally:
        conn.close()


def _sleeper_player(
    *,
    full_name: str = "Test Player",
    position: str = "WR",
    status: str = "Active",
    injury_status: str = "",
    **extra,
) -> dict:
    base = {
        "full_name": full_name,
        "position": position,
        "team": "KC",
        "age": 25,
        "search_rank": 50,
        "active": True,
        "status": status,
        "years_exp": 3,
        "news_updated": 0,
        "depth_chart_position": "",
        "depth_chart_order": None,
        "hashtag": "",
        "team_abbr": "KC",
        "injury_status": injury_status,
        "sport": "nfl",
        "fantasy_positions": ["WR"],
    }
    base.update(extra)
    return base


def test_real_injury_status_change_gets_written(tmp_path):
    db_path = _make_db(
        tmp_path,
        [("1001", "Active", "", "Healthy Guy", 5000.0, 1234.5)],
    )
    players = {
        "1001": _sleeper_player(status="Active", injury_status="Questionable"),
    }

    examined, updated = sis.patch_injury_columns(db_path, players)

    assert examined == 1
    assert updated == 1
    row = _read_all(db_path)["1001"]
    assert row[0] == "Active"
    assert row[1] == "Questionable"


def test_player_not_in_local_db_is_skipped(tmp_path):
    db_path = _make_db(
        tmp_path,
        [("1001", "Active", "", "Healthy Guy", 5000.0, 1234.5)],
    )
    players = {
        "1001": _sleeper_player(status="Active", injury_status=""),
        # Brand-new Sleeper player with no corresponding players.db row.
        "9999": _sleeper_player(full_name="Brand New Rookie", status="Active"),
    }

    examined, updated = sis.patch_injury_columns(db_path, players)

    assert examined == 1  # only the pre-existing row is "examined"
    assert updated == 0  # nothing changed for the one matching row
    rows = _read_all(db_path)
    assert set(rows.keys()) == {"1001"}  # no row inserted for 9999


def test_noop_when_nothing_changed(tmp_path):
    db_path = _make_db(
        tmp_path,
        [("1001", "Active", "Questionable", "Healthy-ish Guy", 5000.0, 1234.5)],
    )
    players = {
        "1001": _sleeper_player(status="Active", injury_status="Questionable"),
    }
    before = _read_all(db_path)

    examined, updated = sis.patch_injury_columns(db_path, players)

    assert examined == 1
    assert updated == 0
    assert _read_all(db_path) == before


def test_non_injury_columns_are_never_touched(tmp_path):
    db_path = _make_db(
        tmp_path,
        [("1001", "Active", "", "Original Name", 7777.0, 9999.0)],
    )
    players = {
        "1001": _sleeper_player(
            full_name="A Totally Different Name",  # would change "name" in a full rebuild
            status="Injured Reserve",
            injury_status="Out",
        ),
    }

    examined, updated = sis.patch_injury_columns(db_path, players)

    assert updated == 1
    row = _read_all(db_path)["1001"]
    assert row[0] == "Injured Reserve"
    assert row[1] == "Out"
    # name/value/score must be exactly as they were -- this script never
    # writes anything but status/injury_status.
    assert row[2] == "Original Name"
    assert row[3] == 7777.0
    assert row[4] == 9999.0


def test_missing_db_file_is_a_safe_noop(tmp_path):
    missing_db = tmp_path / "does_not_exist.db"
    examined, updated = sis.patch_injury_columns(missing_db, {"1001": _sleeper_player()})
    assert (examined, updated) == (0, 0)


def test_default_patch_runner_fails_closed_on_empty_sleeper_response(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, [("1001", "Active", "", "Healthy Guy", 1.0, 1.0)])
    monkeypatch.setattr(sis.sleeper, "get_players", lambda refresh=False: {})

    rc = sis.default_patch_runner(db_path)

    assert rc == 1
    # Untouched -- a failed/empty fetch must never be treated as "nothing
    # changed" in a way that could zero out existing injury data.
    assert _read_all(db_path)["1001"] == ("Active", "", "Healthy Guy", 1.0, 1.0)


def test_default_patch_runner_succeeds_and_patches_on_real_data(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, [("1001", "Active", "", "Healthy Guy", 1.0, 1.0)])
    monkeypatch.setattr(
        sis.sleeper,
        "get_players",
        lambda refresh=False: {"1001": _sleeper_player(status="Active", injury_status="Doubtful")},
    )

    rc = sis.default_patch_runner(db_path)

    assert rc == 0
    row = _read_all(db_path)["1001"]
    assert row[0] == "Active"
    assert row[1] == "Doubtful"
