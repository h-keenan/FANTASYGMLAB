"""Deterministic browser harness for native/clipboard Trade Share UX."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import share_recommendation_cards as share
from modules import share_recommendation_ui


IDEA = {
    "partner_team_name": "Tongue Punchers",
    "send_assets": [
        {"asset_type": "player", "player_id": "1", "name": "Tank Bigsby"},
        {"asset_type": "pick", "name": "2027 Round 3"},
    ],
    "receive_assets": [
        {"asset_type": "player", "player_id": "2", "name": "Omar Cooper"},
    ],
    "trade_gain": -991,
    "fit_grade": "Strong Fit",
    "trade_confidence_label": "Medium",
    "reasoning_summary": "Tongue Punchers gets RB help and moves from WR surplus.",
}

card = share.build_trade_share_card(IDEA, source_surface="trade_review")
text = share.build_share_text_payload(card)

st.set_page_config(page_title="Trade Share UX fixture", layout="centered")
st.caption("Synthetic fixture only — no customer or production data")
st.title("Trade Share Idea")
st.code(text)
components.html(
    share_recommendation_ui.native_share_markup(
        b"\x89PNG\r\n\x1a\n",
        file_name="fantasygmlab-trade-fixture.png",
        title=card.title,
        text=text,
        button_label=share.TRADE_HUB_SHARE_LABEL,
    ),
    height=52,
)
