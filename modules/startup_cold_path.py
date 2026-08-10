"""Cold-data startup helpers: persist-first players + shell/football readiness.

Presentation/orchestration only. Does not change valuation formulas, rankings, or
recommendation truth — only when expensive reusable data work runs relative to
global loading dismissal.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, MutableMapping

from modules import performance
from modules import runtime_trace


FOOTBALL_CONTEXT_READY_KEY = "_football_context_ready"
FOOTBALL_CONTEXT_PENDING_KEY = "_football_context_pending"
PLAYERS_REFRESH_PENDING_KEY = "_players_network_refresh_pending"
IDENTITY_SHELL_READY_KEY = "_identity_shell_ready"
SLOW_STARTUP_WARN_MS = 500.0
SLOW_STARTUP_MARK_MS = 2_000.0
STARTUP_ENV_KEY = "DYNASTYGM_STARTUP"


def startup_diagnostics_enabled(*, environ: dict | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return str(env.get(STARTUP_ENV_KEY, "")).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def log_slow_startup_operation(
    label: str,
    elapsed_ms: float,
    *,
    category: str = "startup",
    cache_status: str = "",
    detail: dict | None = None,
) -> None:
    """Emit diagnostic rows for long startup operations (no PII)."""

    ms = float(elapsed_ms)
    if ms < SLOW_STARTUP_WARN_MS:
        return
    if not startup_diagnostics_enabled():
        performance.record_timing(label, ms, category=category)
        return
    entry = {
        "kind": "slow_startup_operation" if ms < SLOW_STARTUP_MARK_MS else "SLOW_STARTUP_OPERATION",
        "label": performance._safe_label(label),
        "category": performance._safe_label(category),
        "elapsed_ms": round(ms, 1),
        "cache_status": performance._safe_label(cache_status) if cache_status else "",
    }
    if isinstance(detail, dict) and detail:
        # Keep values scalar / short — no player or account payloads.
        safe_detail = {}
        for key, value in list(detail.items())[:12]:
            if isinstance(value, (int, float, bool)) or value is None:
                safe_detail[str(key)[:48]] = value
            else:
                safe_detail[str(key)[:48]] = str(value)[:80]
        entry["detail"] = safe_detail
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(entry, sort_keys=True), flush=True)
    except Exception:
        pass
    performance.record_timing(label, ms, category=category)
    if ms >= SLOW_STARTUP_MARK_MS:
        runtime_trace.count("slow_startup_operation")


def log_startup_cache_event(
    label: str,
    *,
    cache_status: str,
    signature_prefix: str = "",
    elapsed_ms: float = 0.0,
    detail: dict | None = None,
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Always emit cache hit/miss when startup diagnostics are on (no 500ms gate)."""

    if not startup_diagnostics_enabled():
        return
    entry = {
        "kind": "startup_cache_event",
        "label": performance._safe_label(label),
        "cache_status": performance._safe_label(cache_status) if cache_status else "",
        "elapsed_ms": round(float(elapsed_ms), 1),
        "signature_prefix": performance._safe_label(signature_prefix)[:16],
    }
    if isinstance(detail, dict) and detail:
        safe_detail = {}
        for key, value in list(detail.items())[:12]:
            if isinstance(value, (int, float, bool)) or value is None:
                safe_detail[str(key)[:48]] = value
            else:
                safe_detail[str(key)[:48]] = str(value)[:80]
        entry["detail"] = safe_detail
    if session_state is not None:
        try:
            from modules import auth_restore_lifecycle
            from modules import tail_latency_diagnostics

            meta = auth_restore_lifecycle.run_context(session_state)
            entry["startup_session_id"] = meta.get("startup_session_id")
            entry["startup_run_number"] = meta.get("startup_run_number")
            entry["restore_phase"] = meta.get("restore_phase")
            entry["process_temperature"] = (
                tail_latency_diagnostics.classify_process_temperature(session_state)
            )
        except Exception:
            pass
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(entry, sort_keys=True), flush=True)
    except Exception:
        pass
    runtime_trace.count(
        f"{performance._safe_label(label)}_{performance._safe_label(cache_status) or 'unknown'}"
    )


def mark_football_pending(session_state: MutableMapping[str, Any], pending: bool = True) -> None:
    session_state[FOOTBALL_CONTEXT_PENDING_KEY] = bool(pending)
    if pending:
        session_state[FOOTBALL_CONTEXT_READY_KEY] = False


def mark_football_ready(session_state: MutableMapping[str, Any]) -> None:
    session_state[FOOTBALL_CONTEXT_PENDING_KEY] = False
    session_state[FOOTBALL_CONTEXT_READY_KEY] = True
    session_state["_football_context_ready_mono"] = time.perf_counter()


def football_context_ready(session_state: MutableMapping[str, Any]) -> bool:
    return bool(session_state.get(FOOTBALL_CONTEXT_READY_KEY))


def football_context_pending(session_state: MutableMapping[str, Any]) -> bool:
    return bool(session_state.get(FOOTBALL_CONTEXT_PENDING_KEY)) and not football_context_ready(
        session_state
    )


