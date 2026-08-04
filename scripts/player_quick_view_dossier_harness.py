"""Deterministic Streamlit harness for the canonical player dossier."""

import pandas as pd
import streamlit as st

from modules.app_styles import APP_CSS
from modules import player_history, player_quick_view


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
    history_rows = [
        PLAYER.to_dict(),
        {
            **PLAYER.to_dict(),
            "stats_season": 2024,
            "games_played": 17,
            "receiving_yards": 1532,
            "receiving_tds": 12,
            "fantasy_points_ppr": 302.4,
            "ppg": 17.8,
            "position_finish": 4,
        },
        {
            **PLAYER.to_dict(),
            "stats_season": 2023,
            "games_played": 15,
            "receiving_yards": 1040,
            "receiving_tds": 7,
            "fantasy_points_ppr": 231.2,
            "ppg": 15.4,
            "position_finish": 11,
        },
    ]
    resume = player_history.build_career_resume(
        history_rows,
        position="WR",
        current_season=2025,
        source_note="Synthetic verified regular-season fixture.",
        historical_cache_loaded=True,
    )
    expanded = bool(st.session_state.get("dossier_history_expanded", False))
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
        player_quick_view.executive_snapshot_html(
            player_quick_view.ExecutiveSnapshot(
                years_in_league="3 seasons",
                draft_capital="2023 / Round 1 / Pick 18",
                college="Fixture State",
                height="6'2\"",
                weight="205 lb",
                bye_week="7",
            )
        ),
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
    st.markdown(
        player_quick_view.recommendation_context_html(
            "Stable role and current production support the existing assessment.",
            "The active roster has no immediate pressure to move this player.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        player_quick_view.career_resume_html(resume, expanded=expanded),
        unsafe_allow_html=True,
    )
    if st.button(
        "Collapse career history" if expanded else "View full career resume",
        use_container_width=True,
    ):
        st.session_state["dossier_history_expanded"] = not expanded
        st.rerun()
    st.markdown(
        player_quick_view.career_timeline_html(resume, expanded=expanded),
        unsafe_allow_html=True,
    )
    player_quick_view.render_current_season(PLAYER)
    st.button("Open in Trade Hub", use_container_width=True)
    with st.expander("Advanced Details", expanded=False):
        player_quick_view.render_news(
            [player_quick_view.NewsItem("Synthetic Player retained a full-time role.")]
        )
        st.caption("Technical roster and valuation context.")


render_dossier()
