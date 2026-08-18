from __future__ import annotations

import pandas as pd
import streamlit as st

from modules import trade_analyzer_assembly as assembly
from modules import trade_analyzer_builder as builder
from modules import trade_analyzer_ui
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

st.session_state.setdefault(assembly.SEND_KEY, [])
st.session_state.setdefault(assembly.RECEIVE_KEY, [])
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
    partner_name="Fixture Partner",
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
if st.session_state.get("fixture_analysis_complete"):
    st.success("Analysis complete")
