"""Fixture-backed visual harness for the Waivers page's player cards.

Run locally with:
    streamlit run scripts/waivers_visual_harness.py

This file is test-only. It uses synthetic free-agent rows and the production
renderer (modules.waivers_ui.render_free_agent_cards, wired through app.py's
own module-level wrapper exactly as the real Waivers route calls it) so the
avatar ring / position pill / name treatment shown here is byte-identical to
what a real session renders.
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


FREE_AGENTS = pd.DataFrame(
    [
        {
            "player_id": "9221",
            "name": "Emanuel Wilson",
            "position": "RB",
            "team": "GB",
            "age": 24,
            "dynasty_score": 78,
            "value_score": 78,
            "stale_free_agent": False,
            "injury_replacement_fit": True,
            "injury_replacement_note": "Healthy injury replacement at RB for a starter spot your roster is already sweating.",
            "opportunity_label": "Committee Back",
            "opportunity_explanation": "Shares an uncertain backfield but has flashed standalone value.",
            "position_rank": 1,
            "overall_rank": 4,
            "player_tier": "contributor",
            "canonical_overall_rank": 48,
            "canonical_position_rank": 9,
            "opportunity_confidence": "Medium",
            "sleeper_trending_add": True,
            "sleeper_trending_add_count": 3200,
            "sleeper_trending_add_rank": 5,
            "priority_need_fit": True,
            "priority_value_opportunity": False,
            "status": "",
            "injury_status": "",
        },
        {
            "player_id": "8155",
            "name": "Pat Bryant",
            "position": "WR",
            "team": "DEN",
            "age": 22,
            "dynasty_score": 71,
            "value_score": 71,
            "stale_free_agent": False,
            "injury_replacement_fit": False,
            "opportunity_label": "Backup With Upside",
            "opportunity_explanation": "Young receiver flashing on early-down snaps behind the starter.",
            "position_rank": 2,
            "overall_rank": 7,
            "player_tier": "development",
            "canonical_overall_rank": 92,
            "canonical_position_rank": 21,
            "opportunity_confidence": "Medium",
            "sleeper_trending_add": False,
            "priority_need_fit": False,
            "priority_value_opportunity": True,
            "status": "",
            "injury_status": "",
        },
        {
            "player_id": "6794",
            "name": "Tyrone Tracy",
            "position": "RB",
            "team": "NYG",
            "age": 26,
            "dynasty_score": 55,
            "value_score": 55,
            "stale_free_agent": False,
            "injury_replacement_fit": False,
            "opportunity_label": "Starter At Risk",
            "opportunity_explanation": "Lead-role upside if the current starter misses time.",
            "position_rank": 3,
            "overall_rank": 11,
            "player_tier": "starter",
            "canonical_overall_rank": 110,
            "canonical_position_rank": 28,
            "opportunity_confidence": "Low",
            "sleeper_trending_add": False,
            "priority_need_fit": False,
            "priority_value_opportunity": False,
            "status": "Q",
            "injury_status": "Questionable",
        },
    ]
)


def main() -> None:
    st.set_page_config(
        page_title="Waivers Visual Harness",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_styles(APP_CSS)
    st.session_state.setdefault("selected_league_id", "visual-league")
    st.title("Waivers Visual Harness")
    st.caption(
        "Synthetic fixture only. No production account, league, roster, "
        "player, or entitlement data is loaded."
    )
    app.render_free_agent_cards(
        FREE_AGENTS,
        "dynasty_score",
        max_items=6,
        needed_positions=["RB", "WR"],
        key_prefix="visual_waiver_priority",
    )


if __name__ == "__main__":
    main()
