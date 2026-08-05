from pathlib import Path

import pytest

from modules import application_shell
from modules.application_shell_styles import APPLICATION_SHELL_CSS


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "page_title",
    (
        "Dashboard", "My Team", "Trade Hub", "League Overview", "Waivers",
        "Draft Center", "Live Draft", "Premium", "Labs [EXPERIMENTAL]",
    ),
)
def test_authenticated_workspaces_share_one_compact_shell_contract(page_title):
    html = application_shell.executive_workspace_shell_html(
        application_shell.ExecutiveWorkspaceShell(
            page_title=page_title,
            page_note="This description belongs to page content.",
            league_name="War Room League With A Long Name",
            team_name="Fixture Team",
            platform="Sleeper",
            account_label="Signed In",
            entitlement_label="Premium",
            has_league=True,
            metrics=(application_shell.WorkspaceMetric("Power Rank", "#4", "Strength"),),
        )
    )
    assert html.count("<header") == 1
    assert page_title in html
    assert "War Room League With A Long Name" in html
    assert "Signed In" in html and "Premium" in html
    assert "This description belongs to page content." not in html
    assert "Power Rank" not in html and "#4" not in html


def test_production_wraps_existing_switcher_inside_the_executive_shell():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    renderer = source[source.index("def render_platform_topbar(") : source.index("def _query_param_page(")]
    assert 'st.container(key="executive_workspace_shell")' in renderer
    assert renderer.index("executive_workspace_shell_html(") < renderer.index("render_top_league_identity_header(")
    assert 'key="executive_command_actions"' in renderer
    assert "metrics=()," in renderer
    assert "shell_ack_html" in renderer
    assert "render_workspace_archetype_affordance" not in renderer


def test_shell_styles_are_isolated_token_backed_and_mobile_bounded():
    assert ".dg-executive-shell" in APPLICATION_SHELL_CSS
    assert 'st-key-executive_workspace_shell' in APPLICATION_SHELL_CSS
    assert "var(--touch-target-min)" in APPLICATION_SHELL_CSS
    assert "var(--color-surface-primary)" in APPLICATION_SHELL_CSS
    assert "var(--space-sm)" in APPLICATION_SHELL_CSS
    assert "@media (max-width: 760px)" in APPLICATION_SHELL_CSS
    assert "#" not in APPLICATION_SHELL_CSS
    assert "rgba(" not in APPLICATION_SHELL_CSS


def test_visual_validation_covers_all_required_release_widths_and_height_contract():
    source = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert "WIDTHS = (320, 390, 430, 768, 1024, 1440)" in source
    assert 'metrics["shellHeight"] > 140' in source
    assert 'metrics["shellCount"] != 1' in source
    assert 'metrics["switcherCount"] != 1' in source
    assert "st-key-top_league_actions" in source
