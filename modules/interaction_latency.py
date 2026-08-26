"""Interaction latency helpers — first-useful paint and warm memos only.

Does not change football logic, valuations, rankings, recommendations, Trust,
entitlements, auth, or lifecycle semantics.

First useful PQV content (PR #127 hierarchy preserved)
-------------------------------------------------------
identity, position, OVR/position rank, scoring format, dynasty value,
recommendation/context, health, verified PPG when available.

Secondary (deferred behind explicit gates):
news, full career resume timeline, complete season stats, advanced details.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from copy import deepcopy
from typing import Any

import pandas as pd

from modules import runtime_trace


FIT_CONTEXT_KEY = "_prepared_player_fit_contexts"
FIT_HIT_COUNTER = "prepared_player_fit_hits"
FIT_MISS_COUNTER = "prepared_player_fit_misses"

INTERACTION_MILESTONES: frozenset[str] = frozenset(
    {
        "pqv_open_received",
        "pqv_first_useful",
        "pqv_secondary_ready",
        "trade_review_open_received",
        "trade_review_first_useful",
        "alerts_compose_only",
        "gm_menu_open",
        "league_switcher_open",
    }
)

LATENCY_CLASSES: tuple[str, ...] = (
    "browser_ui",
    "streamlit_rerun",
    "python_compute",
    "provider_network",
    "serialization",
)


def clear_interaction_memos(state: MutableMapping[str, Any]) -> None:
    """Drop warm interaction memos on account / league hygiene."""

    state.pop(FIT_CONTEXT_KEY, None)


def build_fit_context_signature(
    *,
    league_id: object,
    roster_id: object,
    score_field: object,
    league_settings_key: object,
    frame_signature: object = "",
) -> str:
    return "|".join(
        [
            str(league_id or ""),
            str(roster_id or ""),
            str(score_field or ""),
            str(league_settings_key or ""),
            str(frame_signature or ""),
        ]
    )


def _fit_context_without_roster_frame(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep fit ids/metrics/assessment; drop fat roster copies from the memo."""

    return {
        "roster_player_ids": set(payload.get("roster_player_ids") or ()),
        "roster_df": pd.DataFrame(),
        "metrics": dict(payload.get("metrics") or {}),
        "assessment": payload.get("assessment"),
    }


def get_or_build_fit_context(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse roster-fit context across warm PQV / dossier opens."""

    key = str(signature or "").strip()
    store = state.get(FIT_CONTEXT_KEY)
    if not isinstance(store, dict):
        store = {}
        state[FIT_CONTEXT_KEY] = store
    cached = store.get(key) if key else None
    if key and isinstance(cached, Mapping):
        runtime_trace.count(FIT_HIT_COUNTER)
        return deepcopy(_fit_context_without_roster_frame(cached)), True
    built = _fit_context_without_roster_frame(dict(builder() or {}))
    if key:
        # Keep a small LRU of recent league/roster signatures.
        store[key] = deepcopy(built)
        while len(store) > 4:
            store.pop(next(iter(store)))
    runtime_trace.count(FIT_MISS_COUNTER)
    return deepcopy(built), False


def mark_interaction_milestone(name: str) -> None:
    label = str(name or "").strip()
    if not label:
        return
    runtime_trace.count(f"interaction_stage_{label}")
    if label in INTERACTION_MILESTONES or label in runtime_trace.SAFE_MILESTONES:
        runtime_trace.mark(label)
