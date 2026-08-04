"""Contracts for the Executive Command Header and Notification Center shell."""

from pathlib import Path

from modules import application_shell, brand_identity, notification_center
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_notification_center_demo_covers_required_categories():
    items = notification_center.list_founder_beta_notifications()
    categories = {item.category for item in items}
    for required in notification_center.NOTIFICATION_CATEGORIES:
        assert required in categories
    assert notification_center.unread_count(items) >= 1
    html = notification_center.notification_item_html(items[0])
    assert "dg-notification-item" in html
    assert items[0].title in html


def test_executive_command_header_css_is_token_backed_and_loaded():
    assert "executive_command_actions" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "dg-notification-item" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "#" not in EXECUTIVE_COMMAND_HEADER_CSS
    assert "rgba(" not in EXECUTIVE_COMMAND_HEADER_CSS
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "EXECUTIVE_COMMAND_HEADER_CSS" in app_source
    assert "inject_global_styles(EXECUTIVE_COMMAND_HEADER_CSS)" in app_source


def test_shell_html_includes_founder_badge_premium_and_alerts_without_metrics():
    html = application_shell.executive_workspace_shell_html(
        application_shell.ExecutiveWorkspaceShell(
            page_title="Trade Hub",
            page_note="Page note stays out of the header.",
            league_name="War Room League",
            team_name="Fixture Team",
            platform="Sleeper",
            account_label="Signed in",
            entitlement_label="Premium",
            has_league=True,
            metrics=(application_shell.WorkspaceMetric("Power Rank", "#2", "Nope"),),
            notification_unread=3,
        )
    )
    assert "executive command header" in html
    assert brand_identity.FOUNDER_BETA_LABEL in html
    assert "dg-executive-shell__chip--premium" in html
    assert "3 new" in html
    assert "Power Rank" not in html
    assert "Page note stays out of the header." not in html


def test_platform_topbar_wires_command_actions_and_suppresses_duplicate_feedback():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_platform_topbar(") : source.index("def _query_param_page(")
    ]
    assert 'key="executive_command_actions"' in renderer
    assert "render_notification_center(" in renderer
    assert "render_executive_profile_control(" in renderer
    assert 'placement="header"' in renderer
    assert "_executive_command_header_mounted" in source
    feedback = source[
        source.index("def render_global_feedback_entry(") : source.index(
            "free_agent_priority_badge"
        )
    ]
    assert 'placement == "floating"' in feedback
    assert "_executive_command_header_mounted" in feedback


def test_mobile_validator_counts_only_league_switcher_in_command_header():
    source = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert 'st-key-top_league_actions' in source
    assert 'metrics["shellHeight"] > 140' in source


def test_docs_describe_executive_command_header_and_notification_shell():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "Executive Command Header" in docs
    assert "Notification Center" in docs
    assert "GM Orb remains the primary full navigation" in docs
