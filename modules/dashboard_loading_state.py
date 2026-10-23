"""Dashboard loading-state session keys (cleared on sign-out by auth_supabase)."""

from __future__ import annotations
from collections.abc import MutableMapping
from typing import Any

PHASE_KEY = "_dashboard_loading_phase"
LAST_USEFUL_LEAGUE_KEY = "_dashboard_last_useful_league_id"
LAST_USEFUL_FP_KEY = "_dashboard_last_useful_content_fp"
HYDRATE_TOKEN_KEY = "_dashboard_hydrate_token"
PLACEHOLDER_RENDERED_KEY = "_dashboard_hydrate_placeholder_rendered"


def clear_on_logout(state: MutableMapping[str, Any]) -> None:
    for key in (
        PHASE_KEY,
        LAST_USEFUL_LEAGUE_KEY,
        LAST_USEFUL_FP_KEY,
        HYDRATE_TOKEN_KEY,
        PLACEHOLDER_RENDERED_KEY,
    ):
        state.pop(key, None)
