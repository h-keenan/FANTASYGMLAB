"""Production-renderer harness for post-#367 command-header ownership.

Uses app.render_platform_topbar directly; it does not recreate the shell HTML.
Synthetic account/league labels only, with no credentials or provider calls.
"""

from __future__ import annotations

import streamlit as st

import app
from modules import render_ownership


st.set_page_config(page_title="Header ownership harness", layout="wide")
app.inject_global_styles(app.APP_CSS)
app.inject_global_styles(app.MOBILE_VISUAL_POLISH_CSS)
app.inject_global_styles(app.FOUNDER_BETA_UX_CSS)
app.inject_global_styles(app.DASHBOARD_WORKFLOW_CSS)

st.session_state.setdefault("auth_session", {"user_id": "fixture-user"})
st.session_state.setdefault("platform_nav_page", "my_team")
st.session_state.setdefault("_effective_entitlement", "premium")
render_ownership.begin_script_run(st.session_state)

slot = st.container(key="application_command_header_slot")
page = str(st.session_state.get("platform_nav_page") or "my_team")
title = "My Team" if page == "my_team" else "Dashboard"
app.render_platform_topbar(
    page_title=title,
    page_note="Production renderer ownership proof.",
    selected_league_id="fixture-league",
    selected_league_name="Revivalry",
    team_profile={"team_name": "Fixture Team", "username": "fixture"},
    platform="Sleeper",
    account_label="Signed In",
    entitlement_label="Premium",
    host_slot=slot,
)
# Deliberately exercise a second real call in the same script run. The canonical
# owner must reject it, rather than relying on CSS to hide duplicate output.
app.render_platform_topbar(
    page_title="Dashboard",
    page_note="Rejected duplicate.",
    selected_league_id="fixture-league",
    selected_league_name="Revivalry",
    team_profile={"team_name": "Fixture Team"},
    platform="Sleeper",
    account_label="Signed In",
    entitlement_label="Premium",
    host_slot=slot,
)

st.markdown(f"<main data-route='{page}'><h2>{title} content</h2></main>", unsafe_allow_html=True)


def _switch_route() -> None:
    st.session_state["platform_nav_page"] = (
        "dashboard" if st.session_state.get("platform_nav_page") == "my_team" else "my_team"
    )


st.button("Switch route", on_click=_switch_route, key="switch_route")
