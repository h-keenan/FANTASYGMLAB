"""Contracts for executive decision ordering and command-bar cohesion."""

from pathlib import Path

from modules import premium, trade_hub_ui
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_presentation_order_uses_gain_only_as_final_tiebreak():
    tied = [
        {
            "tag": "Lower gain twin",
            "partner_team_name": "B",
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "High",
            "market_realism_score": 80,
            "fit_score": 80,
            "partner_fit_score": 80,
            "strategy_fit_score": 80,
            "priority": 50,
            "trade_gain": 10,
            "send_assets": [{"player_id": "s1"}],
            "receive_assets": [{"player_id": "r1"}],
            "reasoning_summary": "Same surface strength, smaller delta",
        },
        {
            "tag": "Higher gain twin",
            "partner_team_name": "A",
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "High",
            "market_realism_score": 80,
            "fit_score": 80,
            "partner_fit_score": 80,
            "strategy_fit_score": 80,
            "priority": 50,
            "trade_gain": 40,
            "send_assets": [{"player_id": "s2"}],
            "receive_assets": [{"player_id": "r2"}],
            "reasoning_summary": "Same surface strength, larger delta",
        },
    ]
    ordered = trade_hub_ui.order_trade_hub_visible_ideas(tied)
    assert [idea["tag"] for idea in ordered] == [
        "Higher gain twin",
        "Lower gain twin",
    ]


def test_trade_hub_lead_is_presentation_first_card():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    selector = source[
        source.index("def select_trade_hub_headline_idea") : source.index(
            "def enrich_trade_ideas_with_manager_tendencies"
        )
    ]
    assert "order_trade_hub_visible_ideas" in selector
    assert "ordered[0]" in selector
    assert "market_realism_label" not in selector
    board = source[
        source.index("def render_top_trade_opportunities()") : source.index(
            'with st.expander("Search return paths from one of your players"'
        )
    ]
    assert "select_trade_hub_headline_idea(eligible_ideas)" in board
    assert "visible_count_key, 1)" in board


def test_player_and_acquisition_boards_order_before_render():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "order_trade_hub_visible_ideas(ideas[:max_ideas])" in source
    assert "order_trade_hub_visible_ideas(hub_ideas)" in source


def test_command_bar_uses_equal_columns_and_shared_control_metrics():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    topbar = source[
        source.index("def render_platform_topbar(") : source.index(
            "def _query_param_page("
        )
    ]
    assert "[1, 1, 1]" in topbar
    assert "[1.45, 1.1, 1.0]" not in topbar
    assert "height: var(--touch-target-min) !important" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "padding-inline: var(--space-md) !important" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "0.62rem" not in EXECUTIVE_COMMAND_HEADER_CSS
    legacy = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "min-height: 31px !important" not in legacy


def test_value_delta_label_replaces_impact_rank_ambiguity():
    disordered = [
        {
            "tag": "True headline",
            "partner_team_name": "A",
            "partner_roster_id": "a",
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "High",
            "market_realism_score": 90,
            "fit_score": 80,
            "partner_fit_score": 70,
            "strategy_fit_score": 60,
            "priority": 100,
            "trade_gain": -500,
            "send_assets": [{"player_id": "s2"}],
            "receive_assets": [{"player_id": "r2"}],
            "reasoning_summary": "Fixes a thin position need",
        }
    ]
    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        disordered,
        [],
        entitlement=premium.PREMIUM,
    )
    feed = trade_hub_ui.annotate_trade_hub_feed_categories(
        presentation["visible_ideas"],
        headline_idea=disordered[0],
    )
    assert feed[0]["_display_section"] == "Headline Recommendation"
    css_source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert ">Value delta<" in css_source or "Value delta" in css_source
