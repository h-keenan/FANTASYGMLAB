"""#242 Auth storage startup stall — deadline fail-soft + request correlation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import auth_restore_lifecycle
from modules import auth_storage_handshake
from modules import auth_supabase
from modules import startup_critical_path


ROOT = Path(__file__).resolve().parents[1]
CRITICAL = (ROOT / "modules" / "startup_critical_path.py").read_text(encoding="utf-8")


def test_auth_pending_allows_only_one_stop():
    state: dict = {}
    assert startup_critical_path.should_stop_for_auth_pending(state) is True
    assert startup_critical_path.should_stop_for_auth_pending(state) is False
    assert state.get(startup_critical_path.AUTH_RESTORE_TIMED_OUT_KEY) is True
    assert state.get(startup_critical_path.AUTH_LATE_RECONCILE_ARMED_KEY) is True


def test_request_emitted_and_handshake_carry_request_id():
    state: dict = {}
    auth_storage_handshake.mark_request_emitted(state, request_id="abcd1234")
    state[auth_storage_handshake.MOUNT_ID_KEY] = "mount001"
    auth_storage_handshake.mark_component_mount_start(state)
    summary = auth_storage_handshake.record_payload_received(
        state,
        payload={
            "ts": 1_700_000_000_100,
            "request_id": "abcd1234",
            "browser_instance_id": "binst001",
            "mount_id": "mount001",
            "_resume_reason": "startup_deadline",
            "_handshake": {
                "reason": "startup_deadline",
                "request_id": "abcd1234",
                "browser_instance_id": "binst001",
                "mount_id": "mount001",
                "js_entry_ms": 5.0,
                "js_entry_wall_ms": 1_700_000_000_000,
                "localStorage_read_ms": 0.2,
                "js_emit_ms": 3010.0,
                "emit_wall_ms": 1_700_000_000_050,
                "visibility": "visible",
                "hidden": False,
                "ready_state": "complete",
                "probe_document": "parent",
            },
        },
        source="status",
    )
    assert summary["request_id"] == "abcd1234"
    assert summary["browser_instance_id"] == "binst001"
    assert summary["mount_id"] == "mount001"
    assert summary["reason"] == "startup_deadline"
    assert summary["wall_vs_frontend_delta_ms"] is not None


def test_cold_start_hang_protection_contract_still_times_out():
    # Compatibility with #138 contract: second pending call fails soft.
    state: dict = {}
    assert startup_critical_path.should_stop_for_auth_pending(state) is True
    assert startup_critical_path.should_stop_for_auth_pending(state) is False


def test_stale_obsolete_bridge_response_is_rejected_by_request_and_mount():
    state = {
        auth_storage_handshake.REQUEST_ID_KEY: "newreq",
        auth_storage_handshake.MOUNT_ID_KEY: "newmount",
    }
    assert auth_storage_handshake.response_matches_active_mount(
        state,
        {"request_id": "newreq", "mount_id": "newmount"},
    ) is True
    assert auth_storage_handshake.response_matches_active_mount(
        state,
        {"request_id": "oldreq", "mount_id": "oldmount"},
    ) is False
    assert state[auth_storage_handshake.STALE_RESPONSE_COUNT_KEY] == 1
