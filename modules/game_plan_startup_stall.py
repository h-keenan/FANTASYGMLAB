"""Game Plan startup stall hardening (#233).

Diagnostics and fail-soft helpers for the package-MISS path.
Gated by DYNASTYGM_STARTUP=1 for emissions. Fail-soft UX is always available.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, MutableMapping
from contextlib import contextmanager
from typing import Any, Iterator

from modules import startup_cold_path


SESSION_ACTIVE_STAGE_KEY = "_game_plan_startup_active_stage"
SESSION_FAIL_SOFT_KEY = "_game_plan_startup_fail_soft"
SESSION_RETRY_COUNT_KEY = "_game_plan_startup_retry_count"
SESSION_FINGERPRINT_PREFIX_KEY = "_game_plan_startup_fp_prefix"
MAX_AUTO_RETRIES = 1

# Synchronous stall thresholds (seconds) — emit diagnostics only; never mutate Streamlit.
WATCHDOG_THRESHOLDS_S = (2.0, 5.0, 10.0)
# User-visible fail-soft ceiling — separate from the 45s hard single-flight lock timeout.
# A waiter should never appear frozen for the full hard safety ceiling.
USER_VISIBLE_FAILSOFT_S = 12.0
# Recommended hard lock safety ceiling (documented; enforced in process cache).
RECOMMENDED_HARD_SINGLEFLIGHT_TIMEOUT_S = 45.0

_SAFE_STAGE_LABELS = frozenset(
    {
        "game_plan_package_build",
        "game_plan_shared_context",
        "game_plan_trade",
        "game_plan_briefing",
        "game_plan_compose",
        "game_plan_package_store",
        "game_plan_render",
        "game_plan_first_useful",
        "singleflight_wait",
        "singleflight_builder",
    }
)


def diagnostics_enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    return startup_cold_path.startup_diagnostics_enabled(environ=environ)


def _safe_label(value: object, *, limit: int = 48) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    cleaned = "".join(ch if ch.isalnum() or ch in "._:-" else "_" for ch in text)
    return cleaned[:limit]


def _emit(payload: Mapping[str, Any]) -> None:
    if not diagnostics_enabled():
        return
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(dict(payload), sort_keys=True), flush=True)
    except Exception:
        pass


def _attach_correlation(
    session_state: MutableMapping[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        from modules import auth_restore_lifecycle
        from modules import auth_storage_handshake

        payload["startup_session_id"] = _safe_label(
            session_state.get(auth_restore_lifecycle.STARTUP_SESSION_ID_KEY), limit=32
        )
        payload["startup_run_number"] = int(
            session_state.get(auth_restore_lifecycle.STARTUP_RUN_NUMBER_KEY) or 0
        )
        payload["run_cause"] = _safe_label(
            auth_storage_handshake.classify_script_run_cause(session_state), limit=48
        )
    except Exception:
        payload.setdefault("startup_run_number", 0)
        payload.setdefault("run_cause", "unknown")
    return payload


def mark_active_stage(session_state: MutableMapping[str, Any], stage: str) -> None:
    session_state[SESSION_ACTIVE_STAGE_KEY] = _safe_label(stage, limit=64)


def clear_active_stage(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop(SESSION_ACTIVE_STAGE_KEY, None)


def active_stage(session_state: Mapping[str, Any] | None) -> str:
    return _safe_label((session_state or {}).get(SESSION_ACTIVE_STAGE_KEY), limit=64)


def emit_stage_event(
    session_state: MutableMapping[str, Any],
    *,
    stage: str,
    phase: str,
    duration_ms: float = 0.0,
    signature_prefix: str = "",
    cache_status: str = "",
    exception_type: str = "",
) -> None:
    """Emit START/COMPLETE/ERROR/FINALLY for a Game Plan stage (diagnostics only)."""

    if not diagnostics_enabled():
        return
    label = _safe_label(stage, limit=48) or "unknown"
    kind = {
        "start": "startup_stage_start",
        "complete": "startup_stage_complete",
        "error": "startup_stage_error",
        "finally": "startup_stage_finally",
    }.get(str(phase or "").casefold(), "startup_stage_event")
    payload: dict[str, Any] = {
        "kind": kind,
        "stage": label,
        "phase": _safe_label(phase, limit=16),
        "duration_ms": round(max(0.0, float(duration_ms)), 1),
        "signature_prefix": _safe_label(signature_prefix, limit=16),
    }
    if cache_status:
        payload["cache_status"] = _safe_label(cache_status, limit=24)
    if exception_type:
        payload["exception_type"] = _safe_label(exception_type, limit=64)
    _attach_correlation(session_state, payload)
    _emit(payload)


@contextmanager
def stage_span(
    session_state: MutableMapping[str, Any],
    stage: str,
    *,
    signature_prefix: str = "",
) -> Iterator[dict[str, Any]]:
    """START → COMPLETE/ERROR → FINALLY for one stage. Always clears active stage."""

    meta: dict[str, Any] = {"cache_status": "", "error": ""}
    started = time.perf_counter()
    mark_active_stage(session_state, stage)
    emit_stage_event(
        session_state,
        stage=stage,
        phase="start",
        signature_prefix=signature_prefix,
    )
    error_type = ""
    try:
        yield meta
    except Exception as exc:
        error_type = type(exc).__name__
        meta["error"] = error_type
        emit_stage_event(
            session_state,
            stage=stage,
            phase="error",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            signature_prefix=signature_prefix,
            exception_type=error_type,
        )
        raise
    finally:
        elapsed = (time.perf_counter() - started) * 1000.0
        if not error_type:
            emit_stage_event(
                session_state,
                stage=stage,
                phase="complete",
                duration_ms=elapsed,
                signature_prefix=signature_prefix,
                cache_status=str(meta.get("cache_status") or ""),
            )
        emit_stage_event(
            session_state,
            stage=stage,
            phase="finally",
            duration_ms=elapsed,
            signature_prefix=signature_prefix,
            exception_type=error_type,
        )
        clear_active_stage(session_state)


def check_watchdog(
    session_state: MutableMapping[str, Any],
    *,
    stage: str,
    started_mono: float,
    signature_prefix: str = "",
) -> list[float]:
    """Emit stall_watchdog events when stage elapsed crosses thresholds (sync only)."""

    if not diagnostics_enabled():
        return []
    elapsed_s = max(0.0, time.perf_counter() - float(started_mono))
    emitted_key = f"_gp_stall_wd_{_safe_label(stage, limit=32)}"
    already = session_state.get(emitted_key)
    if not isinstance(already, list):
        already = []
    fired: list[float] = []
    for threshold in WATCHDOG_THRESHOLDS_S:
        if elapsed_s + 1e-9 < threshold:
            break
        if threshold in already:
            continue
        already.append(threshold)
        fired.append(threshold)
        payload = {
            "kind": "stall_watchdog",
            "stage": _safe_label(stage, limit=48),
            "threshold_s": threshold,
            "elapsed_ms": round(elapsed_s * 1000.0, 1),
            "signature_prefix": _safe_label(signature_prefix, limit=16),
            "active_stage": active_stage(session_state),
        }
        _attach_correlation(session_state, payload)
        _emit(payload)
    session_state[emitted_key] = already
    return fired


def should_fail_soft_for_elapsed(
    elapsed_s: float,
    *,
    threshold_s: float = USER_VISIBLE_FAILSOFT_S,
) -> bool:
    """True when elapsed work exceeds the user-visible fail-soft ceiling."""

    return float(elapsed_s) + 1e-9 >= float(threshold_s)


def apply_user_visible_failsoft_if_needed(
    session_state: MutableMapping[str, Any],
    *,
    started_mono: float,
    reason: str = "builder_slow",
    threshold_s: float = USER_VISIBLE_FAILSOFT_S,
) -> bool:
    """Mark fail-soft when a stage exceeds the user-visible ceiling (not the hard lock)."""

    elapsed_s = max(0.0, time.perf_counter() - float(started_mono))
    if not should_fail_soft_for_elapsed(elapsed_s, threshold_s=threshold_s):
        return False
    if fail_soft_state(session_state):
        return True
    set_fail_soft(session_state, reason=reason, exception_type="SlowBuilder")
    if diagnostics_enabled():
        payload = {
            "kind": "user_visible_failsoft",
            "reason": _safe_label(reason, limit=64),
            "threshold_s": float(threshold_s),
            "elapsed_ms": round(elapsed_s * 1000.0, 1),
            "hard_timeout_s": RECOMMENDED_HARD_SINGLEFLIGHT_TIMEOUT_S,
        }
        _attach_correlation(session_state, payload)
        _emit(payload)
    return True


def set_fail_soft(
    session_state: MutableMapping[str, Any],
    *,
    reason: str,
    exception_type: str = "",
) -> None:
    session_state[SESSION_FAIL_SOFT_KEY] = {
        "reason": _safe_label(reason, limit=64),
        "exception_type": _safe_label(exception_type, limit=64),
        "ts": time.time(),
    }


def clear_fail_soft(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop(SESSION_FAIL_SOFT_KEY, None)


def fail_soft_state(session_state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    raw = (session_state or {}).get(SESSION_FAIL_SOFT_KEY)
    return dict(raw) if isinstance(raw, Mapping) else None


def can_retry(session_state: Mapping[str, Any] | None) -> bool:
    count = int((session_state or {}).get(SESSION_RETRY_COUNT_KEY) or 0)
    return count < MAX_AUTO_RETRIES


def note_retry(session_state: MutableMapping[str, Any]) -> int:
    count = int(session_state.get(SESSION_RETRY_COUNT_KEY) or 0) + 1
    session_state[SESSION_RETRY_COUNT_KEY] = count
    return count


def fail_soft_copy(*, exception_type: str = "") -> tuple[str, str]:
    label = str(exception_type or "").casefold()
    if label in {"deferredenrichment", "deferred_enrichment", "post_football_refresh"}:
        return (
            "Game Plan is catching up",
            "Your dashboard shell stays available. Open My Team, Trade Hub, "
            "Waivers, League, or PQV while Game Plan finishes — we will not invent recommendations.",
        )
    return (
        "Game Plan is taking longer than expected",
        "Your dashboard shell stays available. Retry Game Plan, or open My Team, "
        "Trade Hub, Waivers, or League while we recover.",
    )


def apply_post_football_deadline_failsoft(
    session_state: MutableMapping[str, Any],
    *,
    threshold_s: float = USER_VISIBLE_FAILSOFT_S,
) -> bool:
    """Dashboard-level fail-soft when Game Plan has not become useful after football ready.

    Does not invent recommendations and does not schedule automatic recovery reruns.
    """

    if fail_soft_state(session_state):
        return True
    if session_state.get("game_plan_first_useful") or session_state.get(
        "_startup_milestones_once", {}
    ).get("game_plan_first_useful"):
        return False
    ready_mono = session_state.get("_football_context_ready_mono")
    if not isinstance(ready_mono, (int, float)):
        return False
    elapsed_s = max(0.0, time.perf_counter() - float(ready_mono))
    if not should_fail_soft_for_elapsed(elapsed_s, threshold_s=threshold_s):
        return False
    set_fail_soft(
        session_state,
        reason="post_football_deadline",
        exception_type="DeferredEnrichment",
    )
    if diagnostics_enabled():
        payload = {
            "kind": "dashboard_post_football_failsoft",
            "threshold_s": float(threshold_s),
            "elapsed_ms": round(elapsed_s * 1000.0, 1),
        }
        _attach_correlation(session_state, payload)
        _emit(payload)
    return True


def record_fingerprint_prefix(
    session_state: MutableMapping[str, Any], prefix: str, *, when: str
) -> None:
    if not diagnostics_enabled():
        return
    store = session_state.setdefault(SESSION_FINGERPRINT_PREFIX_KEY, {})
    if not isinstance(store, dict):
        store = {}
        session_state[SESSION_FINGERPRINT_PREFIX_KEY] = store
    store[_safe_label(when, limit=24)] = _safe_label(prefix, limit=16)
    before = store.get("before_build")
    after = store.get("after_build")
    if before and after and before != after:
        payload = {
            "kind": "package_fingerprint_drift",
            "before_prefix": before,
            "after_prefix": after,
        }
        _attach_correlation(session_state, payload)
        _emit(payload)
