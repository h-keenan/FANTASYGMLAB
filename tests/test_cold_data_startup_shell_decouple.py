"""Cold-data startup: persist-first players + dismiss before heavy football work."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from modules import startup_cold_path


ROOT = Path(__file__).resolve().parents[1]


def test_ensure_players_for_startup_uses_disk_without_network_when_present():
    state: dict = {}
    frame = pd.DataFrame([{"player_id": "1", "name": "A"}])
    build = MagicMock(return_value=pd.DataFrame())
    result = startup_cold_path.ensure_players_for_startup(
        db_path="data/players.db",
        load_players_fn=lambda _path: frame,
        build_players_table_fn=build,
        session_state=state,
        allow_network_refresh=False,
    )
    assert result.equals(frame)
    build.assert_not_called()


def test_ensure_players_for_startup_rebuilds_only_when_disk_missing():
    state: dict = {}
    rebuilt = pd.DataFrame([{"player_id": "2"}])
    build = MagicMock(return_value=rebuilt)
    with patch.object(startup_cold_path.os.path, "exists", return_value=False):
        result = startup_cold_path.ensure_players_for_startup(
            db_path="data/players.db",
            load_players_fn=lambda _path: pd.DataFrame(),
            build_players_table_fn=build,
            session_state=state,
            allow_network_refresh=False,
        )
    assert result.equals(rebuilt)
    build.assert_called_once()


def test_stale_sleeper_cache_queues_refresh_without_blocking():
    state: dict = {}
    frame = pd.DataFrame([{"player_id": "1"}])
    build = MagicMock()
    with patch.object(startup_cold_path, "sleeper_players_cache_stale", return_value=True):
        startup_cold_path.ensure_players_for_startup(
            db_path="data/players.db",
            load_players_fn=lambda _path: frame,
            build_players_table_fn=build,
            session_state=state,
            allow_network_refresh=False,
        )
    assert state.get(startup_cold_path.PLAYERS_REFRESH_PENDING_KEY) is True
    build.assert_not_called()


def test_football_ready_flags_round_trip():
    state: dict = {}
    startup_cold_path.mark_football_pending(state, True)
    assert startup_cold_path.football_context_pending(state)
    startup_cold_path.mark_football_ready(state)
    assert startup_cold_path.football_context_ready(state)
    assert not startup_cold_path.football_context_pending(state)


def test_sleeper_players_cache_ttl_is_a_few_minutes_not_an_hour():
    """Pins the 2026-09-21 gameday-staleness fix: a live injury ruling
    should reach the app in minutes, not up to an hour — see
    modules.sleeper.PLAYERS_CACHE_TTL_SECONDS's own comment for the
    incident (Nico Collins still showing as a starter after being ruled
    Out) this traces back to."""

    from modules import sleeper

    assert sleeper.PLAYERS_CACHE_TTL_SECONDS <= 10 * 60
    # startup_cold_path's own default must track the same constant rather
    # than a second hardcoded literal that could silently drift out of sync.
    import inspect

    default_ttl = inspect.signature(startup_cold_path.sleeper_players_cache_stale).parameters[
        "ttl_seconds"
    ].default
    assert default_ttl == sleeper.PLAYERS_CACHE_TTL_SECONDS
