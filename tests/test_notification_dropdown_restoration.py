"""Contracts for Alerts anchored dropdown restoration (PR #153)."""

from __future__ import annotations

from pathlib import Path

from modules import notification_center as nc


ROOT = Path(__file__).resolve().parents[1]


def test_alerts_uses_popover_not_dialog():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "st.popover(" in source
    assert '@st.dialog("Inbox"' not in source
    assert "Close inbox" not in source
    assert "def _render_inbox_panel(" in source
    assert "def _inbox_header_html(" in source


def test_inbox_header_is_compact_without_duplicate_brand_stack():
    html = nc._inbox_header_html(unread=2, status_note="League activity first.")
    assert html.count("Inbox") == 1
    assert "FOUNDER BETA" not in html
    assert "2 unread" in html
    assert "dg-notification-panel__title'" in html or 'dg-notification-panel__title"' in html
    assert "dg-notification-panel__kicker" not in html
    assert html.count("dg-notification-panel__title-row") == 1
    assert ">Inbox<" in html or ">Inbox</div>" in html.replace(" ", "")


def test_inbox_interleaves_real_ctas_per_item():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    body = source[
        source.index("def _render_inbox_panel(") : source.index(
            "def render_notification_center("
        )
    ]
    assert "notification_item_html(item)" in body
    assert "st.button(" in body or "st.link_button(" in body
    assert "dg_notify_action_" in body
    # Card then CTA in the same loop — not batch HTML then buttons.
    assert body.index("notification_item_html(item)") < body.index(
        'with st.container(key=f"dg_notify_action_'
    )


def test_overlay_css_keeps_alerts_on_popover_layer():
    css = (ROOT / "modules" / "mobile_interaction_overlay_styles.py").read_text(
        encoding="utf-8"
    )
    assert "stPopoverBody" in css
    assert "dg-notification-panel" in css
    assert 'stDialog"]:has(.dg-notification-panel)' not in css


def test_validator_asserts_real_notification_controls_and_widths():
    source = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert "ALERTS_CAPTURE_WIDTHS" in source
    assert "1920" in source
    assert "_capture_alerts_dropdown(" in source
    assert "st.dialog modal" in source or "stDialog" in source
    assert "Open Trade Hub" in source
    assert "data-fixture-notification-destination='trade_hub'" in source
    assert "Close inbox" in source  # asserted absent


def test_dropdown_contract_document_exists():
    doc = (
        ROOT / "docs" / "notification-dropdown-restoration-contract.md"
    ).read_text(encoding="utf-8")
    for section in (
        "Root cause",
        "Final responsive notification-surface contract",
        "Interaction integrity",
        "Overlay layering",
        "Automated validation",
        "Trade Hub first-useful-result",
    ):
        assert section in doc
