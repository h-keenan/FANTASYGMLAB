"""#242 Auth storage startup stall — deadline fail-soft + request correlation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import account_ui
from modules import auth_restore_lifecycle
from modules import auth_storage_handshake
from modules import auth_supabase
from modules import startup_critical_path


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_UI = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CRITICAL = (ROOT / "modules" / "startup_critical_path.py").read_text(encoding="utf-8")


def test_auth_pending_allows_only_one_stop():
    state: dict = {}
    assert startup_critical_path.should_stop_for_auth_pending(state) is True
    assert startup_critical_path.should_stop_for_auth_pending(state) is False
    assert state.get(startup_critical_path.AUTH_RESTORE_TIMED_OUT_KEY) is True
    assert state.get(startup_critical_path.AUTH_LATE_RECONCILE_ARMED_KEY) is True


def test_client_deadline_is_bounded_three_to_five_seconds():
    assert startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_MS == 3_000
    assert startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_ABS_MAX_MS == 5_000
    assert startup_critical_path.AUTH_PENDING_MAX_STOPS == 1
    assert startup_critical_path.AUTH_PENDING_MAX_MS == 5_000.0
    assert "installStartupDeadline" in ACCOUNT_UI
    assert "startup_deadline" in ACCOUNT_UI
    assert "deadlineMs" in ACCOUNT_UI


def test_auth_js_emits_once_and_includes_request_and_browser_ids():
    assert "request_id" in ACCOUNT_UI
    assert "browser_instance_id" in ACCOUNT_UI
    assert "js_entry_wall_ms" in ACCOUNT_UI
    assert "let emitted = false" in ACCOUNT_UI or "emitted = true" in ACCOUNT_UI


def test_request_emitted_and_handshake_carry_request_id():
    state: dict = {}
    auth_storage_handshake.mark_request_emitted(state, request_id="abcd1234")
    auth_storage_handshake.mark_component_mount_start(state)
    summary = auth_storage_handshake.record_payload_received(
        state,
        payload={
            "ts": 1_700_000_000_100,
            "request_id": "abcd1234",
            "browser_instance_id": "binst001",
            "_resume_reason": "startup_deadline",
            "_handshake": {
                "reason": "startup_deadline",
                "request_id": "abcd1234",
                "browser_instance_id": "binst001",
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
    assert summary["reason"] == "startup_deadline"
    assert summary["wall_vs_frontend_delta_ms"] is not None


def test_deadline_status_arms_late_reconcile_without_clearing_session():
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    status = MagicMock()
    status.status = {
        "action": "read",
        "ok": True,
        "reason": "startup_deadline",
        "durableAuthPresent": False,
        "request_id": "dead01",
    }
    status.stored = None
    component = MagicMock(return_value=status)
    with patch.object(account_ui, "AUTH_STORAGE_COMPONENT", component):
        with patch.object(account_ui, "st") as mock_st:
            mock_st.session_state = state
            actions = account_ui.render_durable_auth_bridge(
                config={
                    "enabled": True,
                    "url": "https://example.supabase.co",
                    "anon_key": "x",
                }
            )
    assert actions["timed_out"] is True
    assert actions["pending"] is False
    assert startup_critical_path.late_auth_reconcile_armed(state) is True
    assert auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY not in state


def test_app_arms_late_reconcile_on_pending_failsoft():
    pending = APP.index('if auth_restore.get("pending") and startup.active:')
    block = APP[pending : pending + 900]
    assert "arm_late_auth_reconcile" in block
    assert "st.stop()" in block
    assert "AUTH_STORAGE_CLIENT_DEADLINE" in CRITICAL or "deadline" in block.lower()


def test_cold_start_hang_protection_contract_still_times_out():
    # Compatibility with #138 contract: second pending call fails soft.
    state: dict = {}
    assert startup_critical_path.should_stop_for_auth_pending(state) is True
    assert startup_critical_path.should_stop_for_auth_pending(state) is False
