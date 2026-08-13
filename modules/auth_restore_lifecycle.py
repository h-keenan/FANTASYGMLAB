"""Auth restore lifecycle: run IDs, restore phases, and identical-payload guards.

Presentation/orchestration only. Does not change auth security rules, entitlement
semantics, or football logic — only how many Streamlit runs are required to settle
a returning authenticated session.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from enum import IntEnum
from typing import Any, MutableMapping

from modules import performance
from modules import runtime_trace


STARTUP_SESSION_ID_KEY = "_startup_session_id"
STARTUP_RUN_NUMBER_KEY = "_startup_run_number"
RESTORE_PHASE_KEY = "_auth_restore_phase"
AUTH_FINGERPRINT_KEY = "_auth_restore_fingerprint"
AUTH_FINGERPRINT_USER_KEY = "_auth_restore_fingerprint_user"
STORAGE_REQUESTED_KEY = "_auth_storage_requested_session"
STORAGE_RECEIVED_KEY = "_auth_storage_received_session"
MILESTONES_ONCE_KEY = "_startup_milestones_once"
ENTITLEMENT_MEMO_KEY = "_startup_entitlement_memo"
ENTITLEMENT_MEMO_USER_KEY = "_startup_entitlement_memo_user"
POST_USABLE_SAVE_RERUN_KEY = "_auth_post_usable_save_rerun_done"
# Marked at loading_dismissed; remount requested only after football hydration so
# the dismiss run can still build the prepared frame / Game Plan.
POST_USABLE_SAVE_AFTER_FOOTBALL_KEY = "_auth_post_usable_save_after_football"
PROFILE_FETCH_COUNT_KEY = "_startup_profile_fetch_count"
ENTITLEMENT_REFRESH_COUNT_KEY = "_startup_entitlement_refresh_count"
AUTH_READY_LOGGED_KEY = "_startup_auth_ready_logged"
AUTH_HYDRATION_OUTCOME_KEY = "_auth_hydration_outcome"
AUTH_HYDRATION_DIAG_KEY = "_auth_hydration_diagnostics"
AUTH_LAST_EVENT_KEY = "_auth_restore_last_event"


class RestorePhase(IntEnum):
    UNINITIALIZED = 0
    STORAGE_PENDING = 1
    AUTH_RESOLVED = 2
    PROFILE_RESOLVED = 3
    ENTITLEMENT_RESOLVED = 4
    LEAGUE_RESTORED = 5
    READY = 6


class AuthHydrationOutcome(IntEnum):
    """Canonical per-run auth hydration outcome (presentation only)."""

    UNKNOWN = 0
    RESTORING = 1
    AUTHENTICATED = 2
    GUEST = 3


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def ensure_startup_session(session_state: MutableMapping[str, Any]) -> str:
    """Stable diagnostic id for one browser Streamlit session startup cascade."""

    existing = _safe_text(session_state.get(STARTUP_SESSION_ID_KEY))
    if existing:
        return existing
    session_id = secrets.token_hex(4)
    session_state[STARTUP_SESSION_ID_KEY] = session_id
    session_state[STARTUP_RUN_NUMBER_KEY] = 0
    session_state[RESTORE_PHASE_KEY] = int(RestorePhase.UNINITIALIZED)
    session_state[MILESTONES_ONCE_KEY] = {}
    return session_id


def begin_script_run(session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    """Increment the per-startup script run counter and emit a diagnostic row."""

    session_id = ensure_startup_session(session_state)
    run_number = int(session_state.get(STARTUP_RUN_NUMBER_KEY) or 0) + 1
    session_state[STARTUP_RUN_NUMBER_KEY] = run_number
    payload = {
        "kind": "startup_run",
        "startup_session_id": session_id,
        "startup_run_number": run_number,
        "restore_phase": current_phase(session_state).name,
        "has_selected_league": bool(_safe_text(session_state.get("selected_league_id"))),
        "profile_status": _safe_text(session_state.get("account_profile_status")),
        "entitlement_cached": bool(session_state.get("_effective_entitlement")),
    }
    try:
        from modules import auth_storage_handshake

        payload["run_cause"] = auth_storage_handshake.classify_script_run_cause(session_state)
        handshake = session_state.get(auth_storage_handshake.HANDSHAKE_STATE_KEY)
        if isinstance(handshake, dict):
            if handshake.get("browser_instance_id"):
                payload["browser_instance_id"] = str(handshake.get("browser_instance_id"))[:24]
            if handshake.get("request_id"):
                payload["auth_request_id"] = str(handshake.get("request_id"))[:16]
        req = session_state.get(auth_storage_handshake.REQUEST_ID_KEY)
        if req and "auth_request_id" not in payload:
            payload["auth_request_id"] = str(req)[:16]
    except Exception:
        payload["run_cause"] = "unknown"
    try:
        from modules import tail_latency_diagnostics

        payload["process_temperature"] = tail_latency_diagnostics.classify_process_temperature(
            session_state, run_cause=str(payload.get("run_cause") or "")
        )
        payload["process_uptime_ms"] = round(tail_latency_diagnostics.process_uptime_ms(), 1)
        tail_latency_diagnostics.note_process_session(session_id)
        emit = tail_latency_diagnostics.diagnostics_enabled()
    except Exception:
        emit = True
    if emit:
        try:
            print("DYNASTYGM_STARTUP " + json.dumps(payload, sort_keys=True), flush=True)
        except Exception:
            pass
    performance.record_timing(f"startup_run_{run_number}", 0.0, category="startup")
    runtime_trace.count("startup_script_runs")
    return payload


def current_phase(session_state: MutableMapping[str, Any]) -> RestorePhase:
    try:
        return RestorePhase(int(session_state.get(RESTORE_PHASE_KEY) or 0))
    except (TypeError, ValueError):
        return RestorePhase.UNINITIALIZED


def advance_phase(session_state: MutableMapping[str, Any], phase: RestorePhase) -> RestorePhase:
    """Advance restore phase monotonically during normal restore."""

    resolved = max(current_phase(session_state), RestorePhase(phase))
    session_state[RESTORE_PHASE_KEY] = int(resolved)
    return resolved


def auth_payload_fingerprint(payload: dict | None) -> str:
    """Stable non-PII fingerprint for identical-restore detection."""

    data = payload if isinstance(payload, dict) else {}
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    user_id = _safe_text(data.get("user_id") or user.get("id"))
    access = _safe_text(data.get("access_token"))
    refresh = _safe_text(data.get("refresh_token"))
    expires_at = _safe_text(data.get("expires_at"))
    digest = hashlib.sha256(
        f"{user_id}|{access}|{refresh}|{expires_at}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{user_id}:{expires_at}:{digest}" if user_id else ""


def stored_auth_fingerprint(session_state: MutableMapping[str, Any]) -> str:
    return _safe_text(session_state.get(AUTH_FINGERPRINT_KEY))


def mark_auth_fingerprint(session_state: MutableMapping[str, Any], payload: dict | None) -> str:
    fingerprint = auth_payload_fingerprint(payload)
    if fingerprint:
        session_state[AUTH_FINGERPRINT_KEY] = fingerprint
        session_state[AUTH_FINGERPRINT_USER_KEY] = fingerprint.split(":", 1)[0]
    return fingerprint


def is_identical_auth_payload(
    session_state: MutableMapping[str, Any],
    payload: dict | None,
) -> bool:
    fingerprint = auth_payload_fingerprint(payload)
    if not fingerprint:
        return False
    return fingerprint == stored_auth_fingerprint(session_state)


def clear_restore_lifecycle(session_state: MutableMapping[str, Any]) -> None:
    """Drop restore memoization on logout / account switch / failed auth."""

    for key in (
        AUTH_FINGERPRINT_KEY,
        AUTH_FINGERPRINT_USER_KEY,
        STORAGE_REQUESTED_KEY,
        STORAGE_RECEIVED_KEY,
        ENTITLEMENT_MEMO_KEY,
        ENTITLEMENT_MEMO_USER_KEY,
        POST_USABLE_SAVE_RERUN_KEY,
        POST_USABLE_SAVE_AFTER_FOOTBALL_KEY,
        AUTH_READY_LOGGED_KEY,
        PROFILE_FETCH_COUNT_KEY,
        ENTITLEMENT_REFRESH_COUNT_KEY,
        MILESTONES_ONCE_KEY,
        AUTH_HYDRATION_OUTCOME_KEY,
        AUTH_HYDRATION_DIAG_KEY,
        AUTH_LAST_EVENT_KEY,
    ):
        session_state.pop(key, None)
    session_state[RESTORE_PHASE_KEY] = int(RestorePhase.UNINITIALIZED)
    session_state[AUTH_HYDRATION_OUTCOME_KEY] = int(AuthHydrationOutcome.UNKNOWN)
    try:
        from modules import startup_critical_path

        startup_critical_path.clear_late_auth_reconcile(session_state)
        startup_critical_path.clear_auth_pending_wait(session_state)
    except Exception:
        pass


def mark_storage_requested(session_state: MutableMapping[str, Any]) -> bool:
    """Return True the first time a storage read is requested this startup session."""

    if session_state.get(STORAGE_REQUESTED_KEY):
        return False
    session_state[STORAGE_REQUESTED_KEY] = True
    return True


def mark_storage_received(session_state: MutableMapping[str, Any]) -> bool:
    if session_state.get(STORAGE_RECEIVED_KEY):
        return False
    session_state[STORAGE_RECEIVED_KEY] = True
    return True


def record_profile_fetch(session_state: MutableMapping[str, Any]) -> int:
    count = int(session_state.get(PROFILE_FETCH_COUNT_KEY) or 0) + 1
    session_state[PROFILE_FETCH_COUNT_KEY] = count
    return count


def record_entitlement_refresh(session_state: MutableMapping[str, Any]) -> int:
    count = int(session_state.get(ENTITLEMENT_REFRESH_COUNT_KEY) or 0) + 1
    session_state[ENTITLEMENT_REFRESH_COUNT_KEY] = count
    return count


def run_context(session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    return {
        "startup_session_id": ensure_startup_session(session_state),
        "startup_run_number": int(session_state.get(STARTUP_RUN_NUMBER_KEY) or 0),
        "restore_phase": current_phase(session_state).name,
    }


def current_hydration_outcome(session_state: MutableMapping[str, Any]) -> AuthHydrationOutcome:
    try:
        return AuthHydrationOutcome(int(session_state.get(AUTH_HYDRATION_OUTCOME_KEY) or 0))
    except (TypeError, ValueError):
        return AuthHydrationOutcome.UNKNOWN


def set_hydration_outcome(
    session_state: MutableMapping[str, Any],
    outcome: AuthHydrationOutcome,
    *,
    event: str = "",
    rerun_reason: str = "",
) -> AuthHydrationOutcome:
    """Record one canonical hydration outcome + lightweight restore diagnostics."""

    session_state[AUTH_HYDRATION_OUTCOME_KEY] = int(outcome)
    diag = {
        "outcome": outcome.name,
        "event": _safe_text(event)[:48],
        "rerun_reason": _safe_text(rerun_reason)[:64],
        "restore_phase": current_phase(session_state).name,
        "startup_run_number": int(session_state.get(STARTUP_RUN_NUMBER_KEY) or 0),
    }
    session_state[AUTH_HYDRATION_DIAG_KEY] = diag
    if event:
        session_state[AUTH_LAST_EVENT_KEY] = _safe_text(event)[:48]
    return outcome


def record_auth_restore_event(
    session_state: MutableMapping[str, Any],
    *,
    event: str,
    rerun_reason: str = "",
) -> dict[str, Any]:
    """Dev/diagnostic event for RESTORE / REUSE / RERUN_REASON (no PII)."""

    label = _safe_text(event, "UNKNOWN").upper()
    if label not in {"RESTORE", "REUSE", "RERUN_REASON", "SKIP_BRIDGE"}:
        label = "RESTORE"
    prior = session_state.get(AUTH_HYDRATION_DIAG_KEY)
    payload = {
        "event": label,
        "rerun_reason": _safe_text(rerun_reason)[:64],
        "outcome": current_hydration_outcome(session_state).name,
        "restore_phase": current_phase(session_state).name,
        "startup_run_number": int(session_state.get(STARTUP_RUN_NUMBER_KEY) or 0),
    }
    if isinstance(prior, dict):
        payload["prior_event"] = _safe_text(prior.get("event"))[:48]
    session_state[AUTH_HYDRATION_DIAG_KEY] = payload
    session_state[AUTH_LAST_EVENT_KEY] = label
    runtime_trace.count(f"auth_restore_event_{label.casefold()}")
    return payload


def resolve_settled_hydration_outcome(
    session_state: MutableMapping[str, Any],
    *,
    pending: bool = False,
    authenticated: bool = False,
) -> AuthHydrationOutcome:
    """Map settle state onto UNKNOWN → RESTORING → AUTHENTICATED|GUEST."""

    if pending:
        return set_hydration_outcome(
            session_state,
            AuthHydrationOutcome.RESTORING,
            event="RESTORE",
            rerun_reason="storage_pending",
        )
    if authenticated:
        return set_hydration_outcome(
            session_state,
            AuthHydrationOutcome.AUTHENTICATED,
            event="REUSE" if stored_auth_fingerprint(session_state) else "RESTORE",
        )
    return set_hydration_outcome(
        session_state,
        AuthHydrationOutcome.GUEST,
        event="REUSE",
    )
