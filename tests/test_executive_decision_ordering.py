"""Contracts for executive decision ordering and command-bar cohesion."""

from pathlib import Path

from modules import premium, trade_hub_presentation


ROOT = Path(__file__).resolve().parents[1]


def test_presentation_order_uses_gain_only_as_final_tiebreak():
    tied = [
        {
            "tag": "Lower gain twin",
            "partner_team_name": "B",
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "High",
            "market_realism_score": 80,
            "fit_score": 80,
            "partner_fit_score": 80,
            "strategy_fit_score": 80,
            "priority": 50,
            "trade_gain": 10,
            "send_assets": [{"player_id": "s1"}],
            "receive_assets": [{"player_id": "r1"}],
            "reasoning_summary": "Same surface strength, smaller delta",
        },
        {
            "tag": "Higher gain twin",
            "partner_team_name": "A",
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "High",
            "market_realism_score": 80,
            "fit_score": 80,
            "partner_fit_score": 80,
            "strategy_fit_score": 80,
            "priority": 50,
            "trade_gain": 40,
            "send_assets": [{"player_id": "s2"}],
            "receive_assets": [{"player_id": "r2"}],
            "reasoning_summary": "Same surface strength, larger delta",
        },
    ]
    ordered = trade_hub_presentation.order_trade_hub_visible_ideas(tied)
    assert [idea["tag"] for idea in ordered] == [
        "Higher gain twin",
        "Lower gain twin",
    ]
