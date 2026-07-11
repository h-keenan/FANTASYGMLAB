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
        "timing_count": len(timings),
        "slow_events": [entry for entry in timings if float(entry.get("elapsed_ms") or 0) >= SLOW_MS],
        "recent_timings": timings[-20:],
    }


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
