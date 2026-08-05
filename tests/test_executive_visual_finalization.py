"""Presentation-only regression for executive visual system finalization."""

from pathlib import Path

from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_command_bar_and_portrait_finalization_live_in_unify_layer():
    css = EXECUTIVE_DESIGN_UNIFY_CSS
    assert ".dg-executive-shell{padding-block:0" in css
    assert "dg-founder-badge{min-height:var(--touch-target-min)" in css
    assert "#" not in css
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "EXECUTIVE_DESIGN_UNIFY_CSS" in styles


def test_trade_summary_eye_flow_puts_package_before_impact():
    css = TRADE_SUMMARY_COMPONENT_CSS
    assert ".trade-summary-package" in css and "order: 2" in css
    assert ".trade-summary-executive" in css and "order: 3" in css
    assert "flex-direction: column" in css
    assert "opacity: 0.72" in css
    html_source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    start = html_source.index('<article class="trade-summary-card')
    end = html_source.index("</article>", start)
    card = html_source[start:end]
    assert card.index("trade-summary-title") < card.index("trade-summary-category")
    assert card.index("trade-summary-package") < card.index("trade-summary-executive")
    assert card.index("trade-summary-impact-row") < card.index("trade-summary-why")


def test_dashboard_actions_precede_analysis_zones():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    order = [
        source.index(title)
        for title in (
            '"Your Next Move"',
            '"League Intelligence"',
            '"Immediate Action"',
            '"Team Snapshot"',
            '"Deep Analysis"',
        )
    ]
    assert order == sorted(order)


def test_legacy_avatar_black_gradient_removed_from_shared_portrait_classes():
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    avatar_block = styles[
        styles.index(".trade-avatar,") : styles.index(".trade-avatar,") + 900
    ]
    assert "#020617" not in avatar_block
    assert "var(--color-surface-raised)" in avatar_block
    assert "border-radius: 50%" not in avatar_block
    assert "--dg-headshot-scale: 1.18" in styles
