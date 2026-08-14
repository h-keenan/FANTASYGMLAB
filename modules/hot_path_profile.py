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
    _PROCESS.update({"spans": [], "origin": origin, "path": str(path or "")})
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
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    if not enabled():
        return
    rows = _spans(session_state)
    rows.append(
        {
            "name": str(name or "span")[:64],
            "elapsed_ms": round(max(0.0, float(elapsed_ms)), 1),
            "cache_status": str(cache_status or "")[:24],
            "mandatory_before_useful": bool(mandatory_before_useful),
            "kind": str(kind or "cpu")[:24],
        }
    )


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
        "span_count": len(rows),
        "top": top,
        "spans": rows,
    }
    try:
        print("HOT_PATH " + json.dumps(payload, sort_keys=True), flush=True)
    except Exception:
        pass
    return payload
