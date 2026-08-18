"""Deterministic Streamlit harness for the canonical player dossier."""

import pandas as pd
import streamlit as st

from modules.app_styles import APP_CSS
from modules import player_history, player_awards, player_quick_view
from modules.player_tier_identity import resolve_player_tier_identity


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
    stats = player_quick_view.build_stats_view(PLAYER)
    st.markdown(
        player_quick_view.pqv_hero_html(
            avatar_html="<div class='player-quick-view-avatar' aria-hidden='true'>SP</div>",
            name="Synthetic Player",
            position="WR",
            team="CHI",
            age_text="24",
            source_label="Fixture Roster",
            role_label="Featured",
            overall_display="#14",
            position_display="WR #6",
            dynasty_value="8,420",
            scoring_format="",
            signal_badges=(),
            identity=resolve_player_tier_identity(stored_tier="Star"),
            include_tier_legend=True,
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        player_quick_view.recommendation_context_html(
            "Stable role and current production support the existing assessment.",
            "",
            action="Hold",
            confidence="High confidence",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='pqv-decision-grid'>"
        "<div class='pqv-decision-primary'>"
        + (player_quick_view.current_season_summary_html(stats) or "")
        + "</div>"
        "<div class='pqv-decision-secondary'>"
        + player_quick_view.why_this_recommendation_html(
            player_quick_view.compose_fantasygm_read_factors(
                why="Stable role and current production support the existing assessment.",
                team_fit="No immediate pressure to move",
                skip_values=("Featured",),
            )
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )
    award_badges = player_awards.build_player_awards(history_rows, position="WR")
    career = player_quick_view.career_dossier_html(
        badges=player_awards.select_display_badges(award_badges),
        overflow=player_awards.remaining_badges(award_badges),
        years_exp=3,
        position="WR",
    )
    if career:
        st.markdown(career, unsafe_allow_html=True)
    st.button("Open in Trade Hub", use_container_width=True)
    st.button("Share Recommendation", use_container_width=True)
    st.button("Feedback", use_container_width=True)
    detail = str(st.session_state.get("dossier_detail") or "")

    def _set_detail(label: str) -> None:
        current = str(st.session_state.get("dossier_detail") or "")
        st.session_state["dossier_detail"] = "" if current == label else label

    cols = st.columns(3, gap="small")
    for column, label in zip(cols, ("STATS", "CAREER", "MODEL")):
        with column:
            st.button(label, use_container_width=True, type="secondary", on_click=_set_detail, args=(label,))
    if detail == "STATS":
        player_quick_view.render_current_season(stats)
    if detail == "CAREER":
        st.markdown(
            player_quick_view.career_timeline_html(
                resume,
                expanded=True,
                include_achievements=False,
                skip_current_season=True,
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            player_quick_view.compact_bio_html(
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
        player_quick_view.render_news(
            [
                player_quick_view.NewsItem(
                    headline="Synthetic Player retained a full-time role.",
                    source="ESPN",
                    freshness="2h",
                    snippet="Depth-chart notes remain stable.",
                    url="https://www.espn.com/example",
                )
            ],
            include_shell=True,
            status="ok",
            omit_empty=True,
        )
        st.caption("Technical roster and valuation context.")


render_dossier()
