"""Tail-latency / 15s-load diagnostics (#230).

Extends DYNASTYGM_STARTUP with correlated stage timing, process-temperature
classification, same-signature duplicate detection, and a compact summary event.

Gated by DYNASTYGM_STARTUP=1. No PII. No football methodology changes.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable, Mapping, MutableMapping
from contextlib import contextmanager
from typing import Any, Iterator

from modules import performance
from modules import startup_cold_path


STARTUP_ENV_KEY = startup_cold_path.STARTUP_ENV_KEY
TRACE_STATE_KEY = "_tail_latency_trace"
SUMMARY_EMITTED_KEY = "_tail_latency_summary_emitted"
POST_READY_REBUILD_KEY = "_tail_latency_post_ready_rebuilds"
# True only after first post-dismiss football/Game Plan hydration finishes (#233).
FOOTBALL_HYDRATION_COMPLETE_KEY = "_tail_latency_football_hydration_complete"

# Milestone pairs → exclusive stage durations for summary aggregation (#233).
# Values are (start_milestone, duration_stage_name).
MILESTONE_STAGE_GAPS: dict[str, tuple[str, str]] = {
    "auth_storage_received": ("auth_storage_requested", "auth_storage_wait"),
    "profile_fetch_complete": ("profile_fetch_start", "profile_fetch"),
    "entitlement_fetch_complete": ("entitlement_fetch_start", "entitlement_fetch"),
    "league_restore_complete": ("league_restore_start", "league_restore"),
    "league_restored": ("league_restore_start", "league_restore"),
}


# User-perceived milestone buckets (A–F).
USER_MILESTONES = {
    "shell_chrome_ready": "app_shell_visible",
    "workspace_chrome_ready": "app_shell_visible",
    "loading_dismissed": "loading_dismissed",
    "first_usable_paint": "first_useful",
    "game_plan_first_useful": "first_useful",
    "game_plan_package_ready": "game_plan_ready",
    "game_plan_composed": "game_plan_ready",
    "dashboard_football_ready": "dashboard_complete",
    "dashboard_rendered": "dashboard_complete",
}

PROCESS_TEMPERATURES = frozenset(
    {
        "PROCESS_COLD",
        "PROCESS_WARM_SESSION_COLD",
        "SESSION_WARM",
        "PRESENTATION_RERUN",
        "AUTH_RESTORE",
        "GUEST_COLD",
    }
)

_BUILD_FAMILIES = (
    "prepared_frame",
    "league_context",
    "trade_inventory",
    "briefing_assembly",
    "compose",
    "game_plan_package",
)

# Process boot marker — survives across Streamlit sessions in the same worker.
_PROCESS_BOOT_MONO = time.perf_counter()
_PROCESS_SEEN_SESSION_IDS: set[str] = set()


def diagnostics_enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    return startup_cold_path.startup_diagnostics_enabled(environ=environ)


def process_uptime_ms() -> float:
    return max(0.0, (time.perf_counter() - _PROCESS_BOOT_MONO) * 1000.0)


def reset_process_boot_for_tests() -> None:
    """Test-only: reset process-scoped trackers."""

    global _PROCESS_BOOT_MONO
    _PROCESS_BOOT_MONO = time.perf_counter()
    _PROCESS_SEEN_SESSION_IDS.clear()


def _safe_label(value: Any, *, limit: int = 64) -> str:
    return performance._safe_label(value)[:limit]


def _trace(session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    store = session_state.get(TRACE_STATE_KEY)
    if not isinstance(store, dict):
        store = {
            "stage_durations_ms": {},
            "milestone_elapsed_ms": {},
            "build_counts": {},
            "build_signatures": {},
            "duplicates": [],
            "provider_ms": {},
            "provider_calls": 0,
            "post_ready_rebuilds": [],
            "last_stage_mono": None,
            "last_stage_name": "",
            "summary_emitted": False,
            "cache_status": {},
        }
        session_state[TRACE_STATE_KEY] = store
    return store


def note_process_session(session_id: str) -> None:
    text = _safe_label(session_id, limit=32)
    if text:
        _PROCESS_SEEN_SESSION_IDS.add(text)


def process_cache_survival_snapshot() -> dict[str, Any]:
    """Non-PII counts showing whether process caches currently hold entries."""

    prepared_entries = 0
    league_entries = 0
    trade_entries = 0
    compose_entries = 0
    try:
        from modules import prepared_player_frame

        prepared_entries = int(len(getattr(prepared_player_frame, "_PROCESS_FRAME_STORE", {}) or {}))
    except Exception:
        prepared_entries = 0
    try:
        from modules import game_plan_process_cache as gppc

        league_entries = int(len(getattr(gppc, "_PROCESS_LEAGUE_CONTEXT", {}) or {}))
        trade_entries = int(len(getattr(gppc, "_PROCESS_TRADE_HEADLINE", {}) or {}))
    except Exception:
        pass
    try:
        from modules import daily_gm_briefing

        compose_entries = int(len(getattr(daily_gm_briefing, "_COMPOSE_MEMO", {}) or {}))
    except Exception:
        pass
    return {
        "prepared_frame_entries": prepared_entries,
        "league_process_entries": league_entries,
        "trade_process_entries": trade_entries,
        "compose_process_entries": compose_entries,
        "process_uptime_ms": round(process_uptime_ms(), 1),
        "process_sessions_seen": len(_PROCESS_SEEN_SESSION_IDS),
    }


def classify_process_temperature(
    session_state: MutableMapping[str, Any],
    *,
    run_cause: str = "",
) -> str:
    """Classify workload temperature for one script run (not interchangeable)."""

    from modules import auth_restore_lifecycle
    from modules import startup_coordinator

    cause = _safe_label(run_cause).casefold()
    complete = bool(session_state.get(startup_coordinator.STARTUP_COMPLETE_KEY))
    run_number = int(session_state.get(auth_restore_lifecycle.STARTUP_RUN_NUMBER_KEY) or 0)
    phase = auth_restore_lifecycle.current_phase(session_state).name
    authenticated = bool(
        str(session_state.get("auth_user_id") or "").strip()
        or (
            isinstance(session_state.get("auth_session"), dict)
            and str(session_state.get("auth_session", {}).get("user_id") or "").strip()
        )
    )
    guest = (not authenticated) and bool(str(session_state.get("selected_league_id") or "").strip())
    caches = process_cache_survival_snapshot()
    process_warm = any(
        int(caches.get(key) or 0) > 0
        for key in (
            "prepared_frame_entries",
            "league_process_entries",
            "trade_process_entries",
            "compose_process_entries",
        )
    )
    package_ready = bool(
        session_state.get("_game_plan_package_signature")
        or session_state.get("_game_plan_package_bundle")
    )

    if complete and cause in {"post_ready_interactive", "player_quick_view"}:
        return "PRESENTATION_RERUN"
    if phase in {"STORAGE_PENDING", "AUTH_RESOLVED", "PROFILE_RESOLVED", "ENTITLEMENT_RESOLVED"} and not complete:
        if authenticated or cause.startswith("auth") or cause.startswith("durable"):
            return "AUTH_RESTORE"
    if guest and run_number <= 3 and not complete:
        return "GUEST_COLD"
    if package_ready and complete:
        return "SESSION_WARM"
    if process_warm and not complete:
        return "PROCESS_WARM_SESSION_COLD"
    if not process_warm and not complete:
        return "PROCESS_COLD"
    if process_warm:
        return "PROCESS_WARM_SESSION_COLD"
    return "PROCESS_COLD"


def record_stage_duration(
    session_state: MutableMapping[str, Any],
    stage: str,
    duration_ms: float,
    *,
    cache_status: str = "",
    signature_prefix: str = "",
    detail: Mapping[str, Any] | None = None,
) -> None:
    """Accumulate monotonic stage duration and optionally emit a diagnostic row."""

    store = _trace(session_state)
    name = _safe_label(stage, limit=48)
    ms = max(0.0, float(duration_ms))
    durations = store.setdefault("stage_durations_ms", {})
    if not isinstance(durations, dict):
        durations = {}
        store["stage_durations_ms"] = durations
    durations[name] = round(float(durations.get(name) or 0.0) + ms, 1)
    if cache_status:
        statuses = store.setdefault("cache_status", {})
        if isinstance(statuses, dict):
            statuses[name] = _safe_label(cache_status, limit=24)
    if not diagnostics_enabled():
        return
    entry = {
        "kind": "startup_stage_duration",
        "stage": name,
        "duration_ms": round(ms, 1),
        "cache_status": _safe_label(cache_status, limit=24),
        "signature_prefix": _safe_label(signature_prefix, limit=16),
    }
    _attach_correlation(session_state, entry)
    if isinstance(detail, Mapping) and detail:
        entry["detail"] = _safe_detail(detail)
    _emit(entry)


@contextmanager
def stage_timer(
    session_state: MutableMapping[str, Any],
    stage: str,
    *,
    cache_status: str = "",
    signature_prefix: str = "",
) -> Iterator[dict[str, Any]]:
    """Context manager measuring one monotonic stage duration."""

    meta: dict[str, Any] = {"cache_status": cache_status, "signature_prefix": signature_prefix}
    started = time.perf_counter()
    try:
        yield meta
    finally:
        record_stage_duration(
            session_state,
            stage,
            (time.perf_counter() - started) * 1000.0,
            cache_status=str(meta.get("cache_status") or cache_status),
            signature_prefix=str(meta.get("signature_prefix") or signature_prefix),
        )


def note_build(
    session_state: MutableMapping[str, Any],
    *,
    family: str,
    signature: str,
    cache_status: str,
    duration_ms: float = 0.0,
) -> dict[str, Any] | None:
    """Track real builds; emit duplicate_work when same signature rebuilds."""

    fam = _safe_label(family, limit=32)
    if fam not in _BUILD_FAMILIES:
        fam = _safe_label(family, limit=32)
    sig = _safe_label(signature, limit=64)
    prefix = sig[:8]
    status = _safe_label(cache_status, limit=24).casefold() or "unknown"
    store = _trace(session_state)
    counts = store.setdefault("build_counts", {})
    if not isinstance(counts, dict):
        counts = {}
        store["build_counts"] = counts
    key = f"{fam}:{prefix or 'none'}"
    prior = int(counts.get(key) or 0)
    if status in {"miss", "build", "rebuild", "compute"}:
        counts[key] = prior + 1
    signatures = store.setdefault("build_signatures", {})
    if not isinstance(signatures, dict):
        signatures = {}
        store["build_signatures"] = signatures
    signatures[fam] = prefix

    from modules import startup_coordinator

    # INITIAL_POST_DISMISS_HYDRATION vs REPEATED_POST_READY_REBUILD (#233).
    # STARTUP_COMPLETE flips at loading_dismissed — first football builds after
    # dismiss are expected hydration, not rebuild regressions.
    football_complete = bool(session_state.get(FOOTBALL_HYDRATION_COMPLETE_KEY))
    dismiss_complete = bool(session_state.get(startup_coordinator.STARTUP_COMPLETE_KEY))
    result = None
    if status in {"miss", "build", "rebuild", "compute"} and prior >= 1:
        result = {
            "kind": "duplicate_work",
            "family": fam,
            "signature_prefix": prefix,
            "occurrence": prior + 1,
            "duration_ms": round(float(duration_ms), 1),
            "post_ready": football_complete,
        }
        dups = store.setdefault("duplicates", [])
        if isinstance(dups, list):
            dups.append(
                {
                    "family": fam,
                    "signature_prefix": prefix,
                    "occurrence": prior + 1,
                    "post_ready": football_complete,
                }
            )
        if diagnostics_enabled():
            _attach_correlation(session_state, result)
            _emit(result)
    if status in {"miss", "build", "rebuild", "compute"} and dismiss_complete and not football_complete:
        hydration = {
            "kind": "initial_post_dismiss_hydration",
            "family": fam,
            "signature_prefix": prefix,
            "duration_ms": round(float(duration_ms), 1),
        }
        hydrations = store.setdefault("initial_post_dismiss_hydrations", [])
        if isinstance(hydrations, list):
            hydrations.append({"family": fam, "signature_prefix": prefix})
        if diagnostics_enabled():
            _attach_correlation(session_state, hydration)
            _emit(hydration)
    elif football_complete and status in {"miss", "build", "rebuild", "compute"}:
        rebuild = {
            "kind": "post_ready_rebuild",
            "family": fam,
            "signature_prefix": prefix,
            "duration_ms": round(float(duration_ms), 1),
        }
        rebuilds = store.setdefault("post_ready_rebuilds", [])
        if isinstance(rebuilds, list):
            rebuilds.append({"family": fam, "signature_prefix": prefix})
        if diagnostics_enabled():
            _attach_correlation(session_state, rebuild)
            _emit(rebuild)
    if duration_ms and fam:
        record_stage_duration(
            session_state,
            fam,
            duration_ms,
            cache_status=status,
            signature_prefix=prefix,
        )
    return result


def mark_football_hydration_complete(session_state: MutableMapping[str, Any]) -> None:
    """Mark first post-dismiss football/Game Plan hydration finished."""

    session_state[FOOTBALL_HYDRATION_COMPLETE_KEY] = True


def note_provider_call(
    session_state: MutableMapping[str, Any],
    *,
    category: str,
    duration_ms: float,
    cache_status: str = "",
    timeout: bool = False,
    retries: int = 0,
    endpoint: str = "",
) -> None:
    """Record a safe provider timing category (no league/user ids)."""

    store = _trace(session_state)
    name = _safe_label(category, limit=40)
    endpoint_label = _safe_label(endpoint, limit=48)
    ms = max(0.0, float(duration_ms))
    provider_ms = store.setdefault("provider_ms", {})
    if not isinstance(provider_ms, dict):
        provider_ms = {}
        store["provider_ms"] = provider_ms
    provider_ms[name] = round(float(provider_ms.get(name) or 0.0) + ms, 1)
    provider_counts = store.setdefault("provider_call_counts", {})
    if not isinstance(provider_counts, dict):
        provider_counts = {}
        store["provider_call_counts"] = provider_counts
    provider_counts[name] = int(provider_counts.get(name) or 0) + 1
    if endpoint_label:
        endpoint_counts = store.setdefault("provider_endpoint_counts", {})
        if not isinstance(endpoint_counts, dict):
            endpoint_counts = {}
            store["provider_endpoint_counts"] = endpoint_counts
        endpoint_counts[endpoint_label] = int(endpoint_counts.get(endpoint_label) or 0) + 1
        endpoint_rows = store.setdefault("provider_endpoint_calls", [])
        if isinstance(endpoint_rows, list) and len(endpoint_rows) < 64:
            endpoint_rows.append(
                {
                    "category": name,
                    "endpoint": endpoint_label,
                    "duration_ms": round(ms, 1),
                    "cache_status": _safe_label(cache_status, limit=24),
                }
            )
    store["provider_calls"] = int(store.get("provider_calls") or 0) + 1
    if not diagnostics_enabled():
        return
    entry = {
        "kind": "provider_timing",
        "category": name,
        "duration_ms": round(ms, 1),
        "cache_status": _safe_label(cache_status, limit=24),
        "timeout": bool(timeout),
        "retries": max(0, int(retries)),
    }
    if endpoint_label:
        entry["endpoint"] = endpoint_label
    _attach_correlation(session_state, entry)
    _emit(entry)


# Golden startup path: distinct league-family endpoints that may each miss once.
# Identical endpoint re-hits must be process/session cache hits (not re-fetched).
MAX_PROVIDER_LEAGUES_CALLS_GOLDEN_STARTUP = 4


def provider_leagues_call_count(session_state: Mapping[str, Any] | None) -> int:
    store = _trace(session_state) if session_state is not None else {}
    counts = store.get("provider_call_counts") if isinstance(store, dict) else {}
    if not isinstance(counts, dict):
        return 0
    return int(counts.get("provider_leagues") or 0)


def provider_endpoint_duplicate_count(session_state: Mapping[str, Any] | None) -> int:
    """Count identical endpoint labels that fired more than once (duplicate work)."""

    store = _trace(session_state) if session_state is not None else {}
    counts = store.get("provider_endpoint_counts") if isinstance(store, dict) else {}
    if not isinstance(counts, dict):
        return 0
    return sum(max(0, int(value) - 1) for value in counts.values())


def provider_timed(
    session_state: MutableMapping[str, Any],
    category: str,
    fn: Callable[[], Any],
    *,
    cache_status: str = "",
) -> Any:
    started = time.perf_counter()
    timeout = False
    try:
        return fn()
    except TimeoutError:
        timeout = True
        raise
    finally:
        note_provider_call(
            session_state,
            category=category,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            cache_status=cache_status,
            timeout=timeout,
        )


def enrich_milestone_entry(
    session_state: MutableMapping[str, Any],
    entry: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Add correlation / duration / temperature fields to a milestone row."""

    store = _trace(session_state)
    now = time.perf_counter()
    last_mono = store.get("last_stage_mono")
    if isinstance(last_mono, (int, float)):
        entry["duration_ms"] = round(max(0.0, (now - float(last_mono)) * 1000.0), 1)
    store["last_stage_mono"] = now
    store["last_stage_name"] = str(entry.get("milestone") or "")
    milestone = str(entry.get("milestone") or "")
    elapsed = entry.get("elapsed_ms")
    if isinstance(elapsed, (int, float)):
        marks = store.setdefault("milestone_elapsed_ms", {})
        if isinstance(marks, dict):
            marks[milestone] = float(elapsed)
            gap = MILESTONE_STAGE_GAPS.get(milestone)
            if gap is not None:
                start_name, stage_name = gap
                start_elapsed = marks.get(start_name)
                if isinstance(start_elapsed, (int, float)):
                    record_stage_duration(
                        session_state,
                        stage_name,
                        max(0.0, float(elapsed) - float(start_elapsed)),
                    )
        bucket = USER_MILESTONES.get(milestone)
        if bucket:
            buckets = store.setdefault("user_milestones_ms", {})
            if isinstance(buckets, dict) and bucket not in buckets:
                buckets[bucket] = float(elapsed)
    if milestone in {
        "game_plan_package_ready",
        "game_plan_first_useful",
        "dashboard_football_ready",
    }:
        mark_football_hydration_complete(session_state)
    run_cause = str(entry.get("run_cause") or "")
    if not run_cause:
        try:
            from modules import auth_storage_handshake

            run_cause = auth_storage_handshake.classify_script_run_cause(session_state)
        except Exception:
            run_cause = "unknown"
        entry["run_cause"] = run_cause
    entry["process_temperature"] = classify_process_temperature(
        session_state, run_cause=run_cause
    )
    entry["process_uptime_ms"] = round(process_uptime_ms(), 1)
    return entry


