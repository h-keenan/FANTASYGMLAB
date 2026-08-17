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


def test_game_plan_owns_current_actions_when_present():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert "if not game_plan_present:" in source
    assert source.index("render_todays_game_plan()") < source.index("render_what_changed()")
    assert source.index("render_what_changed()") < source.index(
        'render_section_header("League Insights"'
    )


def test_primary_card_accent_lives_in_scoped_game_plan_css():
    css = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "dg-game-plan-card-primary" in css
    assert "CATEGORY_TOP_PRIORITY" in css or "top_priority" in css


def test_dashboard_inventory_routes_preserve_destination_owners():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    home = source.split("def render_home_dashboard(", 1)[1]
    assert '"route_key": "trade_hub"' in home
    assert '"route_key": "waivers"' in home
    assert home.count('"route_key": "my_team"') >= 2


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
