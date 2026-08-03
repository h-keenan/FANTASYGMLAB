from pathlib import Path
import re

from modules.app_styles import APP_CSS
from modules.application_shell import WorkspaceHeader, workspace_header_html
from modules.interface_reimagining_styles import INTERFACE_REIMAGINING_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.visual_identity_styles import COMMAND_CENTER_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_reimagining_is_the_final_shared_visual_layer():
    assert APP_CSS.rfind(INTERFACE_REIMAGINING_CSS) > APP_CSS.rfind(COMMAND_CENTER_CSS)
    assert APP_CSS.rfind(INTERFACE_REIMAGINING_CSS) > APP_CSS.rfind(PLAYER_QUICK_VIEW_CSS)


def test_reimagining_uses_tokens_and_no_literal_color_values():
    assert "var(--color-" in INTERFACE_REIMAGINING_CSS
    assert "var(--space-" in INTERFACE_REIMAGINING_CSS
    assert "var(--radius-" in INTERFACE_REIMAGINING_CSS
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", INTERFACE_REIMAGINING_CSS) is None
    assert "rgb(" not in INTERFACE_REIMAGINING_CSS
    assert "rgba(" not in INTERFACE_REIMAGINING_CSS


def test_reimagining_covers_the_primary_operational_rooms():
    for selector in (
        ".home-command-shell",
        ".dg-page-shell--trade-hub",
        ".waiver-section-header",
        ".dg-page-shell--players",
        ".dg-intelligence-group",
        ".dg-application-workspace",
    ):
        assert selector in INTERFACE_REIMAGINING_CSS


def test_reimagining_preserves_accessibility_and_responsive_contracts():
    assert ":focus-visible" in INTERFACE_REIMAGINING_CSS
    assert "var(--focus-ring)" in INTERFACE_REIMAGINING_CSS
    assert "var(--touch-target-min)" in APP_CSS
    assert "@media (max-width: 900px)" in INTERFACE_REIMAGINING_CSS
    assert "@media (prefers-reduced-motion: reduce)" in INTERFACE_REIMAGINING_CSS
    assert "overflow-wrap: anywhere" in INTERFACE_REIMAGINING_CSS


def test_workspace_header_is_an_executive_operations_brief():
    html = workspace_header_html(
        WorkspaceHeader(
            page_title="Dashboard",
            page_note="Today’s front-office priorities.",
            league_name="Synthetic League",
            team_name="Fixture Club",
            platform="Sleeper",
            account_label="Signed in",
            entitlement_label="Free",
            has_league=True,
        )
    )

    assert "dg-executive-shell" in html
    assert "DynastyGM executive workspace" in html
    assert "War Room" in html
    assert "Synthetic League" in html
    assert "class='dg-executive-shell__title' role='heading' aria-level='1'>Dashboard" in html


def test_page_shell_provides_stable_page_specific_visual_namespaces():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "dg-page-shell--{escape(page_class)}" in source
    assert 're.sub(r"[^a-z0-9-]+"' in source
    assert "dg-page-context" in source
    assert "<h2 class='dg-page-title'>" not in source
    assert "aria-label=" in source


def test_visual_layer_does_not_import_domain_or_state_services():
    source = (ROOT / "modules" / "interface_reimagining_styles.py").read_text(encoding="utf-8")
    for forbidden in (
        "pandas",
        "streamlit",
        "valuation",
        "recommendation",
        "trust",
        "supabase",
        "session_state",
    ):
        assert forbidden not in source.lower()
