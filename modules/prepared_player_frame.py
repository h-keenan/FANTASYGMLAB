"""Session-scoped memo for the valued + canonical-ranked player frame.

Ownership
---------
Built once per distinct input signature on the common app path, then reused on
warm Streamlit reruns. Account logout clears everything. League switch clears
*league-scoped* shell/shared/Trade Hub memos but retains the valued+ranked frame
when its signature (scoring/lens/archetype/settings) is still valid — the frame
does not embed ``league_id``.

Invalidation
------------
Signature covers public-player fingerprint, valuation lens, settings, scoring
rank context, archetype, and season. When any input changes the memo misses and
rebuilds. No TTL — freshness follows the same input contracts as a full rebuild.

Does not change valuation math, ranking math, or recommendation behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
import threading
from typing import Any

import pandas as pd

from modules import runtime_trace


FRAME_KEY = "_prepared_valued_ranked_frame"
SIGNATURE_KEY = "_prepared_valued_ranked_signature"
HIT_COUNTER = "prepared_player_frame_hits"
MISS_COUNTER = "prepared_player_frame_misses"
PROCESS_HIT_COUNTER = "prepared_player_frame_process_hits"
# Process-scoped reuse for identical public+settings signatures across Streamlit
# sessions in the same worker. No account/roster identity is embedded.
_PROCESS_FRAME_STORE: dict[str, pd.DataFrame] = {}
_PROCESS_MISS_REASON_KEY = "_prepared_frame_last_miss_reason"
_PROCESS_BUILD_LOCKS: dict[str, threading.Lock] = {}
_PROCESS_BUILD_LOCKS_GUARD = threading.Lock()


def _process_lock_for(key: str) -> threading.Lock:
    with _PROCESS_BUILD_LOCKS_GUARD:
        lock = _PROCESS_BUILD_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PROCESS_BUILD_LOCKS[key] = lock
        return lock

SHELL_BUNDLE_KEY = "_prepared_shell_chrome_bundle"
SHELL_SIGNATURE_KEY = "_prepared_shell_chrome_signature"
SHELL_BUNDLES_KEY = "_prepared_shell_chrome_bundles"
SHELL_HIT_COUNTER = "prepared_shell_chrome_hits"
SHELL_MISS_COUNTER = "prepared_shell_chrome_misses"
SHELL_TTL_SECONDS = 300.0

SHARED_CONTEXT_KEY = "_prepared_shared_league_contexts"
SHARED_HIT_COUNTER = "prepared_shared_context_hits"
SHARED_MISS_COUNTER = "prepared_shared_context_misses"


def clear_valued_ranked_frame(state: MutableMapping[str, Any]) -> None:
    """Drop only the valued+ranked frame memo."""

    state.pop(FRAME_KEY, None)
    state.pop(SIGNATURE_KEY, None)


def clear_shell_chrome(state: MutableMapping[str, Any]) -> None:
    """Drop shell strategy / rank chrome memo (league-scoped)."""

    state.pop(SHELL_BUNDLE_KEY, None)
    state.pop(SHELL_SIGNATURE_KEY, None)
    state.pop(SHELL_BUNDLES_KEY, None)


def prune_shared_league_contexts(
    state: MutableMapping[str, Any],
    *,
    league_id: str = "",
) -> int:
    """Remove shared-context memos for one league, or all when league_id empty.

    Returns the number of entries removed.
    """

    store = state.get(SHARED_CONTEXT_KEY)
    if not isinstance(store, dict):
        state.pop(SHARED_CONTEXT_KEY, None)
        return 0
    league_key = str(league_id or "").strip()
    if not league_key:
        removed = len(store)
        state.pop(SHARED_CONTEXT_KEY, None)
        return removed
    # Shell signatures embed league_id as a pipe-delimited segment.
    needle = f"|{league_key}|"
    doomed = [key for key in list(store.keys()) if needle in str(key)]
    for key in doomed:
        store.pop(key, None)
    if not store:
        state.pop(SHARED_CONTEXT_KEY, None)
    return len(doomed)


def clear_league_scoped_prepared_memos(
    state: MutableMapping[str, Any],
    *,
    previous_league_id: str = "",
) -> None:
    """League-switch hygiene: clear league-scoped memos, keep valued+ranked frame.

    The valued+ranked frame signature has no league_id. Retaining it across
    switches with identical scoring/lens/settings avoids redundant rebuilds.
    Scoring/lens changes still miss via signature on the next common path.

    Always clears:
    - shell chrome (single current-league store)
    - Trade Hub presentation/strategy computation caches
    - Game Plan package memo
    - Game Plan truth canon (#239)

    Retains:
    - valued+ranked frame (signature-gated)
    - shared league contexts for *other* leagues (keyed by league_id) so
      rapid A→B→A can reuse prior League A shared context without retaining
      Trade Hub football boards
    """

    _ = previous_league_id  # reserved for future targeted prune / diagnostics
    clear_shell_chrome(state)
    try:
        from modules import trade_hub_first_useful

        trade_hub_first_useful.clear_trade_hub_computation_caches(state)
    except Exception:
        state.pop("_trade_hub_presentation_board_cache", None)
        state.pop("_trade_hub_strategy_frame_cache", None)
    try:
        from modules import game_plan_package

        game_plan_package.clear_game_plan_package(state)
    except Exception:
        state.pop("_game_plan_package_bundle", None)
        state.pop("_game_plan_package_signature", None)
    try:
        from modules import game_plan_truth_canon

        game_plan_truth_canon.clear_canon(state)
    except Exception:
        state.pop("_game_plan_truth_canon", None)
    try:
        from modules import interaction_latency

        interaction_latency.clear_interaction_memos(state)
    except Exception:
        state.pop("_prepared_player_fit_contexts", None)
    runtime_trace.count("league_switch_prepared_frame_retained")


def clear_prepared_player_frame(state: MutableMapping[str, Any]) -> None:
    """Drop all prepared memos (account logout / full hygiene)."""

    clear_valued_ranked_frame(state)
    clear_shell_chrome(state)
    state.pop(SHARED_CONTEXT_KEY, None)
    try:
        from modules import game_plan_package

        game_plan_package.clear_game_plan_package(state)
        game_plan_package.clear_process_game_plan_packages()
    except Exception:
        state.pop("_game_plan_package_bundle", None)
        state.pop("_game_plan_package_signature", None)
    try:
        from modules import trade_hub_first_useful

        trade_hub_first_useful.clear_trade_hub_computation_caches(state)
    except Exception:
        state.pop("_trade_hub_presentation_board_cache", None)
        state.pop("_trade_hub_strategy_frame_cache", None)
    try:
        from modules import interaction_latency

        interaction_latency.clear_interaction_memos(state)
    except Exception:
        state.pop("_prepared_player_fit_contexts", None)


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


def process_valued_frame_for_inputs(
    *,
    public_fingerprint: object,
    valuation_lens: object,
    score_field: object,
    league_settings_key: object,
    scoring_format: object,
    scoring_supported: object,
    archetype_id: object,
    season: object,
) -> tuple[pd.DataFrame | None, str]:
    """Reuse a process-scoped valued frame when only row_count is still unknown.

    Public fingerprint + settings already identify the player universe. Matching
    without row_count lets a cold Streamlit session skip disk hydrate on a warm
    worker. No account or roster identity is stored.
    """

    prefix = "|".join(
        [
            str(public_fingerprint or ""),
            str(valuation_lens or ""),
            str(score_field or ""),
            str(league_settings_key or ""),
            str(scoring_format or ""),
            str(bool(scoring_supported)),
            str(archetype_id or ""),
            str(season or ""),
            "",
        ]
    )
    for key, frame in _PROCESS_FRAME_STORE.items():
        if str(key).startswith(prefix) and isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame, str(key)
    return None, ""


def clear_process_valued_ranked_frames() -> None:
    """Drop process-scoped valued+ranked frames (tests / process recycle)."""

    _PROCESS_FRAME_STORE.clear()


def session_valued_ranked_frame(
    state: MutableMapping[str, Any],
) -> tuple[pd.DataFrame | None, str]:
    """Return the session memo when a non-empty valued+ranked frame is present."""

    cached = state.get(FRAME_KEY)
    signature = str(state.get(SIGNATURE_KEY) or "").strip()
    if isinstance(cached, pd.DataFrame) and not cached.empty and signature:
        return cached, signature
    return None, ""


def explain_frame_cache_state(
    state: MutableMapping[str, Any],
    *,
    signature: str,
) -> dict[str, Any]:
    """Diagnostic snapshot for prepared-frame cache lookup."""

    key = str(signature or "").strip()
    cached = state.get(FRAME_KEY)
    session_sig = str(state.get(SIGNATURE_KEY) or "")
    session_hit = bool(
        key
        and session_sig == key
        and isinstance(cached, pd.DataFrame)
        and not cached.empty
    )
    process_hit = bool(key and key in _PROCESS_FRAME_STORE and not _PROCESS_FRAME_STORE[key].empty)
    miss_reason = ""
    if not session_hit:
        if not key:
            miss_reason = "empty_signature"
        elif not session_sig:
            miss_reason = "session_cold"
        elif session_sig != key:
            miss_reason = "signature_mismatch"
        elif not isinstance(cached, pd.DataFrame) or cached.empty:
            miss_reason = "session_empty_frame"
        else:
            miss_reason = "unknown"
    return {
        "signature": key,
        "session_hit": session_hit,
        "process_hit": process_hit,
        "miss_reason": miss_reason,
        "process_entries": len(_PROCESS_FRAME_STORE),
    }


def get_or_build_valued_ranked_frame(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], pd.DataFrame],
) -> tuple[pd.DataFrame, bool]:
    """Return a mutation-isolated valued+ranked frame, reusing session/process memo.

    Returns ``(frame, cache_hit)``. ``cache_hit`` is True for session or process hits
    (builder not invoked).
    """

    import time

    key = str(signature or "").strip()
    started = time.perf_counter()
    cached = state.get(FRAME_KEY)
    if (
        key
        and state.get(SIGNATURE_KEY) == key
        and isinstance(cached, pd.DataFrame)
        and not cached.empty
    ):
        state[_PROCESS_MISS_REASON_KEY] = ""
        runtime_trace.count(HIT_COUNTER)
        try:
            from modules import tail_latency_diagnostics

            tail_latency_diagnostics.note_build(
                state,
                family="prepared_frame",
                signature=key,
                cache_status="hit",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
        except Exception:
            pass
        return cached.copy(), True

    if key:
        process_cached = _PROCESS_FRAME_STORE.get(key)
        if isinstance(process_cached, pd.DataFrame) and not process_cached.empty:
            state[SIGNATURE_KEY] = key
            state[FRAME_KEY] = process_cached
            state[_PROCESS_MISS_REASON_KEY] = ""
            runtime_trace.count(PROCESS_HIT_COUNTER)
            runtime_trace.count(HIT_COUNTER)
            try:
                from modules import tail_latency_diagnostics

                tail_latency_diagnostics.note_build(
                    state,
                    family="prepared_frame",
                    signature=key,
                    cache_status="hit",
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                )
            except Exception:
                pass
            return process_cached.copy(), True

    diagnosis = explain_frame_cache_state(state, signature=key)
    state[_PROCESS_MISS_REASON_KEY] = str(diagnosis.get("miss_reason") or "miss")

    lock = _process_lock_for(key) if key else None
    if lock is not None:
        lock.acquire()
    try:
        if key:
            process_cached = _PROCESS_FRAME_STORE.get(key)
            if isinstance(process_cached, pd.DataFrame) and not process_cached.empty:
                state[SIGNATURE_KEY] = key
                state[FRAME_KEY] = process_cached
                state[_PROCESS_MISS_REASON_KEY] = ""
                runtime_trace.count(PROCESS_HIT_COUNTER)
                runtime_trace.count(HIT_COUNTER)
                try:
                    from modules import tail_latency_diagnostics

                    tail_latency_diagnostics.note_build(
                        state,
                        family="prepared_frame",
                        signature=key,
                        cache_status="hit",
                        duration_ms=(time.perf_counter() - started) * 1000.0,
                    )
                except Exception:
                    pass
                return process_cached.copy(), True

        frame = builder()
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame()
        if key and not frame.empty:
            # Store one shared copy; getters always return an isolated view.
            state[SIGNATURE_KEY] = key
            state[FRAME_KEY] = frame
            _PROCESS_FRAME_STORE[key] = frame
        else:
            state.pop(SIGNATURE_KEY, None)
            state.pop(FRAME_KEY, None)
        runtime_trace.count(MISS_COUNTER)
        try:
            from modules import tail_latency_diagnostics

            tail_latency_diagnostics.note_build(
                state,
                family="prepared_frame",
                signature=key,
                cache_status="miss",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
        except Exception:
            pass
        return frame.copy() if not frame.empty else frame, False
    finally:
        if lock is not None:
            lock.release()


def build_shell_signature(
    *,
    frame_signature: object,
    league_id: object,
    roster_id: object,
    score_field: object,
    league_settings_key: object,
    startup_mode: bool,
) -> str:
    """Key for chrome strategy / rank row reuse.

    Soft TTL is enforced on read (``stored_at``), not via a time bucket in the
    signature — presentation clocks must not invalidate football-adjacent chrome.
    """

    return "|".join(
        [
            str(frame_signature or ""),
            str(league_id or ""),
            str(roster_id or ""),
            str(score_field or ""),
            str(league_settings_key or ""),
            "1" if startup_mode else "0",
        ]
    )


def get_or_build_shell_chrome(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse shell chrome fields across warm reruns with soft TTL expiry.

    #239: identity and valued shells use different signatures. Store bundles in a
    per-signature map so valued enrichment cannot clobber the identity memo and
    force a rebuild that reads drifted session strategy.
    """

    import time

    key = str(signature or "").strip()
    store = state.get(SHELL_BUNDLES_KEY)
    if not isinstance(store, dict):
        store = {}
        state[SHELL_BUNDLES_KEY] = store
        # Migrate legacy single-slot memo when present.
        legacy = state.get(SHELL_BUNDLE_KEY)
        legacy_sig = str(state.get(SHELL_SIGNATURE_KEY) or "").strip()
        if legacy_sig and isinstance(legacy, Mapping):
            store[legacy_sig] = dict(legacy)

    if key and isinstance(store.get(key), Mapping):
        cached_raw = dict(store[key])
        stored_at = float(cached_raw.pop("_shell_stored_at", 0.0) or 0.0)
        age = (time.time() - stored_at) if stored_at else 0.0
        if stored_at and age > SHELL_TTL_SECONDS:
            store.pop(key, None)
        else:
            runtime_trace.count(SHELL_HIT_COUNTER)
            state[SHELL_SIGNATURE_KEY] = key
            state[SHELL_BUNDLE_KEY] = dict(cached_raw)
            return cached_raw, True

    bundle = dict(builder() or {})
    if key:
        stored = dict(bundle)
        stored["_shell_stored_at"] = float(time.time())
        store[key] = stored
        state[SHELL_BUNDLES_KEY] = store
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
