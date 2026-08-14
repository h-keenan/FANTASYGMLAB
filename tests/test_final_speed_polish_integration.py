"""Contracts that #303 / #304 / #305 must all survive on the integration branch."""

from __future__ import annotations

from pathlib import Path

from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS
from modules.player_eligibility import (
    filter_current_fantasy_players,
    is_current_fantasy_asset,
)
from modules.ui_primitives import AUTO_STRATEGY_HELP_TITLE


ROOT = Path(__file__).resolve().parents[1]


def test_trade_hub_keeps_share_before_supporting_and_auto_help():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    share_at = source.index("render_share_controls(")
    supporting_at = source.index("supporting_section_id = f\"trade_review_supporting_")
    actions_at = source.index("render_detail_actions(idea")
    assert share_at < supporting_at < actions_at
    assert "render_auto_strategy_help(" in source
    assert AUTO_STRATEGY_HELP_TITLE == "What is Auto?"


def test_app_keeps_auto_help_and_eligibility_and_shop_routing():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "render_auto_strategy_help(" in source
    assert 'st.columns([4, 1], gap="small")' in source
    assert 'surface="prepared_player_frame"' in source
    assert 'surface="trade_search_pool"' in source
    assert "next_move_shop_player_id" in source
    assert 'st.session_state["waivers_focus_player_id"]' in source


def test_harness_keeps_auto_fixture_and_roster_guide():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert 'key="ci_trade_strategy"' in harness
    assert "How these roster grades work" in harness


def test_desktop_width_tokens_and_roster_action_height_coexist():
    assert "--dg-exec-content-max: 1360px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "--dg-exec-content-max-wide: 1520px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "--dg-exec-content-max-ultra: 1680px" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    css = (ROOT / "modules" / "visual_hierarchy_styles.py").read_text(encoding="utf-8")
    assert "st-key-my_team_roster_actions" in css
    assert "height: auto" in css
    assert "How to read this roster" not in (
        ROOT / "modules" / "my_team_ui.py"
    ).read_text(encoding="utf-8")


def test_share_preview_export_contract_and_single_edge_bar():
    assert share.PREVIEW_DISPLAY_WIDTH == 320
    assert share.PREVIEW_RASTER_WIDTH == 640
    assert share.SHARE_WIDTH == 2160
    assert share.SHARE_HEIGHT == 2400
    idea = {
        "tag": "Win-now swap",
        "trade_gain": 200,
        "trade_confidence_label": "High",
        "reasoning_summary": "Send depth for a starter.",
        "send_assets": [
            {"asset_type": "player", "name": "Send A", "position": "RB", "team": "KC", "player_id": "s1"},
        ],
        "receive_assets": [
            {"asset_type": "player", "name": "Recv A", "position": "WR", "team": "MIA", "player_id": "r1"},
        ],
        "my_score": 80,
        "their_score": 280,
    }
    card = share.build_trade_share_card(idea, scoring_format="PPR")
    geometry = share_card_renderer.value_edge_bar_geometry(
        acquire=card.acquire_total,
        send=card.send_total,
        delta=share_card_renderer.card_value_delta(card),
        max_px=1000,
    )
    assert geometry["direction"] == "receive"
    assert int(geometry["fill"]) > 0
    png = share_card_renderer.render_share_card_png(card)
    preview = share_card_renderer.preview_png_bytes(png)
    assert png != preview
    assert len(png) < 2_500_000
    from PIL import Image
    from io import BytesIO

    export = Image.open(BytesIO(png))
    thumb = Image.open(BytesIO(preview))
    assert export.size == (2160, 2400)
    assert thumb.size == (640, int(round(2400 * 640 / 2160)))


def test_canonical_eligibility_owner_still_excludes_stale_listed_veteran():
    from datetime import datetime, timezone

    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    retired = {
        "player_id": "138",
        "name": "Stale Veteran",
        "full_name": "Stale Veteran",
        "sport": "nfl",
        "active": True,
        "status": "Active",
        "team": "PIT",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "years_exp": 18,
        "news_updated": 1643296817250,
        "depth_chart_order": 0,
        "depth_chart_position": "",
        "stats_season": None,
        "fantasycalc_value": 0,
        "age": 39,
        "injury_status": "",
    }
    assert is_current_fantasy_asset(retired, now=now) is False
    import pandas as pd

    kept = filter_current_fantasy_players(pd.DataFrame([retired]), now=now)
    assert kept.empty
    owner = (ROOT / "modules" / "player_eligibility.py").read_text(encoding="utf-8")
    assert "roethlisberger" not in owner.casefold()
