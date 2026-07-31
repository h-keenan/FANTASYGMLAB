"""Deterministic Streamlit harness for League Intelligence presentation."""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.app_styles import APP_CSS
from modules import football_assets
from modules import league_intelligence
from modules import league_intelligence_ui


NOW = datetime(2026, 7, 31, 12, 0).timestamp()
PLAYERS = pd.DataFrame(
    [
        {
            "player_id": "synthetic-owned",
            "name": "Synthetic Owned Player",
            "position": "WR",
            "team": "MIN",
            "age": 25,
            "value_score": 80,
        },
        {
            "player_id": "synthetic-waiver",
            "name": "Synthetic Waiver Player",
            "position": "RB",
            "team": "SEA",
            "age": 23,
            "value_score": 58,
        },
    ]
)
NEWS = [
    {
        "title": "Synthetic Owned Player limited at practice",
        "matched_player": "Synthetic Owned Player",
        "published_ts": NOW - 900,
        "source": "Fixture Wire",
        "summary": "The player was limited during the latest practice.",
        "relevance_reason": "injury/status",
        "link": "https://example.com/owned",
    },
    {
        "title": "Synthetic Waiver Player earns a larger role",
        "matched_player": "Synthetic Waiver Player",
        "published_ts": NOW - 3600,
        "source": "Fixture Wire",
        "summary": "The available player worked with the first unit.",
        "relevance_reason": "role/depth chart",
        "link": "https://example.com/waiver",
    },
]


def summary(item, max_chars):
    return str(item.get("summary") or "")[:max_chars]


def relative(item):
    return "15m ago" if item["matched_player"] == "Synthetic Owned Player" else "1h ago"


def player_card(row, **_kwargs):
    return football_assets.player_card_html(
        football_assets.FootballPlayerAsset(
            player_id=str(row["player_id"]),
            display_name=str(row["name"]),
            position=str(row["position"]),
            team=str(row["team"]),
            prestige_label="Contributor",
            prestige_level="contributor",
            value_label="Dynasty Score",
            value=str(row["value_score"]),
            age=f"Age {row['age']}",
        ),
        density="dense",
    )


def render_tappable(*, html, **_kwargs):
    st.markdown(html, unsafe_allow_html=True)
    return ""


st.set_page_config(page_title="League Intelligence Harness", layout="wide")
st.markdown(APP_CSS, unsafe_allow_html=True)
st.title("League Intelligence Harness")
feed = league_intelligence.build_league_intelligence_feed(
    NEWS,
    PLAYERS,
    roster_player_map={"1": ("synthetic-owned",)},
    roster_names={"1": "Synthetic Franchise"},
    current_roster_id="1",
    summary_builder=summary,
    relative_time_builder=relative,
    now_timestamp=NOW,
)
league_intelligence_ui.render_league_intelligence_feed(
    feed,
    score_field="value_score",
    score_label="Dynasty Score",
    player_card_builder=player_card,
    render_tappable_player_html=render_tappable,
    open_player_quick_view=lambda *_args, **_kwargs: None,
)
