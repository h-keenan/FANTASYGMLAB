"""Critical-path startup helpers: hang protection and first-usable boundaries.

Presentation/orchestration only. Does not change football, auth rules, or
entitlement semantics — only when work executes and when the loading shell exits.
"""

from __future__ import annotations

import time
from typing import Any, MutableMapping

from modules import performance
from modules import runtime_trace


# Bounded waits for phases that previously could hang forever on the loading shell.
AUTH_PENDING_MAX_STOPS = 2
AUTH_PENDING_MAX_MS = 2_500.0
STARTUP_NETWORK_TIMEOUT_SECONDS = 4.0
STARTUP_SOFT_DEADLINE_MS = 8_000.0

AUTH_PENDING_COUNT_KEY = "_auth_restore_pending_count"
AUTH_PENDING_STARTED_KEY = "_auth_restore_pending_started_at"
AUTH_RESTORE_TIMED_OUT_KEY = "_auth_restore_timed_out"
STARTUP_DEGRADED_NOTICE_KEY = "_startup_degraded_notice"
FIRST_USABLE_MARKED_KEY = "_startup_first_usable_marked"


def startup_elapsed_ms(session_state: MutableMapping[str, Any], *, started_at: float) -> float:
    return max(0.0, round((time.perf_counter() - float(started_at)) * 1000, 1))


def should_stop_for_auth_pending(session_state: MutableMapping[str, Any]) -> bool:
    """Return True when the auth bridge is still pending within hang limits."""

    count = int(session_state.get(AUTH_PENDING_COUNT_KEY) or 0) + 1
    session_state[AUTH_PENDING_COUNT_KEY] = count
    if AUTH_PENDING_STARTED_KEY not in session_state:
        session_state[AUTH_PENDING_STARTED_KEY] = time.perf_counter()
    started = float(session_state[AUTH_PENDING_STARTED_KEY])
    elapsed_ms = (time.perf_counter() - started) * 1000
    performance.record_timing("auth_restore_pending_wait", elapsed_ms, category="startup")
    if count >= AUTH_PENDING_MAX_STOPS or elapsed_ms >= AUTH_PENDING_MAX_MS:
        session_state[AUTH_RESTORE_TIMED_OUT_KEY] = True
        session_state[STARTUP_DEGRADED_NOTICE_KEY] = (
            "Session restore is taking longer than expected. Continue as a guest or sign in again."
        )
        clear_auth_pending_wait(session_state)
        runtime_trace.count("auth_restore_pending_timeout")
        return False
    return True


def clear_auth_pending_wait(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop(AUTH_PENDING_COUNT_KEY, None)
    session_state.pop(AUTH_PENDING_STARTED_KEY, None)


def mark_soft_deadline_if_exceeded(
    session_state: MutableMapping[str, Any],
    *,
    started_at: float,
) -> bool:
    """Record a soft deadline miss without blocking the usable shell."""

    elapsed = startup_elapsed_ms(session_state, started_at=started_at)
    if elapsed < STARTUP_SOFT_DEADLINE_MS:
        return False
    if not session_state.get(STARTUP_DEGRADED_NOTICE_KEY):
        session_state[STARTUP_DEGRADED_NOTICE_KEY] = (
            "Workspace is taking longer than usual. Showing the available shell while details finish loading."
        )
    performance.record_timing("startup_soft_deadline_exceeded", elapsed, category="startup")
    runtime_trace.count("startup_soft_deadline")
    return True


def consume_degraded_notice(session_state: MutableMapping[str, Any]) -> str:
    return str(session_state.pop(STARTUP_DEGRADED_NOTICE_KEY, "") or "").strip()
