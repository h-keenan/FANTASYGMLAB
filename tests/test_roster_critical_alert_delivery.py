"""Roster-critical in-app delivery and Alerts hierarchy contracts."""

from __future__ import annotations

from pathlib import Path

from modules import alerts_activity
from modules import dashboard_workflow
from modules import notification_center as nc


ROOT = Path(__file__).resolve().parents[1]


def _injury_tile(*, relationship: str = "MY_BENCH", event_id: str = "injury-1"):
    return {
        "label": "News Alert",
        "value": "Ashton Jeanty: Injury update",
        "note": "Potentially significant injury event affecting your roster.",
        "recommendation_id": f"news-event:{event_id}",
        "route_key": "player_quick_view",
        "route_player_id": "12527",
        "player_id": "12527",
        "news_player_name": "Ashton Jeanty",
        "news_event_type": "INJURY",
        "news_event_severity": "HIGH",
        "news_roster_relationship": relationship,
        "news_age_seconds": 120,
        "news_age_label": "2 minutes ago",
        "news_corroboration": "AWAITING STATUS UPDATE",
        "news_significant_injury_event": True,
        "should_alert": True,
    }


def test_dashboard_places_high_news_in_immediate_action():
    tile = _injury_tile()
    briefing = dashboard_workflow.organize_dashboard_items(
        [tile], immediate_labels=frozenset({"News Alert"})
    )
    assert tuple(briefing.immediate) == (tile,)
