"""Auth storage handshake diagnostics + game_plan timing origin (#218)."""

from __future__ import annotations

from pathlib import Path

from modules import auth_restore_lifecycle
from modules import auth_storage_handshake
from modules import startup_coordinator


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ACCOUNT_UI = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")


def test_startup_complete_preserves_timing_origin_for_game_plan():
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    origin = startup_coordinator.startup_session_origin(state)
    state[startup_coordinator.STARTUP_COMPLETE_KEY] = False
    coordinator = startup_coordinator.StartupCoordinator(session_state=state, active=True)
    coordinator.complete()
    assert state.get(startup_coordinator.STARTUP_TIMING_STARTED_KEY) == origin
    later = startup_coordinator.startup_session_origin(state)
    assert later == origin


def test_game_plan_first_useful_uses_startup_session_origin():
    useful = APP.index('data-fgl-dashboard-useful="1"')
    block = APP[useful : useful + 500]
    assert "game_plan_first_useful" in block
    assert "startup_session_origin" in block


def test_auth_storage_js_emits_handshake_diagnostics():
    assert "_handshake" in ACCOUNT_UI
    assert "localStorage_read_ms" in ACCOUNT_UI
    assert "js_emit_ms" in ACCOUNT_UI
    assert "visibility" in ACCOUNT_UI
    assert "mark_component_mount_start" in ACCOUNT_UI
    assert "record_pending_return" in ACCOUNT_UI
    assert "record_payload_received" in ACCOUNT_UI


def test_handshake_receive_summary_separates_python_and_js_gaps():
    state: dict = {}
    auth_storage_handshake.mark_component_mount_start(state)
    auth_storage_handshake.record_pending_return(state)
    summary = auth_storage_handshake.record_payload_received(
        state,
        payload={
            "ts": 1_700_000_000_000,
            "_resume_reason": "initial_read",
            "_handshake": {
                "reason": "initial_read",
                "js_entry_ms": 12.5,
                "localStorage_read_ms": 0.4,
                "js_emit_ms": 13.1,
                "emit_wall_ms": 1_700_000_000_050,
                "visibility": "visible",
                "hidden": False,
            },
        },
        source="stored",
    )
    assert summary["pending_returns"] == 1
    assert summary["python_first_pending_ms"] is not None
    assert summary["localStorage_read_ms"] == 0.4
    assert summary["js_entry_ms"] == 12.5
    assert summary["reason"] == "initial_read"
    assert summary["visibility"] == "visible"


def test_script_run_cause_classifies_storage_pending_and_post_usable_save():
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    auth_restore_lifecycle.advance_phase(
        state, auth_restore_lifecycle.RestorePhase.STORAGE_PENDING
    )
    assert (
        auth_storage_handshake.classify_script_run_cause(state)
        == "auth_storage_pending"
    )
    state[startup_coordinator.STARTUP_COMPLETE_KEY] = True
    state[auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY] = True
    from modules import auth_supabase

    state[auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY] = {"access_token": "x"}
    assert (
        auth_storage_handshake.classify_script_run_cause(state)
        == "post_usable_auth_save"
    )


def test_loading_dismissed_still_before_players_prepared_and_game_plan():
    main = APP.index("def main():")
    dismiss = APP.index('"loading_dismissed"', main)
    players = APP.index('"players_ready"', main)
    prepared = APP.index('"prepared_frame_ready"', main)
    football = APP.index('"football_context_ready"', prepared)
    assert dismiss < players < prepared < football


def test_game_plan_path_has_named_owner_instrumentation():
    assert "game_plan_shared_league_context" in APP
    assert "game_plan_league_context" in APP
    assert "game_plan_trade_inventory" in APP
    assert "game_plan_compose" in APP
    assert '"game_plan_trade_inventory_ready"' in APP
    assert '"game_plan_composed"' in APP


def test_has_session_fast_path_still_skips_localstorage_restore():
    assert 'reason: "session_present"' in ACCOUNT_UI or "session_present" in ACCOUNT_UI
    assert "already_authenticated" in ACCOUNT_UI
    assert "hasSession" in ACCOUNT_UI
