"""build_players_table must not rewrite players.db when content is unchanged.

players.db's size/mtime is part of the public-player fingerprint, so a no-op
rewrite rebuilds every derived frame (a second rebuild per refresh cycle).
"""

from __future__ import annotations

import os
import time

import pandas as pd
import pytest

from modules import rankings, sleeper


def _player(pid: str, name: str, pos: str, team: str, **extra) -> dict:
    base = {
        "player_id": pid,
        "full_name": name,
        "first_name": name.split()[0],
        "last_name": name.split()[-1],
        "position": pos,
        "fantasy_positions": [pos],
        "team": team,
        "status": "Active",
        "active": True,
        "age": 25,
        "years_exp": 3,
        "depth_chart_position": pos,
        "depth_chart_order": 1,
        "injury_status": None,
        "search_rank": 50,
        "sport": "nfl",
    }
    base.update(extra)
    return base


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    dump = {
        str(i): _player(str(i), f"Player{i} Name{i}", pos, team, search_rank=10 + i)
        for i, (pos, team) in enumerate(
            [("QB", "KC"), ("RB", "KC"), ("WR", "KC"), ("WR", "SF"), ("TE", "SF"), ("RB", "SF")]
        )
    }
    monkeypatch.setattr(rankings, "get_players", lambda refresh=False: dump)
    monkeypatch.setattr(
        rankings,
        "get_dynasty_values",
        lambda *a, **k: pd.DataFrame(
            [{"name": "Player0 Name0", "position": "QB", "team": "KC", "value": 5000}]
        ),
    )
    monkeypatch.setattr(sleeper, "PLAYERS_CACHE_PATH", str(tmp_path / "data" / "sleeper_players.json"))
    (tmp_path / "data" / "sleeper_players.json").write_text("{}")
    return dump, str(tmp_path / "data" / "players.db")


def test_unchanged_content_leaves_the_database_file_untouched(env):
    dump, db = env
    frame = rankings.build_players_table(db, refresh=False)
    if frame.empty:
        pytest.skip("synthetic dump produced no eligible players in this environment")
    first = os.stat(db)
    time.sleep(0.05)
    again = rankings.build_players_table(db, refresh=False)
    second = os.stat(db)
    assert (second.st_mtime_ns, second.st_size) == (first.st_mtime_ns, first.st_size)
    assert again.equals(frame)


def test_changed_content_is_written(env):
    dump, db = env
    frame = rankings.build_players_table(db, refresh=False)
    if frame.empty:
        pytest.skip("synthetic dump produced no eligible players in this environment")
    first = os.stat(db)
    time.sleep(0.05)
    dump["1"]["news_updated"] = 1_700_000_000_000
    dump["1"]["injury_status"] = "Out"
    rankings.build_players_table(db, refresh=False)
    assert os.stat(db).st_mtime_ns != first.st_mtime_ns


def test_identity_check_rejects_missing_changed_and_stale_metadata(env, monkeypatch):
    dump, db = env
    frame = rankings.build_players_table(db, refresh=False)
    if frame.empty:
        pytest.skip("synthetic dump produced no eligible players in this environment")
    _, stored = rankings._persistable_players_frame(frame, dump)
    assert rankings._persisted_players_are_identical(db, stored)
    assert not rankings._persisted_players_are_identical(db + ".missing", stored)
    changed = stored.copy()
    changed.loc[changed.index[0], "player_id"] = "zzz"
    assert not rankings._persisted_players_are_identical(db, changed)
    monkeypatch.setattr(
        rankings,
        "_player_universe_metadata_payload",
        lambda: {"eligibility_contract": "x", "sleeper_universe": "y", "canonical_inputs": "z", "valuation_authority": "w"},
    )
    assert not rankings._persisted_players_are_identical(db, stored)


def test_reconciled_universe_is_persisted_by_the_build(env):
    """A current-eligible player the build filters out is added by the load
    reconcile; the build must persist that row itself, or the first load
    rewrites the file and the next build rewrites it back."""
    dump, db = env
    frame = rankings.build_players_table(db, refresh=False)
    if frame.empty:
        pytest.skip("synthetic dump produced no eligible players in this environment")
    persisted, _ = rankings._persistable_players_frame(frame, dump)
    assert set(frame["player_id"].astype(str)) <= set(persisted["player_id"].astype(str))
    import sqlite3

    with sqlite3.connect(db) as conn:
        stored_ids = set(pd.read_sql_query("SELECT player_id FROM players", conn)["player_id"].astype(str))
    assert stored_ids == set(persisted["player_id"].astype(str))
