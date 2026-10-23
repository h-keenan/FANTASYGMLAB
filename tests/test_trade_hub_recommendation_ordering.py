"""Trade Hub surface ranking and presentation order contracts."""

from __future__ import annotations

from pathlib import Path

from modules import premium, trade_hub_presentation, trade_ideas
from scripts.profile_trade_hub import FixtureSpec, build_fixture, run_trade_hub


ROOT = Path(__file__).resolve().parents[1]


def _ident(idea: dict) -> tuple:
    return (
        str(idea.get("partner_team_name") or ""),
        str(idea.get("tag") or ""),
        int(idea.get("trade_gain") or 0),
        tuple(str(asset.get("player_id") or "") for asset in (idea.get("send_assets") or [])),
        tuple(str(asset.get("player_id") or "") for asset in (idea.get("receive_assets") or [])),
    )


def test_trade_surface_sort_key_prefers_headline_primary_and_confidence():
    weaker = {
        "trade_headline_ready": False,
        "trade_surface_tier": "secondary",
        "trade_confidence_label": "Medium",
        "market_realism_score": 90,
        "fit_score": 90,
        "partner_fit_score": 90,
        "strategy_fit_score": 90,
        "priority": 90,
    }
    stronger = {
        "trade_headline_ready": True,
        "trade_surface_tier": "primary",
        "trade_confidence_label": "High",
        "market_realism_score": 10,
        "fit_score": 10,
        "partner_fit_score": 10,
        "strategy_fit_score": 10,
        "priority": 10,
    }
    assert trade_ideas._trade_surface_sort_key(stronger) > trade_ideas._trade_surface_sort_key(
        weaker
    )