def maybe_emit_summary(
    session_state: MutableMapping[str, Any],
    *,
    trigger: str = "interactive_stable",
    force: bool = False,
) -> dict[str, Any] | None:
    """Emit one compact startup_trace_summary at terminal useful state."""

    store = _trace(session_state)
    if store.get("summary_emitted") and not force:
        return None
    marks = store.get("milestone_elapsed_ms") if isinstance(store.get("milestone_elapsed_ms"), dict) else {}
    buckets = store.get("user_milestones_ms") if isinstance(store.get("user_milestones_ms"), dict) else {}
    # Prefer explicit interactive_stable once dashboard_complete exists.
    if trigger == "interactive_stable" and "dashboard_complete" not in buckets and not force:
        if "game_plan_ready" not in buckets and "first_useful" not in buckets:
            return None

    from modules import auth_restore_lifecycle

    session_id = str(session_state.get(auth_restore_lifecycle.STARTUP_SESSION_ID_KEY) or "")
    note_process_session(session_id)
    run_count = int(session_state.get(auth_restore_lifecycle.STARTUP_RUN_NUMBER_KEY) or 0)
    durations = store.get("stage_durations_ms") if isinstance(store.get("stage_durations_ms"), dict) else {}
    provider_ms = store.get("provider_ms") if isinstance(store.get("provider_ms"), dict) else {}
    caches = store.get("cache_status") if isinstance(store.get("cache_status"), dict) else {}
    duplicates = store.get("duplicates") if isinstance(store.get("duplicates"), list) else []
    post_ready = store.get("post_ready_rebuilds") if isinstance(store.get("post_ready_rebuilds"), list) else []

    interactive_ms = buckets.get("dashboard_complete") or buckets.get("game_plan_ready") or buckets.get(
        "first_useful"
    )
    if interactive_ms is not None and "interactive_stable" not in buckets:
        buckets["interactive_stable"] = float(interactive_ms)

    # Ownership stages for slowest_stage — do NOT let tiny exclusive slices
    # (e.g. auth_payload_applied 1.4ms) win when real work lives in profile /
    # league_restore / league_context / trade / briefing / compose.
    owner_stage_keys = (
        "auth_storage_wait",
        "auth_storage_handshake",
        "profile_fetch",
        "entitlement_fetch",
        "league_restore",
        "players",
        "players_disk_load",
        "prepared_frame",
        "league_context",
        "trade_inventory",
        "briefing_assembly",
        "briefing",
        "compose",
        "package_store",
        "package_serialize",
        "presentation",
        "shell_chrome",
        "provider_total",
    )
    slowest_stage = ""
    slowest_ms = 0.0
    for name in owner_stage_keys:
        raw = durations.get(name)
        try:
            ms = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            continue
        if ms >= slowest_ms:
            slowest_ms = ms
            slowest_stage = str(name)
    # Fallback: if no owner stages recorded, use max of all durations but ignore
    # stages under 25ms so noise cannot dominate the summary.
    if not slowest_stage:
        for name, value in durations.items():
            try:
                ms = float(value)
            except (TypeError, ValueError):
                continue
            if ms < 25.0:
                continue
            if ms >= slowest_ms:
                slowest_ms = ms
                slowest_stage = str(name)

    # Exclusive stage fields (sum of record_stage_duration / milestone gaps).
    auth_storage_wait_ms = _num(durations.get("auth_storage_wait") or durations.get("auth_storage_handshake"))
    auth_apply_ms = _num(durations.get("auth_payload_applied"))
    profile_fetch_ms = _num(durations.get("profile_fetch"))
    entitlement_ms = _num(durations.get("entitlement_fetch"))
    league_restore_ms = _num(durations.get("league_restore"))
    auth_ms = round(
        sum(
            float(v or 0.0)
            for v in (
                auth_storage_wait_ms,
                auth_apply_ms,
                profile_fetch_ms,
                entitlement_ms,
                league_restore_ms,
            )
        ),
        1,
    )
    provider_total_ms = round(sum(float(v or 0) for v in provider_ms.values()), 1)
    player_frame_ms = _num(durations.get("players") or durations.get("players_disk_load"))
    prepared_frame_ms = _num(durations.get("prepared_frame"))
    league_context_ms = _num(durations.get("league_context"))
    trade_inventory_ms = _num(durations.get("trade_inventory"))
    briefing_assembly_ms = _num(durations.get("briefing_assembly") or durations.get("briefing"))
    compose_ms = _num(durations.get("compose"))
    package_store_ms = _num(
        durations.get("package_store") or durations.get("package_serialize")
    )
    presentation_ms = _num(durations.get("presentation") or durations.get("shell_chrome"))

    # Exclusive accounted work (do not double-count nested provider under stages).
    accounted_ms = round(
        sum(
            float(v or 0.0)
            for v in (
                auth_storage_wait_ms,
                auth_apply_ms,
                profile_fetch_ms,
                entitlement_ms,
                league_restore_ms,
                player_frame_ms,
                prepared_frame_ms,
                league_context_ms,
                trade_inventory_ms,
                briefing_assembly_ms,
                compose_ms,
                package_store_ms,
                presentation_ms,
            )
        ),
        1,
    )
    # Prefer interactive_stable / dashboard_complete as the wall for unexplained.
    wall_ms = _num(buckets.get("interactive_stable")) or _num(buckets.get("dashboard_complete"))
    unexplained_ms = None
    if wall_ms is not None:
        unexplained_ms = round(max(0.0, float(wall_ms) - accounted_ms), 1)

    run_cause = "unknown"
    try:
        from modules import auth_storage_handshake

        run_cause = auth_storage_handshake.classify_script_run_cause(session_state)
    except Exception:
        pass
    temperature = classify_process_temperature(session_state, run_cause=run_cause)
    survival = process_cache_survival_snapshot()

    summary = {
        "kind": "startup_trace_summary",
        "trigger": _safe_label(trigger, limit=32),
        "startup_session_id": _safe_label(session_id, limit=32),
        "run_count": run_count,
        "process_temperature": temperature,
        "loading_dismissed_ms": _num(buckets.get("loading_dismissed")),
        "first_useful_ms": _num(buckets.get("first_useful")),
        "game_plan_ready_ms": _num(buckets.get("game_plan_ready")),
        "dashboard_complete_ms": _num(buckets.get("dashboard_complete")),
        "interactive_stable_ms": _num(buckets.get("interactive_stable")),
        # Exclusive stage durations (not inclusive milestone gaps).
        "auth_ms": auth_ms,
        "auth_storage_wait_ms": auth_storage_wait_ms,
        "auth_apply_ms": auth_apply_ms,
        "profile_fetch_ms": profile_fetch_ms,
        "entitlement_ms": entitlement_ms,
        "league_restore_ms": league_restore_ms,
        "provider_ms": provider_total_ms,
        "player_frame_ms": player_frame_ms,
        "player_disk_ms": _num(durations.get("players_disk_load") or durations.get("players")),
        "prepared_frame_ms": prepared_frame_ms,
        "league_context_ms": league_context_ms,
        "trade_inventory_ms": trade_inventory_ms,
        "briefing_ms": briefing_assembly_ms,
        "briefing_assembly_ms": briefing_assembly_ms,
        "compose_ms": compose_ms,
        "package_store_ms": package_store_ms,
        "presentation_ms": presentation_ms,
        "accounted_ms": accounted_ms,
        "unexplained_ms": unexplained_ms,
        "package_cache_status": _safe_label(caches.get("game_plan_package") or "", limit=24),
        "league_process_cache_status": _safe_label(caches.get("league_context") or "", limit=24),
        "trade_process_cache_status": _safe_label(caches.get("trade_inventory") or "", limit=24),
        "rerun_count_before_stable": run_count,
        "slowest_stage": slowest_stage,
        "slowest_stage_ms": round(slowest_ms, 1),
        "slowest_stage_semantics": "owner_exclusive",
        "duplicate_build_count": len(duplicates),
        "post_ready_rebuild_count": len(post_ready),
        "process_cache_survival": survival,
        "milestone_elapsed_ms": {
            key: _num(value) for key, value in list(marks.items())[:24] if _num(value) is not None
        },
        "stage_duration_semantics": "exclusive",
    }
    store["summary_emitted"] = True
    session_state[SUMMARY_EMITTED_KEY] = True
    if diagnostics_enabled():
        _emit(summary)
    return summary


