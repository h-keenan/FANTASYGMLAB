from pathlib import Path

from modules.app_styles import APP_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.founder_beta_consistency_styles import FOUNDER_BETA_CONSISTENCY_CSS
from modules.mobile_workflow_styles import MOBILE_WORKFLOW_CSS
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_ten_level_typography_hierarchy_is_tokenized():
    required = (
        "--type-page-eyebrow-size",
        "--type-page-title",
        "--type-body-explanation",
        "--type-section-eyebrow-size",
        "--type-section-title",
        "--type-card-title",
        "--type-primary-metric",
        "--type-supporting-metadata",
        "--type-badge-size",
    )
    for token in required:
        assert token in DESIGN_TOKEN_CSS


def test_consistency_layer_is_loaded_last():
    assert APP_CSS.index(FOUNDER_BETA_CONSISTENCY_CSS) > APP_CSS.index(
        MOBILE_WORKFLOW_CSS
    )
    assert APP_CSS.rindex(".dg-workspace-page-title") >= APP_CSS.index(
        FOUNDER_BETA_CONSISTENCY_CSS
    )


def test_mobile_titles_wrap_by_words_without_clipping():
    css = FOUNDER_BETA_CONSISTENCY_CSS
    assert "@media (max-width: 700px)" in css
    assert "@media (max-width: 340px)" in css
    assert "overflow-wrap: break-word !important;" in css
    assert "word-break: normal !important;" in css
    assert "writing-mode: horizontal-tb !important;" in css
    assert "max-width: none !important;" in css


def test_mobile_cards_share_full_width_and_geometry():
    css = FOUNDER_BETA_CONSISTENCY_CSS
    for selector in (
        ".dg-ui-card",
        ".summary-tile",
        ".home-command-card",
        ".trade-summary-card",
        ".free-agent-card",
        ".player-asset-card",
    ):
        assert selector in css
    assert ".team-rank-card" not in css
    assert "width: 100% !important;" in css
    assert "grid-template-columns: minmax(0, 1fr) !important;" in css
    assert "border-radius: var(--radius-panel) !important;" in css
    assert "padding: var(--space-md) !important;" in css


def test_workspace_hero_is_bounded_on_mobile():
    css = FOUNDER_BETA_CONSISTENCY_CSS
    assert "min-height: 5.25rem !important;" in css
    assert "font-size: clamp(1.55rem, 8vw, 2.05rem) !important;" in css
    assert ".dg-workspace-page-note {\n        display: none;" in css


def test_league_overview_prioritizes_rankings_and_discloses_four_concepts():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    rankings = source[source.index('if league_section == "Rankings":') :]
    board_index = rankings.index("render_power_rankings_board(")
    about_index = rankings.index('with st.expander("About these metrics"')
    concept_block = rankings[about_index : rankings.index("strongest_starters =")]
    assert 'elif league_section != "Rankings":' in source
    assert board_index < about_index
    for label in ("Power Rank", "Franchise Rank", "Strategy", "Archetype"):
        assert f'"label": "{label}"' in concept_block
    assert "Power Rank answers who is strongest right now" not in rankings[:6000]


def test_trade_summary_remains_summary_first():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_trade_idea_card(") :
        source.index("\ndef render_trade_idea_player_actions(")
    ]
    summary = renderer[: renderer.index("if summary_clicked is True:")]
    assert "trade-summary-card" in summary
    assert "_trade_summary_assets_html" in summary
    assert "{assets_html(send_assets)}" not in summary
    assert "trade-avatar" not in summary
    assert "View trade" in summary


def test_global_hierarchy_does_not_enter_isolated_trade_component():
    assert FOUNDER_BETA_CONSISTENCY_CSS not in TRADE_SUMMARY_COMPONENT_CSS
    assert "css=TRADE_SUMMARY_COMPONENT_CSS" in (
        ROOT / "modules" / "trade_hub_ui.py"
    ).read_text(encoding="utf-8")


def test_hierarchy_document_contains_before_after_table_and_all_surfaces():
    document = (ROOT / "docs" / "founder-beta-ui-hierarchy.md").read_text(
        encoding="utf-8"
    )
    assert "| Level | Role | Token | Before | Founder Beta |" in document
    for surface in (
        "Dashboard",
        "League Overview",
        "Trade Board",
        "My Team",
        "Waivers",
        "Player Explorer",
        "Premium",
    ):
        assert surface in document
