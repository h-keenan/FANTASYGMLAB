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


def test_returns_the_reloaded_frame_on_a_successful_subprocess_run():
    completed = MagicMock(returncode=0)
    reloaded = pd.DataFrame({"player_id": ["1"], "name": ["Test Player"]})
    with patch("subprocess.run", return_value=completed) as mock_run:
        with patch("modules.rankings.load_players", return_value=reloaded) as mock_load:
            result = players_refresh_flight.build_players_table_out_of_process("data/players.db")

    assert result is reloaded
    mock_load.assert_called_once_with("data/players.db")
    # The subprocess actually receives the db_path, not just any argv.
    args = mock_run.call_args.args[0]
    assert "data/players.db" in args


def test_returns_an_empty_frame_when_the_subprocess_exits_non_zero():
    completed = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=completed):
        with patch("modules.rankings.load_players") as mock_load:
            result = players_refresh_flight.build_players_table_out_of_process("data/players.db")

    assert result.empty
    mock_load.assert_not_called()


def test_returns_an_empty_frame_when_the_subprocess_times_out():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=180)):
        result = players_refresh_flight.build_players_table_out_of_process("data/players.db")

    assert result.empty


def test_returns_an_empty_frame_on_any_unexpected_subprocess_error():
    with patch("subprocess.run", side_effect=OSError("boom")):
        result = players_refresh_flight.build_players_table_out_of_process("data/players.db")

    assert result.empty
