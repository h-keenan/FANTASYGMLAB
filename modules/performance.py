from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

from modules import app_config


DEBUG_ENV_KEY = "DYNASTYGM_DEBUG_PERF"
SLOW_MS = 1000.0
MAX_SESSION_TIMINGS = 80
PROCESS_STARTED_AT = time.perf_counter()
SENSITIVE_TOKENS = (
    "token",
    "secret",
    "key",
    "email",
    "authorization",
    "cookie",
    "password",
    "supabase",
    "stripe",
)


def debug_enabled(*, environ: dict | None = None, secrets: Any = None) -> bool:
    value = app_config.config_value(DEBUG_ENV_KEY, environ=environ, secrets=secrets)
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _safe_label(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.strip().replace("\n", " ")[:96]
    lowered = text.casefold()
    if any(token in lowered for token in SENSITIVE_TOKENS):
        return "[redacted]"
    return text or "unknown"


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
    """Return current RSS on Linux without retaining a user or league identifier."""
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as handle:
            resident_pages = int(handle.read().split()[1])
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return round(resident_pages * page_size / (1024 * 1024), 1)
    except Exception:
        return None


def _append_session_timing(entry: dict[str, Any]) -> None:
    try:
        import streamlit as st

        timings = list(st.session_state.get("_perf_timings", []))
        timings.append(entry)
        st.session_state["_perf_timings"] = timings[-MAX_SESSION_TIMINGS:]
    except Exception:
        return


def record_timing(label: str, elapsed_ms: float, *, category: str = "app") -> dict[str, Any]:
    entry = {
        "category": _safe_label(category),
        "label": _safe_label(label),
        "elapsed_ms": round(float(elapsed_ms), 1),
        "memory_mb": _memory_mb(),
    }
    if debug_enabled():
        _append_session_timing(entry)
        try:
            print("DYNASTYGM_PERF " + json.dumps(entry, sort_keys=True), flush=True)
        except Exception:
            pass
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
    try:
        import streamlit as st

        return list(st.session_state.get("_perf_timings", []))
    except Exception:
        return []


def redacted_diagnostics() -> dict[str, Any]:
    timings = session_timings()
    return {
        "debug_enabled": debug_enabled(),
        "memory_mb": _memory_mb(),
        "current_memory_mb": _current_memory_mb(),
        "process_uptime_ms": round((time.perf_counter() - PROCESS_STARTED_AT) * 1000, 1),
        "timing_count": len(timings),
        "slow_events": [entry for entry in timings if float(entry.get("elapsed_ms") or 0) >= SLOW_MS],
        "recent_timings": timings[-20:],
    }


def begin_rerun() -> dict[str, Any]:
    """Classify a rerun without using account or league data."""
    started = time.perf_counter()
    try:
        import streamlit as st

        count = int(st.session_state.get("_perf_rerun_count", 0)) + 1
        st.session_state["_perf_rerun_count"] = count
    except Exception:
        count = 1
    return {"started": started, "cache_state": "cold" if count == 1 else "warm", "sequence": count}


def finish_rerun(\n    context: dict[str, Any],\n    *,\n    route: str = "unknown",\n    label_prefix: str = "app_rerun_total_",\n) -> dict[str, Any]:
    elapsed_ms = (time.perf_counter() - float(context.get("started") or time.perf_counter())) * 1000
    cache_state = "cold" if context.get("cache_state") == "cold" else "warm"
    return record_timing(
        f"{_safe_label(label_prefix)}{cache_state}_{_safe_label(route)}",
        elapsed_ms,
        category="render",
    )


def render_debug_panel() -> None:
    if not debug_enabled():
        return
    try:
        import streamlit as st

        diagnostics = redacted_diagnostics()
        with st.expander("Performance diagnostics", expanded=False):
            st.caption("Debug-only timings. No secrets, emails, tokens, or raw IDs are shown.")
            st.json(diagnostics)
    except Exception:
        return
