"""Canonical Notification Center composition and routing contracts."""

from __future__ import annotations

from pathlib import Path

from modules import daily_gm_briefing
from modules import dashboard_workflow
from modules import notification_center as nc


ROOT = Path(__file__).resolve().parents[1]


def _tile(label, value, **extra):
    payload = {"label": label, "value": value, "note": extra.pop("note", "note")}
    payload.update(extra)
    return payload


def test_compose_trade_waiver_injury_and_product():
    session = {}
    nc.publish_activity_inventory(
        session,
        [
            _tile(
                "Top Trade Opportunity",
                "Acquire RB depth",
                recommendation_id="trade-1",
                route_key="trade_hub",
                route_player_id="6794",
                recommendation_narrative={
                    "recommendation_id": "trade-1",
                    "kind": "trade",
                    "action": "Acquire RB depth",
                    "reason": "Fit",
                    "is_active_recommendation": True,
                },
            ),
            _tile(
                "Top Waiver Opportunity",
                "Add WR",
                recommendation_id="waiver-1",
                route_key="waivers",
                player_id="4046",
            ),
            _tile("Injury Alert", "1 injured starter"),
        ],
        league_id="L1",
        roster_id="R1",
        entitlement="premium",
    )
    items = nc.compose_activity_inbox(session=session, league_id="L1", entitlement="premium")
    categories = [item.category for item in items]
    assert "Trades" in categories
    assert "Waivers" in categories
    assert "Injuries" in categories
    assert "Product updates" in categories
    trade = next(item for item in items if item.category == "Trades")
    assert trade.recommendation_id == "trade-1"
    assert trade.player_id == "6794"
    assert trade.href_hint == "trade_hub"


def test_quiet_inbox_is_product_only_without_manufactured_events():
    session = {}
    nc.publish_activity_inventory(
        session, [], league_id="L1", entitlement="free", live_draft_active=False
    )
    items = nc.compose_activity_inbox(session=session, league_id="L1")
    assert len(items) == 1
    assert items[0].source_kind == "product"
    assert items[0].category == "Product updates"


def test_duplicate_recommendation_suppressed_in_inbox():
    session = {}
    tiles = [
        _tile(
            "Top Trade Opportunity",
            "Acquire RB",
            recommendation_id="same",
            route_key="trade_hub",
        ),
        _tile(
            "Top Trade Opportunity",
            "Acquire RB again",
            recommendation_id="same",
            route_key="trade_hub",
        ),
    ]
    nc.publish_activity_inventory(session, tiles, league_id="L1")
    items = [item for item in nc.compose_activity_inbox(session=session, league_id="L1") if item.recommendation_id]
    assert len(items) == 1


def test_live_draft_route_from_cache():
    session = {"_cached_live_draft_active": True}
    items = nc.compose_activity_inbox(session=session, league_id="L1")
    draft = next(item for item in items if item.category == "Live Draft")
    assert draft.href_hint == "live_draft"


def test_read_unread_is_scoped_and_deterministic():
    session = {"account_user_id": "user-a", "selected_league_id": "L1"}
    nc.publish_activity_inventory(
        session,
        [_tile("Top Waiver Opportunity", "Add X", recommendation_id="w1", route_key="waivers")],
        league_id="L1",
    )
    items = nc.compose_activity_inbox(session=session, league_id="L1")
    target = next(item for item in items if item.recommendation_id == "w1")
    assert target.unread is True
    assert nc.unread_count(items) >= 1
    nc.mark_notification_read(session, target.id, league_id="L1")
    again = nc.compose_activity_inbox(session=session, league_id="L1")
    reread = next(item for item in again if item.recommendation_id == "w1")
    assert reread.unread is False
    # Other league scope does not inherit reads.
    other = {
        "account_user_id": "user-a",
        "selected_league_id": "L2",
        nc.NOTIFICATION_READ_IDS_KEY: dict(session[nc.NOTIFICATION_READ_IDS_KEY]),
    }
    nc.publish_activity_inventory(
        other,
        [_tile("Top Waiver Opportunity", "Add X", recommendation_id="w1", route_key="waivers")],
        league_id="L2",
    )
    cross = nc.compose_activity_inbox(session=other, league_id="L2")
    assert next(item for item in cross if item.recommendation_id == "w1").unread is True


def test_account_switch_clears_notification_state():
    session = {
        "account_user_id": "a",
        nc.ACTIVITY_INBOX_SNAPSHOT_KEY: {"league_id": "L1", "records": []},
        nc.NOTIFICATION_READ_IDS_KEY: {"a|L1": ["x"]},
    }
    nc.clear_notification_session_state(session)
    assert nc.ACTIVITY_INBOX_SNAPSHOT_KEY not in session
    assert nc.NOTIFICATION_READ_IDS_KEY not in session


