"""Fixture-backed visual harness for My Team's Roster Core / Depth rows.

Run locally with:
    streamlit run scripts/my_team_visual_harness.py

This file is test-only. It uses synthetic roster rows and the production
renderer (app.render_player_scan_cards, the same module-level wrapper the
real My Team route calls for Roster Core/Depth), with the same
show_age=False / show_reason=False / show_overall_rating=True flags the
real route now passes (coridian_, 2026-10-13: "for my team it should just
be the quick view card of the player ... name, ring, overall, position,
that's really it") — so what renders here is byte-identical to a real
session's compact roster row.

Value-score magnitudes are drawn from data/players.db's real scale
(top dynasty assets run ~7000-9700, a solid bench piece ~1500-4000) rather
than unrealistic 2-digit placeholders — see PR #1028's identical Waivers
fixture fix for why that matters (a 2-digit value score reads as an OVR
rating, not a value score).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app
from modules.app_styles import APP_CSS
from modules.html_rendering import inject_global_styles
from modules.my_team_decision_styles import MY_TEAM_DECISION_CSS

STARTERS = pd.DataFrame(
    [
        {
            "player_id": "7564",
            "name": "Bijan Robinson",
            "position": "RB",
            "team": "ATL",
            "age": 23,
            "slot": "RB",
            "value_score": 9681,
            "player_tier": "Elite",
            "opportunity_label": "Bell Cow",
            "opportunity_explanation": "Workhorse back in a top-tier offense — should never render inline anymore.",
            "canonical_overall_rank": 2,
            "canonical_position_rank": 1,
            "_overall_rating_col": 98,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "",
        },
        {
            "player_id": "9509",
            "name": "Ja'Marr Chase",
            "position": "WR",
            "team": "CIN",
            "age": 25,
            "slot": "WR",
            "value_score": 9266,
            "player_tier": "Elite",
            "opportunity_label": "Target Monster",
            "opportunity_explanation": "Alpha WR1, should never render inline anymore.",
            "canonical_overall_rank": 3,
            "canonical_position_rank": 1,
            "_overall_rating_col": 97,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "",
        },
        {
            "player_id": "11566",
            "name": "Brock Bowers",
            "position": "TE",
            "team": "LV",
            "age": 22,
            "slot": "TE",
            "value_score": 7847,
            "player_tier": "Elite",
            "opportunity_label": "Target Monster",
            "canonical_overall_rank": 9,
            "canonical_position_rank": 1,
            "_overall_rating_col": 95,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "Questionable",
        },
        {
            "player_id": "4866",
            "name": "Jonathan Taylor",
            "position": "RB",
            "team": "IND",
            "age": 26,
            "slot": "FLEX",
            "value_score": 7459,
            "player_tier": "Star",
            "opportunity_label": "Bell Cow",
            "canonical_overall_rank": 12,
            "canonical_position_rank": 4,
            "_overall_rating_col": 89,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "",
        },
        {
            "player_id": "6945",
            "name": "CeeDee Lamb",
            "position": "WR",
            "team": "DAL",
            "age": 26,
            "slot": "WR",
            "value_score": 7399,
            "player_tier": "Star",
            "opportunity_label": "Target Monster",
            "canonical_overall_rank": 14,
            "canonical_position_rank": 6,
            "_overall_rating_col": 88,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "",
        },
        {
            "player_id": "5849",
            "name": "Patrick Mahomes",
            "position": "QB",
            "team": "KC",
            "age": 30,
            "slot": "QB",
            "value_score": 4210,
            "player_tier": "Core Starter",
            "opportunity_label": "Starter",
            "canonical_overall_rank": 28,
            "canonical_position_rank": 3,
            "_overall_rating_col": 82,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "",
        },
    ]
)

BENCH = pd.DataFrame(
    [
        {
            "player_id": "11004",
            "name": "Alvin Kamara",
            "position": "RB",
            "team": "NO",
            "age": 30,
            "slot": "RB",
            "value_score": 3912,
            "player_tier": "Contributor",
            "opportunity_label": "Committee Back",
            "canonical_overall_rank": 64,
            "canonical_position_rank": 22,
            "_overall_rating_col": 61,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "",
        },
        {
            "player_id": "10859",
            "name": "DeVonta Smith",
            "position": "WR",
            "team": "PHI",
            "age": 27,
            "slot": "WR",
            "value_score": 3851,
            "player_tier": "Contributor",
            "opportunity_label": "Backup With Upside",
            "canonical_overall_rank": 70,
            "canonical_position_rank": 31,
            "_overall_rating_col": 58,
            "injury_level": "minor",
            "status": "",
            "injury_status": "Questionable",
        },
        {
            "player_id": "8130",
            "name": "Gunnar Helm",
            "position": "TE",
            "team": "TEN",
            "age": 23,
            "slot": "TE",
            "value_score": 3721,
            "player_tier": "Development",
            "opportunity_label": "Rising",
            "canonical_overall_rank": 80,
            "canonical_position_rank": 9,
            "_overall_rating_col": 55,
            "injury_level": "healthy",
            "status": "",
            "injury_status": "",
        },
    ]
)


def main() -> None:
    st.set_page_config(
        page_title="My Team Visual Harness",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_styles(APP_CSS)
    inject_global_styles(MY_TEAM_DECISION_CSS)
    st.session_state.setdefault("selected_league_id", "visual-league")
    st.title("My Team Visual Harness")
    st.caption(
        "Synthetic fixture only. No production account, league, roster, "
        "player, or entitlement data is loaded."
    )
    st.markdown("#### Roster Core")
    with st.container(key="my_team_roster_core"):
        app.render_player_scan_cards(
            STARTERS,
            score_field="value_score",
            title="Starters",
            note="Projected core group",
            max_items=len(STARTERS),
            show_slot=True,
            status_label="Core",
            compact=True,
            enable_quick_view=False,
            show_header=False,
            design_system=True,
            show_age=False,
            show_reason=False,
            show_overall_rating=True,
        )
    st.markdown("#### Depth")
    with st.expander(
        f"Key backups | {len(BENCH)}", expanded=True, key="my_team_key_backups"
    ):
        app.render_player_scan_cards(
            BENCH,
            score_field="value_score",
            title="Key Backups",
            note="First bench players who become meaningful if injuries or lineup changes hit.",
            max_items=len(BENCH),
            status_label="Hold",
            compact=True,
            enable_quick_view=False,
            show_header=False,
            design_system=True,
            show_age=False,
            show_reason=False,
            show_overall_rating=True,
        )


if __name__ == "__main__":
    main()
