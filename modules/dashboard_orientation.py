"""League-scoped, non-blocking Dashboard orientation."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256

import streamlit as st

from modules import ui_modal, ui_primitives

ORIENTATION_VERSION = "v1"
ORIENTATION_STATE_PREFIX = "_dg_dashboard_orientation_"
ORIENTATION_MODAL_SURFACE = "dashboard_orientation"

ORIENTATION_TITLE = "Your DynastyGM game plan"
ORIENTATION_SUMMARY = (
    "Start with today's priorities, then open the workspace built for the decision."
)
ORIENTATION_STEPS = (
    "Dashboard: choose the priority.",
    "My Team: diagnose the roster.",
    "Trade Hub: explore deals.",
    "Waivers: find available upgrades.",
)
ORIENTATION_TRUST_NOTE = (
    "Use Trust details to review the evidence. Return when values, injuries, or league context change."
)


def orientation_scope_key(platform: object, league_identity: object) -> str:
    """Return a stable, non-identifying state namespace for one league."""

    normalized_platform = str(platform or "").strip().casefold()
    normalized_league = str(league_identity or "").strip()
    if not normalized_platform or not normalized_league:
        raise ValueError("Dashboard orientation requires stable platform and league identity.")
    payload = f"{ORIENTATION_VERSION}\x1f{normalized_platform}\x1f{normalized_league}"
    return ORIENTATION_STATE_PREFIX + sha256(payload.encode("utf-8")).hexdigest()[:20]


def should_show_orientation(
    *,
    authenticated: bool,
    page_ready: bool,
    route: object,
    platform: object,
    league_identity: object,
    active_roster_available: bool,
    startup_mode: bool,
    persistently_dismissed: bool,
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
        and not persistently_dismissed
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


def _render_dashboard_orientation_content(
    *,
    platform: object,
    league_identity: object,
    on_open_my_team: Callable[[], None],
    on_dont_show_again: Callable[[], None],
) -> None:
    """Render one compact card plus an optional canonical detail dialog."""

    scope_key = orientation_scope_key(platform, league_identity)

    ui_primitives.render_status_badge("League orientation", variant="information")
    ui_primitives.render_content_card(
        ORIENTATION_SUMMARY,
        title=ORIENTATION_TITLE,
        items=ORIENTATION_STEPS,
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
            "Don't show again",
            key=f"{scope_key}_dismiss",
            type="tertiary",
            use_container_width=True,
            on_click=on_dont_show_again,
            help="Permanently hide League Orientation for this account on every device.",
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


def render_dashboard_orientation(
    *,
    platform: object,
    league_identity: object,
    on_open_my_team: Callable[[], None],
    on_dont_show_again: Callable[[], None],
) -> None:
    """Render the compact orientation in one stable, style-scoped container."""

    with st.container(key="dashboard_orientation_panel"):
        _render_dashboard_orientation_content(
            platform=platform,
            league_identity=league_identity,
            on_open_my_team=on_open_my_team,
            on_dont_show_again=on_dont_show_again,
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
    persistently_dismissed: bool = False,
    on_dont_show_again: Callable[[], None] = lambda: None,
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
        persistently_dismissed=persistently_dismissed,
    ):
        return False
    render_dashboard_orientation(
        platform=platform,
        league_identity=league_identity,
        on_open_my_team=on_open_my_team,
        on_dont_show_again=on_dont_show_again,
    )
    return True
