"""Site-wide UI/UX audit contracts (PR #167)."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_site_wide_ui_ux_audit_doc_exists():
    doc = (ROOT / "docs" / "site-wide-ui-ux-audit.md").read_text(encoding="utf-8")
    assert "P0" in doc and "P1" in doc and "P2" in doc
    assert "terminology" in doc.casefold()
    assert "screenshot matrix" in doc.casefold() or "Screenshot matrix" in doc
    assert "No football" in doc or "no football" in doc.casefold()
    assert "Alerts" in doc
    assert "Your Next Move" in doc


def test_alerts_panel_title_matches_command_bar_trigger():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "dg-notification-panel__title'>Alerts</div>" in source
    assert "Notification inbox" not in source
    assert "dg-notification-panel__title'>Inbox</div>" not in source


def test_waivers_and_trade_analyzer_drop_raw_st_metric():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    waivers = source[
        source.index('if current_page == "waivers":') : source.index(
            'if current_page == "my_team":'
        )
    ]
    analyzer = source[
        source.index('if current_page == "trade_analyzer":') : source.index(
            'if current_page == "premium":'
        )
    ]
    assert "st.metric(" not in waivers
    assert "st.metric(" not in analyzer
    assert "render_executive_metric_tiles" in waivers
    assert "toa-share-card" in analyzer or "build_offer_result_card_html" in analyzer
    assert "Analyze Trade" in analyzer


def test_mobile_validator_covers_full_responsive_width_matrix():
    source = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert "1280" in source and "1600" in source and "1920" in source
    assert "expected one Alerts title" in source
    assert "Immediate Action must appear above Your Next Move" not in source
    assert "Today's Game Plan" in source
    assert "What Changed" in source
