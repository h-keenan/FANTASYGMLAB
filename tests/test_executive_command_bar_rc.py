"""Contracts for Executive Command Bar & Notification Center RC polish."""

from pathlib import Path

from modules import brand_identity, notification_center
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_notification_copy_is_customer_facing():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "architecture supports" not in source
    assert "Stay ahead of your league" in source
    assert "sample alerts" in source.casefold()
    assert "Lightweight inbox shell" not in source
    assert "GM Orb" not in source
    items = notification_center.list_founder_beta_notifications()
    titles = {item.title for item in items}
    assert "Trade board updated" in titles
    assert any("What's new" in title for title in titles)
    bodies = " ".join(item.body for item in items)
    assert "War Room identity" not in bodies
    assert "executive bar" not in bodies.casefold()


def test_notification_inbox_has_no_category_navigation_chips():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "dg-notification-chip" not in source
    assert "dg-notification-panel__categories" not in source
    assert "dg-notification-panel__list" in source
    assert "Open Trade Hub" in notification_center.notification_item_html(
        notification_center.FOUNDER_BETA_DEMO_NOTIFICATIONS[0]
    )


def test_notification_priority_puts_action_before_product():
    items = notification_center.list_founder_beta_notifications()
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
    assert "45vh" in css
    assert "overflow-y: auto" in css
    assert "overscroll-behavior: contain" in css
    assert "dg-notification-item__cta" in css
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
