"""League-switch first-useful-workspace orchestration — hygiene timing only.

Does not change football logic, valuations, rankings, recommendations, Trust,
entitlements, auth, lifecycle material-change meaning, or workflow continuity
semantics.

First useful workspace
----------------------
After League A → League B the user must see:
- FantasyGM Lab shell
- correct League B identity / account
- correct scoring/strategy context once resolved
- navigation
- no stale League A player / recommendation / trade / notification content

Deep Trade Hub generation, Daily GM Briefing, League Intelligence, news, and
secondary analytics hydrate after first useful when the active route needs them.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from contextlib import contextmanager
import time
from typing import Any, Iterator

from modules import runtime_trace


SWITCH_GUARD_KEY = "_league_switch_first_useful_guard"
SWITCH_HIT_COUNTER = "league_switch_transitions"
FRAME_RETAINED_COUNTER = "league_switch_prepared_frame_retained"
FRAME_CLEARED_COUNTER = "league_switch_prepared_frame_cleared"

CRITICAL_PATH_STAGES: tuple[str, ...] = (
    "selector_interaction_received",
    "selected_league_persisted",
    "transient_state_cleanup",
    "active_league_context_invalidated",
    "canonical_league_identity_resolved",
    "roster_identity_resolved",
    "league_settings_context_loaded",
    "provider_cache_reads",
    "player_roster_maps_prepared",
    "valuation_context_ready",
    "canonical_ranks_ready",
    "shell_shows_league_b",
    "first_useful_workspace_visible",
    "dashboard_primary_ready",
    "daily_gm_briefing_ready",
    "notifications_snapshot_ready",
    "secondary_intelligence_ready",
    "full_route_hydration_complete",
)

LEAGUE_SWITCH_MILESTONES: frozenset[str] = frozenset(
    {
        "league_switch_received",
        "league_switch_cleanup_complete",
        "league_switch_shell_ready",
        "league_switch_first_useful",
        "league_switch_route_complete",
    }
)

# Artifact ownership for documentation / harness classification.
ARTIFACT_SCOPE: dict[str, str] = {
    "public_player_metadata": "global/static",
    "player_portraits": "global/static",
    "prepared_valued_ranked_frame": "scoring+lens+archetype (not league_id)",
    "shell_chrome_bundle": "league+roster+scoring",
    "shared_league_context": "league+roster+scoring+flags",
    "trade_hub_presentation_board": "league+roster+strategy+entitlement",
    "trade_hub_strategy_frame": "strategy+frame_signature",
    "activity_inbox_snapshot": "league",
    "decision_change_history": "league+account",
    "canonical_recommendation_narrative": "league-bound overlay",
    "role_map": "roster/league derived",
    "trade_analyzer_package": "session (must clear on switch)",
    "pqv_overlay": "session (must clear on switch)",
    "trade_detail": "session (must clear on switch)",
}


def mark_league_switch_milestone(name: str) -> None:
    label = str(name or "").strip()
    if not label:
        return
    runtime_trace.count(f"league_switch_stage_{label}")
    if label in LEAGUE_SWITCH_MILESTONES or label in runtime_trace.SAFE_MILESTONES:
        runtime_trace.mark(label)


@contextmanager
def stage_timer(stage: str, *, category: str = "navigation") -> Iterator[None]:
    from modules import performance

    label = str(stage or "unknown").strip() or "unknown"
    with performance.time_block(f"league_switch_{label}", category=category):
        yield
    runtime_trace.count(f"league_switch_stage_{label}")


def begin_switch_guard(
    state: MutableMapping[str, Any],
    *,
    previous_league_id: str,
    next_league_id: str,
    next_league_name: str = "",
    preserved_route: str = "",
) -> None:
    """Record a switch transition for stale-flash / timing harnesses."""

    runtime_trace.count(SWITCH_HIT_COUNTER)
    state[SWITCH_GUARD_KEY] = {
        "previous_league_id": str(previous_league_id or "").strip(),
        "next_league_id": str(next_league_id or "").strip(),
        "next_league_name": str(next_league_name or "").strip(),
        "preserved_route": str(preserved_route or "").strip(),
        "started_at": time.perf_counter(),
        "cleanup_complete": False,
        "stale_keys_cleared": [],
    }
    mark_league_switch_milestone("league_switch_received")


def note_cleanup_keys(
    state: MutableMapping[str, Any],
    keys: Sequence[str],
) -> None:
    guard = state.get(SWITCH_GUARD_KEY)
    if not isinstance(guard, dict):
        return
    cleared = list(guard.get("stale_keys_cleared") or [])
    cleared.extend(str(key) for key in keys if str(key))
    guard["stale_keys_cleared"] = cleared


def mark_cleanup_complete(state: MutableMapping[str, Any]) -> None:
    guard = state.get(SWITCH_GUARD_KEY)
    if isinstance(guard, dict):
        guard["cleanup_complete"] = True
        started = float(guard.get("started_at") or time.perf_counter())
        guard["cleanup_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    mark_league_switch_milestone("league_switch_cleanup_complete")


def consume_switch_guard(state: MutableMapping[str, Any]) -> dict[str, Any] | None:
    raw = state.pop(SWITCH_GUARD_KEY, None)
    return dict(raw) if isinstance(raw, Mapping) else None


def assert_no_stale_league_payload(
    *,
    active_league_id: str,
    payload_league_id: str = "",
    surface: str = "",
) -> None:
    """Fail closed helper for tests — payloads must match the active league."""

    active = str(active_league_id or "").strip()
    payload = str(payload_league_id or "").strip()
    if active and payload and active != payload:
        raise AssertionError(
            f"stale league payload on {surface or 'surface'}: "
            f"active={active!r} payload={payload!r}"
        )


def retained_frame_after_switch(
    state: Mapping[str, Any],
    *,
    expected_signature: str = "",
) -> bool:
    """True when the valued+ranked frame memo survived league-scoped cleanup."""

    from modules import prepared_player_frame

    if prepared_player_frame.FRAME_KEY not in state:
        return False
    if expected_signature and state.get(prepared_player_frame.SIGNATURE_KEY) != expected_signature:
        return False
    return True