def test_league_mismatch_and_stale_recommendation():
    session = {}
    nc.publish_activity_inventory(
        session,
        [_tile("Top Trade Opportunity", "X", recommendation_id="t1", route_key="trade_hub")],
        league_id="L1",
    )
    item = next(
        i
        for i in nc.compose_activity_inbox(session=session, league_id="L1")
        if i.recommendation_id == "t1"
    )
    mismatched = nc.NotificationItem(**{**item.to_dict(), "league_id": "L-other"})
    stale_league = nc.validate_notification_for_open(
        mismatched, session=session, current_league_id="L1"
    )
    assert stale_league.stale
    assert "another league" in stale_league.stale_reason.casefold()

    nc.publish_activity_inventory(session, [], league_id="L1")
    stale_rec = nc.validate_notification_for_open(
        item, session=session, current_league_id="L1"
    )
    assert stale_rec.stale
    assert "recommendation updated" in stale_rec.stale_reason.casefold()


def test_stale_live_draft_and_player():
    draft = nc.NotificationItem(
        id="live-draft:L1",
        category="Live Draft",
        title="Live Draft is active",
        body="Join",
        href_hint="live_draft",
        league_id="L1",
        source_kind="canonical",
        provenance="live_draft_cache",
    )
    ended = nc.validate_notification_for_open(
        draft, session={}, current_league_id="L1"
    )
    assert ended.stale
    assert "draft has ended" in ended.stale_reason.casefold()

    player = nc.NotificationItem(
        id="p1",
        category="Injuries",
        title="Watch",
        body="note",
        href_hint="player_quick_view",
        player_id="99",
        league_id="L1",
        provenance="dashboard_inventory|Injury Alert",
        source_kind="canonical",
    )
    missing = nc.validate_notification_for_open(
        player, session={}, current_league_id="L1"
    )
    assert missing.stale


def test_free_and_premium_share_compose_path():
    session = {}
    tiles = [
        _tile("Top Trade Opportunity", "Move", recommendation_id="t1", route_key="trade_hub")
    ]
    nc.publish_activity_inventory(session, tiles, league_id="L1", entitlement="free")
    free = nc.compose_activity_inbox(session=session, league_id="L1", entitlement="free")
    premium = nc.compose_activity_inbox(
        session=session, league_id="L1", entitlement="premium"
    )
    free_trade = next(i for i in free if i.recommendation_id == "t1")
    premium_trade = next(i for i in premium if i.recommendation_id == "t1")
    assert free_trade.title == premium_trade.title
    assert free_trade.recommendation_id == premium_trade.recommendation_id


def test_briefing_overlap_keeps_distinct_roles():
    trade = _tile(
        "Top Trade Opportunity",
        "Acquire RB depth",
        recommendation_id="shared-1",
        route_key="trade_hub",
    )
    briefing = dashboard_workflow.organize_dashboard_items([trade])
    plan = daily_gm_briefing.compose_daily_gm_briefing(briefing, league_id="L1")
    session = {}
    nc.publish_activity_inventory(session, [trade], league_id="L1")
    inbox = nc.compose_activity_inbox(session=session, league_id="L1")
    assert plan.items[0].recommendation_id == "shared-1"
    note = next(i for i in inbox if i.recommendation_id == "shared-1")
    assert note.category == "Trades"
    assert note.provenance.startswith("dashboard_inventory")
    # Briefing is priority framing; notification is inbox framing.
    assert plan.items[0].category == daily_gm_briefing.CATEGORY_TOP_PRIORITY
    assert note.source_kind == "canonical"


def test_no_football_score_helpers():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "notification_score" not in source
    assert "daily_briefing_score" not in source
    assert "Does not generate football" in source or "does not invent football" in source.casefold()


def test_app_wires_publish_and_deep_link_open():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "publish_activity_inventory(" in app
    assert "def _open_notification_item(" in app
    assert "on_open_item=_open_notification_item" in app
    assert "clear_notification_league_snapshot(" in app
    opener = app.split("def _open_notification_item", 1)[1].split("\ndef ", 1)[0]
    assert "validate_notification_for_open(" in opener
    assert "mark_notification_read(" in opener
    assert 'handoff_source="notification_center"' in opener
    assert "open_player_quick_view(" in opener
    assert "bind_narrative(" in opener


def test_workflow_back_remaps_notification_center_origin():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    body = app.split("def _workflow_return_to_origin", 1)[1].split("\ndef ", 1)[0]
    assert 'destination == "notification_center"' in body
    assert 'destination = "dashboard"' in body


def test_contract_doc_exists():
    text = (ROOT / "docs" / "canonical-notification-center-contract.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "Architecture",
        "Notification model",
        "Canonical sources",
        "Routing matrix",
        "Stale-state behavior",
        "Read / unread",
        "Briefing vs Notification",
        "Performance",
        "Known limitations",
    ):
        assert heading in text
