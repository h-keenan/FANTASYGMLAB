"""Structured hot-path profiling for Dashboard first-useful and trade-modal open.

Enabled with DYNASTYGM_HOT_PATH=1 (also follows DYNASTYGM_DASHBOARD_WATERFALL=1).
Records named wall-time spans, cache status, and whether the span is mandatory
before first useful paint. Does not change football truth.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import time
from typing import Any, Iterator, MutableMapping


ENV_KEY = "DYNASTYGM_HOT_PATH"
STATE_KEY = "_hot_path_spans"
ORIGIN_KEY = "_hot_path_origin"
PATH_KEY = "_hot_path_name"

_PROCESS: dict[str, Any] = {"spans": [], "origin": 0.0, "path": ""}


def enabled(*, environ: dict | None = None) -> bool:
    if float(_PROCESS.get("origin") or 0.0):
        return True
    env = environ if environ is not None else os.environ
    flag = str(env.get(ENV_KEY, "")).strip().casefold()
    if flag in {"1", "true", "yes", "on"}:
        return True
    dash = str(env.get("DYNASTYGM_DASHBOARD_WATERFALL", "")).strip().casefold()
    return dash in {"1", "true", "yes", "on"}


def begin(path: str, session_state: MutableMapping[str, Any] | None = None) -> None:
    origin = time.perf_counter()
    _PROCESS.update({"spans": [], "origin": origin, "path": str(path or ""), "last_phase_at": origin})
    if session_state is not None:
        session_state[STATE_KEY] = _PROCESS["spans"]
        session_state[ORIGIN_KEY] = origin
        session_state[PATH_KEY] = str(path or "")


def _spans(session_state: MutableMapping[str, Any] | None) -> list[dict[str, Any]]:
    if session_state is not None:
        rows = session_state.get(STATE_KEY)
        if isinstance(rows, list):
            return rows
        session_state[STATE_KEY] = []
        return session_state[STATE_KEY]
    rows = _PROCESS.get("spans")
    if not isinstance(rows, list):
        rows = []
        _PROCESS["spans"] = rows
    return rows


def record(
    name: str,
    elapsed_ms: float,
    *,
    cache_status: str = "",
    mandatory_before_useful: bool = True,
    kind: str = "cpu",
    detail: str = "",
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    if not enabled():
        return
    rows = _spans(session_state)
    rows.append(
        {
            "name": str(name or "span")[:64],
            "elapsed_ms": round(max(0.0, float(elapsed_ms)), 1),
            "cache_status": str(cache_status or "")[:48],
            "mandatory_before_useful": bool(mandatory_before_useful),
            "kind": str(kind or "cpu")[:24],
            "detail": str(detail or "")[:96],
        }
    )


def mark_phase(
    name: str,
    *,
    session_state: MutableMapping[str, Any] | None = None,
) -> float:
    """Record elapsed since the previous phase (and since script origin)."""

    if not enabled():
        return 0.0
    now = time.perf_counter()
    origin = float(_PROCESS.get("origin") or 0.0)
    if session_state is not None:
        origin = float(session_state.get(ORIGIN_KEY) or origin or now)
    last = float(_PROCESS.get("last_phase_at") or origin or now)
    elapsed = (now - last) * 1000.0
    since_origin = (now - origin) * 1000.0 if origin else elapsed
    _PROCESS["last_phase_at"] = now
    record(
        f"phase_{name}",
        elapsed,
        cache_status=f"t+{since_origin:.0f}",
        kind="phase",
        mandatory_before_useful=False,
        session_state=session_state,
    )
    return elapsed


def advance_phase_cursor(
    *,
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Move the exclusive phase cursor without emitting a span.

    Used when a sibling tracer already recorded the exclusive elapsed so
    ``phase_script_complete`` does not claim the same wall twice.
    """

    now = time.perf_counter()
    _PROCESS["last_phase_at"] = now
    if session_state is not None:
        origin = float(session_state.get(ORIGIN_KEY) or _PROCESS.get("origin") or now)
        session_state[ORIGIN_KEY] = origin



@contextmanager
def span(
    name: str,
    *,
    cache_status: str = "",
    mandatory_before_useful: bool = True,
    kind: str = "cpu",
    session_state: MutableMapping[str, Any] | None = None,
) -> Iterator[dict[str, str]]:
    meta = {"cache_status": cache_status}
    if not enabled():
        yield meta
        return
    started = time.perf_counter()
    try:
        yield meta
    finally:
        record(
            name,
            (time.perf_counter() - started) * 1000,
            cache_status=meta.get("cache_status") or "",
            mandatory_before_useful=mandatory_before_useful,
            kind=kind,
            session_state=session_state,
        )


def report(
    session_state: MutableMapping[str, Any] | None = None,
    *,
    top_n: int = 10,
) -> dict[str, Any]:
    rows = list(_spans(session_state))
    total = sum(float(row.get("elapsed_ms") or 0.0) for row in rows)
    origin = 0.0
    if session_state is not None:
        origin = float(session_state.get(ORIGIN_KEY) or 0.0)
    else:
        origin = float(_PROCESS.get("origin") or 0.0)
    wall = (time.perf_counter() - origin) * 1000 if origin else total
    phase_sum = sum(
        float(row.get("elapsed_ms") or 0.0)
        for row in rows
        if str(row.get("kind") or "") == "phase"
    )
    unaccounted = max(0.0, wall - phase_sum) if phase_sum else max(0.0, wall - total)
    ranked = sorted(rows, key=lambda row: float(row.get("elapsed_ms") or 0.0), reverse=True)
    top = []
    for row in ranked[: max(1, int(top_n))]:
        ms = float(row.get("elapsed_ms") or 0.0)
        pct = (ms / wall * 100.0) if wall else 0.0
        top.append({**row, "pct_of_wall": round(pct, 1)})
    payload = {
        "path": (
            str(session_state.get(PATH_KEY) or "")
            if session_state is not None
            else str(_PROCESS.get("path") or "")
        ),
        "wall_ms": round(wall, 1),
        "span_sum_ms": round(total, 1),
        "unaccounted_ms": round(unaccounted, 1),
        "phase_sum_ms": round(phase_sum, 1),
        "python_complete_ms": round(wall, 1),
        "span_count": len(rows),
        "top": top,
        "spans": rows,
    }
    try:
        print("HOT_PATH " + json.dumps(payload, sort_keys=True), flush=True)
    except Exception:
        pass
    return payload
