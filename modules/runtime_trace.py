from __future__ import annotations

import contextvars
import functools
import json
import os
import secrets
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator


TRACE_ENV_KEY = "DYNASTYGM_RUNTIME_TRACE"
TRACE_ENABLED = str(os.environ.get(TRACE_ENV_KEY, "")).strip().casefold() in {
    "1",
    "true",
    "yes",
    "on",
}
MAX_DATAFRAMES = 12
SAFE_MILESTONES = frozenset(
    {
        "authentication_complete",
        "auth_storage_bridge_complete",
        "entitlement_lookup_complete",
        "explicit_rerun_requested",
        "external_requests_complete",
        "league_data_complete",
        "league_restore_complete",
        "page_calculation_complete",
        "page_elements_built",
        "profile_lookup_complete",
        "public_player_load_complete",
        "public_player_load_deferred",
        "rerun_complete",
        "route_restore_complete",
        "session_initialization_complete",
        "startup_page_ready",
        "startup_shell_complete",
        "first_usable_paint",
        "startup_session_restored",
        "startup_auth_storage_requested",
        "startup_auth_storage_received",
        "startup_auth_storage_handshake",
        "startup_auth_payload_applied",
        "startup_auth_ready",
        "startup_profile_fetch_start",
        "startup_profile_fetch_complete",
        "startup_profile_loaded",
        "startup_entitlement_fetch_start",
        "startup_entitlement_fetch_complete",
        "startup_entitlements_loaded",
        "startup_league_restore_start",
        "startup_league_restore_complete",
        "startup_league_restored",
        "startup_players_ready",
        "startup_players_deferred",
        "startup_valuation_league_transform_ready",
        "startup_ranks_ready",
        "startup_prepared_frame_cache_lookup",
        "startup_prepared_frame_build_start",
        "startup_prepared_frame_build_complete",
        "startup_prepared_frame_ready",
        "startup_prepared_frame_cache_write",
        "startup_startup_draft_context_ready",
        "startup_shell_summary_start",
        "startup_shell_summary_complete",
        "startup_roster_profiles_ready",
        "startup_team_metrics_ready",
        "startup_shell_bundle_complete",
        "startup_shell_commit",
        "startup_shell_chrome_ready",
        "startup_workspace_chrome_ready",
        "startup_football_context_ready",
        "startup_dashboard_game_plan_entry",
        "startup_game_plan_fingerprint_start",
        "startup_game_plan_fingerprint_complete",
        "startup_game_plan_package_lookup_start",
        "startup_game_plan_package_lookup_complete",
        "startup_game_plan_prefs_ready",
        "startup_game_plan_league_context_ready",
        "startup_game_plan_trade_inventory_ready",
        "startup_game_plan_composed",
        "startup_game_plan_first_useful",
        "startup_dashboard_football_ready",
        "startup_dashboard_rendered",
        "startup_loading_dismissed",
        "startup_post_usable_auth_save_deferred",
        "startup_post_usable_auth_save_rerun",
        "thread_boundary",
        # Trade Hub first-useful-result critical path (PR #154)
        "trade_hub_nav_received",
        "trade_hub_context_ready",
        "trade_hub_strategy_ready",
        "trade_hub_rec1_ready",
        "trade_hub_rec1_rendered",
        "trade_hub_board_ready",
        "trade_hub_route_complete",
        # League-switch first-useful workspace (PR #156)
        "league_switch_received",
        "league_switch_cleanup_complete",
        "league_switch_shell_ready",
        "league_switch_first_useful",
        "league_switch_route_complete",
        # Interaction first-useful content (PR #157)
        "pqv_open_received",
        "pqv_first_useful",
        "pqv_secondary_ready",
        "pqv_trade_hub_click",
        "pqv_closed",
        "destination_committed",
        "full_app_rerun_requested",
        "trade_hub_route_ready",
        "trade_review_open_received",
        "trade_review_first_useful",
        "alerts_compose_only",
        "gm_menu_open",
        "league_switcher_open",
    }
)
TRACKED_DUPLICATES = {
    "assess_team_needs",
    "build_league_summary",
    "classify_roster_rooms",
    "get_team_vs_league",
    "injury_parsing",
    "news_parsing",
    "ownership_map_construction",
    "player_metadata_construction",
    "suggest_optimal_lineup",
    "trade_board_generation",
    "true_roster_needs",
}

_active_trace: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "dynastygm_runtime_trace",
    default=None,
)
_patch_lock = threading.Lock()
_pandas_patched = False
_streamlit_patched = False
_process_started = time.perf_counter()
_process_trace_count = 0


def _anonymous_correlation_id(value: str = "") -> str:
    candidate = str(value)
    if len(candidate) == 16 and set(candidate) <= set("0123456789abcdef"):
        return candidate
    return secrets.token_hex(8)


