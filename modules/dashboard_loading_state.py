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
from contextlib import contextmanager
from html import escape
from typing import Any
import time

import streamlit as st

from modules import runtime_trace


PHASE_KEY = "_dashboard_loading_phase"
LAST_USEFUL_LEAGUE_KEY = "_dashboard_last_useful_league_id"
LAST_USEFUL_FP_KEY = "_dashboard_last_useful_content_fp"
HYDRATE_TOKEN_KEY = "_dashboard_hydrate_token"
PLACEHOLDER_RENDERED_KEY = "_dashboard_hydrate_placeholder_rendered"

# Same-run Streamlit slot(s) so a hydrate card can be cleared before the
# route's real content mounts. Do not persist across processes. Keyed per
# route so the Dashboard's slot and a non-Dashboard surface's slot (e.g.
# Trade Hub search) never clobber each other if both end up bound in the
# same run.
_placeholder_slots: dict[str, Any] = {}

PHASE_IDLE = "idle"
PHASE_HYDRATING = "hydrating"
PHASE_USEFUL = "useful"

# --- Routes/contexts --------------------------------------------------
#
# "dashboard" keeps the original clear-then-hydrate state machine below
# (cross-rerun league-switch detection, "first useful" contract, etc). The
# others are non-Dashboard surfaces that previously showed a bare
# `st.spinner(...)` with no reserved-height placeholder -- replacing a
# spinner with differently-sized real content causes a visible layout jump.
# `hydrate_placeholder()` extends the same primitives (the hydrate-card HTML/
# CSS and the slot-based begin/render/clear calls) to those surfaces with a
# shape-matched skeleton instead of inventing a parallel loading system.
ROUTE_DASHBOARD = "dashboard"
ROUTE_TRADE_HUB_SEARCH = "trade_hub_search"
ROUTE_TRADE_HUB_ACQUISITION_SEARCH = "trade_hub_acquisition_search"
ROUTE_PLAYER_QUICK_VIEW_WEEKLY_POINTS = "player_quick_view_weekly_points"
ROUTE_LEAGUE_LOADING = "league_loading"
ROUTE_PLAYER_NEWS = "player_news"
ROUTE_NFL_HEADLINES_FALLBACK = "nfl_headlines_fallback"
ROUTE_GENERIC_SURFACE = "generic_surface"
ROUTE_DRAFT_CENTER = "draft_center"
ROUTE_LIVE_DRAFT = "live_draft"

# Skeleton "shape" a route's placeholder should roughly match. Perfect shape
# matching isn't required -- a reasonable reserved-height block beats a bare
# spinner that collapses to nothing.
SHAPE_CARDS = "cards"  # list-of-cards, e.g. Trade Hub idea results
SHAPE_CHART = "chart"  # single chart-shaped block, e.g. weekly points
SHAPE_LIST = "list"  # compact list rows, e.g. league list / news items
SHAPE_GENERIC = "generic"  # fallback reserved-height block

_ROUTE_SHAPES: dict[str, str] = {
    ROUTE_TRADE_HUB_SEARCH: SHAPE_CARDS,
    ROUTE_TRADE_HUB_ACQUISITION_SEARCH: SHAPE_CARDS,
    ROUTE_PLAYER_QUICK_VIEW_WEEKLY_POINTS: SHAPE_CHART,
    ROUTE_LEAGUE_LOADING: SHAPE_LIST,
    ROUTE_PLAYER_NEWS: SHAPE_LIST,
    ROUTE_NFL_HEADLINES_FALLBACK: SHAPE_LIST,
    ROUTE_DRAFT_CENTER: SHAPE_LIST,
    ROUTE_LIVE_DRAFT: SHAPE_LIST,
}

_SHAPE_ROW_COUNTS: dict[str, int] = {
    SHAPE_CARDS: 3,
    SHAPE_CHART: 1,
    SHAPE_LIST: 4,
    SHAPE_GENERIC: 1,
}

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
    league_id: object = "",
    league_name: object = "",
    route: object = ROUTE_DASHBOARD,
) -> bool:
    """Enter hydrating phase when stale body must be cleared. Returns True if active.

    For routes other than ``dashboard``, there is no cross-rerun "did the
    football context change" question to answer the way Dashboard's
    league-switch detection (`should_clear_stale_dashboard`) does -- callers
    only reach here from inside a branch that is about to run a real
    blocking fetch (a cache miss), so a placeholder is always wanted for the
    duration of that call. Most callers should use `hydrate_placeholder()`
    below instead of calling this directly.
    """

    route_text = _text(route)
    if route_text and route_text != ROUTE_DASHBOARD:
        try:
            runtime_trace.count("non_dashboard_hydrate_begin")
        except Exception:
            pass
        return True

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


def bind_placeholder_slot(slot: Any, *, route: object = ROUTE_DASHBOARD) -> None:
    """Bind the `st.empty()` owner for this run, scoped per route."""

    route_text = _text(route) or ROUTE_DASHBOARD
    _placeholder_slots[route_text] = slot


