from __future__ import annotations

import pandas as pd
import streamlit as st

from modules import trade_analyzer_assembly as assembly
from modules import trade_analyzer_builder as builder
from modules import trade_analyzer_ui
from modules import session_integrity
from modules import viewport_preservation


st.set_page_config(page_title="Interaction integrity", layout="wide")
viewport_preservation.render_viewport_preservation()
st.title("Interaction Integrity")

st.markdown(
    '<div data-dg-scroll-anchor="trade-analyzer-builder" '
    'class="trade-analyzer-semantic-anchor" aria-hidden="true"></div>',
    unsafe_allow_html=True,
)

players = pd.DataFrame(
    [
        {
            "player_id": "parker-washington",
            "name": "Parker Washington",
            "position": "WR",
            "team": "JAX",
            "value_score": 2100,
            "score": 2100,
            "owner_roster_id": "me",
        },
        {
            "player_id": "partner-player",
            "name": "Partner Player",
            "position": "RB",
            "team": "BUF",
            "value_score": 1800,
            "score": 1800,
            "owner_roster_id": "partner",
        },
    ]
)

# Production-equivalent ownership: the lightweight shell and full analyzer can
# resolve different strategy labels, but they must never fight over one guard.
shell_context = "ppr|fringe_contender"
analyzer_context = "ppr|fringe-contender"
if st.session_state.get("trade_asset_strategy_context") != shell_context:
    st.session_state[assembly.SEND_KEY] = []
    st.session_state[assembly.RECEIVE_KEY] = []
    st.session_state["trade_asset_strategy_context"] = shell_context
assembly.ensure_package_context(st.session_state, context_key=analyzer_context)
assembly.ensure_catalogs(
    st.session_state,
    context_key="interaction-integrity",
    my_roster_id="me",
    partner_roster_id="partner",
    players_df=players,
    my_player_ids=["parker-washington"],
    partner_player_ids=["partner-player"],
    my_picks=[
        {
            "label": "2027 Round 2",
            "season": 2027,
            "round": 2,
            "score": 1200,
            "owner_roster_id": "me",
        }
    ],
    partner_picks=[
        {
            "label": "2027 Round 2",
            "season": 2027,
            "round": 2,
            "score": 1200,
            "owner_roster_id": "partner",
        }
    ],
    player_owner_map={
        "parker-washington": {"owner_roster_id": "me"},
        "partner-player": {"owner_roster_id": "partner"},
    },
)

trade_analyzer_ui.render_trade_analyzer_assembly(
    my_roster_id="me",
    partner_roster_id="partner",
    partner_name="KING TITUS",
    league_ready=True,
)

ready = builder.package_is_analyzable(
    st.session_state.get(assembly.SEND_KEY),
    st.session_state.get(assembly.RECEIVE_KEY),
)
st.markdown(
    f"<div data-toa-analyze-ready='{'1' if ready else '0'}'></div>",
    unsafe_allow_html=True,
)
if st.button("Analyze Trade", key="trade_analyzer_analyze", disabled=not ready):
    st.session_state["fixture_analysis_complete"] = True
    st.session_state["fixture_evaluated_send"] = list(
        st.session_state.get(assembly.SEND_KEY) or []
    )
    st.session_state["fixture_evaluated_receive"] = list(
        st.session_state.get(assembly.RECEIVE_KEY) or []
    )
st.button(
    "Reset package",
    key="trade_analyzer_reset",
    on_click=session_integrity.clear_trade_analyzer_package,
    args=(st.session_state,),
)
if st.session_state.get("fixture_analysis_complete"):
    st.success("Analysis complete")
