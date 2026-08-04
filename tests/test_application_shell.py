from pathlib import Path

from modules import application_shell
from modules.application_shell_styles import APPLICATION_SHELL_CSS


def _header(**overrides):
    values = {
        "page_title": "Trade Hub",
        "page_note": "Explore current trade paths.",
        "league_name": "Fixture League",
        "team_name": "Fixture Team",
        "platform": "Sleeper",
        "account_label": "Signed in",
        "entitlement_label": "Premium",
        "has_league": True,
        "avatar_url": "https://example.com/avatar.png",
        "metrics": (
            application_shell.WorkspaceMetric("Strategy", "Contender", "Current roster lens"),
            application_shell.WorkspaceMetric("Power Rank", "#2", "Current strength"),
        ),
    }
    values.update(overrides)
    return application_shell.WorkspaceHeader(**values)


def test_workspace_header_combines_page_and_active_league_context():
    html = application_shell.workspace_header_html(_header())

    assert html.count("dg-executive-shell") >= 1
    assert "class='dg-executive-shell__title' role='heading' aria-level='1'>Trade Hub" in html
    assert "Fixture League" in html
    assert "Sleeper" in html
    assert "Signed in" in html
    assert "Premium" in html
    assert "War Room" in html
    assert "Contender" not in html
    assert "Power Rank" not in html
    assert "#2" not in html
    assert "aria-label='FantasyGM Lab executive workspace'" in html


def test_workspace_header_handles_missing_league_without_inventing_sync_data():
    html = application_shell.workspace_header_html(
        _header(
            has_league=False,
            league_name="",
            team_name="",
            avatar_url="",
            metrics=(),
        )
    )

    assert "No league selected" in html
    assert "Guest" not in html
    assert "Last synced" not in html
    assert "dg-executive-shell__brand" in html


def test_workspace_header_escapes_all_external_labels_and_avatar_attributes():
    html = application_shell.workspace_header_html(
        _header(
            page_title="<script>alert(1)</script>",
            league_name="<League>",
            team_name='"Team"',
            avatar_url="' onerror='alert(1)",
        )
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;League&gt;" in html
    assert "Team" not in html
    assert "onerror=" not in html


def test_shell_styles_use_semantic_tokens_and_define_responsive_safe_area():
    assert "var(--color-surface-primary)" in APPLICATION_SHELL_CSS
    assert "var(--space-lg)" in APPLICATION_SHELL_CSS
    assert "var(--focus-ring)" in APPLICATION_SHELL_CSS
    assert "var(--touch-target-min)" in APPLICATION_SHELL_CSS
    assert "@media (max-width: 760px)" in APPLICATION_SHELL_CSS
    assert "@media (prefers-reduced-motion: reduce)" in APPLICATION_SHELL_CSS
    assert "max-height: calc(100dvh" in APPLICATION_SHELL_CSS
    assert "env(safe-area-inset-left)" in APPLICATION_SHELL_CSS
    assert "#" not in APPLICATION_SHELL_CSS
    assert "rgba(" not in APPLICATION_SHELL_CSS


def test_production_mounts_one_workspace_header_and_preserves_existing_actions():
    source = Path("app.py").read_text(encoding="utf-8")

    assert source.count("render_platform_topbar(") == 2
    assert "application_shell.executive_workspace_shell_html" in source
    assert "app_header.league_identity_header_html" not in source
    assert '"Switch League" if selected_league_id else "Select League"' in source
    assert '"Refresh Current League"' in source
    assert '"Manage Leagues"' in source
    assert '"Premium"' in source
    assert "render_header_league_switcher(" in source


def test_shell_ignores_legacy_franchise_metrics_and_long_descriptions():
    html = application_shell.executive_workspace_shell_html(_header())
    assert "Explore current trade paths." not in html
    assert "Strategy" not in html
    assert "Power Rank" not in html
    assert "Sync status" not in html


def test_cross_page_state_styles_share_one_canonical_rhythm():
    for selector in (
        ".dg-ui-section-header",
        ".dg-ui-card",
        ".dg-ui-empty-state",
        '[data-testid="stAlert"]',
        '[data-testid="stSpinner"]',
        'div[data-testid="stDialog"] div[role="dialog"]',
    ):
        assert selector in APPLICATION_SHELL_CSS
