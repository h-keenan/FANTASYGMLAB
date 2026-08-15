"""Desktop density, Auto help affordance, and Refresh recommendations wrapping."""

from pathlib import Path

from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS
from modules.ui_primitives import AUTO_STRATEGY_HELP_TITLE


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_content_max_uses_more_horizontal_space():
    assert "--dg-exec-content-max: 1360px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "--dg-exec-content-max-wide: 1520px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "--dg-exec-content-max-ultra: 1680px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "dashboard_context_pair" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "@media (max-width: 760px)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    styles = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(encoding="utf-8")
    assert "flex-direction: column" in styles
    assert "width: 100%" in styles
    assert "st-key-dashboard_workflow > div" in DESKTOP_EXECUTIVE_LAYOUT_CSS or "st-key-dg_cta_" in DESKTOP_EXECUTIVE_LAYOUT_CSS


def test_auto_help_is_an_explicit_what_is_auto_control():
    trade = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    selector = trade.split("def render_trade_strategy_selector", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "help=" not in selector
    assert "render_auto_strategy_help" in selector
    assert AUTO_STRATEGY_HELP_TITLE == "What is Auto?"
    primitives = (ROOT / "modules" / "ui_primitives.py").read_text(encoding="utf-8")
    assert 'st.popover(AUTO_STRATEGY_HELP_TITLE' in primitives
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'help="Auto follows your team\'s evaluated direction. Manual choices only change how recommendations are ranked."' not in app
    assert "render_auto_strategy_help" in app
    my_team_block = app.split('"Team strategy"', 1)[1].split("with st.expander", 1)[0]
    assert "render_auto_strategy_help" in my_team_block
    assert "Untouchables" in my_team_block
    assert "selector_cols" not in my_team_block


def test_refresh_recommendations_does_not_wrap():
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert '"Refresh"' in briefing
    assert "white-space:nowrap" in briefing.replace(" ", "")
    assert "use_container_width=False" in briefing
    assert "st.columns(" not in briefing


def test_trade_harness_includes_auto_help_affordance():
    source = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert "render_trade_strategy_selector" in source
    assert 'key="ci_trade_strategy"' in source


def test_dashboard_secondary_context_is_paired_on_desktop():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert 'key="dashboard_context_pair"' in source
    insights = source.index('with st.expander("League Insights"')
    snapshot = source.index('with st.expander("Team Snapshot"')
    pair = source.index('key="dashboard_context_pair"')
    assert pair < insights < snapshot
