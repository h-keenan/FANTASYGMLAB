"""Process-scoped Game Plan dependency memos (#221).

Avoids re-paying Streamlit ``@st.cache_data`` DataFrame hashing for:

- lightweight shared league context (league-reusable)
- Dashboard trade headline inventory (roster/user-specific)

Keys are explicit football fingerprints — never raw DataFrame identity.
Session package memo (#219) remains the warm Dashboard remount owner.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
import threading
import time
from typing import Any

import pandas as pd

from modules import runtime_trace


PROCESS_LEAGUE_HIT = "game_plan_process_league_hits"
PROCESS_LEAGUE_MISS = "game_plan_process_league_misses"
PROCESS_TRADE_HIT = "game_plan_process_trade_hits"
PROCESS_TRADE_MISS = "game_plan_process_trade_misses"

# League-reusable lightweight Game Plan context (no account identity in key).
_PROCESS_LEAGUE_CONTEXT: dict[str, dict[str, Any]] = {}
# Roster/user-specific trade headline results (post enforce + tendencies).
_PROCESS_TRADE_HEADLINE: dict[str, list[dict[str, Any]]] = {}

_MAX_LEAGUE = 48
_MAX_TRADE = 64

# Per-signature single-flight — prevents cold stampede for the SAME key only.
# Non-reentrant Lock plus owner tracking: same-thread nested acquire must not hang.
_BUILD_LOCKS: dict[str, threading.Lock] = {}
_BUILD_LOCKS_GUARD = threading.Lock()
_BUILD_OWNERS: dict[str, int] = {}
# Hard ceiling so a cancelled/dead owner cannot brick waiters forever (#233).
SINGLEFLIGHT_WAIT_TIMEOUT_S = 45.0


def _lock_token(family: str, key: str) -> str:
    return f"{family}:{key}"


def _lock_for(family: str, key: str) -> threading.Lock:
    token = _lock_token(family, key)
    with _BUILD_LOCKS_GUARD:
        lock = _BUILD_LOCKS.get(token)
        if lock is None:
            lock = threading.Lock()
            _BUILD_LOCKS[token] = lock
        return lock


def clear_process_game_plan_caches() -> None:
    """Drop process memos (tests / worker recycle)."""

    _PROCESS_LEAGUE_CONTEXT.clear()
    _PROCESS_TRADE_HEADLINE.clear()
    with _BUILD_LOCKS_GUARD:
        _BUILD_OWNERS.clear()


def _emit_singleflight(
    session_state: MutableMapping[str, Any] | None,
    *,
    kind: str,
    family: str,
    signature: str,
    wait_ms: float = 0.0,
    builder_ms: float = 0.0,
    exception_type: str = "",
) -> None:
    if session_state is None:
        return
    try:
        from modules import startup_cold_path

        if not startup_cold_path.startup_diagnostics_enabled():
            return
        from modules import game_plan_startup_stall as stall

        payload = {
            "kind": kind,
            "family": _text(family)[:32],
            "signature_prefix": signature_prefix(signature),
            "wait_ms": round(max(0.0, float(wait_ms)), 1),
            "builder_ms": round(max(0.0, float(builder_ms)), 1),
        }
        if exception_type:
            payload["exception_type"] = _text(exception_type)[:64]
        stall._attach_correlation(session_state, payload)
        stall._emit(payload)
    except Exception:
        pass


def _single_flight_run(
    *,
    family: str,
    key: str,
    builder: Callable[[], Any],
    session_state: MutableMapping[str, Any] | None = None,
) -> Any:
    """Acquire signature lock (reentrant-safe), run builder, always release."""

    token = _lock_token(family, key) if key else ""
    lock = _lock_for(family, key) if key else None
    ident = threading.get_ident()
    reentrant = bool(token and _BUILD_OWNERS.get(token) == ident)
    acquired = False
    wait_ms = 0.0
    if lock is not None and not reentrant:
        _emit_singleflight(
            session_state,
            kind="singleflight_wait_start",
            family=family,
            signature=key,
        )
        wait_started = time.perf_counter()
        acquired = lock.acquire(timeout=SINGLEFLIGHT_WAIT_TIMEOUT_S)
        wait_ms = (time.perf_counter() - wait_started) * 1000.0
        _emit_singleflight(
            session_state,
            kind="singleflight_wait_complete",
            family=family,
            signature=key,
            wait_ms=wait_ms,
            exception_type="" if acquired else "TimeoutError",
        )
        if not acquired:
            raise TimeoutError(f"singleflight_wait_timeout:{family}")
        _BUILD_OWNERS[token] = ident
    builder_started = time.perf_counter()
    _emit_singleflight(
        session_state,
        kind="singleflight_builder_start",
        family=family,
        signature=key,
        wait_ms=wait_ms,
    )
    error_type = ""
    try:
        return builder()
    except Exception as exc:
        error_type = type(exc).__name__
        _emit_singleflight(
            session_state,
            kind="singleflight_builder_error",
            family=family,
            signature=key,
            wait_ms=wait_ms,
            builder_ms=(time.perf_counter() - builder_started) * 1000.0,
            exception_type=error_type,
        )
        raise
    finally:
        builder_ms = (time.perf_counter() - builder_started) * 1000.0
        if not error_type:
            _emit_singleflight(
                session_state,
                kind="singleflight_builder_complete",
                family=family,
                signature=key,
                wait_ms=wait_ms,
                builder_ms=builder_ms,
            )
        if lock is not None and acquired and not reentrant:
            _BUILD_OWNERS.pop(token, None)
            lock.release()


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _stable_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()[:32]


def build_league_process_signature(
    *,
    prepared_frame_signature: object = "",
    league_id: object = "",
    score_field: object = "",
    league_settings_key: object = "",
    startup_mode: bool = False,  # compat; ignored — not football truth (#222)
    flags: tuple[bool, bool, bool, bool] = (False, True, True, True),
) -> str:
    """League-reusable Game Plan context key (no account / roster identity)."""

    _ = startup_mode
    return _stable_digest(
        {
            "fingerprint_version": 2,
            "prepared_frame_signature": _text(prepared_frame_signature),
            "league_id": _text(league_id),
            "score_field": _text(score_field),
            "league_settings_key": _text(league_settings_key),
            "flags": tuple(bool(flag) for flag in flags),
        }
    )


def trade_fingerprint_components(
    *,
    prepared_frame_signature: object = "",
    league_id: object = "",
    roster_id: object = "",
    score_field: object = "",
    league_settings_key: object = "",
    team_strategy: object = "",
    role_items: Sequence[tuple[str, str]] | None = None,
    untouchables: Sequence[str] | None = None,
    pick_score_multiplier: object = "",
    roster_state_version: object = "",
    maturity_digest: object = "",
) -> dict[str, str]:
    roles = tuple(sorted((str(pid), str(role)) for pid, role in (role_items or ())))
    untouchable_key = tuple(sorted(str(name) for name in (untouchables or ())))
    return {
        "fingerprint_version": "2",
        "prepared_frame_signature": _stable_digest({"v": _text(prepared_frame_signature)})[:8],
        "league_id": _stable_digest({"v": _text(league_id)})[:8],
        "roster_id": _stable_digest({"v": _text(roster_id)})[:8],
        "score_field": _stable_digest({"v": _text(score_field)})[:8],
        "league_settings_key": _stable_digest({"v": _text(league_settings_key)})[:8],
        "team_strategy": _stable_digest({"v": _text(team_strategy)})[:8],
        "role_items": _stable_digest({"v": roles})[:8],
        "untouchables": _stable_digest({"v": untouchable_key})[:8],
        "pick_score_multiplier": _stable_digest({"v": str(pick_score_multiplier)})[:8],
        "roster_state_version": _stable_digest({"v": _text(roster_state_version)})[:8],
        "maturity_digest": _stable_digest({"v": _text(maturity_digest)})[:8],
    }


def build_trade_process_signature(
    *,
    prepared_frame_signature: object = "",
    league_id: object = "",
    roster_id: object = "",
    score_field: object = "",
    league_settings_key: object = "",
    team_strategy: object = "",
    role_items: Sequence[tuple[str, str]] | None = None,
    untouchables: Sequence[str] | None = None,
    pick_score_multiplier: object = "",
    roster_state_version: object = "",
    maturity_digest: object = "",
) -> str:
    """Roster-specific trade headline key (user prefs + league football truth)."""

    roles = tuple(sorted((str(pid), str(role)) for pid, role in (role_items or ())))
    untouchable_key = tuple(sorted(str(name) for name in (untouchables or ())))
    return _stable_digest(
        {
            "fingerprint_version": 2,
            "prepared_frame_signature": _text(prepared_frame_signature),
            "league_id": _text(league_id),
            "roster_id": _text(roster_id),
            "score_field": _text(score_field),
            "league_settings_key": _text(league_settings_key),
            "team_strategy": _text(team_strategy),
            "role_items": roles,
            "untouchables": untouchable_key,
            "pick_score_multiplier": str(pick_score_multiplier),
            "roster_state_version": _text(roster_state_version),
            "maturity_digest": _text(maturity_digest),
        }
    )


def maturity_context_digest(maturity_context: Mapping[str, Any] | None) -> str:
    """Stable digest of maturity fields that affect trade enrichment.

    Excludes ephemeral startup/presentation flags (``startup_complete``) that flip
    across post-usable remounts without changing football truth (#222).
    """

    raw = maturity_context if isinstance(maturity_context, Mapping) else {}
    # Keep only scalar / short keys — avoid embedding large frames.
    safe = {
        key: raw.get(key)
        for key in (
            "dashboard_phase",
            "season_phase",
            "league_maturity",
            "evidence_level",
        )
        if key in raw
    }
    return _stable_digest(safe) if safe else ""


def _copy_league_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in dict(payload or {}).items():
        if isinstance(value, pd.DataFrame):
            out[key] = value.copy(deep=False)
        elif isinstance(value, Mapping):
            out[key] = deepcopy(dict(value))
        elif isinstance(value, list):
            out[key] = deepcopy(list(value))
        else:
            out[key] = value
    return out


def get_or_build_league_context(
    *,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
    session_state: MutableMapping[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Process-reuse lightweight Game Plan league context across sessions."""

    key = _text(signature)
    started = time.perf_counter()
    if key and key in _PROCESS_LEAGUE_CONTEXT:
        runtime_trace.count(PROCESS_LEAGUE_HIT)
        if session_state is not None:
            try:
                from modules import tail_latency_diagnostics

                tail_latency_diagnostics.note_build(
                    session_state,
                    family="league_context",
                    signature=key,
                    cache_status="hit",
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                )
            except Exception:
                pass
        return _copy_league_context(_PROCESS_LEAGUE_CONTEXT[key]), True

    result_hit = {"value": False}

    def _build_and_store() -> dict[str, Any]:
        if key and key in _PROCESS_LEAGUE_CONTEXT:
            result_hit["value"] = True
            return _copy_league_context(_PROCESS_LEAGUE_CONTEXT[key])
        built = dict(builder() or {})
        if key:
            if len(_PROCESS_LEAGUE_CONTEXT) >= _MAX_LEAGUE:
                _PROCESS_LEAGUE_CONTEXT.clear()
            _PROCESS_LEAGUE_CONTEXT[key] = _copy_league_context(built)
        result_hit["value"] = False
        return _copy_league_context(built)

    try:
        built = _single_flight_run(
            family="league",
            key=key,
            builder=_build_and_store,
            session_state=session_state,
        )
    except TimeoutError:
        built = dict(builder() or {})
        result_hit["value"] = False

    hit = bool(result_hit["value"])
    runtime_trace.count(PROCESS_LEAGUE_HIT if hit else PROCESS_LEAGUE_MISS)
    if session_state is not None:
        try:
            from modules import tail_latency_diagnostics

            tail_latency_diagnostics.note_build(
                session_state,
                family="league_context",
                signature=key,
                cache_status="hit" if hit else "miss",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
        except Exception:
            pass
    return _copy_league_context(built if isinstance(built, Mapping) else {}), hit


def get_or_build_trade_headline(
    *,
    signature: str,
    builder: Callable[[], Sequence[Mapping[str, Any]]],
    session_state: MutableMapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Process-reuse Dashboard trade headline inventory across sessions."""

    key = _text(signature)
    started = time.perf_counter()
    if key and key in _PROCESS_TRADE_HEADLINE:
        runtime_trace.count(PROCESS_TRADE_HIT)
        if session_state is not None:
            try:
                from modules import tail_latency_diagnostics

                tail_latency_diagnostics.note_build(
                    session_state,
                    family="trade_inventory",
                    signature=key,
                    cache_status="hit",
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                )
            except Exception:
                pass
        return deepcopy(_PROCESS_TRADE_HEADLINE[key]), True

    result_hit = {"value": False}

    def _build_and_store() -> list[dict[str, Any]]:
        if key and key in _PROCESS_TRADE_HEADLINE:
            result_hit["value"] = True
            return deepcopy(_PROCESS_TRADE_HEADLINE[key])
        built = [dict(item) for item in (builder() or ()) if isinstance(item, Mapping)]
        if key:
            if len(_PROCESS_TRADE_HEADLINE) >= _MAX_TRADE:
                _PROCESS_TRADE_HEADLINE.clear()
            _PROCESS_TRADE_HEADLINE[key] = deepcopy(built)
        result_hit["value"] = False
        return deepcopy(built)

    try:
        built = _single_flight_run(
            family="trade",
            key=key,
            builder=_build_and_store,
            session_state=session_state,
        )
    except TimeoutError:
        built = [dict(item) for item in (builder() or ()) if isinstance(item, Mapping)]
        result_hit["value"] = False

    hit = bool(result_hit["value"])
    runtime_trace.count(PROCESS_TRADE_HIT if hit else PROCESS_TRADE_MISS)
    if session_state is not None:
        try:
            from modules import tail_latency_diagnostics

            tail_latency_diagnostics.note_build(
                session_state,
                family="trade_inventory",
                signature=key,
                cache_status="hit" if hit else "miss",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
        except Exception:
            pass
    return list(built) if isinstance(built, list) else [], hit


def signature_prefix(signature: str, *, length: int = 8) -> str:
    text = _text(signature)
    return text[: max(1, length)] if text else ""


def timed_builder_phases(
    phases: MutableMapping[str, float],
    phase: str,
    fn: Callable[[], Any],
) -> Any:
    """Accumulate phase elapsed_ms for cold-path diagnostics."""

    started = time.perf_counter()
    try:
        return fn()
    finally:
        phases[phase] = phases.get(phase, 0.0) + (time.perf_counter() - started) * 1000
