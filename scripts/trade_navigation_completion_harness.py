"""Production-module harness for one-time Trade Hub landing and route ownership."""

from __future__ import annotations

import streamlit as st

import app
from modules import navigation_state
from modules import route_render_ownership
from modules import trade_hub_ui


st.set_page_config(page_title="Trade navigation completion", layout="wide")
app.inject_global_styles(app.APP_CSS)
app.inject_global_styles(app.DASHBOARD_WORKFLOW_CSS)
app.inject_global_styles(trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS)

st.session_state.setdefault("platform_nav_page", "dashboard")
st.session_state.setdefault("selected_league_id", "fixture-league")


def _pqv_to_trade_hub() -> None:
    navigation_state.request_scroll_anchor(
        st.session_state,
        "trade_hub",
        anchor="trade-hub-player-search",
        reason="player_quick_view",
    )
    navigation_state.commit_destination_navigation(
        st.session_state,
        "trade_hub",
        current_destination="dashboard",
        source="player_quick_view",
    )


st.markdown(
    '<header class="dg-executive-shell" data-harness-command-header="1">'
    '<strong>Trade navigation proof</strong></header>',
    unsafe_allow_html=True,
)
st.button("PQV → Trade Hub", key="harness_pqv_trade", on_click=_pqv_to_trade_hub)

route = str(st.session_state.get("platform_nav_page") or "dashboard")
app._render_navigation_scroll_reset(route, league_id="fixture-league")
route_slot = st.empty()
route_container = route_render_ownership.enter_after_chrome(
    st.session_state, route, slot=route_slot
)

if route == "dashboard":
    st.markdown('<main data-route-body="dashboard"><h1>Dashboard</h1>', unsafe_allow_html=True)
    for index in range(16):
        st.markdown(f"Dashboard prior-route row {index}")
    st.markdown("</main>", unsafe_allow_html=True)
else:
    st.markdown('<main data-route-body="trade_hub"><h1>Trade Hub</h1>', unsafe_allow_html=True)
    for index in range(12):
        st.markdown(f"Trade Hub market context {index}")
    st.markdown(
        '<div data-dg-scroll-anchor="trade-hub-player-search" '
        'class="trade-hub-semantic-anchor" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.subheader("Search Around a Player")
    st.selectbox("Selected player", ["Ashton Jeanty"], key="harness_player")
    st.caption("Expanded market search · results ready")
    idea = {
        "partner_roster_id": "partner",
        "partner_team_name": "A Very Long Founder Beta Franchise Name",
        "tag": "Acquire elite running back without clipping",
        "send_assets": [
            {"asset_type": "player", "player_id": "a", "name": "Long Player Name Alpha"},
            {"asset_type": "player", "player_id": "b", "name": "Long Player Name Beta"},
            {"asset_type": "player", "player_id": "c", "name": "Long Player Name Gamma"},
        ],
        "receive_assets": [
            {"asset_type": "player", "player_id": "elite", "name": "Ashton Jeanty"}
        ],
        "my_score": 9600,
        "their_score": 10000,
        "trade_gain": 400,
        "trade_confidence_label": "Medium",
        "market_realism_label": "Expanded Market",
        "fit_grade": "Strong Fit",
    }
    html = trade_hub_ui._trade_summary_assets_html(idea["send_assets"])
    st.markdown(
        f'<section class="trade-summary-card" data-harness-trade-card="1">'
        f'<div class="trade-summary-title">{idea["partner_team_name"]}</div>'
        f'<div class="trade-summary-side">{html}</div>'
        '<strong class="trade-summary-value-label">Balance +400</strong></section>',
        unsafe_allow_html=True,
    )

route_render_ownership.exit_route_body(route_container, st.session_state)