def enabled() -> bool:
    return TRACE_ENABLED


def _new_trace(
    sequence: int,
    cache_state: str,
    *,
    session_correlation_id: str = "",
    module_import_ms: float | None = None,
) -> dict[str, Any]:
    global _process_trace_count
    with _patch_lock:
        _process_trace_count += 1
        process_trace_sequence = _process_trace_count
    return {
        "schema": "dynastygm-runtime-trace-v3",
        "correlation_id": _anonymous_correlation_id(),
        "session_correlation_id": _anonymous_correlation_id(
            session_correlation_id
        ),
        "sequence": int(sequence),
        "cache_state": str(cache_state),
        "started": time.perf_counter(),
        "process_uptime_ms": round((time.perf_counter() - _process_started) * 1000, 1),
        "first_traced_rerun_after_process_start": process_trace_sequence == 1,
        "milestones": {"streamlit_session_run_started": 0.0},
        "process": {
            "application_import_ms": (
                round(max(0.0, float(module_import_ms)), 1)
                if module_import_ms is not None
                else None
            ),
            "render_process_ready_observable": False,
            "initial_http_request_observable": False,
        },
        "functions": {},
        "phases": {},
        "counters": {
            "dataframe_copies": 0,
            "dataframe_merges": 0,
            "streamlit_messages": 0,
            "streamlit_elements": 0,
            "streamlit_dataframes": 0,
            "streamlit_charts": 0,
            "streamlit_tables": 0,
        },
        "external": {"total": 0, "total_ms": 0.0, "by_source": {}},
        "dataframes": [],
        "streamlit": {
            "protobuf_bytes": 0,
            "largest_messages": [],
            "css_messages": [],
            "observation_overhead_ms": 0.0,
        },
    }


def begin_rerun(
    *,
    sequence: int = 1,
    cache_state: str = "cold",
    session_correlation_id: str = "",
    module_import_ms: float | None = None,
) -> None:
    if not TRACE_ENABLED:
        return
    _install_pandas_hooks()
    _install_streamlit_hooks()
    _active_trace.set(
        _new_trace(
            sequence,
            cache_state,
            session_correlation_id=session_correlation_id,
            module_import_ms=module_import_ms,
        )
    )


def mark(name: str) -> None:
    """Record a safe lifecycle boundary relative to the active rerun."""

    trace = _active_trace.get()
    if trace is None:
        return
    label = str(name)
    if label in SAFE_MILESTONES:
        trace["milestones"][label] = round(
            (time.perf_counter() - float(trace["started"])) * 1000,
            1,
        )


def record_application_import(elapsed_ms: float) -> None:
    """Attach one numeric process-import duration to the active safe trace."""

    trace = _active_trace.get()
    if trace is None:
        return
    trace["process"]["application_import_ms"] = round(
        max(0.0, float(elapsed_ms)), 1
    )


def _record_duration(name: str, phase: str, elapsed_ms: float) -> None:
    trace = _active_trace.get()
    if trace is None:
        return
    function = trace["functions"].setdefault(
        name,
        {"calls": 0, "total_ms": 0.0, "max_ms": 0.0},
    )
    function["calls"] += 1
    function["total_ms"] += elapsed_ms
    function["max_ms"] = max(function["max_ms"], elapsed_ms)
    phase_entry = trace["phases"].setdefault(
        phase,
        {"calls": 0, "total_ms": 0.0},
    )
    phase_entry["calls"] += 1
    phase_entry["total_ms"] += elapsed_ms


def count(name: str, amount: int = 1) -> None:
    trace = _active_trace.get()
    if trace is None:
        return
    trace["counters"][name] = int(trace["counters"].get(name, 0)) + int(amount)


def observe_dataframe(label: str, value: Any) -> None:
    trace = _active_trace.get()
    if trace is None or value is None:
        return
    try:
        rows, columns = value.shape
        if len(value.shape) != 2:
            return
        memory_bytes = int(value.memory_usage(index=True, deep=False).sum())
    except Exception:
        return
    candidate = {
        "label": str(label)[:96],
        "rows": int(rows),
        "columns": int(columns),
        "estimated_memory_bytes": max(0, memory_bytes),
    }
    frames = trace["dataframes"]
    frames.append(candidate)
    frames.sort(
        key=lambda item: (
            int(item.get("estimated_memory_bytes") or 0),
            int(item.get("rows") or 0),
        ),
        reverse=True,
    )
    del frames[MAX_DATAFRAMES:]


def _observe_values(label: str, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any) -> None:
    for index, value in enumerate(args):
        observe_dataframe(f"{label}.arg{index}", value)
    for key, value in kwargs.items():
        observe_dataframe(f"{label}.{key}", value)
    observe_dataframe(f"{label}.result", result)
    if isinstance(result, dict):
        for key, value in result.items():
            observe_dataframe(f"{label}.result.{key}", value)


