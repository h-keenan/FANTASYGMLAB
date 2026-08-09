"""Cold-data startup: persist-first players + dismiss before heavy football work."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

import app
from modules import startup_cold_path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_global_loading_dismisses_before_players_and_prepared_frame():
    main = APP.index("def main():")
    dismiss = APP.index('runtime_trace.mark("first_usable_paint")', main)
    players = APP.index('"players_ready"', main)
    prepared = APP.index('"prepared_frame_ready"', main)
    assert dismiss < players < prepared


def test_identity_shell_does_not_require_valued_frame():
    start = APP.index("def _build_identity_shell_chrome_bundle()")
    end = APP.index("def _build_shell_chrome_bundle()", start)
    body = APP[start:end]
    assert "cached_league_shell_context(" not in body
    assert "cached_league_summary(" not in body
    assert "get_shell_league_context()" not in body


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


def test_slow_provider_mocks_do_not_block_identity_shell_contract():
    """Shell identity path must not call league summary even if providers are slow."""

    start = APP.index("def _build_identity_shell_chrome_bundle()")
    end = APP.index("def _build_shell_chrome_bundle()", start)
    body = APP[start:end]
    for forbidden in (
        "cached_league_summary(",
        "cached_league_shell_context(",
        "build_players_table(",
        "apply_valuation_lens(",
        "attach_canonical_ranks(",
    ):
        assert forbidden not in body


def test_football_ready_flags_round_trip():
    state: dict = {}
    startup_cold_path.mark_football_pending(state, True)
    assert startup_cold_path.football_context_pending(state)
    startup_cold_path.mark_football_ready(state)
    assert startup_cold_path.football_context_ready(state)
    assert not startup_cold_path.football_context_pending(state)


def test_app_ensure_players_defaults_to_no_network_refresh():
    with (
        patch.object(
            app.startup_cold_path,
            "ensure_players_for_startup",
            return_value=pd.DataFrame([{"player_id": "1"}]),
        ) as ensure,
        patch.object(app.st, "session_state", {}),
        patch.object(app.os.path, "exists", return_value=True),
    ):
        app.ensure_players()
    assert ensure.call_args.kwargs.get("allow_network_refresh") is False
