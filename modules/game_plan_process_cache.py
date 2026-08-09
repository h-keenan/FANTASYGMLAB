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


def clear_process_game_plan_caches() -> None:
    """Drop process memos (tests / worker recycle)."""

    _PROCESS_LEAGUE_CONTEXT.clear()
    _PROCESS_TRADE_HEADLINE.clear()


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
    startup_mode: bool = False,
    flags: tuple[bool, bool, bool, bool] = (False, True, True, True),
) -> str:
    """League-reusable Game Plan context key (no account / roster identity)."""

    return _stable_digest(
        {
            "prepared_frame_signature": _text(prepared_frame_signature),
            "league_id": _text(league_id),
            "score_field": _text(score_field),
            "league_settings_key": _text(league_settings_key),
            "startup_mode": bool(startup_mode),
            "flags": tuple(bool(flag) for flag in flags),
        }
    )


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
    """Stable digest of maturity fields that affect trade enrichment."""

    raw = maturity_context if isinstance(maturity_context, Mapping) else {}
    # Keep only scalar / short keys — avoid embedding large frames.
    safe = {
        key: raw.get(key)
        for key in (
            "dashboard_phase",
            "season_phase",
            "league_maturity",
            "startup_complete",
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
) -> tuple[dict[str, Any], bool]:
    """Process-reuse lightweight Game Plan league context across sessions."""

    key = _text(signature)
    if key and key in _PROCESS_LEAGUE_CONTEXT:
        runtime_trace.count(PROCESS_LEAGUE_HIT)
        return _copy_league_context(_PROCESS_LEAGUE_CONTEXT[key]), True
    built = dict(builder() or {})
    if key:
        if len(_PROCESS_LEAGUE_CONTEXT) >= _MAX_LEAGUE:
            _PROCESS_LEAGUE_CONTEXT.clear()
        _PROCESS_LEAGUE_CONTEXT[key] = _copy_league_context(built)
    runtime_trace.count(PROCESS_LEAGUE_MISS)
    return _copy_league_context(built), False


def get_or_build_trade_headline(
    *,
    signature: str,
    builder: Callable[[], Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], bool]:
    """Process-reuse Dashboard trade headline inventory across sessions."""

    key = _text(signature)
    if key and key in _PROCESS_TRADE_HEADLINE:
        runtime_trace.count(PROCESS_TRADE_HIT)
        return deepcopy(_PROCESS_TRADE_HEADLINE[key]), True
    built = [dict(item) for item in (builder() or ()) if isinstance(item, Mapping)]
    if key:
        if len(_PROCESS_TRADE_HEADLINE) >= _MAX_TRADE:
            _PROCESS_TRADE_HEADLINE.clear()
        _PROCESS_TRADE_HEADLINE[key] = deepcopy(built)
    runtime_trace.count(PROCESS_TRADE_MISS)
    return deepcopy(built), False


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
