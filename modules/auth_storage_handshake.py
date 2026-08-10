"""Auth storage handshake diagnostics for returning-session variance (#218).

Separates Python mount time, JS localStorage read, emit, and Python apply so a
~1.3s restore can be distinguished from a ~7s restore without guessing.
"""

from __future__ import annotations

import json
import time
from typing import Any, MutableMapping

from modules import performance
from modules import startup_cold_path


HANDSHAKE_STATE_KEY = "_auth_storage_handshake"
COMPONENT_MOUNT_STARTED_KEY = "_auth_storage_component_mount_started_at"
REQUEST_ID_KEY = "_auth_storage_request_id"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def mark_request_emitted(
    session_state: MutableMapping[str, Any],
    *,
    request_id: str,
) -> dict[str, Any]:
    """Record Python-side auth storage request emission (shared request id)."""

    store = session_state.setdefault(HANDSHAKE_STATE_KEY, {})
    if not isinstance(store, dict):
        store = {}
        session_state[HANDSHAKE_STATE_KEY] = store
    wall_ms = round(time.time() * 1000)
    store["request_id"] = str(request_id or "")[:16]
    store["python_request_wall_ms"] = wall_ms
    store["python_request_emitted_at"] = time.perf_counter()
    entry = {
        "kind": "auth_storage_request_emitted",
        "request_id": store["request_id"],
        "python_request_wall_ms": wall_ms,
    }
    if startup_cold_path.startup_diagnostics_enabled():
        try:
            print("DYNASTYGM_STARTUP " + json.dumps(entry, sort_keys=True), flush=True)
        except Exception:
            pass
    return entry


def mark_component_mount_start(session_state: MutableMapping[str, Any]) -> float:
    started = time.perf_counter()
    session_state[COMPONENT_MOUNT_STARTED_KEY] = started
    store = session_state.setdefault(HANDSHAKE_STATE_KEY, {})
    if isinstance(store, dict):
        store["python_mount_started_at"] = started
        store.setdefault("python_request_wall_ms", round(time.time() * 1000))
        store["python_mount_wall_ms"] = round(time.time() * 1000)
    return started


def record_pending_return(session_state: MutableMapping[str, Any]) -> None:
    """First script return with no stored/status yet (component not ready)."""

    store = session_state.setdefault(HANDSHAKE_STATE_KEY, {})
    if not isinstance(store, dict):
        return
    store["pending_returns"] = int(store.get("pending_returns") or 0) + 1
    mount_started = _safe_float(session_state.get(COMPONENT_MOUNT_STARTED_KEY))
    if mount_started is not None and "python_first_pending_ms" not in store:
        store["python_first_pending_ms"] = round(
            (time.perf_counter() - mount_started) * 1000, 1
        )


