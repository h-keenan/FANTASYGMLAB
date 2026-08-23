"""Roster-critical in-app delivery and Alerts hierarchy contracts."""

from __future__ import annotations

from pathlib import Path

from modules import alerts_activity
from modules import alerts_activity_ui
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


def test_fresh_my_player_injury_queues_once_and_preserves_alert_hierarchy(monkeypatch):
    session = {"account_user_id": "founder", "selected_league_id": "L1"}
    tile = _injury_tile()
    nc.publish_activity_inventory(session, [tile], league_id="L1")

    item = next(
        item
        for item in nc.compose_activity_inbox(session=session, league_id="L1")
        if item.player_id == "12527"
    )
    assert item.category == "URGENT"
    assert item.severity == "HIGH"
    assert item.roster_relationship == "MY_BENCH"
    assert item.status_unconfirmed is True

    calls = []
    monkeypatch.setattr(nc.st, "toast", lambda body, **kwargs: calls.append((body, kwargs)))
    assert nc.render_pending_urgent_delivery(session, league_id="L1") is not None
    assert "Roster alert" in calls[0][0]
    assert nc.render_pending_urgent_delivery(session, league_id="L1") is None

    # An identical Streamlit rerun cannot redeliver the same material event.
    nc.publish_activity_inventory(session, [tile], league_id="L1")
    assert nc.render_pending_urgent_delivery(session, league_id="L1") is None

    row = alerts_activity._row_from_notification(item)
    html = alerts_activity_ui.timeline_row_html(row)
    assert "dg-alerts-row--urgent" in html
    assert "MY PLAYER" in html
    assert "POTENTIALLY SIGNIFICANT INJURY" in html
    assert "STATUS NOT YET CONFIRMED" in html


def test_opponent_and_routine_news_do_not_trigger_roster_delivery():
    session = {"account_user_id": "founder", "selected_league_id": "L1"}
    opponent = _injury_tile(relationship="OPPONENT_STARTER", event_id="opp")
    routine = {
        **_injury_tile(event_id="routine"),
        "news_event_severity": "MEDIUM",
        "news_significant_injury_event": False,
    }
    nc.publish_activity_inventory(session, [opponent, routine], league_id="L1")
    items = nc.compose_activity_inbox(session=session, league_id="L1")
    assert all(item.category == "NEWS" for item in items if item.player_id == "12527")
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None


def test_delivery_is_scoped_by_league_and_cleared_during_switch():
    session = {"account_user_id": "founder", "selected_league_id": "L1"}
    tile = _injury_tile()
    nc.publish_activity_inventory(session, [tile], league_id="L1")
    assert nc.consume_pending_urgent_delivery(session, league_id="L2") is None

    session["selected_league_id"] = "L2"
    nc.publish_activity_inventory(session, [tile], league_id="L2")
    delivered = nc.consume_pending_urgent_delivery(session, league_id="L2")
    assert delivered is not None
    assert delivered["league_id"] == "L2"


def test_dashboard_places_high_news_in_immediate_action():
    tile = _injury_tile()
    briefing = dashboard_workflow.organize_dashboard_items(
        [tile], immediate_labels=frozenset({"News Alert"})
    )
    assert tuple(briefing.immediate) == (tile,)


def test_mobile_alert_contract_has_owned_width_and_normal_wrapping():
    css = (ROOT / "modules" / "alerts_activity_styles.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "@media (max-width:430px)" in css
    assert "minmax(0,1fr)" in css
    assert "overflow-wrap:anywhere" in css
    assert "notification_center.render_pending_urgent_delivery(" in app
