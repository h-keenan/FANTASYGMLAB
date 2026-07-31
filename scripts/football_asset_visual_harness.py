"""Deterministic, synthetic visual harness for the canonical player asset."""

import streamlit as st

from modules.app_styles import APP_CSS
from modules.football_assets import FootballPlayerAsset, player_card_html


st.set_page_config(page_title="Football Asset Harness", layout="wide")
st.markdown(APP_CSS, unsafe_allow_html=True)
st.title("Football Asset Harness")

samples = (
    FootballPlayerAsset(
        "synthetic-elite",
        "Long Synthetic Player Name",
        "QB",
        "MIN",
        "Elite",
        "elite",
        value_label="Dynasty Score",
        value="98",
        insight="Cornerstone asset with an established role.",
        age="Age 24",
    ),
    FootballPlayerAsset(
        "synthetic-injured",
        "Synthetic Injured Player",
        "RB",
        "SEA",
        "Contributor",
        "contributor",
        status="IR",
        value_label="Dynasty Score",
        value="64",
        insight="Current status is shown without changing valuation context.",
        age="Age 27",
    ),
    FootballPlayerAsset(
        "",
        "Synthetic Read Only Player",
        "WR",
        "FA",
        "Development",
        "development",
        value_label="Dynasty Score",
        value="41",
        age="Age 22",
    ),
)

for density in ("compact", "standard", "dense"):
    st.subheader(density.title())
    st.markdown(
        "".join(
            player_card_html(
                sample,
                density=density,
                mode="action-enabled" if sample.player_id else "read-only",
            )
            for sample in samples
        ),
        unsafe_allow_html=True,
    )
