"""Synthetic AppTest surface for the production deferred-content boundary."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import deferred_rendering
from modules import workspace_ui


items = [
    {
        "label": f"League signal {index}",
        "value": f"Fixture team {index}",
        "note": "Synthetic secondary intelligence used only for payload measurement.",
        "tone": "power",
    }
    for index in range(1, 5)
]
table = pd.DataFrame(
    {
        "Player": [f"Synthetic Player {index}" for index in range(1, 51)],
        "Position": (["QB", "RB", "WR", "TE", "K"] * 10),
        "Value": list(range(10_000, 9_950, -1)),
    }
)


mode = str(st.query_params.get("mode", "deferred"))
st.header("Workspace shell")
st.caption("Primary content remains interactive before secondary content loads.")

if mode == "eager":
    workspace_ui.render_summary_tiles(items, compact=True)
    st.dataframe(table, hide_index=True, width="stretch")
    st.selectbox("Player explanation", table["Player"].tolist())
else:
    for section_id, label in (
        ("fixture_league_pulse", "Load League Pulse"),
        ("fixture_player_detail", "Load detailed player content"),
    ):
        if deferred_rendering.is_deferred_section_ready(st.session_state, section_id):
            if section_id.endswith("pulse"):
                workspace_ui.render_summary_tiles(items, compact=True)
            else:
                st.dataframe(table, hide_index=True, width="stretch")
                st.selectbox("Player explanation", table["Player"].tolist())
        else:
            st.button(
                label,
                key=deferred_rendering.deferred_state_key(section_id),
                on_click=deferred_rendering.mark_deferred_section_ready,
                args=(st.session_state, section_id),
            )
