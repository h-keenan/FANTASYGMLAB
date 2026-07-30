from __future__ import annotations

import contextvars
import functools
import json
import os
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


def enabled() -> bool:
    return TRACE_ENABLED


def _new_trace(sequence: int, cache_state: str) -> dict[str, Any]:
    return {
        "schema": "dynastygm-runtime-trace-v1",
        "sequence": int(sequence),
        "cache_state": str(cache_state),
        "started": time.perf_counter(),
        "functions": {},
        "phases": {},
        "counters": {"dataframe_copies": 0, "dataframe_merges": 0},
        "external": {"total": 0, "total_ms": 0.0, "by_source": {}},
        "dataframes": [],
    }


def begin_rerun(*, sequence: int = 1, cache_state: str = "cold") -> None:
    if not TRACE_ENABLED:
        return
    _install_pandas_hooks()
    _active_trace.set(_new_trace(sequence, cache_state))


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


def _install_pandas_hooks() -> None:
    global _pandas_patched
    if _pandas_patched:
        return
    with _patch_lock:
        if _pandas_patched:
            return
        try:
            import pandas as pd

            original_copy = pd.DataFrame.copy
            original_merge = pd.DataFrame.merge
            original_pd_merge = pd.merge

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

            pd.DataFrame.copy = traced_copy
            pd.DataFrame.merge = traced_frame_merge
            pd.merge = traced_pd_merge

            import requests

            original_request = requests.sessions.Session.request

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

            requests.sessions.Session.request = traced_request

            import feedparser

            original_feed_parse = feedparser.parse

            @functools.wraps(original_feed_parse)
            def traced_feed_parse(url, *args, **kwargs):
                label = (
                    "google_player_news"
                    if "news.google.com" in str(url or "").casefold()
                    else "global_news_feed"
                )
                with external_call("rss", label):
                    return original_feed_parse(url, *args, **kwargs)

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
    trace["duplicate_computations"].update(
        {
            name: int(calls)
            for name, calls in trace["counters"].items()
            if name in TRACKED_DUPLICATES and int(calls or 0) > 1
        }
    )
    external["api_calls"] = int(external["total"])
    external["sleeper_calls"] = int(
        (external["by_source"].get("sleeper") or {}).get("calls") or 0
    )
    external["rss_news_calls"] = int(
        (external["by_source"].get("rss") or {}).get("calls") or 0
    )
    trace["timing_semantics"] = "inclusive"
    trace["dataframe_memory_semantics"] = "shallow_estimate"
    report = {key: value for key, value in trace.items() if key != "started"}
    print("DYNASTYGM_RUNTIME " + json.dumps(report, sort_keys=True), flush=True)
    _active_trace.set(None)
    return report
