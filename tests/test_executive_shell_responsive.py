"""Contracts for executive shell & responsive header finalization."""

from pathlib import Path

from modules import application_shell
from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS
from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_shell_uses_token_padding_and_tighter_first_viewport_gap():
    assert "margin-block-end: var(--space-md);" in APPLICATION_SHELL_CSS
    assert "padding-block: 0;" in APPLICATION_SHELL_CSS
    assert "padding-inline: var(--space-md);" in APPLICATION_SHELL_CSS
    assert "gap: 2px" not in APPLICATION_SHELL_CSS


def test_command_strip_centers_labels_and_chevrons():
    assert "flex-direction: row !important;" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "gap: var(--space-xs) !important;" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "button svg" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "width: 22.5rem;" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "letter-spacing: var(--letter-spacing-badge) !important;" in (
        EXECUTIVE_COMMAND_HEADER_CSS
    )
    assert "0.04em" not in EXECUTIVE_COMMAND_HEADER_CSS
    assert "gap: 2px;" not in EXECUTIVE_COMMAND_HEADER_CSS


def test_responsive_canvas_covers_tablet_desktop_and_ultrawide():
    # 1280 inherits the 1024 fixed executive contract; 1600+ centers ultra width.
    assert "@media (min-width: 1024px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "@media (min-width: 1600px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "--dg-exec-content-max-ultra" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "margin-inline: auto !important" in DESKTOP_EXECUTIVE_LAYOUT_CSS


def test_valuation_lens_lives_in_dashboard_page_context_not_shell():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    topbar = app_source[
        app_source.index("def render_platform_topbar(") : app_source.index(
            "def _query_param_page("
        )
    ]
    assert "render_workspace_archetype_affordance" not in topbar
    assert "render_workspace_archetype_affordance" in app_source
    assert app_source.index("def render_home_dashboard(") < app_source.index(
        "render_workspace_archetype_affordance("
    )
    home = app_source[
        app_source.index("def render_home_dashboard(") : app_source.index(
            "def render_platform_topbar("
        )
    ]
    assert "render_workspace_archetype_affordance" in home
    ui = (ROOT / "modules" / "valuation_archetype_ui.py").read_text(encoding="utf-8")
    assert 'key="dashboard_page_context"' in ui
    assert "st-key-dashboard_page_context" in EXECUTIVE_DESIGN_UNIFY_CSS
    assert "st-key-workspace_valuation_archetype" not in EXECUTIVE_DESIGN_UNIFY_CSS


def test_routine_acks_use_compact_shell_ack_not_success_banner():
    html = application_shell.shell_ack_html(
        label="Ready",
        message="Loaded saved league: Fixture League",
    )
    assert "dg-shell-ack" in html
    assert "Loaded saved league: Fixture League" in html
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "shell_ack_html" in app_source
    assert 'st.success(_safe_text(st.session_state.pop("account_resume_notice")))' not in (
        app_source
    )
    assert "dg-shell-ack" in DESKTOP_EXECUTIVE_LAYOUT_CSS
