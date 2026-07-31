"""League-scoped, non-blocking Dashboard orientation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from hashlib import sha256

import streamlit as st

from modules import ui_modal, ui_primitives

ORIENTATION_VERSION = "v1"
ORIENTATION_STATE_PREFIX = "_dg_dashboard_orientation_"
ORIENTATION_MODAL_SURFACE = "dashboard_orientation"

ORIENTATION_TITLE = "Your DynastyGM game plan"
ORIENTATION_SUMMARY = (
    "Start with today's priorities, then use each workspace to decide what to change."
)
ORIENTATION_STEPS = (
    "1. Review Dashboard priorities. "
    "2. Diagnose roster construction in My Team. "
    "3. Explore team-specific ideas in Trade Hub. "
    "4. Check Waivers for available upgrades."
)
ORIENTATION_TRUST_NOTE = (
    "Open Trust details for the evidence behind a recommendation, and return as "
    "values, injuries, and league context change."
)


def orientation_scope_key(platform: object, league_identity: object) -> str:
    """Return a stable, non-identifying state namespace for one league."""

    normalized_platform = str(platform or "").strip().casefold()
    normalized_league = str(league_identity or "").strip()
    if not normalized_platform or not normalized_league:
        raise ValueError("Dashboard orientation requires stable platform and league identity.")
    payload = f"{ORIENTATION_VERSION}\x1f{normalized_platform}\x1f{normalized_league}"
    return ORIENTATION_STATE_PREFIX + sha256(payload.encode("utf-8")).hexdigest()[:20]


def dismiss_orientation(
    session_state: MutableMapping[str, object],
    *,
    platform: object,
    league_identity: object,
) -> None:
    session_state[orientation_scope_key(platform, league_identity)] = True


def orientation_is_dismissed(
    session_state: Mapping[str, object],
    *,
    platform: object,
    league_identity: object,
) -> bool:
    try:
        key = orientation_scope_key(platform, league_identity)
    except ValueError:
        return False
    return session_state.get(key) is True


def should_show_orientation(
    *,
    authenticated: bool,
    page_ready: bool,
    route: object,
    platform: object,
    league_identity: object,
    active_roster_available: bool,
    startup_mode: bool,
    session_state: Mapping[str, object],
) -> bool:
    """Resolve the pure first-use visibility contract."""

    return bool(
        authenticated
        and page_ready
        and str(route or "").strip() == "dashboard"
        and str(platform or "").strip()
        and str(league_identity or "").strip()
        and active_roster_available
        and not startup_mode
        and not orientation_is_dismissed(
            session_state,
            platform=platform,
            league_identity=league_identity,
        )
    )


def orientation_modal_content() -> ui_modal.ModalContent:
    return ui_modal.ModalContent(
        title="How DynastyGM works",
        eyebrow="League workflow",
        summary=(
            "Use the Dashboard to choose the next question, then open the workspace "
            "built to answer it."
        ),
        sections=(
            ui_modal.ModalSection(
                "Dashboard",
                "Review immediate roster, trade, waiver, and health priorities.",
            ),
            ui_modal.ModalSection(
                "My Team",
                "Understand roster construction and position-level context.",
            ),
            ui_modal.ModalSection(
                "Trade Hub",
                "Explore team-specific ideas, then open Trust details to review the evidence.",
            ),
            ui_modal.ModalSection(
                "Waivers",
                "Find available additions that address current priorities or improve depth.",
            ),
            ui_modal.ModalSection(
                "Keep it current",
                "Revisit the workflow as player values, injuries, and league context change.",
            ),
        ),
        footer="Details explain the current recommendation; they do not guarantee an outcome.",
    )


def render_dashboard_orientation(
    *,
    platform: object,
    league_identity: object,
    on_open_my_team: Callable[[], None],
    session_state: MutableMapping[str, object] | None = None,
) -> None:
    """Render one compact card plus an optional canonical detail dialog."""

    state = st.session_state if session_state is None else session_state
    scope_key = orientation_scope_key(platform, league_identity)

    ui_primitives.render_status_badge("League orientation", variant="information")
    ui_primitives.render_content_card(
        ORIENTATION_SUMMARY,
        title=ORIENTATION_TITLE,
        metadata=ORIENTATION_STEPS,
        footer=ORIENTATION_TRUST_NOTE,
    )

    interaction = {"show_modal": False}

    def _review_my_team() -> None:
        st.button(
            "Review My Team",
            key=f"{scope_key}_my_team",
            type="primary",
            use_container_width=True,
            on_click=on_open_my_team,
            help="Open My Team for roster construction and position-level context.",
        )

    def _show_how_it_works() -> None:
        interaction["show_modal"] = st.button(
            "How DynastyGM works",
            key=f"{scope_key}_how",
            type="secondary",
            use_container_width=True,
            help="Open a concise explanation of the DynastyGM league workflow.",
        )

    def _dismiss() -> None:
        st.button(
            "Dismiss league orientation",
            key=f"{scope_key}_dismiss",
            type="tertiary",
            use_container_width=True,
            on_click=dismiss_orientation,
            args=(state,),
            kwargs={
                "platform": platform,
                "league_identity": league_identity,
            },
            help="Hide this orientation for the current league during this session.",
        )

    ui_primitives.render_action_row(
        _review_my_team,
        key=scope_key,
        secondary_action=_show_how_it_works,
        tertiary_action=_dismiss,
        primary_first=True,
        horizontal_alignment="left",
    )
    if interaction["show_modal"]:
        ui_modal.render_modal(
            orientation_modal_content(),
            surface=ORIENTATION_MODAL_SURFACE,
        )


def render_orientation_if_applicable(
    *,
    authenticated: bool,
    page_ready: bool,
    route: object,
    platform: object,
    league_identity: object,
    active_roster_available: bool,
    startup_mode: bool,
    on_open_my_team: Callable[[], None],
) -> bool:
    """Keep the complete visibility boundary outside Dashboard orchestration."""

    if not should_show_orientation(
        authenticated=authenticated,
        page_ready=page_ready,
        route=route,
        platform=platform,
        league_identity=league_identity,
        active_roster_available=active_roster_available,
        startup_mode=startup_mode,
        session_state=st.session_state,
    ):
        return False
    render_dashboard_orientation(
        platform=platform,
        league_identity=league_identity,
        on_open_my_team=on_open_my_team,
    )
    return True
