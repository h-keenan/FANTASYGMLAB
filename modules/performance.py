from __future__ import annotations

import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from typing import Any, Iterator

from modules import app_config
from modules import runtime_trace


DEBUG_ENV_KEY = "DYNASTYGM_DEBUG_PERF"
SLOW_MS = 1000.0
MAX_SESSION_TIMINGS = 120
PROCESS_STARTED_AT = time.perf_counter()
HEAVY_BUILDERS = {
    "trade_hub_board_generation",
    "my_team_advice_generation",
    "league_summary_generation",
    "waiver_analysis_generation",
    "startup_draft_context_generation",
    "live_draft_player_rankings",
    "live_draft_team_rankings",
    "shared_league_context_generation",
}
SENSITIVE_TOKENS = (
    "token",
    "secret",
    "apikey",
    "api_key",
    "email",
    "authorization",
    "cookie",
    "password",
    "customer",
)
_IDENTIFIER_PATTERN = re.compile(
    r"(?:[0-9a-f]{8}-[0-9a-f-]{27,}|\b\d{12,}\b|[A-Za-z0-9_-]{32,})",
    re.IGNORECASE,
)


def debug_enabled(*, environ: dict | None = None, secrets: Any = None) -> bool:
    if not app_config.customer_unsafe_debug_allowed(environ=environ, secrets=secrets):
        return False
    value = app_config.config_value(DEBUG_ENV_KEY, environ=environ, secrets=secrets)
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _safe_label(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.strip().replace("\n", " ")[:96]
    lowered = text.casefold()
    if any(token in lowered for token in SENSITIVE_TOKENS) or _IDENTIFIER_PATTERN.search(text):
        return "[redacted]"
    sanitized = re.sub(r"[^A-Za-z0-9_.:/ -]", "_", text)
    return sanitized or "unknown"


def _memory_mb() -> float | None:
    try:
        import resource

        usage = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if usage <= 0:
            return None
        if usage > 10_000_000:
            return round(usage / (1024 * 1024), 1)
        return round(usage / 1024, 1)
    except Exception:
        return None


def _current_memory_mb() -> float | None:
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as handle:
            resident_pages = int(handle.read().split()[1])
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return round(resident_pages * page_size / (1024 * 1024), 1)
    except Exception:
        return None


def _session_state():
    try:
        import streamlit as st

        return st.session_state
    except Exception:
        return None


def _append_session_timing(entry: dict[str, Any]) -> None:
    state = _session_state()
    if state is None:
        return
    try:
        timings = list(state.get("_perf_timings", []))
        timings.append(entry)
        state["_perf_timings"] = timings[-MAX_SESSION_TIMINGS:]
        current = list(state.get("_perf_current_events", []))
        current.append(entry)
        state["_perf_current_events"] = current[-MAX_SESSION_TIMINGS:]
    except Exception:
        return


def mark_interaction(name: str, *, lightweight: bool = True) -> None:
    if not debug_enabled():
        return
    state = _session_state()
    if state is None:
        return
    state["_perf_pending_interaction"] = {
        "name": _safe_label(name),
        "lightweight": bool(lightweight),
    }


def record_timing(
    label: str,
    elapsed_ms: float,
    *,
    category: str = "app",
    result_size: int | None = None,
) -> dict[str, Any]:
    safe_label = _safe_label(label)
    entry = {
        "kind": "timing",
        "category": _safe_label(category),
        "label": safe_label,
        "elapsed_ms": round(float(elapsed_ms), 1),
        "memory_mb": _memory_mb(),
    }
    if result_size is not None:
        entry["result_size"] = max(0, int(result_size))
    if debug_enabled():
        _append_session_timing(entry)
        try:
            print("DYNASTYGM_PERF " + json.dumps(entry, sort_keys=True), flush=True)
        except Exception:
            pass
    return entry


def record_cache_event(
    category: str,
    status: str,
    *,
    elapsed_ms: float = 0.0,
    result_size: int | None = None,
    result_memory_bytes: int | None = None,
    fingerprint_category: str = "",
    invalidation_reason: str = "",
) -> dict[str, Any]:
    normalized_status = status if status in {"hit", "miss", "unknown"} else "unknown"
    entry = {
        "kind": "cache",
        "category": _safe_label(category),
        "status": normalized_status,
        "elapsed_ms": round(float(elapsed_ms), 1),
        "invalidation_reason": _safe_label(invalidation_reason) if invalidation_reason else "",
    }
    if result_size is not None:
        entry["result_size"] = max(0, int(result_size))
    if result_memory_bytes is not None:
        entry["result_memory_mb"] = round(max(0, int(result_memory_bytes)) / (1024 * 1024), 2)
    if fingerprint_category:
        entry["fingerprint_category"] = _safe_label(fingerprint_category)
    if debug_enabled():
        _append_session_timing(entry)
    return entry


TRUST_COUNT_KEYS = {
    "players_validated",
    "players_passed",
    "players_degraded",
    "players_blocked",
    "trades_validated",
    "trades_passed",
    "trades_degraded",
    "trades_blocked",
    "validation_cache_hits",
    "validation_cache_misses",
    "confidence_caps_applied",
}
TRUST_REASON_KEYS = {
    "invalid_player_identity",
    "invalid_pick",
    "ownership_conflict",
    "duplicate_asset",
    "invalid_roster",
    "ambiguous_asset",
    "invalid_league_context",
    "protected_constraint",
    "validation_error",
}


def record_trust_diagnostics(summary: dict[str, Any]) -> dict[str, Any]:
    """Record only aggregate allowlisted Trust Engine diagnostics."""

    entry: dict[str, Any] = {"kind": "trust"}
    for key in TRUST_COUNT_KEYS:
        if key in summary:
            entry[key] = max(0, int(summary.get(key) or 0))
    reason_counts = summary.get("blocked_reason_counts")
    if isinstance(reason_counts, dict):
        entry["blocked_reason_counts"] = {
            key: max(0, int(value or 0))
            for key, value in reason_counts.items()
            if key in TRUST_REASON_KEYS
        }
    if debug_enabled():
        _append_session_timing(entry)
        print("DYNASTYGM_TRUST " + json.dumps(entry, sort_keys=True), flush=True)
    return entry


@contextmanager
def time_block(label: str, *, category: str = "app") -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        record_timing(label, (time.perf_counter() - start) * 1000, category=category)


def timed_call(label: str, func, *args, category: str = "app", **kwargs):
    with time_block(label, category=category):
        return func(*args, **kwargs)


def session_timings() -> list[dict[str, Any]]:
    state = _session_state()
    if state is None:
        return []
    try:
        return list(state.get("_perf_timings", []))
    except Exception:
        return []


def begin_rerun() -> dict[str, Any]:
    started = time.perf_counter()
    state = _session_state()
    if state is None:
        count = 1
        interaction = {}
    else:
        try:
            count = int(state.get("_perf_rerun_count", 0)) + 1
            state["_perf_rerun_count"] = count
            state["_perf_current_events"] = []
            interaction = state.pop("_perf_pending_interaction", {})
            observed = {
                "gm": bool(state.get("_mobile_destination_sheet_open")),
                "quick_view": bool(state.get("player_quick_view_player_id")),
                "live_filter": str(state.get("live_draft_rank_filter") or ""),
            }
            previous = state.get("_perf_observed_ui", {})
            if not interaction and isinstance(previous, dict):
                changed = [name for name, value in observed.items() if previous.get(name) != value]
                if changed:
                    interaction = {"name": f"{changed[0]}_change", "lightweight": True}
            state["_perf_observed_ui"] = observed
            session_correlation_id = str(
                state.get("_runtime_trace_session_correlation_id") or ""
            )
            if (
                len(session_correlation_id) != 16
                or not set(session_correlation_id) <= set("0123456789abcdef")
            ):
                session_correlation_id = secrets.token_hex(8)
                state["_runtime_trace_session_correlation_id"] = session_correlation_id
            state["_perf_active_rerun"] = {
                "cache_state": "cold" if count == 1 else "warm",
                "sequence": count,
                "interaction": interaction,
            }
        except Exception:
            count = 1
            interaction = {}
            session_correlation_id = ""
    if state is None:
        session_correlation_id = ""
    context = {
        "started": started,
        "cache_state": "cold" if count == 1 else "warm",
        "sequence": count,
        "interaction": interaction,
    }
    runtime_trace.begin_rerun(
        sequence=context["sequence"],
        cache_state=context["cache_state"],
        session_correlation_id=session_correlation_id,
    )
    return context


def finish_rerun(
    context: dict[str, Any],
    *,
    route: str = "unknown",
    label_prefix: str = "app_rerun_total_",
) -> dict[str, Any]:
    elapsed_ms = (time.perf_counter() - float(context.get("started") or time.perf_counter())) * 1000
    cache_state = "cold" if context.get("cache_state") == "cold" else "warm"
    entry = record_timing(
        f"{_safe_label(label_prefix)}{cache_state}_{_safe_label(route)}",
        elapsed_ms,
        category="render",
    )
    runtime_report = runtime_trace.finish_rerun(
        route=_safe_label(route),
        total_ms=elapsed_ms,
    )
    state = _session_state()
    if state is not None:
        try:
            active = dict(state.get("_perf_active_rerun", {}))
            active.update({"route": _safe_label(route), "total_ms": entry["elapsed_ms"]})
            state["_perf_last_rerun"] = active
            if runtime_report:
                state["_runtime_trace_last"] = runtime_report
                reports = dict(state.get("_runtime_trace_pages", {}))
                reports[_safe_label(route)] = runtime_report
                state["_runtime_trace_pages"] = reports
        except Exception:
            pass
    return entry


def _sanitized_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for raw in events[-MAX_SESSION_TIMINGS:]:
        if not isinstance(raw, dict):
            continue
        entry = {
            key: raw.get(key)
            for key in (
                "kind",
                "category",
                "label",
                "elapsed_ms",
                "memory_mb",
                "result_size",
                "status",
                "invalidation_reason",
            )
            if key in raw
        }
        for key in ("category", "label", "invalidation_reason"):
            if key in entry:
                entry[key] = _safe_label(entry[key]) if entry[key] else ""
        sanitized.append(entry)
    return sanitized


def performance_snapshot(*, route: str = "unknown") -> dict[str, Any]:
    state = _session_state()
    current = []
    last_rerun = {}
    if state is not None:
        try:
            current = list(state.get("_perf_current_events", []))
            last_rerun = dict(state.get("_perf_last_rerun", state.get("_perf_active_rerun", {})))
        except Exception:
            pass
    events = _sanitized_events(current)
    timings = [entry for entry in events if entry.get("kind") == "timing"]
    resolved_route = _safe_label(route)
    if resolved_route == "unknown":
        resolved_route = _safe_label(last_rerun.get("route"))

    external = [entry for entry in timings if entry.get("category") in {"sleeper", "supabase"}]
    cache_events = [entry for entry in events if entry.get("kind") == "cache"]
    cache_hits = sum(entry.get("status") == "hit" for entry in cache_events)
    cache_misses = sum(entry.get("status") == "miss" for entry in cache_events)
    cache_observed = cache_hits + cache_misses
    slowest = sorted(timings, key=lambda item: float(item.get("elapsed_ms") or 0), reverse=True)[:5]
    heavy = [entry["label"] for entry in timings if entry.get("label") in HEAVY_BUILDERS]
    interaction = last_rerun.get("interaction") if isinstance(last_rerun.get("interaction"), dict) else {}
    trade_stage_order = (
        "partner_selection",
        "candidate_target_generation",
        "outgoing_asset_filtering",
        "package_construction",
        "package_scoring",
        "confidence_scoring",
        "protected_player_checks",
        "duplicate_package_elimination",
        "final_sorting",
    )
    trade_event_stages = {
        "trade_pipe_partner": "partner_selection",
        "trade_pipe_targets": "candidate_target_generation",
        "trade_pipe_outgoing": "outgoing_asset_filtering",
        "trade_pipe_construct": "package_construction",
        "trade_pipe_score": "package_scoring",
        "trade_pipe_confidence": "confidence_scoring",
        "trade_pipe_protected": "protected_player_checks",
        "trade_pipe_dedupe": "duplicate_package_elimination",
        "trade_pipe_sort": "final_sorting",
    }
    trade_by_stage = {
        trade_event_stages[str(entry.get("label") or "")]: entry
        for entry in timings
        if str(entry.get("label") or "") in trade_event_stages
    }
    trade_total_ms = sum(float(entry.get("elapsed_ms") or 0) for entry in trade_by_stage.values())
    trade_flame = []
    for stage in trade_stage_order:
        entry = trade_by_stage.get(stage)
        if not entry:
            continue
        elapsed_ms = float(entry.get("elapsed_ms") or 0)
        share = (elapsed_ms / trade_total_ms * 100.0) if trade_total_ms else 0.0
        trade_flame.append({
            "stage": stage,
            "elapsed_ms": round(elapsed_ms, 1),
            "calls": int(entry.get("result_size") or 0),
            "share_pct": round(share, 1),
            "bar": "█" * max(1, min(20, int(round(share / 5.0)))) if elapsed_ms else "",
        })
    runtime_pages = {}
    if state is not None:
        try:
            runtime_pages = dict(state.get("_runtime_trace_pages", {}))
        except Exception:
            runtime_pages = {}
    return {
        "schema": "dynastygm-performance-v1",
        "process_uptime_ms": round((time.perf_counter() - PROCESS_STARTED_AT) * 1000, 1),
        "current_memory_mb": _current_memory_mb(),
        "peak_memory_mb": _memory_mb(),
        "rerun": {
            "classification": "cold" if last_rerun.get("cache_state") == "cold" else "warm",
            "total_ms": float(last_rerun.get("total_ms") or 0),
            "route": resolved_route,
            "interaction": _safe_label(interaction.get("name")) if interaction.get("name") else "",
            "lightweight": bool(interaction.get("lightweight")),
            "heavy_builders_ran": heavy,
            "unexpected_heavy_work": bool(interaction.get("lightweight") and heavy),
        },
        "external_api_total_ms": round(sum(float(entry.get("elapsed_ms") or 0) for entry in external), 1),
        "sleeper_call_count": sum(entry.get("category") == "sleeper" for entry in timings),
        "supabase_call_count": sum(entry.get("category") == "supabase" for entry in timings),
        "live_draft_poll_ms": round(sum(float(entry.get("elapsed_ms") or 0) for entry in timings if entry.get("label") == "live_draft_poll_picks"), 1),
        "slowest_five": slowest,
        "cache": {
            "observed": cache_observed,
            "hits": cache_hits,
            "misses": cache_misses,
            "hit_rate_pct": round(cache_hits / cache_observed * 100.0, 1) if cache_observed else None,
        },
        "cache_events": cache_events,
        "trade_generation_flame": trade_flame,
        "runtime_trace_pages": runtime_pages,
        "events": events,
    }


def snapshot_json(*, route: str = "unknown") -> str:
    return json.dumps(performance_snapshot(route=route), indent=2, sort_keys=True)


def redacted_diagnostics() -> dict[str, Any]:
    snapshot = performance_snapshot()
    timings = session_timings()
    snapshot.update({
        "debug_enabled": debug_enabled(),
        "timing_count": len(timings),
        "slow_events": [
            entry for entry in _sanitized_events(timings)
            if float(entry.get("elapsed_ms") or 0) >= SLOW_MS
        ],
    })
    return snapshot


def render_debug_panel(*, route: str = "unknown") -> None:
    if not debug_enabled():
        return
    try:
        import streamlit as st

        snapshot = performance_snapshot(route=route)
        with st.expander("Performance Report", expanded=False):
            cols = st.columns(4)
            cols[0].metric("Rerun", f"{snapshot['rerun']['total_ms']:.0f} ms")
            cols[1].metric("Cache", snapshot["rerun"]["classification"].title())
            cols[2].metric("Memory", f"{snapshot['current_memory_mb'] or 0:.1f} MB")
            cols[3].metric("API calls", snapshot["sleeper_call_count"] + snapshot["supabase_call_count"])
            st.caption("Debug-only sanitized diagnostics. No secrets, emails, raw IDs, cache keys, or API payloads are included.")
            st.json(snapshot)
            st.download_button(
                "Copy Performance Snapshot",
                data=json.dumps(snapshot, indent=2, sort_keys=True),
                file_name="dynastygm-performance-snapshot.json",
                mime="application/json",
                key="download_performance_snapshot",
            )
    except Exception:
        return
