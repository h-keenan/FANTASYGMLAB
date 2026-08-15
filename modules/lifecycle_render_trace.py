"""Monotonic T0–T7 lifecycle markers for Dashboard / Trade Hub ownership.

Timing only. Does not alter recommendation semantics or trigger reruns.
"""

from __future__ import annotations

import time
from typing import Any, MutableMapping

from modules import runtime_trace

PHASES = (
    "T0_main_entry",
    "T1_auth_session_complete",
    "T2_route_resolved",
    "T3_league_context_available",
    "T4_useful_page_shell",
    "T5_page_expensive_begin",
    "T6_page_expensive_end",
    "T7_page_tree_complete",
)

ORIGIN_KEY = "_fgl_lifecycle_origin"
MARKS_KEY = "_fgl_lifecycle_marks"


def begin(state: MutableMapping[str, Any]) -> float:
    origin = time.perf_counter()
    state[ORIGIN_KEY] = origin
    state[MARKS_KEY] = {}
    mark(state, "T0_main_entry")
    return origin


def mark(state: MutableMapping[str, Any], phase: str) -> float:
    origin = float(state.get(ORIGIN_KEY) or time.perf_counter())
    elapsed_ms = max(0.0, round((time.perf_counter() - origin) * 1000.0, 1))
    bag = state.get(MARKS_KEY)
    if not isinstance(bag, dict):
        bag = {}
        state[MARKS_KEY] = bag
    if phase not in bag:
        bag[phase] = elapsed_ms
        runtime_trace.mark(f"lifecycle_{phase}")
        runtime_trace.count(f"lifecycle_{phase}")
    return elapsed_ms


def snapshot(state: MutableMapping[str, Any] | None) -> dict[str, float]:
    bag = (state or {}).get(MARKS_KEY)
    if not isinstance(bag, dict):
        return {}
    return {str(key): float(value) for key, value in bag.items()}
