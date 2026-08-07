"""Session-scoped memo for the valued + canonical-ranked player frame.

Ownership
---------
Built once per distinct input signature on the common app path, then reused on
warm Streamlit reruns. Cleared on account logout and league-switch transient
cleanup. Not a mutable global: callers receive an isolated DataFrame copy.

Invalidation
------------
Signature covers public-player fingerprint, valuation lens, settings, scoring
rank context, archetype, and season. When any input changes the memo misses and
rebuilds. No TTL — freshness follows the same input contracts as a full rebuild.

Does not change valuation math, ranking math, or recommendation behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from typing import Any

import pandas as pd

from modules import runtime_trace


FRAME_KEY = "_prepared_valued_ranked_frame"
SIGNATURE_KEY = "_prepared_valued_ranked_signature"
HIT_COUNTER = "prepared_player_frame_hits"
MISS_COUNTER = "prepared_player_frame_misses"

SHELL_BUNDLE_KEY = "_prepared_shell_chrome_bundle"
SHELL_SIGNATURE_KEY = "_prepared_shell_chrome_signature"
SHELL_HIT_COUNTER = "prepared_shell_chrome_hits"
SHELL_MISS_COUNTER = "prepared_shell_chrome_misses"
SHELL_TTL_SECONDS = 300.0

SHARED_CONTEXT_KEY = "_prepared_shared_league_contexts"
SHARED_HIT_COUNTER = "prepared_shared_context_hits"
SHARED_MISS_COUNTER = "prepared_shared_context_misses"


def clear_prepared_player_frame(state: MutableMapping[str, Any]) -> None:
    """Drop the valued/ranked frame memo (account or league hygiene)."""

    state.pop(FRAME_KEY, None)
    state.pop(SIGNATURE_KEY, None)
    state.pop(SHELL_BUNDLE_KEY, None)
    state.pop(SHELL_SIGNATURE_KEY, None)
    state.pop(SHARED_CONTEXT_KEY, None)


def build_frame_signature(
    *,
    public_fingerprint: object,
    valuation_lens: object,
    score_field: object,
    league_settings_key: object,
    scoring_format: object,
    scoring_supported: object,
    archetype_id: object,
    season: object,
    row_count: int,
) -> str:
    """Stable key for the prepared valued+ranked frame."""

    return "|".join(
        [
            str(public_fingerprint or ""),
            str(valuation_lens or ""),
            str(score_field or ""),
            str(league_settings_key or ""),
            str(scoring_format or ""),
            str(bool(scoring_supported)),
            str(archetype_id or ""),
            str(season or ""),
            str(int(row_count or 0)),
        ]
    )


def get_or_build_valued_ranked_frame(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], pd.DataFrame],
) -> tuple[pd.DataFrame, bool]:
    """Return a mutation-isolated valued+ranked frame, reusing session memo on hit.

    Returns ``(frame, cache_hit)``.
    """

    key = str(signature or "").strip()
    cached = state.get(FRAME_KEY)
    if (
        key
        and state.get(SIGNATURE_KEY) == key
        and isinstance(cached, pd.DataFrame)
        and not cached.empty
    ):
        runtime_trace.count(HIT_COUNTER)
        return cached.copy(), True

    frame = builder()
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame()
    if key and not frame.empty:
        # Store one shared copy; getters always return an isolated view.
        state[SIGNATURE_KEY] = key
        state[FRAME_KEY] = frame
    else:
        state.pop(SIGNATURE_KEY, None)
        state.pop(FRAME_KEY, None)
    runtime_trace.count(MISS_COUNTER)
    return frame.copy() if not frame.empty else frame, False


def build_shell_signature(
    *,
    frame_signature: object,
    league_id: object,
    roster_id: object,
    score_field: object,
    league_settings_key: object,
    startup_mode: bool,
) -> str:
    """Key for chrome strategy / rank row reuse (matches 5-minute shell TTL)."""

    import time

    bucket = int(time.time() // SHELL_TTL_SECONDS)
    return "|".join(
        [
            str(frame_signature or ""),
            str(league_id or ""),
            str(roster_id or ""),
            str(score_field or ""),
            str(league_settings_key or ""),
            "1" if startup_mode else "0",
            str(bucket),
        ]
    )


def get_or_build_shell_chrome(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse shell chrome fields across warm reruns within the TTL bucket."""

    key = str(signature or "").strip()
    cached = state.get(SHELL_BUNDLE_KEY)
    if key and state.get(SHELL_SIGNATURE_KEY) == key and isinstance(cached, Mapping):
        runtime_trace.count(SHELL_HIT_COUNTER)
        return dict(cached), True

    bundle = dict(builder() or {})
    if key:
        state[SHELL_SIGNATURE_KEY] = key
        state[SHELL_BUNDLE_KEY] = dict(bundle)
    runtime_trace.count(SHELL_MISS_COUNTER)
    return bundle, False


def get_or_build_shared_league_context(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    flags: tuple[bool, bool, bool, bool],
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse route shared-league context across warm reruns within the TTL bucket."""

    store = state.get(SHARED_CONTEXT_KEY)
    if not isinstance(store, dict):
        store = {}
        state[SHARED_CONTEXT_KEY] = store
    memo_key = f"{signature}|{int(flags[0])}|{int(flags[1])}|{int(flags[2])}|{int(flags[3])}"
    cached = store.get(memo_key)
    if isinstance(cached, Mapping):
        runtime_trace.count(SHARED_HIT_COUNTER)
        return dict(cached), True
    bundle = dict(builder() or {})
    store[memo_key] = dict(bundle)
    runtime_trace.count(SHARED_MISS_COUNTER)
    return bundle, False
