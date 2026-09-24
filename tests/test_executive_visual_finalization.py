"""Presentation-only regression for executive visual system finalization."""

from pathlib import Path

from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_command_bar_and_portrait_finalization_live_in_unify_layer():
    css = EXECUTIVE_DESIGN_UNIFY_CSS
    assert "dg-founder-badge{align-items:center!important;min-height:0!important" in css
    assert "#" not in css
    from modules.application_shell_styles import APPLICATION_SHELL_CSS

    assert "padding-block: 0;" in APPLICATION_SHELL_CSS
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "EXECUTIVE_DESIGN_UNIFY_CSS" in styles


def test_trade_summary_eye_flow_puts_value_before_package():
    # Magna Carta pass: recommendation type (category) leads, then team name +
    # fairness pill, then the value-change number gets its own prominent row
    # ahead of the send/receive package; confidence moved after the package so
    # it reads as supporting detail rather than competing with the verdict.
    css = TRADE_SUMMARY_COMPONENT_CSS
    assert ".trade-summary-value-row" in css and "order: 2" in css
    assert ".trade-summary-package" in css and "order: 3" in css
    assert ".trade-summary-executive" in css and "order: 4" in css
    assert "flex-direction: column" in css
    assert "opacity: 0.72" in css
    html_source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    start = html_source.index('<article class="trade-summary-card')
    end = html_source.index("</article>", start)
    card = html_source[start:end]
    assert card.index("trade-summary-category") < card.index("trade-summary-title")
    assert card.index("trade-summary-title") < card.index("trade-summary-value-row")
    assert card.index("trade-summary-value-row") < card.index("trade-summary-package")
    assert card.index("trade-summary-package") < card.index("trade-summary-executive")
    assert card.index("trade-summary-executive") < card.index("trade-summary-why")


def test_dashboard_actions_precede_analysis_zones():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    order = [
        source.index(title)
        for title in (
            "render_todays_game_plan()",
            "render_what_changed()",
            'render_section_header("League Insights"',
            'render_section_header("Team Snapshot"',
            '"Explore"',
        )
    ]
    assert order == sorted(order)


def test_legacy_avatar_black_gradient_removed_from_shared_portrait_classes():
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    avatar_block = styles.split("\n.trade-avatar,\n.player-avatar,\n.free-agent-avatar {", 1)[1].split("}", 1)[0]
    assert "#020617" not in avatar_block
    assert "var(--color-surface-raised)" in avatar_block
    assert "border-radius: 50%" not in avatar_block
    assert "--dg-headshot-scale: 1.16" in styles
