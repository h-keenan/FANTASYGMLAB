"""Auth storage handshake diagnostics + game_plan timing origin (#218)."""

from __future__ import annotations

from pathlib import Path

from modules import auth_restore_lifecycle
from modules import auth_storage_handshake
from modules import startup_coordinator


ROOT = Path(__file__).resolve().parents[1]


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
