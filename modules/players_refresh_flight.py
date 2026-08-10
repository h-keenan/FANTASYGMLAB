"""Process-scoped single-flight for public Sleeper player refresh (#238).

Public player corpus is global (no account/league identity). After startup has a
usable persisted frame (players_ready), optional stale-while-revalidate refresh
must not block Dashboard first-useful and must not stampede across sessions.

Contract:
- One refresh owner per public signature
- Followers keep last-known-good persisted frame; they do NOT wait for the owner
- Result replaces SQLite/process artifacts atomically after success
- Failure preserves the previous valid frame
- No global lock around league-specific football work
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, MutableMapping
from typing import Any

from modules import performance
from modules import runtime_trace


PUBLIC_PLAYERS_REFRESH_SIGNATURE = "public_sleeper_players_v1"
PLAYERS_REFRESH_SCHEDULED_KEY = "_players_network_refresh_scheduled"
PLAYERS_REFRESH_ROLE_KEY = "_players_network_refresh_role"

# Process-scoped flight state (survives Streamlit session remounts in one worker).
_GUARD = threading.Lock()
_IN_FLIGHT: dict[str, threading.Event] = {}
_OWNER_THREAD: dict[str, int] = {}
_COMPLETED_OK: dict[str, float] = {}
_LAST_ATTEMPT_MONO: dict[str, float] = {}
_PROVIDER_CALL_COUNT: dict[str, int] = {}
_FAILURE_COUNT: dict[str, int] = {}
_LAST_ERROR: dict[str, str] = {}

# After a failed attempt, do not re-arm every Streamlit run (rerun storm fuel).
FAILURE_COOLDOWN_S = 45.0


def reset_process_refresh_state_for_tests() -> None:
    """Test-only: drop process flight state."""

    with _GUARD:
        _IN_FLIGHT.clear()
        _OWNER_THREAD.clear()
        _COMPLETED_OK.clear()
        _LAST_ATTEMPT_MONO.clear()
        _PROVIDER_CALL_COUNT.clear()
        _FAILURE_COUNT.clear()
        _LAST_ERROR.clear()


def public_refresh_signature() -> str:
    return PUBLIC_PLAYERS_REFRESH_SIGNATURE


def provider_refresh_call_count(signature: str | None = None) -> int:
    sig = signature or PUBLIC_PLAYERS_REFRESH_SIGNATURE
    with _GUARD:
        return int(_PROVIDER_CALL_COUNT.get(sig, 0))


def refresh_in_flight(signature: str | None = None) -> bool:
    sig = signature or PUBLIC_PLAYERS_REFRESH_SIGNATURE
    with _GUARD:
        event = _IN_FLIGHT.get(sig)
        return bool(event is not None and not event.is_set())


def last_refresh_error(signature: str | None = None) -> str:
    sig = signature or PUBLIC_PLAYERS_REFRESH_SIGNATURE
    with _GUARD:
        return str(_LAST_ERROR.get(sig) or "")


def _emit(kind: str, **fields: Any) -> None:
    try:
        from modules import startup_cold_path

        if not startup_cold_path.startup_diagnostics_enabled():
            return
    except Exception:
        return
    payload: dict[str, Any] = {
        "kind": kind,
        "signature_prefix": performance._safe_label(PUBLIC_PLAYERS_REFRESH_SIGNATURE)[:16],
    }
    for key, value in fields.items():
        if isinstance(value, (int, float, bool)) or value is None:
            payload[str(key)[:40]] = value
        else:
            payload[str(key)[:40]] = str(value)[:80]
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(payload, sort_keys=True), flush=True)
    except Exception:
        pass


def _cooldown_active_unlocked(signature: str) -> bool:
    last = _LAST_ATTEMPT_MONO.get(signature)
    failed = int(_FAILURE_COUNT.get(signature, 0))
    if last is None or failed <= 0:
        return False
    # Cooldown only applies after failure; success clears failure count.
    return (time.perf_counter() - float(last)) < FAILURE_COOLDOWN_S


def _cooldown_active(signature: str) -> bool:
    with _GUARD:
        return _cooldown_active_unlocked(signature)


def should_queue_stale_refresh(session_state: MutableMapping[str, Any]) -> bool:
    """True when a session may arm deferred refresh without stampeding."""

    if session_state.get(PLAYERS_REFRESH_SCHEDULED_KEY):
        return False
    if refresh_in_flight():
        return False
    if _cooldown_active(PUBLIC_PLAYERS_REFRESH_SIGNATURE):
        return False
    return True


def try_become_refresh_owner(signature: str | None = None) -> tuple[bool, str]:
    """Return (is_owner, role). Never blocks waiters."""

    sig = signature or PUBLIC_PLAYERS_REFRESH_SIGNATURE
    with _GUARD:
        existing = _IN_FLIGHT.get(sig)
        if existing is not None and not existing.is_set():
            return False, "coalesced_follower"
        if _cooldown_active_unlocked(sig):
            return False, "cooldown"
        event = threading.Event()
        _IN_FLIGHT[sig] = event
        _OWNER_THREAD[sig] = threading.get_ident()
        _LAST_ATTEMPT_MONO[sig] = time.perf_counter()
        return True, "refresh_owner"


def _mark_refresh_complete(
    signature: str,
    *,
    ok: bool,
    error: str = "",
) -> None:
    with _GUARD:
        event = _IN_FLIGHT.pop(signature, None)
        _OWNER_THREAD.pop(signature, None)
        if ok:
            _COMPLETED_OK[signature] = time.perf_counter()
            _FAILURE_COUNT[signature] = 0
            _LAST_ERROR.pop(signature, None)
        else:
            _FAILURE_COUNT[signature] = int(_FAILURE_COUNT.get(signature, 0)) + 1
            if error:
                _LAST_ERROR[signature] = error[:120]
        if event is not None:
            event.set()


def run_public_players_refresh(
    *,
    db_path: str,
    build_players_table_fn: Callable[..., Any],
    signature: str | None = None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Synchronously run refresh as the current owner (tests / background worker)."""

    sig = signature or PUBLIC_PLAYERS_REFRESH_SIGNATURE
    started = time.perf_counter()
    _emit("players_refresh_builder_start", role="refresh_owner")
    with _GUARD:
        _PROVIDER_CALL_COUNT[sig] = int(_PROVIDER_CALL_COUNT.get(sig, 0)) + 1
        call_n = _PROVIDER_CALL_COUNT[sig]
    runtime_trace.count("public_players_refresh_builder")
    try:
        frame = build_players_table_fn(db_path, refresh=True)
        empty = bool(getattr(frame, "empty", frame is None))
        if empty:
            _mark_refresh_complete(sig, ok=False, error="empty_frame")
            _emit(
                "players_refresh_builder_complete",
                role="refresh_owner",
                ok=False,
                provider_call=call_n,
                elapsed_ms=round((time.perf_counter() - started) * 1000.0, 1),
            )
            return {
                "ok": False,
                "role": "refresh_owner",
                "frame": frame,
                "error": "empty_frame",
                "provider_call": call_n,
            }
        _mark_refresh_complete(sig, ok=True)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        try:
            from modules import startup_cold_path

            startup_cold_path.log_slow_startup_operation(
                "players_provider_refresh",
                elapsed_ms,
                cache_status="deferred_bg",
                detail={"role": "refresh_owner", "provider_call": call_n},
            )
        except Exception:
            pass
        _emit(
            "players_refresh_builder_complete",
            role="refresh_owner",
            ok=True,
            provider_call=call_n,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return {
            "ok": True,
            "role": "refresh_owner",
            "frame": frame,
            "error": "",
            "provider_call": call_n,
            "elapsed_ms": elapsed_ms,
        }
    except Exception as exc:
        _mark_refresh_complete(sig, ok=False, error=type(exc).__name__)
        _emit(
            "players_refresh_builder_error",
            role="refresh_owner",
            ok=False,
            exception_type=type(exc).__name__,
            provider_call=call_n,
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        return {
            "ok": False,
            "role": "refresh_owner",
            "frame": None,
            "error": type(exc).__name__,
            "provider_call": call_n,
        }


def schedule_deferred_players_refresh(
    *,
    db_path: str,
    build_players_table_fn: Callable[..., Any],
    session_state: MutableMapping[str, Any],
    pending_key: str,
    background: bool = True,
) -> dict[str, Any]:
    """Arm at most one process refresh; never block Dashboard first-useful.

    Returns immediately with a role describing ownership. When ``background`` is
    True (production default), the owner runs in a daemon thread and does not
    mutate ``st.session_state`` from that thread.
    """

    if not session_state.pop(pending_key, False):
        return {"scheduled": False, "role": "noop", "provider_call": provider_refresh_call_count()}

    # Session one-shot: do not re-arm this browser session after scheduling.
    session_state[PLAYERS_REFRESH_SCHEDULED_KEY] = True

    is_owner, role = try_become_refresh_owner()
    session_state[PLAYERS_REFRESH_ROLE_KEY] = role
    _emit(
        "players_refresh_schedule",
        role=role,
        background=bool(background),
        scheduled=True,
    )
    if not is_owner:
        return {
            "scheduled": True,
            "role": role,
            "provider_call": provider_refresh_call_count(),
        }

    if background:

        def _worker() -> None:
            run_public_players_refresh(
                db_path=db_path,
                build_players_table_fn=build_players_table_fn,
                session_state=None,
            )

        thread = threading.Thread(
            target=_worker,
            name="dgm-public-players-refresh",
            daemon=True,
        )
        thread.start()
        return {
            "scheduled": True,
            "role": role,
            "provider_call": provider_refresh_call_count(),
            "thread": thread,
        }

    result = run_public_players_refresh(
        db_path=db_path,
        build_players_table_fn=build_players_table_fn,
        session_state=session_state,
    )
    return {
        "scheduled": True,
        "role": role,
        "provider_call": result.get("provider_call"),
        "ok": result.get("ok"),
        "frame": result.get("frame"),
        "error": result.get("error"),
    }


def wait_for_refresh(
    *,
    timeout_s: float = 15.0,
    signature: str | None = None,
) -> bool:
    """Test helper: wait until in-flight refresh completes (or timeout)."""

    sig = signature or PUBLIC_PLAYERS_REFRESH_SIGNATURE
    deadline = time.perf_counter() + max(0.0, float(timeout_s))
    while time.perf_counter() < deadline:
        with _GUARD:
            event = _IN_FLIGHT.get(sig)
        if event is None:
            return True
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        if event.wait(timeout=min(0.05, remaining)):
            # Event set — confirm slot cleared.
            with _GUARD:
                if sig not in _IN_FLIGHT:
                    return True
        time.sleep(0.01)
    return not refresh_in_flight(sig)
