"""Deterministic Streamlit harness for the canonical player dossier."""

import pandas as pd
import streamlit as st

from modules.app_styles import APP_CSS
from modules import player_quick_view


PLAYER = pd.Series(
    {
        "player_id": "synthetic-player",
        "name": "Synthetic Player",
        "position": "WR",
        "team": "CHI",
        "age": 24,
        "stats_season": 2025,
        "games_played": 17,
        "targets": 121,
        "receptions": 78,
        "receiving_yards": 1088,
        "receiving_tds": 8,
        "fantasy_points_ppr": 235.8,
        "fantasy_points_half_ppr": 196.8,
        "fantasy_points": 157.8,
        "ppg": 13.9,
        "snap_share": 0.82,
        "target_share": 0.24,
    }
)

st.set_page_config(page_title="Player Dossier Harness", layout="wide")
st.markdown(APP_CSS, unsafe_allow_html=True)


@st.dialog("Front Office Dossier", width="large")
def render_dossier() -> None:
    st.markdown(
        "<section class='player-quick-view-shell dg-quick-view-panel'>"
        "<div class='player-quick-view-header-band player-quick-view-hero'>"
        "<div class='player-quick-view-avatar' aria-hidden='true'>SP</div>"
        "<div class='player-quick-view-copy'>"
        "<div class='player-quick-view-source'>Fixture Roster</div>"
        "<h3 class='player-quick-view-name'>Synthetic Player</h3>"
        "<div class='player-quick-view-meta'>WR | CHI | Age 24</div>"
        "<div class='player-quick-view-primary-row'>Active | Healthy</div>"
        "</div></div></section>",
        unsafe_allow_html=True,
    )
    st.markdown(
        player_quick_view.snapshot_html(
            player_quick_view.DossierSnapshot(
                dynasty_value="8,420",
                rank="#14",
                position_rank="#6 WR",
                fantasy_ppg="13.9",
                tier="Starter",
                recommendation="Hold",
                trend="Stable",
                recommendation_note="A reliable core asset under the current roster lens.",
            )
        ),
        unsafe_allow_html=True,
    )
    player_quick_view.render_current_season(PLAYER)
    st.markdown(
        player_quick_view.recommendation_context_html(
            "Stable role and current production support the existing assessment.",
            "The active roster has no immediate pressure to move this player.",
        ),
        unsafe_allow_html=True,
    )
    player_quick_view.render_news(
        [player_quick_view.NewsItem("Synthetic Player retained a full-time role.")]
    )
    st.button("Open in Trade Hub", use_container_width=True)
    with st.expander("Advanced Details", expanded=False):
        st.caption("Technical roster and valuation context.")
        st.markdown(
            player_quick_view.career_profile_html(player_quick_view.CareerProfile()),
            unsafe_allow_html=True,
        )


render_dossier()
