"""Dashboard loading-state ownership — clear-then-hydrate (no stale-fade mix).

Policy (option B)
-----------------
When football context changes, clear context-sensitive Dashboard body and show a
stable placeholder. Do **not** keep prior Game Plan / recommendations faded as if
current (Streamlit's default stale opacity during long post-dismiss work).

First useful Dashboard contract
-------------------------------
Minimum content that counts as usable:
- shell / header with correct league identity
- navigation
- Today's Game Plan core (top items)

Not required for first useful:
- What Changed / Decision Memory detail
- Deep Analysis nav targets' bodies
- League Insights / Team Snapshot (already-computed; not a load gate)
- League Pulse expander
- secondary news enrichment
- full recommendation expansion
- draft discovery / non-visible routes

Phases: ``idle`` → ``hydrating`` → ``useful``.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any
import time

import streamlit as st

from modules import runtime_trace


PHASE_KEY = "_dashboard_loading_phase"
LAST_USEFUL_LEAGUE_KEY = "_dashboard_last_useful_league_id"
LAST_USEFUL_FP_KEY = "_dashboard_last_useful_content_fp"
HYDRATE_TOKEN_KEY = "_dashboard_hydrate_token"
PLACEHOLDER_RENDERED_KEY = "_dashboard_hydrate_placeholder_rendered"

# Same-run Streamlit slot so the hydrate card can be cleared before Game Plan
# widgets mount. Do not persist across processes.
_placeholder_slot: Any = None

PHASE_IDLE = "idle"
PHASE_HYDRATING = "hydrating"
PHASE_USEFUL = "useful"

# Explicit product budget (architecture-realistic; not faked).
BUDGET_WARM_FIRST_USEFUL_MS = 1000
BUDGET_WARM_STABLE_MS = 1500
BUDGET_COLD_FIRST_USEFUL_MS = 2500
BUDGET_COLD_STABLE_MS = 4000
BUDGET_SWITCH_CACHED_FIRST_USEFUL_MS = 1500


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def content_fingerprint(
    *,
    league_id: object,
    prepared_frame_signature: object = "",
    score_field: object = "",
) -> str:
    return "|".join(
        (
            _text(league_id),
            _text(prepared_frame_signature)[:48],
            _text(score_field),
        )
    )


def current_phase(state: MutableMapping[str, Any]) -> str:
    phase = _text(state.get(PHASE_KEY), PHASE_IDLE)
    return phase if phase in {PHASE_IDLE, PHASE_HYDRATING, PHASE_USEFUL} else PHASE_IDLE


def should_clear_stale_dashboard(
    state: MutableMapping[str, Any],
    *,
    league_id: object,
) -> bool:
    """True when prior Dashboard body must not remain visible as current."""

    league = _text(league_id)
    if not league:
        return False
    ack = state.get("_league_switch_ack")
    if isinstance(ack, dict) and _text(ack.get("phase")) == "loading":
        return True
    if state.get("_league_switch_first_useful_guard"):
        return True
    last_league = _text(state.get(LAST_USEFUL_LEAGUE_KEY))
    if last_league and last_league != league:
        return True
    # No prior useful paint for this session league → avoid painting empty fades.
    if not last_league:
        pkg_sig = state.get("_game_plan_package_signature")
        if not pkg_sig:
            return True
    return False


def begin_hydrate(
    state: MutableMapping[str, Any],
    *,
    league_id: object,
    league_name: object = "",
    route: object = "dashboard",
) -> bool:
    """Enter hydrating phase when stale body must be cleared. Returns True if active."""

    if _text(route) != "dashboard":
        return False
    if not should_clear_stale_dashboard(state, league_id=league_id):
        state[PHASE_KEY] = PHASE_IDLE
        state.pop(PLACEHOLDER_RENDERED_KEY, None)
        return False
    state[PHASE_KEY] = PHASE_HYDRATING
    state[HYDRATE_TOKEN_KEY] = f"{_text(league_id)}|{_text(league_name)}"
    state["_dashboard_hydrate_started_mono"] = time.perf_counter()
    # Secondary Dashboard sections render in the same run as Game Plan.
    # Do not arm a 250ms repeating fragment — that dimmed the useful page on iPhone.
    state.pop("_dashboard_defer_secondary_once", None)
    state.pop("_dashboard_secondary_mounted", None)
    state.pop("_dashboard_secondary_defer_armed", None)
    state.pop(PLACEHOLDER_RENDERED_KEY, None)
    runtime_trace.mark("dashboard_hydrate_begin")
    runtime_trace.count("dashboard_hydrate_clears")
    try:
        from modules import dashboard_waterfall as _waterfall

        _waterfall.begin(state)
    except Exception:
        pass
    return True


def bind_placeholder_slot(slot: Any) -> None:
    """Bind the Dashboard `st.empty()` owner for this run."""

    global _placeholder_slot
    _placeholder_slot = slot


def clear_hydrate_placeholder() -> None:
    """Remove the hydrate card so it cannot sit above first-useful Game Plan."""

    slot = _placeholder_slot
    if slot is None:
        return
    try:
        slot.empty()
    except Exception:
        pass


def render_hydrate_placeholder(
    state: MutableMapping[str, Any],
    *,
    league_name: object = "",
) -> None:
    """Stable placeholder that replaces stale body before heavy football work."""

    if current_phase(state) != PHASE_HYDRATING:
        return
    if state.get(PLACEHOLDER_RENDERED_KEY):
        return
    name = _text(league_name, "your league")
    first_open = not _text(state.get(LAST_USEFUL_LEAGUE_KEY))
    kicker = "Your Game Plan" if first_open else "Updating Dashboard"
    copy = (
        f"Building the Game Plan for {name}. Recommendations wait until this league is ready."
        if first_open
        else (
            "Loading this league's Game Plan. Prior recommendations are cleared so they "
            "are not shown as current."
        )
    )
    html = (
        "<div class='dashboard-hydrate-placeholder' data-fgl-dashboard-hydrating='1' "
        "role='status' aria-live='polite'>"
        f"<div class='dashboard-hydrate-kicker'>{kicker}</div>"
        f"<div class='dashboard-hydrate-title'>{name}</div>"
        f"<div class='dashboard-hydrate-copy'>{copy}</div>"
        "</div>"
    )
    slot = _placeholder_slot
    if slot is not None:
        slot.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(html, unsafe_allow_html=True)
    state[PLACEHOLDER_RENDERED_KEY] = True


def mark_first_useful(
    state: MutableMapping[str, Any],
    *,
    league_id: object,
    content_fp: object = "",
) -> None:
    """Mark first useful Dashboard for this league/context."""

    state[PHASE_KEY] = PHASE_USEFUL
    state[LAST_USEFUL_LEAGUE_KEY] = _text(league_id)
    if _text(content_fp):
        state[LAST_USEFUL_FP_KEY] = _text(content_fp)
    state.pop(PLACEHOLDER_RENDERED_KEY, None)
    state.pop("_opening_selected_league", None)
    clear_hydrate_placeholder()
    runtime_trace.mark("dashboard_first_useful_owned")
    try:
        from modules import dashboard_waterfall as _waterfall

        _waterfall.record(
            "first_useful_marked",
            0.0,
            cache_status="useful",
            session_state=state,
        )
    except Exception:
        pass


def clear_on_logout(state: MutableMapping[str, Any]) -> None:
    for key in (
        PHASE_KEY,
        LAST_USEFUL_LEAGUE_KEY,
        LAST_USEFUL_FP_KEY,
        HYDRATE_TOKEN_KEY,
        PLACEHOLDER_RENDERED_KEY,
    ):
        state.pop(key, None)
