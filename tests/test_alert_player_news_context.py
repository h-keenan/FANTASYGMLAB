"""Canonical Alert -> player focus -> PQV news-context contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import app
from modules import news_intelligence
from modules import notification_center as nc
from modules import player_cards
from modules import alerts_activity
from modules import alerts_activity_ui


ROOT = Path(__file__).resolve().parents[1]
JEANTY_ID = "12527"


def _tile(*, source_url: str = "https://example.com/jeanty-report") -> dict:
    return {
        "label": "News Alert",
        "value": "Ashton Jeanty injury update",
        "note": "A potentially significant injury was reported.",
        "recommendation_id": "news-event:12527:injury_chain",
        "route_key": "my_team",
        "route_player_id": JEANTY_ID,
        "player_id": JEANTY_ID,
        "news_player_name": "Ashton Jeanty",
        "news_event_type": "INJURY",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_event_time": 2_000_000_000.0,
        "news_age_seconds": 120,
        "news_age_label": "2m",
        "news_corroboration": "AWAITING STATUS UPDATE",
        "news_corroboration_note": "Player status has not yet been confirmed.",
        "news_significant_injury_event": True,
        "news_source": "Fixture Wire",
        "source_url": source_url,
        "news_article_title": "Ashton Jeanty injury update",
        "should_alert": True,
    }


def _state(tile: dict | None = None) -> dict:
    state = {"account_user_id": "founder", "selected_league_id": "L1"}
    nc.publish_activity_inventory(state, [tile or _tile()], league_id="L1")
    return state


def test_news_alert_tile_preserves_existing_canonical_source_fields():
    event = news_intelligence.FootballEvent(
        event_type="INJURY",
        player_name="Ashton Jeanty",
        player_id=JEANTY_ID,
        source="Fixture Wire",
        source_url="https://example.com/jeanty-report",
        article_title="Ashton Jeanty injury update",
    )
    tile = news_intelligence.NewsAlert(
        event=event,
        severity="HIGH",
        should_alert=True,
        title="Ashton Jeanty injury update",
        body="Report",
        why_care="Affects your starter.",
        action_hint="Review roster.",
    ).as_tile()
    assert tile["news_source"] == "Fixture Wire"
    assert tile["source_url"] == "https://example.com/jeanty-report"
    assert tile["news_article_title"] == "Ashton Jeanty injury update"


def test_same_canonical_event_resolves_for_player_and_dedupes():
    state = _state()
    nc.publish_activity_inventory(state, [_tile()], league_id="L1")
    records = nc.canonical_player_event_records(
        state,
        league_id="L1",
        player_id=JEANTY_ID,
        event_id="rec:news-event:12527:injury_chain",
    )
    assert len(records) == 1
    assert records[0]["source_url"] == "https://example.com/jeanty-report"
    assert records[0]["news_corroboration"] == "AWAITING STATUS UPDATE"
    item = next(
        item
        for item in nc.compose_activity_inbox(
            session=state,
            league_id="L1",
            include_product_update=False,
            header_cap=False,
        )
        if item.player_id == JEANTY_ID
    )
    row = alerts_activity._row_from_notification(item)
    assert row["source_url"] == "https://example.com/jeanty-report"
    assert "href='https://example.com/jeanty-report'" in alerts_activity_ui.timeline_row_html(row)


def test_toast_delivery_is_once_and_does_not_mark_event_read(monkeypatch):
    state = _state()
    opened = []
    buttons = []
    monkeypatch.setattr(nc.st, "toast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        nc.st,
        "button",
        lambda label, **kwargs: buttons.append((label, kwargs)),
    )
    record = nc.render_pending_urgent_delivery(
        state,
        league_id="L1",
        on_open_item=lambda item: opened.append(item.id),
    )
    assert record is not None
    assert buttons[0][0] == "Review Ashton Jeanty"
    assert not nc.is_notification_read(state, str(record["id"]), league_id="L1")
    assert nc.render_pending_urgent_delivery(state, league_id="L1") is None


def test_player_event_focus_is_league_scoped_and_consumed_once():
    state: dict = {}
    assert nc.queue_player_event_focus(
        state,
        league_id="L1",
        player_id=JEANTY_ID,
        event_id="rec:event-1",
    )
    assert nc.peek_player_event_focus(state, league_id="L2") is None
    assert nc.peek_player_event_focus(state, league_id="L1") == {
        "league_id": "L1",
        "player_id": JEANTY_ID,
        "event_id": "rec:event-1",
    }
    assert nc.consume_player_event_focus(state, league_id="L1") is not None
    assert nc.consume_player_event_focus(state, league_id="L1") is None


def test_notification_open_queues_exact_my_team_player_and_event(monkeypatch):
    state = _state()
    item = next(
        item
        for item in nc.compose_activity_inbox(
            session=state,
            league_id="L1",
            include_product_update=False,
            header_cap=False,
        )
        if item.player_id == JEANTY_ID
    )
    fake_st = SimpleNamespace(session_state=state)
    monkeypatch.setattr(app, "st", fake_st)
    monkeypatch.setattr(app, "_clear_player_quick_view", lambda: None)
    monkeypatch.setattr(app.trade_detail_navigation, "close", lambda _state: None)
    monkeypatch.setattr(app, "_capture_workflow_handoff", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_queue_platform_route", lambda *_args, **_kwargs: None)

    app._open_notification_item(item)

    focus = nc.peek_player_event_focus(state, league_id="L1")
    assert focus is not None
    assert focus["player_id"] == JEANTY_ID
    assert focus["event_id"] == item.id
    assert state["_navigation_scroll_reset_pending"]["anchor"] == "my-team-player-focus"
    assert nc.is_notification_read(state, item.id, league_id="L1")
    # Read is presentation state, not football resolution.
    assert JEANTY_ID in nc.active_roster_injury_attention(
        state,
        league_id="L1",
        now=2_000_000_120.0,
    )


def test_pqv_uses_canonical_event_and_truthful_source_fallback(monkeypatch):
    with_url = _state()
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state=with_url))
    items = app._canonical_pqv_event_items(
        league_id="L1",
        player_id=JEANTY_ID,
        event_id="rec:news-event:12527:injury_chain",
    )
    assert items[0].headline == "Ashton Jeanty injury update"
    assert items[0].url == "https://example.com/jeanty-report"
    assert items[0].source_link_unavailable is False
    assert "unchanged" in items[0].status_line

    without_url = _state(_tile(source_url=""))
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state=without_url))
    unavailable = app._canonical_pqv_event_items(
        league_id="L1",
        player_id=JEANTY_ID,
    )
    assert unavailable[0].url == ""
    assert unavailable[0].source_link_unavailable is True


def test_injury_attention_uses_warning_tone_without_official_designation():
    tags = player_cards.player_scan_tags(
        {
            "injury_attention_label": "Injury Alert",
            "opportunity_label": "Elite Opportunity",
            "injury_status": "",
            "status": "Active",
        },
        primary_status="Elite",
        is_injury_status=lambda _row: False,
    )
    assert "player-support-chip-warning" in tags
    assert "Injury Alert" in tags
    assert all(label not in tags for label in ("OUT", "Questionable", "IR"))


def test_my_team_and_pqv_wiring_owns_semantic_focus_and_event_context():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    team_source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert 'anchor="my-team-player-focus"' in app_source
    assert 'data-dg-scroll-anchor="my-team-player-focus"' in team_source
    assert "quick_view_event_id=focused_event_id" in team_source
    assert '"Recent development"' in app_source
    assert "canonical_player_event_records(" in app_source