def traced(name: str, *, phase: str, counter: str = "") -> Callable:
    def decorator(func: Callable) -> Callable:
        if not TRACE_ENABLED:
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if _active_trace.get() is None:
                return func(*args, **kwargs)
            started = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                _record_duration(name, phase, elapsed_ms)
                if counter:
                    count(counter)
            _observe_values(name, args, kwargs, result)
            return result

        return wrapper

    return decorator


@contextmanager
def block(name: str, *, phase: str) -> Iterator[None]:
    if not TRACE_ENABLED or _active_trace.get() is None:
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        _record_duration(name, phase, (time.perf_counter() - started) * 1000.0)


@contextmanager
def external_call(source: str, label: str) -> Iterator[None]:
    if not TRACE_ENABLED or _active_trace.get() is None:
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        trace = _active_trace.get()
        if trace is not None:
            external = trace["external"]
            external["total"] += 1
            external["total_ms"] += elapsed_ms
            source_entry = external["by_source"].setdefault(
                str(source),
                {"calls": 0, "total_ms": 0.0, "labels": {}},
            )
            source_entry["calls"] += 1
            source_entry["total_ms"] += elapsed_ms
            source_entry["labels"][str(label)] = (
                int(source_entry["labels"].get(str(label), 0)) + 1
            )
            trace["milestones"]["external_requests_complete"] = round(
                (time.perf_counter() - float(trace["started"])) * 1000,
                1,
            )


def _observe_streamlit_message(message: Any) -> None:
    trace = _active_trace.get()
    if trace is None:
        return
    started = time.perf_counter()
    try:
        message_type = str(message.WhichOneof("type") or "unknown")
        label = message_type
        if message_type == "delta":
            delta_type = str(message.delta.WhichOneof("type") or "delta")
            label = delta_type
            if delta_type == "new_element":
                label = str(message.delta.new_element.WhichOneof("type") or "element")
                count("streamlit_elements")
                if label in {"arrow_data_frame", "data_frame"}:
                    count("streamlit_dataframes")
                if label in {"table", "arrow_table"}:
                    count("streamlit_tables")
                if "chart" in label:
                    count("streamlit_charts")
        size = int(message.ByteSize())
        count("streamlit_messages")
        streamlit = trace["streamlit"]
        streamlit["protobuf_bytes"] += max(0, size)
        if label == "markdown":
            body = str(message.delta.new_element.markdown.body or "")
            if body.lstrip().casefold().startswith("<style"):
                import hashlib

                encoded = body.encode("utf-8")
                streamlit["css_messages"].append(
                    {
                        "ordinal": len(streamlit["css_messages"]) + 1,
                        "sha256": hashlib.sha256(encoded).hexdigest(),
                        "utf8_bytes": len(encoded),
                        "protobuf_bytes": max(0, size),
                    }
                )
        largest = streamlit["largest_messages"]
        largest.append({"type": label[:64], "protobuf_bytes": max(0, size)})
        largest.sort(key=lambda item: int(item["protobuf_bytes"]), reverse=True)
        del largest[12:]
    except Exception:
        return
    finally:
        trace = _active_trace.get()
        if trace is not None:
            trace["streamlit"]["observation_overhead_ms"] += (
                time.perf_counter() - started
            ) * 1000


def _emit_rerun_request() -> None:
    trace = _active_trace.get()
    if trace is None:
        return
    elapsed_ms = round(
        (time.perf_counter() - float(trace["started"])) * 1000,
        1,
    )
    trace["milestones"]["explicit_rerun_requested"] = elapsed_ms
    event = {
        "schema": "dynastygm-runtime-rerun-event-v1",
        "correlation_id": trace["correlation_id"],
        "sequence": trace["sequence"],
        "elapsed_ms": elapsed_ms,
    }
    try:
        print(
            "DYNASTYGM_RUNTIME_RERUN " + json.dumps(event, sort_keys=True),
            flush=True,
        )
    except Exception:
        pass


def _install_streamlit_hooks() -> None:
    global _streamlit_patched
    if _streamlit_patched:
        return
    with _patch_lock:
        if _streamlit_patched:
            return
        try:
            import streamlit as st
            from streamlit.runtime.scriptrunner_utils.script_run_context import (
                ScriptRunContext,
            )

            original_enqueue = ScriptRunContext.enqueue
            original_rerun = st.rerun

            @functools.wraps(original_enqueue)
            def traced_enqueue(context, message):
                result = original_enqueue(context, message)
                _observe_streamlit_message(message)
                return result

            ScriptRunContext.enqueue = traced_enqueue

            @functools.wraps(original_rerun)
            def traced_rerun(*args, **kwargs):
                _emit_rerun_request()
                return original_rerun(*args, **kwargs)

            st.rerun = traced_rerun
            _streamlit_patched = True
        except Exception:
            return


