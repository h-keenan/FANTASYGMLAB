"""Run-scoped canonical UI owners — one logical control per script run.

Presentation ownership only. Does not change football, valuation, ranking,
eligibility, news, providers, auth, or share-card composition.

Call ``begin_script_run`` once at ``main()`` entry so leftover flags from a
prior rerun cannot suppress a legitimate remount.
"""

from __future__ import annotations

from typing import Any, MutableMapping

RUN_FLAGS_KEY = "_fgl_render_ownership_counts"

OWNER_TRADE_STRATEGY = "trade_strategy_selector"
OWNER_WHAT_IS_AUTO = "what_is_auto"
OWNER_TRADE_HUB_LOADING = "trade_hub_board_loading"
OWNER_DASHBOARD_HERO = "dashboard_game_plan_hero"
OWNER_BOOTSTRAP_LOADER = "app_bootstrap_loader"
OWNER_SECONDARY_SEARCH = "secondary_player_search"
OWNER_REFRESH = "dashboard_refresh"


def begin_script_run(state: MutableMapping[str, Any]) -> None:
    state[RUN_FLAGS_KEY] = {}


def counts(state: MutableMapping[str, Any] | None) -> dict[str, int]:
    bag = (state or {}).get(RUN_FLAGS_KEY)
    if not isinstance(bag, dict):
        return {}
    return {str(key): int(value or 0) for key, value in bag.items()}


def count(state: MutableMapping[str, Any] | None, owner: str) -> int:
    return int(counts(state).get(str(owner), 0))


def claim(state: MutableMapping[str, Any], owner: str) -> bool:
    """Record one render attempt. Return True only for the first claim this run."""

    key = str(owner or "").strip()
    if not key:
        raise ValueError("render ownership requires a non-empty owner id")
    bag = state.get(RUN_FLAGS_KEY)
    if not isinstance(bag, dict):
        bag = {}
        state[RUN_FLAGS_KEY] = bag
    next_count = int(bag.get(key) or 0) + 1
    bag[key] = next_count
    return next_count == 1
