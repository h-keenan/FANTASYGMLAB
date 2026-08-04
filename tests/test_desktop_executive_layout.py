"""Contracts for desktop executive layout composition (presentation only)."""

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_executive_layout_css_is_token_backed_and_loaded_last():
    assert "--dg-exec-content-max" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "1180px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "1220px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "1280px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "@media (min-width: 1024px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "@media (min-width: 1440px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "@media (min-width: 1800px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "dg-gm-sheet-enter" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "dg-league-switch-ack" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "mobile-gm-sheet-marker" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "#" not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "rgba(" not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert DESKTOP_EXECUTIVE_LAYOUT_CSS in APP_CSS
    assert APP_CSS.rindex("dg-league-switch-ack") > APP_CSS.rindex("home-command-card-primary")


def test_competing_block_container_widths_converge_on_executive_contract():
    assert "max-width: 1480px" not in APP_CSS
    assert APP_CSS.count("max-width: 1180px") >= 1
    assert "--dg-exec-content-max-wide: 1220px" in DESKTOP_EXECUTIVE_LAYOUT_CSS


def test_customer_facing_surfaces_use_fantasygm_lab_not_dynastygm():
    for relative in (
        "modules/legal_pages.py",
        "modules/dashboard_orientation.py",
        "modules/app_header.py",
        "modules/valuation_archetype_ui.py",
        "modules/platform_import_ui.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "DynastyGM" not in source, relative

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "launch-title'>DynastyGM" not in app_source
    assert "DynastyGM Command Center" not in app_source
    assert "Sleeper League Analyzer" not in app_source
    assert "not unfinished surfaces" not in app_source
    assert "_league_switch_ack" in app_source
    assert "dg-league-switch-ack" in app_source


def test_executive_shell_docs_describe_desktop_composition():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "single executive command bar" in docs