def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile for small diagnostic samples."""

    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    # Nearest-rank: ceil(P/100 * N), clamped to [1, N].
    rank = max(1, min(len(ordered), int(math.ceil((pct / 100.0) * len(ordered)))))
    return ordered[rank - 1]


def summarize_samples(samples: list[Mapping[str, Any]], field: str) -> dict[str, Any]:
    values = []
    for sample in samples:
        raw = sample.get(field)
        if isinstance(raw, (int, float)):
            values.append(float(raw))
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "median": percentile(values, 50),
        "p75": percentile(values, 75),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "max": max(values),
        "min": min(values),
    }


def estimate_diagnostics_overhead_ms(*, iterations: int = 200) -> float:
    """Cheap self-check: emit-path overhead when diagnostics are off."""

    prior = os.environ.pop(STARTUP_ENV_KEY, None)
    try:
        state: dict[str, Any] = {}
        started = time.perf_counter()
        for index in range(max(1, int(iterations))):
            record_stage_duration(state, "overhead_probe", 0.01)
            note_build(
                state,
                family="compose",
                signature=f"sig{index % 3}",
                cache_status="hit",
                duration_ms=0.01,
            )
        return round(((time.perf_counter() - started) * 1000.0) / max(1, iterations), 4)
    finally:
        if prior is not None:
            os.environ[STARTUP_ENV_KEY] = prior



def _attach_correlation(session_state: MutableMapping[str, Any], entry: MutableMapping[str, Any]) -> None:
    try:
        from modules import auth_restore_lifecycle

        meta = auth_restore_lifecycle.run_context(session_state)
        entry["startup_session_id"] = meta.get("startup_session_id")
        entry["startup_run_number"] = meta.get("startup_run_number")
        entry["restore_phase"] = meta.get("restore_phase")
    except Exception:
        pass
    try:
        from modules import auth_storage_handshake

        entry["run_cause"] = auth_storage_handshake.classify_script_run_cause(session_state)
    except Exception:
        entry["run_cause"] = "unknown"
    entry["process_temperature"] = classify_process_temperature(
        session_state, run_cause=str(entry.get("run_cause") or "")
    )


def _safe_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in list(detail.items())[:12]:
        label = str(key)[:40].casefold()
        if any(token in label for token in ("email", "user", "token", "league_name", "player", "secret")):
            continue
        if isinstance(value, (int, float, bool)) or value is None:
            safe[str(key)[:40]] = value
        else:
            safe[str(key)[:40]] = str(value)[:64]
    return safe


def _emit(entry: Mapping[str, Any]) -> None:
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(dict(entry), sort_keys=True), flush=True)
    except Exception:
        pass


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 1)
    return None


def _sum_keys(durations: Mapping[str, Any], keys: tuple[str, ...]) -> float:
    total = 0.0
    for key in keys:
        raw = durations.get(key)
        if isinstance(raw, (int, float)):
            total += float(raw)
    return round(total, 1)
