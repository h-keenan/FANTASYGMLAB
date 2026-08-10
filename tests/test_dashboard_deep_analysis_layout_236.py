"""Dashboard Deep Analysis layout regression (#236)."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules import mobile_visual_polish_styles, workspace_ui
from modules.app_styles import APP_CSS


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
POLISH = mobile_visual_polish_styles.MOBILE_VISUAL_POLISH_CSS
HARNESS = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
DOC = ROOT / "docs" / "dashboard-deep-analysis-layout-236.md"


def _quick_actions_block() -> str:
    return WORKSPACE.split("def render_home_quick_actions", 1)[1].split("\ndef ", 1)[0]


def test_render_owner_is_workspace_quick_actions_from_dashboard_workflow():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert 'render_section_header("Deep Analysis", weight="support")' in source
    assert "League Overview" in source and "Draft Center" in source
    assert "render_quick_actions(" in source
    assert "def render_home_quick_actions" in WORKSPACE


def test_no_empty_shell_markdown_or_dual_border_owner():
    block = _quick_actions_block()
    assert "home-quick-actions-shell" not in block
    assert "dg-cta-tertiary" not in block
    assert "st.markdown" not in block
    # Obsolete #231 dual-border selector must stay gone.
    assert (
        '[class*="dashboard_deep_analysis_nav"],.home-quick-actions-shell'
        not in POLISH
    )
    assert ".home-quick-actions-shell" in POLISH
    assert "display:none!important" in POLISH.replace(" ", "")


def test_compact_secondary_grid_contract():
    block = _quick_actions_block()
    assert 'st.container(key="dashboard_deep_analysis_nav")' in block
    assert "st.columns(2, gap=\"small\")" in block
    assert "dg_cta_secondary_deep_" in block
    assert "dg_cta_tertiary_deep_" not in block
    assert 'type="secondary"' in block
    for route in ("rankings", "my_team", "trade_hub", "draft_summary"):
        assert route in (
            ROOT / "modules" / "dashboard_workflow.py"
        ).read_text(encoding="utf-8")


def test_mobile_keeps_two_column_grid_against_streamlit_wrap():
    """Streamlit emotion sets min-width:calc(100% - 1.5rem) below 640px."""

    compact = POLISH.replace(" ", "")
    assert "min-width:0!important" in compact
    assert "dashboard_deep_analysis_nav" in POLISH
    assert "max-width:calc(50%" in compact
    assert "flex:1 1 calc(50%" in POLISH or "flex:1 1 calc(50%" in compact.replace("11calc", "1 1 calc")
    assert "flex:1 1 calc(50%" in POLISH


def test_polish_gives_interactive_tiles_not_floating_text():
    assert '[class*="dashboard_deep_analysis_nav"] [data-testid="stButton"] button' in POLISH
    button_rule = POLISH.split(
        '[class*="dashboard_deep_analysis_nav"] [data-testid="stButton"] button',
        1,
    )[1].split("@media", 1)[0]
    assert "color-surface-raised" in button_rule
    assert "border:0!important" not in button_rule.replace(" ", "")
    assert "background:transparent!important" not in button_rule.replace(" ", "")
    assert "min-height:var(--touch-target-min)" in button_rule
    assert "min-height:0!important" in POLISH.replace(" ", "")
    assert "height:auto!important" in POLISH.replace(" ", "")
    assert "min-width:0!important" in POLISH.replace(" ", "")
    assert "flex:1 1 calc(50%" in POLISH



def test_no_nested_duplicate_border_on_shell_and_nav():
    # Only the nav container owns the L1 border; shell is forced display:none.
    assert POLISH.count("dashboard_deep_analysis_nav") >= 2
    assert "home-quick-actions-shell" in POLISH
    assert "display:none" in POLISH


def test_harness_renders_real_deep_analysis_dom_not_synthetic_stub():
    assert "fixture_dashboard_deep_analysis" not in HARNESS
    assert "workspace_ui.render_home_quick_actions" in HARNESS
    assert "MOBILE_VISUAL_POLISH_CSS" in HARNESS
    assert "inject_global_styles(MOBILE_VISUAL_POLISH_CSS)" in HARNESS


def test_dashboard_workflow_destinations_unchanged():
    actions = [
        ("League Overview", "rankings"),
        ("My Team", "my_team"),
        ("Trade Hub", "trade_hub"),
        ("Draft Center", "draft_summary"),
    ]
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    for label, route in actions:
        assert f'("{label}", "{route}")' in source


def test_apptest_renders_four_deep_analysis_controls():
    """Would have failed under the synthetic single-button harness stub."""

    app = AppTest.from_file(str(ROOT / "scripts" / "ui_validation_harness.py"), default_timeout=45)
    app.query_params["surface"] = "dashboard"
    app.run()
    assert not app.exception
    labels = [btn.label for btn in app.button]
    for expected in ("League Overview", "My Team", "Trade Hub", "Draft Center"):
        assert expected in labels, f"missing {expected} in {labels}"


def test_app_css_budget_unchanged_by_polish_inject():
    # Polish is injected separately from APP_CSS; this PR must not bloat APP_CSS.
    assert len(APP_CSS) <= 422_000


def test_doc_records_root_cause_and_qa_miss():
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert "home-quick-actions-shell" in text
    assert "fixture" in text.casefold() or "harness" in text.casefold()
    assert "dual" in text.casefold() or "double" in text.casefold()
