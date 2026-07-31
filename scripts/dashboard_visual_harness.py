"""Fixture-backed visual harness for the authenticated Dashboard top region.

Run locally with:
    streamlit run scripts/dashboard_visual_harness.py

This file is test-only. It uses synthetic labels and the production renderers,
styles, primitives, orientation state, and modal contracts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app
from modules import app_header, dashboard_orientation, premium, startup_coordinator
from modules.app_styles import APP_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.ux_polish_styles import FOUNDER_BETA_UX_CSS


LEAGUES = {
    "League A": {
        "id": "visual-league-a",
        "name": "Fixture League A",
        "team": "Fixture Franchise",
    },
    "League B": {
        "id": "visual-league-b",
        "name": "Fixture League B",
        "team": "Second Fixture Franchise",
    },
}
LONG_LEAGUE_NAME = (
    "The Extraordinarily Long Synthetic Dynasty League Name for Responsive Validation"
)

MULTIPLE_RECOMMENDATIONS = (
    {
        "label": "Roster Pressure",
        "value": "Within Limit",
        "note": "Twenty-four active players against a twenty-five player limit.",
        "tone": "draft",
    },
    {
        "label": "Top Trade Opportunity",
        "value": "Fixture Trade Partner",
        "note": "Explore a balanced package without changing the underlying recommendation.",
        "tone": "trade",
    },
    {
        "label": "Top Waiver Opportunity",
        "value": "Fixture Available Player",
        "note": "Adds useful depth at a position with a current upgrade opportunity.",
        "tone": "waiver",
    },
    {
        "label": "Upgrade Opportunity",
        "value": "TE",
        "note": "The room is covered; this is an upgrade, not a roster deficiency.",
        "tone": "power",
    },
    {
        "label": "Injury Alert",
        "value": "Stable",
        "note": "No acute starter pressure in this deterministic fixture.",
        "tone": "risk",
    },
)

LEAGUE_PULSE = (
    {
        "label": "Biggest Contender",
        "value": "Fixture Contender",
        "note": "Strongest current starting lineup in the synthetic league.",
        "tone": "power",
        "detail": "This compares current starting-lineup strength across fixture teams.",
        "detail_items": (
            {"title": "Fixture Contender", "value": "1st", "current": True},
            {"title": "Fixture Challenger", "value": "2nd"},
        ),
    },
    {
        "label": "Draft Capital Leader",
        "value": "Fixture Rebuilder",
        "note": "Largest synthetic future-pick position.",
        "tone": "draft",
        "detail": "This summarizes fixture draft-capital ownership without live league data.",
    },
)


def _controls() -> tuple[str, str, str, bool]:
    with st.sidebar:
        st.header("Visual fixture controls")
        lifecycle = st.radio(
            "Lifecycle",
            ("Dashboard ready", "Startup shell"),
            key="visual_lifecycle",
        )
        entitlement = st.radio(
            "Entitlement",
            (premium.FREE, premium.PREMIUM),
            key="visual_entitlement",
        )
        league_label = st.selectbox(
            "League",
            tuple(LEAGUES),
            key="visual_league",
        )
        recommendation_state = st.radio(
            "Next Moves",
            ("Multiple", "Limited", "Empty"),
            key="visual_recommendations",
        )
        long_name = st.checkbox("Long league name", key="visual_long_name")
        if st.button("Reset orientation states", use_container_width=True):
            for key in tuple(st.session_state):
                if str(key).startswith(
                    dashboard_orientation.ORIENTATION_STATE_PREFIX
                ):
                    st.session_state.pop(key, None)
    return lifecycle, entitlement, league_label, recommendation_state, long_name


def _render_startup_shell() -> None:
    render_html_fragment(
        startup_coordinator.startup_shell_html(
            startup_coordinator.StartupPhase.AUTH_RESTORING
        )
    )


def _render_dashboard(
    *,
    entitlement: str,
    league_label: str,
    recommendation_state: str,
    long_name: bool,
) -> None:
    league = LEAGUES[league_label]
    league_name = LONG_LEAGUE_NAME if long_name else league["name"]

    render_html_fragment(
        app_header.league_identity_header_html(
            league_name=league_name,
            team_name=league["team"],
            platform="Sleeper",
            has_league=True,
            account_label="Fixture Account",
            entitlement_label="Premium" if entitlement == premium.PREMIUM else "Free",
        )
    )
    app.render_home_command_hero(
        team_profile={"team_name": league["team"], "owner_name": "Fixture Manager"},
        selected_league_name=league_name,
        record_label="7-3",
        direction_label="Balanced",
        health_status="Stable",
        archetype_label="Flexible Contender",
        power_rank=3,
        franchise_rank=4,
    )
    dashboard_orientation.render_orientation_if_applicable(
        authenticated=True,
        page_ready=True,
        route="dashboard",
        platform="sleeper",
        league_identity=league["id"],
        active_roster_available=True,
        startup_mode=False,
        on_open_my_team=lambda: st.session_state.update(
            {"visual_last_action": "my_team"}
        ),
    )

    app.render_section_header(
        "Next Moves",
        kicker="Dashboard",
        note="Highest-priority roster, trade, waiver, and health signals for this league.",
        compact=True,
    )
    if recommendation_state == "Multiple":
        action_items = list(MULTIPLE_RECOMMENDATIONS)
    elif recommendation_state == "Limited":
        action_items = [MULTIPLE_RECOMMENDATIONS[1]]
    else:
        action_items = []

    visible_items = (
        action_items
        if entitlement == premium.PREMIUM
        else action_items[:4]
    )
    app.render_home_command_tiles(visible_items)
    if not action_items:
        st.info("No immediate fixture recommendations.")
    if entitlement == premium.FREE and len(action_items) > len(visible_items):
        premium.render_premium_lock(
            "Full Next Moves",
            "More roster, trade, waiver, and health signals for the current league.",
            feature="Premium Dashboard",
        )

    with st.expander("League Pulse", expanded=True):
        if entitlement == premium.PREMIUM:
            st.caption(
                "Secondary league-wide context. Open this when you want the broader league read."
            )
            app.render_summary_tiles(
                list(LEAGUE_PULSE),
                compact=True,
                detail_dialog_renderer=app.workspace_ui.render_canonical_summary_tile_detail_dialog,
            )
        else:
            premium.render_premium_lock(
                "Expanded League Pulse",
                "League-wide contender, rebuilder, and market context.",
                feature="Premium Intelligence",
            )

    st.caption(
        "Synthetic fixture only. No production account, league, roster, player, or entitlement data is loaded."
    )


def main() -> None:
    st.set_page_config(
        page_title="Dashboard Visual Harness",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_styles(APP_CSS)
    inject_global_styles(FOUNDER_BETA_UX_CSS)
    lifecycle, entitlement, league_label, recommendations, long_name = _controls()
    if lifecycle == "Startup shell":
        _render_startup_shell()
        return
    _render_dashboard(
        entitlement=entitlement,
        league_label=league_label,
        recommendation_state=recommendations,
        long_name=long_name,
    )


if __name__ == "__main__":
    main()
