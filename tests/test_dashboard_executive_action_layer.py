"""Dashboard executive action layer — presentation hierarchy (#201)."""

from __future__ import annotations

from pathlib import Path

from modules import daily_gm_briefing
from modules import dashboard_workflow

ROOT = Path(__file__).resolve().parents[1]


def test_executive_action_layer_doc_exists():
    doc = (ROOT / "docs" / "dashboard-executive-action-layer.md").read_text(encoding="utf-8")
    assert "Top Priority" in doc
    assert "Your Next Move" in doc
    assert "REMOVE" in doc
    assert "handoff" in doc.casefold()


def test_compose_still_dedupes_by_recommendation_id():
    briefing = dashboard_workflow.organize_dashboard_items(
        [
            {
                "label": "Top Trade Opportunity",
                "value": "Partner A",
                "note": "Primary",
                "recommendation_id": "rec-1",
                "route_key": "trade_hub",
            },
            {
                "label": "Top Waiver Opportunity",
                "value": "Player B",
                "note": "Wire",
                "recommendation_id": "rec-2",
                "route_key": "waivers",
            },
            {
                "label": "Top Trade Opportunity",
                "value": "Partner A",
                "note": "Duplicate intel",
                "recommendation_id": "rec-1",
                "route_key": "trade_hub",
            },
        ]
    )
    plan = daily_gm_briefing.compose_daily_gm_briefing(
        briefing,
        entitlement="premium",
    )
    ids = [item.recommendation_id for item in plan.items if item.recommendation_id]
    assert ids.count("rec-1") == 1
    assert plan.items[0].category == daily_gm_briefing.CATEGORY_TOP_PRIORITY