def clear_football_context_flags(session_state: MutableMapping[str, Any]) -> None:
    for key in (
        FOOTBALL_CONTEXT_READY_KEY,
        FOOTBALL_CONTEXT_PENDING_KEY,
        PLAYERS_REFRESH_PENDING_KEY,
        IDENTITY_SHELL_READY_KEY,
    ):
        session_state.pop(key, None)
    try:
        from modules import players_refresh_flight as refresh_flight

        session_state.pop(refresh_flight.PLAYERS_REFRESH_SCHEDULED_KEY, None)
        session_state.pop(refresh_flight.PLAYERS_REFRESH_ROLE_KEY, None)
    except Exception:
        pass


def load_persisted_players(
    *,
    db_path: str,
    load_players_fn: Callable[[str], Any],
) -> Any:
    """Load players from the local DB without network refresh."""

    started = time.perf_counter()
    if not os.path.exists(db_path):
        log_slow_startup_operation("players_cache_lookup", 0.0, cache_status="miss")
        return None
    frame = load_players_fn(db_path)
    elapsed = (time.perf_counter() - started) * 1000
    empty = getattr(frame, "empty", True)
    log_slow_startup_operation(
        "players_disk_load",
        elapsed,
        cache_status="miss" if empty else "hit",
    )
    if empty:
        return None
    return frame


def sleeper_players_cache_stale(
    *,
    cache_path: str = "data/sleeper_players.json",
    ttl_seconds: float = 60 * 60,
) -> bool:
    if not os.path.exists(cache_path):
        return True
    try:
        age = time.time() - os.path.getmtime(cache_path)
    except OSError:
        return True
    return age > float(ttl_seconds)


def ensure_players_for_startup(
    *,
    db_path: str,
    load_players_fn: Callable[[str], Any],
    build_players_table_fn: Callable[..., Any],
    session_state: MutableMapping[str, Any],
    allow_network_refresh: bool = False,
):
    """Prefer persisted players before first-useful; optionally refresh after.

    Cold production pathology: ``ensure_players`` called ``build_players_table(refresh=True)``
    whenever ``sleeper_players.json`` was >1h old, blocking the global loader on
    Sleeper/FantasyCalc/stats network work. First-useful must use disk when present.

    #238: when disk is present and Sleeper JSON is merely aged, queue a deferred
    process-scoped refresh — never synchronously rebuild on the startup path.
    ``allow_network_refresh`` remains for callers that opt in to arming the queue;
    both branches only set the pending flag (identical arming). Missing disk still
    requires a foreground rebuild.
    """

    started = time.perf_counter()
    log_slow_startup_operation("players_cache_lookup", 0.0, cache_status="start")
    persisted = load_persisted_players(db_path=db_path, load_players_fn=load_players_fn)
    if persisted is not None:
        if sleeper_players_cache_stale():
            try:
                from modules import players_refresh_flight as refresh_flight

                if refresh_flight.should_queue_stale_refresh(session_state):
                    session_state[PLAYERS_REFRESH_PENDING_KEY] = True
            except Exception:
                # Fail open: keep prior arming behavior if flight helpers fail.
                session_state[PLAYERS_REFRESH_PENDING_KEY] = True
        # allow_network_refresh is intentionally unused for arming — both True and
        # False only queue; they must never force a sync network rebuild here.
        _ = allow_network_refresh
        log_slow_startup_operation(
            "players_normalize_complete",
            (time.perf_counter() - started) * 1000,
            cache_status="hit",
        )
        return persisted

    # No usable disk baseline — network rebuild is unavoidable.
    rebuild_started = time.perf_counter()
    frame = build_players_table_fn(db_path, refresh=True)
    log_slow_startup_operation(
        "players_provider_refresh",
        (time.perf_counter() - rebuild_started) * 1000,
        cache_status="miss",
    )
    log_slow_startup_operation(
        "players_normalize_complete",
        (time.perf_counter() - started) * 1000,
        cache_status="miss",
    )
    return frame


def maybe_refresh_players_after_shell(
    *,
    db_path: str,
    build_players_table_fn: Callable[..., Any],
    session_state: MutableMapping[str, Any],
    background: bool = True,
) -> Any | None:
    """Schedule deferred public player refresh without blocking first-useful (#238).

    Pre-#238 this awaited ``build_players_table(refresh=True)`` on the request
    thread after ``football_context_ready``, which could spend ~9s before Game
    Plan entry and feed a Streamlit rerun storm. Production must schedule only.
    """

    from modules import players_refresh_flight as refresh_flight

    result = refresh_flight.schedule_deferred_players_refresh(
        db_path=db_path,
        build_players_table_fn=build_players_table_fn,
        session_state=session_state,
        pending_key=PLAYERS_REFRESH_PENDING_KEY,
        background=background,
    )
    if not result.get("scheduled"):
        return None
    # Background owner: never return a replacement frame on this run — keep the
    # startup last-known-good frame until a later remount reads refreshed SQLite.
    if background:
        return None
    frame = result.get("frame")
    if frame is not None and not getattr(frame, "empty", True):
        return frame
    return None