def _install_pandas_hooks() -> None:
    global _pandas_patched
    if _pandas_patched:
        return
    with _patch_lock:
        if _pandas_patched:
            return
        try:
            import feedparser
            import pandas as pd
            import requests
        except Exception:
            return
        try:
            original_copy = pd.DataFrame.copy
            original_merge = pd.DataFrame.merge
            original_pd_merge = pd.merge
            original_request = requests.sessions.Session.request
            original_feed_parse = feedparser.parse

            @functools.wraps(original_copy)
            def traced_copy(frame, *args, **kwargs):
                result = original_copy(frame, *args, **kwargs)
                if _active_trace.get() is not None:
                    count("dataframe_copies")
                    observe_dataframe("DataFrame.copy", result)
                return result

            @functools.wraps(original_merge)
            def traced_frame_merge(frame, *args, **kwargs):
                result = original_merge(frame, *args, **kwargs)
                if _active_trace.get() is not None:
                    count("dataframe_merges")
                    observe_dataframe("DataFrame.merge", result)
                return result

            @functools.wraps(original_pd_merge)
            def traced_pd_merge(*args, **kwargs):
                result = original_pd_merge(*args, **kwargs)
                if _active_trace.get() is not None:
                    count("dataframe_merges")
                    observe_dataframe("pandas.merge", result)
                return result

            @functools.wraps(original_request)
            def traced_request(session, method, url, *args, **kwargs):
                url_text = str(url or "").casefold()
                if "api.sleeper.app" in url_text:
                    source = "sleeper"
                elif "/auth/v1/" in url_text or "/rest/v1/" in url_text:
                    source = "supabase"
                elif "fantasycalc.com" in url_text:
                    source = "fantasycalc"
                elif "sleepercdn.com" in url_text:
                    source = "image"
                else:
                    source = "http"
                with external_call(source, f"http_{str(method).casefold()}"):
                    return original_request(session, method, url, *args, **kwargs)

            @functools.wraps(original_feed_parse)
            def traced_feed_parse(url, *args, **kwargs):
                url_text = str(url or "").casefold()
                if not url_text.startswith(("http://", "https://")):
                    return original_feed_parse(url, *args, **kwargs)
                label = (
                    "google_player_news"
                    if "news.google.com" in url_text
                    else "global_news_feed"
                )
                with external_call("rss", label):
                    return original_feed_parse(url, *args, **kwargs)

            pd.DataFrame.copy = traced_copy
            pd.DataFrame.merge = traced_frame_merge
            pd.merge = traced_pd_merge
            requests.sessions.Session.request = traced_request
            feedparser.parse = traced_feed_parse
            _pandas_patched = True
        except Exception:
            return


def finish_rerun(*, route: str, total_ms: float | None = None) -> dict[str, Any]:
    trace = _active_trace.get()
    if trace is None:
        return {}
    resolved_total = (
        float(total_ms)
        if total_ms is not None
        else (time.perf_counter() - float(trace["started"])) * 1000.0
    )
    mark("page_elements_built")
    mark("rerun_complete")
    trace["route"] = str(route)
    trace["total_page_ms"] = round(resolved_total, 1)
    for collection in ("functions", "phases"):
        for entry in trace[collection].values():
            for key in ("total_ms", "max_ms"):
                if key in entry:
                    entry[key] = round(float(entry[key]), 1)
    external = trace["external"]
    external["total_ms"] = round(float(external["total_ms"]), 1)
    for entry in external["by_source"].values():
        entry["total_ms"] = round(float(entry["total_ms"]), 1)
    trace["duplicate_computations"] = {
        name: int(entry.get("calls") or 0)
        for name, entry in trace["functions"].items()
        if name in TRACKED_DUPLICATES and int(entry.get("calls") or 0) > 1
    }
    external["api_calls"] = int(external["total"])
    external["sleeper_calls"] = int(
        (external["by_source"].get("sleeper") or {}).get("calls") or 0
    )
    external["rss_news_calls"] = int(
        (external["by_source"].get("rss") or {}).get("calls") or 0
    )
    trace["timing_semantics"] = "inclusive"
    trace["dataframe_memory_semantics"] = "shallow_estimate"
    trace["streamlit"]["protobuf_semantics"] = (
        "uncompressed ForwardMsg protobuf bytes observed at server enqueue"
    )
    trace["streamlit"]["observation_overhead_ms"] = round(
        float(trace["streamlit"]["observation_overhead_ms"]),
        1,
    )
    report = {key: value for key, value in trace.items() if key != "started"}
    _active_trace.set(None)
    try:
        print("DYNASTYGM_RUNTIME " + json.dumps(report, sort_keys=True), flush=True)
    except Exception:
        pass
    return report