def clear_hydrate_placeholder(*, route: object = ROUTE_DASHBOARD) -> None:
    """Remove the hydrate card so it cannot sit above the route's real content."""

    route_text = _text(route) or ROUTE_DASHBOARD
    slot = _placeholder_slots.get(route_text)
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
    route: object = ROUTE_DASHBOARD,
    title: object = "",
    subtitle: object = "",
) -> None:
    """Stable placeholder that replaces stale body before heavy work.

    Dashboard keeps its original shape-matched "Your Game Plan" / "Updating
    Dashboard" card. Any other route renders a shape-matched skeleton sized
    for that surface (see `_ROUTE_SHAPES`) using the same hydrate-card
    primitives, via `_render_shape_placeholder`.
    """

    route_text = _text(route)
    if route_text and route_text != ROUTE_DASHBOARD:
        _render_shape_placeholder(route_text, title=_text(title), subtitle=_text(subtitle))
        return

    if current_phase(state) != PHASE_HYDRATING:
        return
    if state.get(PLACEHOLDER_RENDERED_KEY):
        return
    name = _text(league_name, "your league")
    safe_name = escape(name)
    first_open = not _text(state.get(LAST_USEFUL_LEAGUE_KEY))
    kicker = "Your Game Plan" if first_open else "Updating Dashboard"
    copy = (
        f"Building the Game Plan for {safe_name}. Recommendations wait until this league is ready."
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
        f"<div class='dashboard-hydrate-title'>{safe_name}</div>"
        f"<div class='dashboard-hydrate-copy'>{copy}</div>"
        "<div class='dashboard-hydrate-skeleton' aria-hidden='true'>"
        "<div class='dashboard-hydrate-skeleton-row'></div>"
        "<div class='dashboard-hydrate-skeleton-row'></div>"
        "<div class='dashboard-hydrate-skeleton-row'></div>"
        "</div>"
        "</div>"
    )
    slot = _placeholder_slots.get(ROUTE_DASHBOARD)
    if slot is not None:
        slot.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(html, unsafe_allow_html=True)
    state[PLACEHOLDER_RENDERED_KEY] = True


def _render_shape_placeholder(route_text: str, *, title: str, subtitle: str) -> None:
    """Render a shape-matched skeleton for a non-Dashboard route.

    Reuses the same `.dashboard-hydrate-placeholder` / `-skeleton` /
    `-skeleton-row` CSS primitives Dashboard's card uses (see
    modules/dashboard_workflow_styles.py), with a `--{shape}` modifier class
    that only changes sizing/row-count so the reserved height roughly
    matches the real content for that surface (a list-of-cards shape for
    Trade Hub, a chart-shaped block for weekly points, a list shape for
    league-loading/news). Shape matching is a reasonable approximation, not
    a pixel-perfect one -- the goal is no more full-page reflow jump than a
    bare `st.spinner(...)` already caused.
    """

    shape = _ROUTE_SHAPES.get(route_text, SHAPE_GENERIC)
    rows = "".join(
        "<div class='dashboard-hydrate-skeleton-row'></div>"
        for _ in range(_SHAPE_ROW_COUNTS.get(shape, 1))
    )
    header = ""
    if title:
        header += f"<div class='dashboard-hydrate-kicker'>{escape(title)}</div>"
    if subtitle:
        header += f"<div class='dashboard-hydrate-copy'>{escape(subtitle)}</div>"
    html = (
        f"<div class='dashboard-hydrate-placeholder dashboard-hydrate-placeholder--{shape}' "
        "data-fgl-hydrating='1' role='status' aria-live='polite'>"
        f"{header}"
        "<div class='dashboard-hydrate-skeleton' aria-hidden='true'>"
        f"{rows}"
        "</div>"
        "</div>"
    )
    slot = _placeholder_slots.get(route_text)
    if slot is not None:
        slot.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(html, unsafe_allow_html=True)


@contextmanager
def hydrate_placeholder(
    route: object,
    *,
    title: object = "",
    subtitle: object = "",
    state: MutableMapping[str, Any] | None = None,
):
    """Drop-in replacement for ``with st.spinner(...):`` on a non-Dashboard
    surface. Reserves roughly the real content's height with a shape-matched
    skeleton (built from the same begin_hydrate/render_hydrate_placeholder/
    clear_hydrate_placeholder primitives Dashboard's clear-then-hydrate
    uses) so swapping in the real content on completion does not reflow the
    page the way a bare spinner collapsing to nothing does.

    Usage mirrors `st.spinner`::

        with hydrate_placeholder(
            ROUTE_TRADE_HUB_SEARCH, title="Searching realistic return packages..."
        ):
            do_blocking_work()
    """

    route_text = _text(route) or ROUTE_GENERIC_SURFACE
    session_state: MutableMapping[str, Any] = state if state is not None else st.session_state
    slot = st.empty()
    bind_placeholder_slot(slot, route=route_text)
    begin_hydrate(session_state, route=route_text)
    render_hydrate_placeholder(session_state, route=route_text, title=title, subtitle=subtitle)
    try:
        yield
    finally:
        clear_hydrate_placeholder(route=route_text)


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
