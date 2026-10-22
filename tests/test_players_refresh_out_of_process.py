"""build_players_table_out_of_process runs the expensive rebuild in a
subprocess instead of in-process, so the background refresh thread (see
services/mobile_api_service.py's _maybe_schedule_players_refresh and
app.py's ensure_players_for_startup/maybe_refresh_players_after_shell call
sites) can't hold this process's GIL and stall concurrent request handling.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pandas as pd

from modules import players_refresh_flight


def test_returns_the_reloaded_frame_on_a_successful_subprocess_run(tmp_path):
    db_path = str(tmp_path / "players.db")
    completed = MagicMock(returncode=0)
    reloaded = pd.DataFrame({"player_id": ["1"], "name": ["Test Player"]})
    with patch("subprocess.run", return_value=completed) as mock_run:
        with patch("modules.rankings.load_players", return_value=reloaded) as mock_load:
            result = players_refresh_flight.build_players_table_out_of_process(db_path)

    assert result is reloaded
    mock_load.assert_called_once_with(db_path)
    # The subprocess actually receives the db_path, not just any argv.
    args = mock_run.call_args.args[0]
    assert db_path in args


def test_returns_an_empty_frame_when_the_subprocess_exits_non_zero(tmp_path):
    db_path = str(tmp_path / "players.db")
    completed = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=completed):
        with patch("modules.rankings.load_players") as mock_load:
            result = players_refresh_flight.build_players_table_out_of_process(db_path)

    assert result.empty
    mock_load.assert_not_called()


def test_returns_an_empty_frame_when_the_subprocess_times_out(tmp_path):
    db_path = str(tmp_path / "players.db")
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=180)):
        result = players_refresh_flight.build_players_table_out_of_process(db_path)

    assert result.empty


def test_returns_an_empty_frame_on_any_unexpected_subprocess_error(tmp_path):
    db_path = str(tmp_path / "players.db")
    with patch("subprocess.run", side_effect=OSError("boom")):
        result = players_refresh_flight.build_players_table_out_of_process(db_path)

    assert result.empty


def test_a_rebuild_in_flight_in_another_process_is_not_duplicated(tmp_path):
    """Per-process flight state can't see other uvicorn workers; the file
    lock makes a second worker keep the last-known-good players.db."""

    from modules.file_lock import ExclusiveFileLock

    db_path = str(tmp_path / "players.db")
    current = pd.DataFrame({"player_id": ["1"], "name": ["Test Player"]})
    with ExclusiveFileLock(f"{db_path}.refresh.lock") as other_worker:
        assert other_worker.acquired
        with patch("subprocess.run") as mock_run:
            with patch("modules.rankings.load_players", return_value=current):
                result = players_refresh_flight.build_players_table_out_of_process(db_path)

    assert result is current
    mock_run.assert_not_called()


def test_rebuild_subprocess_reuses_a_dump_another_worker_already_refreshed():
    """refresh=False: get_players() still re-downloads an aged dump, but a
    dump the parent's background refresh just replaced isn't fetched again."""

    from scripts import refresh_players_db_subprocess as script

    frame = pd.DataFrame({"player_id": ["1"]})
    with patch.object(script.rankings, "build_players_table", return_value=frame) as build:
        assert script.main(["refresh_players_db_subprocess.py", "x.db"]) == 0

    build.assert_called_once_with("x.db", refresh=False)
