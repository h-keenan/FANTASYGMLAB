"""Trade Hub first-useful-result orchestration — cache and timing only.

Does not change football logic, valuation, ranking, recommendation generation,
scoring, ordering, Trust thresholds, entitlement rules, or narrative meaning.

Recommendation #1 contract
--------------------------
Presentation order (`order_trade_hub_visible_ideas` / surface sort + Trust +
entitlement) determines #1. The complete approved candidate set must be known
before #1 is final. This module therefore caches the *complete* minimum board
required to establish #1; it does not invent provisional early-result semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import time
from typing import Any, Iterator

from modules import recommendation_lifecycle
from modules import runtime_trace


PRESENTATION_CACHE_KEY = "_trade_hub_presentation_board_cache"
STRATEGY_FRAME_CACHE_KEY = "_trade_hub_strategy_frame_cache"
HIT_COUNTER = "trade_hub_presentation_cache_hits"
MISS_COUNTER = "trade_hub_presentation_cache_misses"
STRATEGY_HIT_COUNTER = "trade_hub_strategy_frame_hits"
STRATEGY_MISS_COUNTER = "trade_hub_strategy_frame_misses"
STAGE_COUNTER_PREFIX = "trade_hub_stage_"

# Ordered critical-path stages for instrumentation / harness reporting.
CRITICAL_PATH_STAGES: tuple[str, ...] = (
    "nav_handoff_received",
    "canonical_context_resolution",
    "prepared_valued_ranked_frame",
    "roster_team_context",
    "strategy_lens_resolution",
    "provider_cache_reads",
    "candidate_construction",
    "recommendation_generation",
    "trust_approval_filtering",
    "presentation_ordering",
    "canonical_narrative_construction",
    "recommendation_1_ready",
    "recommendation_1_rendered",
    "remaining_visible_board_ready",
    "full_route_render_complete",
)

# Milestone names recorded when runtime tracing is enabled.
TRADE_HUB_MILESTONES: frozenset[str] = frozenset(
    {
        "trade_hub_nav_received",
        "trade_hub_context_ready",
        "trade_hub_strategy_ready",
        "trade_hub_rec1_ready",
        "trade_hub_rec1_rendered",
        "trade_hub_board_ready",
        "trade_hub_route_complete",
    }
)


def clear_trade_hub_computation_caches(state: MutableMapping[str, Any]) -> None:
    """Drop session Trade Hub computation memos (account / league hygiene)."""

    state.pop(PRESENTATION_CACHE_KEY, None)
    state.pop(STRATEGY_FRAME_CACHE_KEY, None)


def _stable_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()[:32]


def build_presentation_board_signature(
    *,
    lifecycle_digest: str = "",
    account_scope: str = "",
    league_id: str = "",
    roster_id: str = "",
    season: str = "",
    week: str = "",
    scoring_format: str = "",
    valuation_lens: str = "",
    roster_state_version: str = "",
    provider_data_version: str = "",
    frame_signature: str = "",
    strategy: str = "",
    archetype: str = "",
    score_field: str = "",
    pick_score_multiplier: float | int | str = 1.0,
    league_settings_key: str = "",
    untouchables: Sequence[str] = (),
    role_items: Sequence[tuple[str, str]] = (),
    entitlement: str = "",
    max_ideas: int = 8,
) -> str:
    """Provenance key for the post-Trust, entitlement-visible, ordered board.

    Fail closed: any dimension change must miss. Presentation-only UI state
    (visible_count, expanded cards, PQV open) is intentionally excluded.
    """

    fingerprint = recommendation_lifecycle.build_context_fingerprint(
        account_scope=account_scope,
        league_id=league_id,
        roster_id=roster_id,
        season=season,
        week=week,
        scoring_format=scoring_format,
        valuation_lens=valuation_lens,
        roster_state_version=roster_state_version,
        provider_data_version=provider_data_version,
    )
    digest = str(lifecycle_digest or "").strip() or fingerprint.digest
    payload = {
        "lifecycle_digest": digest,
        # Explicit dims fail closed even if a stale digest is passed.
        "account_scope": fingerprint.account_scope,
        "league_id": fingerprint.league_id,
        "roster_id": fingerprint.roster_id,
        "season": fingerprint.season,
        "week": fingerprint.week,
        "scoring_format": fingerprint.scoring_format,
        "valuation_lens": fingerprint.valuation_lens,
        "roster_state_version": fingerprint.roster_state_version,
        "provider_data_version": fingerprint.provider_data_version,
        "frame_signature": str(frame_signature or ""),
        "strategy": str(strategy or "").strip().casefold(),
        "archetype": str(archetype or "").strip().casefold(),
        "score_field": str(score_field or ""),
        "pick_score_multiplier": str(pick_score_multiplier),
        "league_settings_key": str(league_settings_key or ""),
        "untouchables": tuple(sorted(str(name) for name in untouchables or ())),
        "role_items": tuple(sorted((str(pid), str(role)) for pid, role in role_items or ())),
        "entitlement": str(entitlement or "").strip().casefold(),
        "max_ideas": int(max_ideas or 0),
    }
    return _stable_digest(payload)


def get_or_build_presentation_board(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse the presentation-ready board across warm Trade Hub navigations.

    Returns ``(board, cache_hit)``. Cached payloads are deep-copied so callers
    cannot mutate the memo. Stale signatures fail closed (miss + rebuild).
    """

    key = str(signature or "").strip()
    store = state.get(PRESENTATION_CACHE_KEY)
    if not isinstance(store, dict):
        store = {}
        state[PRESENTATION_CACHE_KEY] = store

    cached = store.get(key) if key else None
    if isinstance(cached, Mapping) and cached.get("signature") == key:
        runtime_trace.count(HIT_COUNTER)
        runtime_trace.count(f"{STAGE_COUNTER_PREFIX}presentation_cache_hit")
        return deepcopy(dict(cached)), True

    built = dict(builder() or {})
    built["signature"] = key
    if key:
        store.clear()  # one active board per session; league/strategy changes replace
        store[key] = deepcopy(built)
    runtime_trace.count(MISS_COUNTER)
    runtime_trace.count(f"{STAGE_COUNTER_PREFIX}presentation_cache_miss")
    return deepcopy(built), False


