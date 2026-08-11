"""P0 Dashboard renderer bisect helpers (#245).

Native Streamlit markers + timed boundary logging. Not a product UI layer.
"""

from __future__ import annotations

import os
import time
import traceback
from contextlib import contextmanager
from typing import Iterator

import streamlit as st

from modules import performance

MINIMAL_ENV = "FGL_P0_DASHBOARD_MINIMAL"
ENABLE_THROUGH_ENV = "FGL_P0_DASHBOARD_ENABLE_THROUGH"
BISECT_ENV = "FGL_P0_DASHBOARD_BISECT"

# Default ON for this diagnostic build so production always emits D0–D9.
# Set FGL_P0_DASHBOARD_BISECT=0 to silence markers (logging still available).
BLOCK_ORDER = (
    "intro",
    "game_plan",
    "what_changed",
    "summary",
    "deep_analysis",
    "remaining",
    "all",
)


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "1" if default else "")).strip().casefold()
    if raw == "":
        return default
    return raw not in {"0", "false", "no", "off"}


def minimal_dashboard_enabled() -> bool:
    return _env_flag(MINIMAL_ENV, default=False)


def bisect_markers_enabled() -> bool:
    return _env_flag(BISECT_ENV, default=True)


def enable_through() -> str:
    raw = str(os.environ.get(ENABLE_THROUGH_ENV, "all")).strip().casefold()
    if raw not in BLOCK_ORDER:
        return "all"
    return raw


def block_allowed(block: str) -> bool:
    """Return True if this named block should run under ENABLE_THROUGH gating."""

    gate = enable_through()
    if gate == "all":
        return True
    if block not in BLOCK_ORDER:
        return True
    return BLOCK_ORDER.index(block) <= BLOCK_ORDER.index(gate)


def emit_marker(label: str) -> None:
    """Ugly native Streamlit text — never HTML, never components."""

    if not bisect_markers_enabled():
        return
    text = str(label)
    st.write(text)
    _log("marker", text, elapsed_ms=0.0, status="emitted")


def _log(
    kind: str,
    boundary: str,
    *,
    elapsed_ms: float,
    status: str,
    error: str = "",
) -> None:
    payload = {
        "kind": "dashboard_bisect",
        "boundary": performance._safe_label(boundary)[:64],
        "status": performance._safe_label(status)[:32],
        "elapsed_ms": round(float(elapsed_ms), 1),
        "event": performance._safe_label(kind)[:32],
    }
    if error:
        payload["error"] = str(error)[:160]
    try:
        import json

        print("DYNASTYGM_STARTUP " + json.dumps(payload, sort_keys=True), flush=True)
    except Exception:
        pass
    try:
        from modules import startup_coordinator

        startup_coordinator.log_startup_milestone(
            st.session_state,
            f"bisect_{status}_{boundary}",
            once=False,
            detail={
                "elapsed_ms": round(float(elapsed_ms), 1),
                "error": str(error)[:80] if error else "",
            },
        )
    except Exception:
        pass


@contextmanager
def boundary(name: str) -> Iterator[None]:
    """Time a Dashboard block; log start/complete/exception. Never swallow."""

    label = str(name)
    started = time.perf_counter()
    _log("boundary", label, elapsed_ms=0.0, status="start")
    try:
        yield
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _log(
            "boundary",
            label,
            elapsed_ms=elapsed_ms,
            status="exception",
            error=f"{type(exc).__name__}: {exc}",
        )
        try:
            st.error(f"FGL_P0_BISECT_EXCEPTION {label}: {type(exc).__name__}: {exc}")
            st.text(traceback.format_exc()[-1500:])
        except Exception:
            pass
        raise
    else:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _log("boundary", label, elapsed_ms=elapsed_ms, status="complete")


def render_minimal_dashboard_body() -> None:
    """Auth/header/orb preserved by caller; body is native Streamlit only.

    Caller must already have emitted C/D/D0 canaries.
    """

    st.title("Dashboard")
    st.success("FGL DASHBOARD MINIMAL RENDER OK")
    st.button("FGL_P0_MINIMAL_DASHBOARD_BUTTON")
    emit_marker("FGL_P0_D9_BEFORE_RETURN")
