"""Founder Beta product-finish contracts: desktop Insights, Trade Hub board, Orb Close."""

from __future__ import annotations

from pathlib import Path

from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.player_quick_view import career_dossier_html
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.trade_detail_styles import TRADE_DETAIL_CSS
from modules.app_styles import APP_CSS
from modules.league_recaps_styles import LEAGUE_RECAPS_CSS
from modules.player_awards import PlayerBadge, TIER_GOLD


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_insights_use_usable_minmax_not_character_wrap():
    pair = DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "minmax(22rem, 1.35fr) minmax(18rem, 0.9fr)" in pair.replace(" ", "") or (
        "minmax(22rem, 1.35fr)" in pair and "minmax(18rem, 0.9fr)" in pair
    )
    css = DASHBOARD_WORKFLOW_CSS
    assert "word-break: normal" in css
    assert "word-break:anywhere" not in css.replace(" ", "").casefold()
    assert "overflow-wrap: break-word" in css
    desktop = css.split("@media (min-width: 1024px)", 1)[1]
    assert "minmax(20rem, 1fr)" in desktop
    assert "st-key-dashboard_league_insights" in css
    assert css not in APP_CSS


def test_trade_hub_board_is_headline_plus_secondary_grid():
    css = TRADE_DETAIL_CSS
    assert "st-key-trade_hub_board" in css
    assert "st-key-trade_hub_headline" in css
    assert "st-key-trade_hub_more_ideas" in css
    assert "st-key-trade_hub_show_more" in css
    assert "st-key-trade_hub_controls" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)" in css
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    feed = app.split("def _trade_hub_visible_feed()", 1)[1].split("_trade_hub_visible_feed()", 1)[0]
    assert "trade_hub_headline" in feed
    assert "trade_hub_more_ideas" in feed
    assert "trade_hub_show_more" in feed
    assert feed.index("visible_ideas[0]") < feed.index("trade_hub_more_ideas")


def test_pqv_desktop_dossier_and_accolades_surface():
    css = PLAYER_QUICK_VIEW_CSS
    assert "st-key-pqv_more_details" in css
    assert "st-key-pqv_actions_strip" in css
    assert "st-key-pqv_more_secondary" in css
    badge = PlayerBadge(
        badge_id="pos-2024",
        category="finish",
        title="Top-5 WR",
        short_label="WR5",
        tier=TIER_GOLD,
        season=2024,
        rank=5,
        metric_value=1.0,
        description="Verified",
        priority=1,
        family="positional-finish",
    )
    html = career_dossier_html(badges=(badge,), years_exp=6, position="WR")
    assert "Accolades" in html
    assert "WR5" in html
    assert "Experience" in html
    assert career_dossier_html(badges=(), years_exp=None) == ""


def test_browser_validator_targets_insights_column_and_compact_trade_cards():
    source = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    desktop = source.split("if width >= 1440:", 1)[1].split('metrics["desktopProductGeometry"]', 1)[0]
    assert 'querySelector(\'[class*="st-key-dashboard_league_insights"]\')' in desktop
    assert "insightsRoot.querySelector('.home-command-card')" not in desktop
    assert "compact_card = cards.nth(1)" in source
    assert "avatar_edge > 56" in source


def test_gm_orb_close_is_horizontal_glyph_owned():
    css = MOBILE_INTERACTION_OVERLAY_CSS
    assert 'content: "×"' in css
    assert "flex-shrink: 0" in css
    assert "st-key-mobile_sheet_close" in css
    assert "button::before" in css
    compact = css.replace(" ", "")
    assert "width:var(--touch-target-min)!important" in compact


def test_recap_and_surface_css_stay_out_of_app_css():
    assert LEAGUE_RECAPS_CSS not in APP_CSS
    assert DASHBOARD_WORKFLOW_CSS not in APP_CSS
    assert "st-key-trade_hub_board" not in APP_CSS
    assert len(APP_CSS) < 390_000