def build_strategy_frame_signature(
    *,
    frame_signature: str = "",
    strategy: str = "",
    score_field: str = "",
) -> str:
    return "|".join(
        [
            str(frame_signature or ""),
            str(strategy or "").strip().casefold(),
            str(score_field or ""),
        ]
    )


def get_or_build_strategy_frame(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], Any],
) -> tuple[Any, bool]:
    """Memoize strategy age-curve frames; return an isolated copy on hit."""

    key = str(signature or "").strip()
    store = state.get(STRATEGY_FRAME_CACHE_KEY)
    if not isinstance(store, dict):
        store = {}
        state[STRATEGY_FRAME_CACHE_KEY] = store

    cached = store.get(key) if key else None
    if key and cached is not None:
        runtime_trace.count(STRATEGY_HIT_COUNTER)
        try:
            return cached.copy(), True
        except Exception:
            return deepcopy(cached), True

    frame = builder()
    if key and frame is not None:
        try:
            store[key] = frame.copy() if hasattr(frame, "copy") else deepcopy(frame)
        except Exception:
            store[key] = frame
    runtime_trace.count(STRATEGY_MISS_COUNTER)
    try:
        return frame.copy(), False
    except Exception:
        return deepcopy(frame) if frame is not None else frame, False


def mark_trade_hub_milestone(name: str) -> None:
    """Record a Trade Hub milestone when tracing is active."""

    label = str(name or "").strip()
    if not label:
        return
    runtime_trace.count(f"{STAGE_COUNTER_PREFIX}{label}")
    # Prefer dedicated Trade Hub milestones; fall back to generic mark.
    if label in TRADE_HUB_MILESTONES or label in runtime_trace.SAFE_MILESTONES:
        runtime_trace.mark(label)


@contextmanager
def stage_timer(stage: str, *, category: str = "analysis") -> Iterator[None]:
    """Time one critical-path stage into runtime_trace + performance counters."""

    from modules import performance

    label = str(stage or "unknown").strip() or "unknown"
    started = time.perf_counter()
    with performance.time_block(f"trade_hub_{label}", category=category):
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            runtime_trace.count(f"{STAGE_COUNTER_PREFIX}{label}")
            # duration also lands via performance.time_block / runtime_trace functions
            _ = elapsed_ms


def idea_equivalence_fingerprint(ideas: Sequence[Mapping[str, Any]] | None) -> str:
    """Stable fingerprint for correctness equivalence (identity + decision fields)."""

    rows: list[dict[str, Any]] = []
    for idea in ideas or ():
        if not isinstance(idea, Mapping):
            continue
        rows.append(
            {
                "partner_roster_id": str(idea.get("partner_roster_id") or ""),
                "tag": str(idea.get("tag") or ""),
                "my_score": int(idea.get("my_score") or 0),
                "their_score": int(idea.get("their_score") or 0),
                "trade_gain": int(idea.get("trade_gain") or 0),
                "fit_score": int(idea.get("fit_score") or 0),
                "partner_fit_score": int(idea.get("partner_fit_score") or 0),
                "strategy_fit_score": int(idea.get("strategy_fit_score") or 0),
                "market_realism_score": int(idea.get("market_realism_score") or 0),
                "trade_confidence_label": str(idea.get("trade_confidence_label") or ""),
                "trade_headline_ready": bool(idea.get("trade_headline_ready")),
                "trade_surface_tier": str(idea.get("trade_surface_tier") or ""),
                "priority": int(idea.get("priority") or 0),
                "send": sorted(
                    (
                        str(asset.get("asset_type") or "player"),
                        str(asset.get("player_id") or ""),
                        str(asset.get("pick_id") or ""),
                        str(asset.get("name") or asset.get("label") or ""),
                    )
                    for asset in (idea.get("send_assets") or [])
                    if isinstance(asset, Mapping)
                ),
                "receive": sorted(
                    (
                        str(asset.get("asset_type") or "player"),
                        str(asset.get("player_id") or ""),
                        str(asset.get("pick_id") or ""),
                        str(asset.get("name") or asset.get("label") or ""),
                    )
                    for asset in (idea.get("receive_assets") or [])
                    if isinstance(asset, Mapping)
                ),
            }
        )
    return _stable_digest({"ideas": rows})


def recommendation_one_identity(ideas: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    """Return the presentation #1 identity fields for contract assertions."""

    if not ideas:
        return {}
    first = ideas[0]
    if not isinstance(first, Mapping):
        return {}
    return {
        "partner_roster_id": str(first.get("partner_roster_id") or ""),
        "tag": str(first.get("tag") or ""),
        "my_score": int(first.get("my_score") or 0),
        "their_score": int(first.get("their_score") or 0),
        "trade_gain": int(first.get("trade_gain") or 0),
        "trade_confidence_label": str(first.get("trade_confidence_label") or ""),
        "send_player_ids": [
            str(asset.get("player_id") or "")
            for asset in (first.get("send_assets") or [])
            if isinstance(asset, Mapping) and str(asset.get("player_id") or "")
        ],
        "receive_player_ids": [
            str(asset.get("player_id") or "")
            for asset in (first.get("receive_assets") or [])
            if isinstance(asset, Mapping) and str(asset.get("player_id") or "")
        ],
    }
