"""Synthetic Trade Board harness for responsive visual validation.

Run locally with:
    streamlit run scripts/trade_board_visual_harness.py

This test-only entry point renders production trade summaries with deterministic
synthetic data. It performs no authentication, persistence, or football work.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import trade_hub_ui
from modules.app_styles import APP_CSS
from modules.html_rendering import inject_global_styles


IDEAS = (
    {
        "partner_roster_id": "fixture-partner-a",
        "partner_team_name": "Lakefront Franchise",
        "tag": "Get Younger + Pick",
        "my_score": 8_540,
        "their_score": 9_028,
        "trade_gain": 488,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "Medium",
        "reasoning_summary": "Adds a younger weekly starter and future flexibility without sacrificing lineup stability.",
        "send_assets": [
            {"asset_type": "player", "player_id": "6794", "name": "Synthetic Veteran RB"},
        ],
        "receive_assets": [
            {"asset_type": "player", "player_id": "8155", "name": "Synthetic Young WR"},
            {"asset_type": "pick", "name": "2027 2nd"},
        ],
    },
    {
        "partner_roster_id": "fixture-partner-b",
        "partner_team_name": "Northside Football Ops",
        "tag": "Acquire Elite QB",
        "my_score": 11_200,
        "their_score": 11_040,
        "trade_gain": -160,
        "fit_grade": "Strong",
        "market_realism_label": "Thin Market",
        "trade_confidence_label": "Low",
        "reasoning_summary": "Consolidates depth into a premium quarterback while keeping the package inside a realistic range.",
        "send_assets": [
            {"asset_type": "player", "player_id": "7564", "name": "Synthetic Receiver"},
            {"asset_type": "pick", "name": "2027 1st"},
        ],
        "receive_assets": [
            {"asset_type": "player", "player_id": "4984", "name": "Synthetic Elite Quarterback"},
        ],
    },
)


def _render_idea(idea: dict, index: int) -> None:
    trade_hub_ui.render_trade_idea_card(
        idea,
        index,
        key_prefix="trade_board_visual_fixture",
        format_score=lambda value: f"{float(value):,.0f}",
        tidy_label=lambda value: str(value).replace("_", " ").title(),
        trade_target_reason=lambda _idea: "Synthetic target rationale.",
        trade_partner_reason=lambda _idea: "Synthetic partner rationale.",
        trade_confidence_reason=lambda _idea: "Synthetic confidence rationale.",
        trade_value_verdict=lambda _idea: "Balanced",
        trade_display_confidence_label=lambda _idea: "Medium",
        injury_display_context=lambda _asset: {"risk": False},
        glyph_chip_html=lambda *args, **kwargs: "",
        assets_html=lambda assets: "<div>Fixture detail assets: "
        + ", ".join(str(asset.get("name", "Asset")) for asset in assets)
        + "</div>",
    )


st.set_page_config(page_title="Trade Board visual fixture", layout="wide")
inject_global_styles(APP_CSS)
st.caption("Synthetic fixture only — no customer or production data")
st.title("Trade Board")
st.write("Visual fixture for compact, tappable recommendation summaries.")
for idea_index, fixture_idea in enumerate(IDEAS):
    _render_idea(fixture_idea, idea_index)

