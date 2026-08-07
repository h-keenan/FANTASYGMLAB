"""Contracts for Executive Command Bar & Notification Center RC polish."""

from pathlib import Path

from modules import brand_identity, notification_center
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_notification_copy_is_customer_facing():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "architecture supports" not in source
    assert "GM Orb" not in source
    assert "Lightweight inbox shell" not in source
    items = notification_center.list_founder_beta_notifications(session={})
    titles = {item.title for item in items}
    assert any("What's new" in title for title in titles)
    bodies = " ".join(item.body for item in items)
    assert "War Room identity" not in bodies
    assert "executive bar" not in bodies.casefold()
    assert all(item.source_kind == "product" for item in items) or any(
        item.source_kind == "product" for item in items
    )


def test_notification_inbox_has_no_category_navigation_chips():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "dg-notification-chip" not in source
    assert "dg-notification-panel__categories" not in source
    assert "dg-notification-panel" in source
    trade = notification_center.NotificationItem(
        id="t1",
        category="Trades",
        title="Acquire RB depth",
        body="Fit",
        href_hint="trade_hub",
        source_kind="canonical",
    )
    assert "dg-notification-item__cta" not in notification_center.notification_item_html(trade)
    assert "Trades" in notification_center.notification_item_html(trade)


def test_notification_priority_puts_action_before_product():
    session = {}
    notification_center.publish_activity_inventory(
        session,
        [
            {
                "label": "Top Trade Opportunity",
                "value": "Trade",
                "note": "n",
                "recommendation_id": "t1",
                "route_key": "trade_hub",
            },
            {
                "label": "Top Waiver Opportunity",
                "value": "Waiver",
                "note": "n",
                "recommendation_id": "w1",
                "route_key": "waivers",
            },
        ],
        league_id="L1",
    )
    items = notification_center.compose_activity_inbox(session=session, league_id="L1")
    categories = [item.category for item in items]
    assert categories[0] == "Trades"
    assert categories.index("Trades") < categories.index("Product updates")
    assert categories.index("Waivers") < categories.index("Product updates")
    assert categories[-1] == "Product updates"
    html = notification_center.notification_item_html(items[0])
    assert "dg-notification-item--action" in html
    product = next(item for item in items if item.category == "Product updates")
    assert "dg-notification-item--product" in notification_center.notification_item_html(
        product
    )


def test_notification_panel_css_is_floating_inbox_with_internal_scroll():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    assert 'stPopoverBody"]:has(.dg-notification-panel)' in css
    assert "60vh" in css
    assert "overflow-y: auto" in css
    assert "overscroll-behavior: contain" in css
    assert "dg-notification-item__action-line" in css
    assert "#" not in css
    assert "rgba(" not in css


def test_trade_hub_and_waivers_do_not_restack_page_titles():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'page_key="trade_hub"' not in app_source
    assert "waivers_ui.render_waivers_page_header()" not in app_source
    board = app_source[
        app_source.index("def render_top_trade_opportunities()") : app_source.index(
            'with st.expander("Search return paths from one of your players"'
        )
    ]
    assert '"Trade Board"' not in board


def test_docs_describe_floating_executive_inbox():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "executive inbox" in docs
    assert "45–60%" in docs
    assert "internal scrolling" in docs
    assert "GM Orb remains the primary full navigation" in docs
