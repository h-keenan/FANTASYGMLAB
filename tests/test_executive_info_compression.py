"""Regression coverage for executive information compression (presentation only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import player_history, player_quick_view, recommendation_trust_ux
from modules import trade_hub_presentation
from modules.recommendation_trust_ux import RECOMMENDATION_TRUST_CSS


ROOT = Path(__file__).resolve().parents[1]


def _season_row(**overrides):
    row = {
        "stats_season": 2025,
        "games_played": 16,
        "fantasy_points_ppr": 240.0,
        "ppg": 15.0,
        "receptions": 70,
        "receiving_yards": 950,
        "receiving_tds": 8,
        "targets": 110,
        "target_share": 0.22,
        "position": "WR",
    }
    row.update(overrides)
    return pd.Series(row)


def test_executive_trade_detail_collapses_evidence_and_keeps_all_fields():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Fills the WR need.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Thin market conditions.",
            "Expected outcome": "Fair · Net +120",
            "Supporting metrics": "Strong fit · High confidence",
        },
        verdict="Fair",
        value_delta="+120",
        confidence="High confidence",
    )
    assert "dg-info-weight-verdict" in html
    assert "Fills the WR need." in html
    assert "Thin market conditions." in html
    assert "Partner has RB surplus." in html
    assert "Strong fit · High confidence" in html
    assert html.index("dg-info-weight-verdict") < html.index("Fills the WR need.")
    assert ">Reason<" not in html
    assert "Why this trade?" not in html
    assert "<details" not in html
    assert "Supporting evidence" not in html
    assert "Supporting metrics" not in html
    assert "tvl-cue--why" in html
    assert "tvl-cue--evidence" in html
    assert "tvl-cue--market" in html


def test_executive_trade_detail_can_omit_supporting_for_first_useful():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Fills the WR need.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Thin market conditions.",
            "Expected outcome": "Fair · Net +120",
            "Supporting metrics": "Strong fit · High confidence",
        },
        verdict="Fair",
        value_delta="+120",
        confidence="High confidence",
        include_supporting=False,
    )
    assert "Fills the WR need." in html
    assert "Thin market conditions." in html
    assert "Fair · Net +120" not in html or "Expected outcome" in html
    assert "Partner has RB surplus." not in html
    assert "Strong fit · High confidence" not in html
    assert "Why this trade?" not in html
    assert "<details" not in html
    assert "Supporting evidence" not in html
    supporting = recommendation_trust_ux.supporting_trade_detail_html(
        {
            "Evidence": "Partner has RB surplus.",
            "Supporting metrics": "Strong fit · High confidence",
        }
    )
    assert "Partner has RB surplus." in supporting
    assert "Strong fit · High confidence" in supporting
    assert "<details" not in supporting
    assert "tvl-cue--evidence" in supporting
