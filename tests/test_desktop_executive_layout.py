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
    assert "@media (min-width: 1600px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "@media (min-width: 1800px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "dg-shell-ack" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "dg-league-switch-ack" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "mobile-gm-sheet-marker" not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "st-key-dashboard_workflow" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "#" not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "rgba(" not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert DESKTOP_EXECUTIVE_LAYOUT_CSS in APP_CSS
    from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
    from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS

    assert APP_CSS.index(DESKTOP_EXECUTIVE_LAYOUT_CSS) < APP_CSS.index(
        EXECUTIVE_DESIGN_UNIFY_CSS
    )
    assert APP_CSS.rindex("dg-shell-ack") > APP_CSS.index(
        DESKTOP_EXECUTIVE_LAYOUT_CSS
    )
    assert "dg-gm-sheet-enter" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "mobile-gm-sheet-marker" in MOBILE_INTERACTION_OVERLAY_CSS


def test_dashboard_immediate_action_marks_primary_urgency(monkeypatch):
    from modules import dashboard_workflow
    import streamlit as st

    briefing = dashboard_workflow.organize_dashboard_items(
        [
            {"label": "Roster Pressure", "value": "2 Over", "note": "Cut now."},
            {"label": "Injury Alert", "value": "1 injured", "note": "Cover needed."},
            {"label": "Biggest Team Need", "value": "QB", "note": "Depth."},
        ],
        immediate_labels=frozenset({"Roster Pressure", "Injury Alert"}),
    )
    captured = []

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(st, "container", lambda **k: _Ctx())
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st, "expander", lambda *a, **k: _Ctx())
    monkeypatch.setattr(
        dashboard_workflow.ui_primitives,
        "render_section_header",
        lambda *a, **k: None,
    )

    def render_tiles(items, **kwargs):
        captured.append(items)

    dashboard_workflow.render_dashboard_workflow(
        briefing,
        snapshot_items=[],
        render_tiles=render_tiles,
        render_snapshot=lambda *_: None,
        render_quick_actions=lambda *_: None,
        render_league_pulse=lambda: None,
    )
    # Immediate Action renders before Your Next Move so urgency is not buried.
    immediate = captured[0]
    assert immediate[0]["priority"] == "primary"
    assert immediate[0]["tone"] == "need"
    assert immediate[1]["tone"] == "risk"
    primary = captured[1]
    assert primary[0].get("wide") is True


def test_ui_harness_tiles_emit_primary_secondary_weight():
    source = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert "home-command-card-primary" in source
    assert "home-command-card-secondary" in source
    assert "home-command-card-note" in source


def test_competing_block_container_widths_converge_on_executive_contract():
    assert "max-width: 1480px" not in APP_CSS
    assert "--dg-exec-content-max: 1180px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "--dg-exec-content-max-wide: 1220px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "max-width: var(--dg-exec-content-max)" in DESKTOP_EXECUTIVE_LAYOUT_CSS


def test_customer_facing_surfaces_use_fantasygm_lab_not_dynastygm():
    for relative in (
        "modules/legal_pages.py",
        "modules/dashboard_orientation.py",
        "modules/application_shell.py",
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
    assert "shell_ack_html" in app_source
    assert "dg-shell-ack" in app_source or "shell_ack_html" in app_source


def test_executive_shell_docs_describe_desktop_composition():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "single executive command bar" in docs
