"""Sequential warm-route render attribution and presentation-model reuse.

Times exclusive post-context route work so ``phase_script_complete`` is not an
anonymous blob. Memoizes deterministic advisor/presentation models derived from
already-canonical football fingerprints — not provider payloads, league-context
keys, Game Plan package keys, or Trade Hub ranking inputs.

Does not change TTLs, freshness, or truth ownership.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import time
from typing import Any

import pandas as pd

from modules import runtime_trace


SESSION_BLOCKS_KEY = "_warm_route_render_blocks"
SESSION_ROUTE_KEY = "_warm_route_render_route"
HIT_COUNTER = "warm_route_presentation_hits"
MISS_COUNTER = "warm_route_presentation_misses"

_PROCESS_MODELS: dict[str, dict[str, Any]] = {}
_PROCESS_MODEL_USED_AT: dict[str, float] = {}
_MAX_MODELS = 16

WORK_KINDS = frozenset({"compute", "html", "emit", "ctx"})


def clear_presentation_models() -> None:
    """Drop derived presentation memos (league/account hygiene / live-input drop)."""

    _PROCESS_MODELS.clear()
    _PROCESS_MODEL_USED_AT.clear()


def presentation_signature(*parts: object) -> str:
    encoded = json.dumps(list(parts), sort_keys=False, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()[:32]


def _copy_model(payload: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in dict(payload or {}).items():
        if isinstance(value, pd.DataFrame):
            out[key] = value.copy(deep=False)
        elif isinstance(value, pd.Series):
            out[key] = value.copy()
        elif isinstance(value, Mapping):
            out[key] = deepcopy(dict(value))
        elif isinstance(value, list):
            out[key] = deepcopy(list(value))
        else:
            out[key] = value
    return out


def _evict_if_needed(*, protect_key: str = "") -> None:
    if len(_PROCESS_MODELS) < _MAX_MODELS:
        return
    candidates = [key for key in _PROCESS_MODELS if key != protect_key]
    if not candidates:
        return
    oldest = min(candidates, key=lambda key: _PROCESS_MODEL_USED_AT.get(key, 0.0))
    _PROCESS_MODELS.pop(oldest, None)
    _PROCESS_MODEL_USED_AT.pop(oldest, None)


def get_or_build_presentation_model(
    *,
    family: str,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse a derived presentation/advisor model for unchanged football+user truth."""

    key = f"{str(family or '').strip()}:{str(signature or '').strip()}"
    if signature and key in _PROCESS_MODELS:
        _PROCESS_MODEL_USED_AT[key] = time.time()
        runtime_trace.count(HIT_COUNTER)
        return _copy_model(_PROCESS_MODELS[key]), True
    built = _copy_model(builder() or {})
    if key.endswith(":") or not str(signature or "").strip():
        runtime_trace.count(MISS_COUNTER)
        return built, False
    _evict_if_needed(protect_key=key)
    _PROCESS_MODELS[key] = _copy_model(built)
    _PROCESS_MODEL_USED_AT[key] = time.time()
    runtime_trace.count(MISS_COUNTER)
    return _copy_model(built), False


def begin_route(
    session_state: MutableMapping[str, Any],
    route: str,
    *,
    reset: bool = True,
) -> None:
    session_state[SESSION_ROUTE_KEY] = str(route or "")[:48]
    if reset or not isinstance(session_state.get(SESSION_BLOCKS_KEY), list):
        session_state[SESSION_BLOCKS_KEY] = []


def recorded_blocks(session_state: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows = (session_state or {}).get(SESSION_BLOCKS_KEY)
    return list(rows) if isinstance(rows, list) else []


def _emit_block(
    session_state: MutableMapping[str, Any],
    *,
    name: str,
    owner: str,
    work_kind: str,
    duration_ms: float,
    cache_status: str,
) -> None:
    route = str(session_state.get(SESSION_ROUTE_KEY) or "")[:48]
    row = {
        "route": route,
        "block": str(name or "")[:64],
        "owner": str(owner or "")[:96],
        "work_kind": str(work_kind or "compute")[:24],
        "duration_ms": round(max(0.0, float(duration_ms)), 1),
        "cache_status": str(cache_status or "")[:24],
    }
    bag = session_state.get(SESSION_BLOCKS_KEY)
    if not isinstance(bag, list):
        bag = []
        session_state[SESSION_BLOCKS_KEY] = bag
    bag.append(row)
    try:
        from modules import tail_latency_diagnostics

        tail_latency_diagnostics.record_stage_duration(
            session_state,
            f"route_{name}"[:48],
            row["duration_ms"],
            cache_status=row["cache_status"],
            detail=row,
        )
    except Exception:
        pass
    try:
        from modules import hot_path_profile

        hot_path_profile.record(
            f"phase_{name}",
            row["duration_ms"],
            cache_status=row["cache_status"] or row["work_kind"],
            kind="phase",
            detail=f"{row['work_kind']}:{row['owner']}"[:96],
            mandatory_before_useful=False,
            session_state=session_state,
        )
        hot_path_profile.advance_phase_cursor(session_state=session_state)
    except Exception:
        pass


@contextmanager
def block(
    session_state: MutableMapping[str, Any],
    name: str,
    *,
    owner: str,
    work_kind: str = "compute",
) -> Iterator[dict[str, str]]:
    """Exclusive sequential route block. Does not nest overlapping CPU claims."""

    kind = str(work_kind or "compute")
    if kind not in WORK_KINDS:
        kind = "compute"
    meta: dict[str, str] = {"cache_status": ""}
    started = time.perf_counter()
    try:
        yield meta
    finally:
        _emit_block(
            session_state,
            name=name,
            owner=owner,
            work_kind=kind,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            cache_status=str(meta.get("cache_status") or ""),
        )


def finish_route(session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    rows = recorded_blocks(session_state)
    total = round(sum(float(row.get("duration_ms") or 0.0) for row in rows), 1)
    payload = {
        "kind": "warm_route_render_summary",
        "route": str(session_state.get(SESSION_ROUTE_KEY) or "")[:48],
        "block_count": len(rows),
        "accounted_ms": total,
        "blocks_over_100ms": [
            row for row in rows if float(row.get("duration_ms") or 0.0) >= 100.0
        ],
    }
    try:
        from modules import tail_latency_diagnostics

        if tail_latency_diagnostics.diagnostics_enabled():
            tail_latency_diagnostics._attach_correlation(session_state, payload)
            tail_latency_diagnostics._emit(payload)
    except Exception:
        pass
    return payload