def record_payload_received(
    session_state: MutableMapping[str, Any],
    *,
    payload: dict | None,
    source: str,
) -> dict[str, Any]:
    """Merge JS diagnostic fields with Python receive timing and emit a row."""

    store = session_state.setdefault(HANDSHAKE_STATE_KEY, {})
    if not isinstance(store, dict):
        store = {}
        session_state[HANDSHAKE_STATE_KEY] = store

    received_at = time.perf_counter()
    wall_ms = round(time.time() * 1000)
    mount_started = _safe_float(session_state.get(COMPONENT_MOUNT_STARTED_KEY))
    data = payload if isinstance(payload, dict) else {}
    diag = data.get("_handshake") if isinstance(data.get("_handshake"), dict) else {}

    js_entry_ms = _safe_float(diag.get("js_entry_ms"))
    js_entry_wall = _safe_float(diag.get("js_entry_wall_ms"))
    js_read_ms = _safe_float(diag.get("localStorage_read_ms"))
    js_emit_ms = _safe_float(diag.get("js_emit_ms"))
    js_emit_wall = _safe_float(diag.get("emit_wall_ms")) or _safe_float(data.get("ts"))
    visibility = str(diag.get("visibility") or "")[:32]
    hidden = diag.get("hidden")
    ready_state = str(diag.get("ready_state") or "")[:16]
    probe_document = str(diag.get("probe_document") or "")[:16]
    request_id = str(
        diag.get("request_id")
        or data.get("request_id")
        or store.get("request_id")
        or session_state.get(REQUEST_ID_KEY)
        or ""
    )[:16]
    browser_instance_id = str(
        diag.get("browser_instance_id") or data.get("browser_instance_id") or ""
    )[:24]
    reason = str(
        diag.get("reason")
        or data.get("_resume_reason")
        or data.get("reason")
        or source
        or ""
    )[:64]

    python_mount_to_receive_ms = None
    if mount_started is not None:
        python_mount_to_receive_ms = round((received_at - mount_started) * 1000, 1)

    frontend_to_python_ms = None
    if js_emit_wall is not None:
        frontend_to_python_ms = round(wall_ms - js_emit_wall, 1)

    request_wall = _safe_float(store.get("python_request_wall_ms"))
    request_to_receive_wall_ms = None
    if request_wall is not None:
        request_to_receive_wall_ms = round(wall_ms - request_wall, 1)

    # Explain clock-domain disagreement: wall gap vs emit→receive when clocks skew.
    wall_vs_frontend_delta_ms = None
    if request_to_receive_wall_ms is not None and frontend_to_python_ms is not None:
        wall_vs_frontend_delta_ms = round(
            float(request_to_receive_wall_ms) - float(frontend_to_python_ms), 1
        )

    summary = {
        "kind": "auth_storage_handshake",
        "source": str(source or "")[:32],
        "reason": reason,
        "request_id": request_id,
        "browser_instance_id": browser_instance_id,
        "pending_returns": int(store.get("pending_returns") or 0),
        "python_first_pending_ms": store.get("python_first_pending_ms"),
        "python_mount_to_receive_ms": python_mount_to_receive_ms,
        "request_to_receive_wall_ms": request_to_receive_wall_ms,
        "js_entry_ms": js_entry_ms,
        "js_entry_wall_ms": js_entry_wall,
        "localStorage_read_ms": js_read_ms,
        "js_emit_ms": js_emit_ms,
        "frontend_to_python_ms": frontend_to_python_ms,
        "wall_vs_frontend_delta_ms": wall_vs_frontend_delta_ms,
        "visibility": visibility,
        "hidden": bool(hidden) if hidden is not None else None,
        "ready_state": ready_state,
        "probe_document": probe_document,
        # Clock domains (do not subtract across domains):
        # - python_*_ms / python_first_pending_ms: time.perf_counter deltas
        # - request_to_receive_wall_ms / frontend_to_python_ms: time.time()*1000 wall
        # - js_*_ms: browser performance.now relative durations
        "clock_domains": {
            "python_mount_to_receive_ms": "perf_counter",
            "python_first_pending_ms": "perf_counter",
            "request_to_receive_wall_ms": "wall_ms",
            "frontend_to_python_ms": "wall_ms",
            "js_entry_ms": "performance_now",
            "localStorage_read_ms": "performance_now",
            "js_emit_ms": "performance_now",
        },
    }
    store.update(summary)
    store["python_receive_at"] = received_at

    if startup_cold_path.startup_diagnostics_enabled():
        try:
            print("DYNASTYGM_STARTUP " + json.dumps(summary, sort_keys=True), flush=True)
        except Exception:
            pass
    performance.record_timing(
        "auth_storage_handshake_receive",
        float(python_mount_to_receive_ms or 0.0),
        category="startup",
    )
    try:
        from modules import tail_latency_diagnostics

        if python_mount_to_receive_ms is not None:
            tail_latency_diagnostics.record_stage_duration(
                session_state,
                "auth_storage_handshake",
                float(python_mount_to_receive_ms),
            )
    except Exception:
        pass
    return summary


def record_python_apply(
    session_state: MutableMapping[str, Any],
    *,
    apply_ms: float,
    refreshed: bool,
) -> None:
    store = session_state.setdefault(HANDSHAKE_STATE_KEY, {})
    if not isinstance(store, dict):
        return
    store["python_apply_ms"] = round(float(apply_ms), 1)
    store["token_refreshed"] = bool(refreshed)
    if startup_cold_path.startup_diagnostics_enabled():
        entry = {
            "kind": "auth_storage_handshake_apply",
            "python_apply_ms": store["python_apply_ms"],
            "token_refreshed": bool(refreshed),
        }
        try:
            print("DYNASTYGM_STARTUP " + json.dumps(entry, sort_keys=True), flush=True)
        except Exception:
            pass
    try:
        from modules import tail_latency_diagnostics

        tail_latency_diagnostics.record_stage_duration(
            session_state,
            "auth_payload_applied",
            float(apply_ms),
        )
    except Exception:
        pass


def classify_script_run_cause(session_state: MutableMapping[str, Any]) -> str:
    """Best-effort owner label for startup_run diagnostics (no PII)."""

    from modules import auth_restore_lifecycle
    from modules import auth_supabase
    from modules import startup_coordinator

    run_number = int(session_state.get(auth_restore_lifecycle.STARTUP_RUN_NUMBER_KEY) or 0)
    complete = bool(session_state.get(startup_coordinator.STARTUP_COMPLETE_KEY))
    phase = auth_restore_lifecycle.current_phase(session_state).name

    if auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY in session_state:
        return "durable_auth_clear"
    if auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY in session_state:
        if session_state.get(auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY):
            return "post_usable_auth_save"
        return "durable_auth_save_pending"
    if session_state.get(auth_restore_lifecycle.POST_USABLE_SAVE_AFTER_FOOTBALL_KEY):
        return "post_usable_auth_save_queued"
    if phase == "STORAGE_PENDING" and not complete:
        return "auth_storage_pending"
    if not complete:
        if run_number <= 2:
            return "startup_shell"
        return "startup_football_or_route"
    if session_state.get("_league_switch_guard") or session_state.get(
        "_pending_league_settings_override_reset"
    ):
        return "league_switch"
    if session_state.get("player_quick_view_player_id"):
        return "player_quick_view"
    return "post_ready_interactive"
