"""Contracts for Trade Hub unified feed and executive toolbar simplification."""

from pathlib import Path

from modules import trade_hub_ui


ROOT = Path(__file__).resolve().parents[1]


def test_annotate_trade_hub_feed_preserves_order_and_sets_category_badges():
    ideas = [
        {
            "tag": "Need Path",
            "partner_team_name": "A",
            "send_assets": [{"player_id": "1"}],
            "receive_assets": [{"player_id": "2"}],
            "reasoning_summary": "Fixes a thin position need",
            "trade_confidence_label": "Medium",
        },
        {
            "tag": "Health Path",
            "partner_team_name": "B",
            "send_assets": [{"player_id": "3"}],
            "receive_assets": [{"player_id": "4"}],
            "reasoning_summary": "Injury relief for an IR starter",
            "trade_confidence_label": "High",
        },
    ]
    feed = trade_hub_ui.annotate_trade_hub_feed_categories(
        ideas,
        headline_idea=ideas[0],
    )
    assert [item["tag"] for item in feed] == ["Need Path", "Health Path"]
    assert feed[0]["_display_section"] == "Headline Recommendation"
    assert feed[1]["_display_section"] == "Health Relief"


def test_trade_hub_route_uses_unified_feed_without_category_pills():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    board = source[
        source.index("def render_top_trade_opportunities()") : source.index(
            'with st.expander("Search return paths from one of your players"'
        )
    ]
    assert "annotate_trade_hub_feed_categories(" in board
    assert "render_trade_hub_section_filter(" not in board
    assert "st.pills(" not in board
    assert 'key_prefix="trade_hub_feed"' in board
    assert "group_trade_hub_ideas(" in board  # retained for internal counts


def test_feedback_lives_in_profile_menu_not_header_strip():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    topbar = source[
        source.index("def render_platform_topbar(") : source.index("def _query_param_page(")
    ]
    profile = source[
        source.index("def render_executive_profile_control(") : source.index(
            "def render_platform_topbar("
        )
    ]
    assert "feedback_col" not in topbar
    assert 'placement="header"' not in topbar
    assert 'placement="profile"' in profile
    assert "Send feedback" in (ROOT / "modules" / "feedback_ui.py").read_text(
        encoding="utf-8"
    )


def test_trade_card_html_includes_category_badge():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "trade-summary-category" in source
    assert "{section}" in source
