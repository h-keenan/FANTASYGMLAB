"""Regression tests for production-screenshot visual and ownership failures."""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS, compact_asset_html
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.player_quick_view import (
    canonical_player_read_copy,
    career_timeline_html,
    compose_fantasygm_read_factors,
    is_trade_package_copy,
    pqv_hero_html,
    why_this_recommendation_html,
)
from modules.player_history import HistoricalSeason, CareerResume
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.semantic_glyphs import gm_orb_row_css
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS, _trade_summary_assets_html


ROOT = Path(__file__).resolve().parents[1]


def test_modal_pqv_portrait_frame_is_square_and_not_stretched():
    css = PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "align-items:start!important" in css
    assert "grid-template-columns:autominmax(0,1fr)!important" in css
    assert "align-self:start!important" in PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "--pqv-portrait-size" in PLAYER_QUICK_VIEW_CSS
    assert "58px minmax(0, 1fr)" not in APP_CSS
    assert "align-items: stretch !important" not in APP_CSS.split(".player-quick-view-header-band.player-quick-view-hero")[1][:400]
    html = pqv_hero_html(
        avatar_html="<div class='player-quick-view-avatar'></div>",
        name="Tyrone Tracy",
        position="RB",
        team="NYG",
        age_text="26",
    )
    assert "pqv-hero-portrait" in html
    assert "player-quick-view-copy" in html


def test_trade_rationale_never_becomes_canonical_player_why():
    trade_why = (
        "You add future flexibility. American Njigba Warriors gets RB help "
        "and moves from WR surplus."
    )
    trade_risk = (
        "Strong fit, believable market path, and enough partner motivation to lead the board."
    )
    assert is_trade_package_copy(trade_why)
    assert is_trade_package_copy(trade_risk)
    read = canonical_player_read_copy(
        why_candidates=(trade_why, "Featured early-down RB with usable receiving work."),
        fit_candidates=(trade_why, "Used as a committee RB behind a stable starter."),
        risk_candidates=(trade_risk, "Workload competition on a crowded backfield."),
        blocked_values=(trade_why, trade_risk),
    )
    assert "future flexibility" not in read["why"].casefold()
    assert "wr surplus" not in read["why"].casefold()
    assert "partner motivation" not in read["risk"].casefold()
    assert "market path" not in read["risk"].casefold()
    assert "Featured early-down" in read["why"]
    assert "committee RB" in read["fit"]
    assert "Workload competition" in read["risk"]
    html = why_this_recommendation_html(
        compose_fantasygm_read_factors(
            why=read["why"],
            team_fit=read["fit"],
            risk=read["risk"],
            skip_values=(trade_why,),
        )
    )
    assert "You add future flexibility" not in html
    assert "partner motivation" not in html
    assert ">Why<" in html
    assert ">Fit<" in html
    assert ">Risk<" in html


def test_standard_trade_idea_portrait_meets_identity_row_contract():
    html = _trade_summary_assets_html(
        [
            {
                "asset_type": "player",
                "player_id": "8228",
                "name": "Tyrone Tracy",
                "position": "RB",
                "team": "NYG",
                "age": 26,
            }
        ]
    )
    assert "dg-compact-asset--standard" in html
    assert "dg-compact-asset-copy" in html
    assert "Tyrone Tracy" in html
    assert "RB · NYG" in html
    css = (COMPACT_FANTASY_ASSET_CSS + TRADE_SUMMARY_COMPONENT_CSS).replace(" ", "")
    assert "dg-compact-asset--standard{--size-asset-standard:3.25rem" in css
    assert ".dg-compact-asset--standard{grid-template-columns:var(--size-asset-standard)" in css
    compact = compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "4046",
            "name": "Jalen Hurts",
            "position": "QB",
            "team": "PHI",
            "age": 27,
        },
        size="standard",
        show_value=False,
        show_role=False,
    )
    assert "dg-compact-asset--standard" in compact
    assert "object-position:center18%" in COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    assert "[data-player-id" not in TRADE_SUMMARY_COMPONENT_CSS
    assert "tvl-count" not in html


def test_gm_orb_glyph_and_label_form_one_left_identity_group():
    css = gm_orb_row_css().replace(" ", "")
    overlay = MOBILE_INTERACTION_OVERLAY_CSS.replace(" ", "")
    assert "justify-content:flex-start!important" in css
    assert "padding-inline-start:calc(var(--dg-orb-glyph-inset)+var(--dg-orb-glyph-slot)+var(--dg-orb-glyph-gap))!important" in css
    assert "--dg-orb-glyph-gap:var(--space-sm)" in css
    assert "--dg-orb-glyph-inset:var(--space-sm)" in css
    assert "left:var(--dg-orb-glyph-inset)" in css
    assert "padding-inline-start:calc(var(--dg-orb-glyph-inset)+var(--dg-orb-glyph-slot)+var(--dg-orb-glyph-gap))" in overlay
    assert "--dg-orb-glyph-inset:var(--space-sm)" in overlay
    assert "padding-inline:0!important" in overlay
    assert "text-align:left!important" in css
    assert 'content:"CURRENT"!important' in overlay
    assert "st-key-mobile_sheet_nav_" in css
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "route_row_glyph_html(page.key)" in app


def test_more_details_and_advanced_analysis_stay_compact_and_accessible():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = app[
        app.index("def render_player_quick_view_content(") : app.index(
            "def render_player_detail_content("
        )
    ]
    assert "More details" in pqv
    assert "Open in Trade Hub" in pqv
    assert pqv.index("Open in Trade Hub") < pqv.index("More details")
    assert "Career &amp; Stats" in pqv
    assert "pqv-more-group-title'>Bio" not in pqv
    assert "pqv-more-group-title'>Model" not in pqv
    assert "Advanced analysis" in pqv
    assert 'st.container(key=f"pqv_actions_{player_id}")' in pqv
    assert 'st.container(key=f"pqv_actions_secondary_{player_id}")' in pqv
    assert '"Untouchable"' in pqv
    assert 'button_label="Share"' in pqv
    assert "pqv-model-matrix" in pqv
    assert "pqv-model-matrix" in PLAYER_QUICK_VIEW_CSS
    assert "canonical_player_read_copy" in pqv
    resume = CareerResume(
        seasons=(
            HistoricalSeason(
                season=2025,
                age=26,
                games=15,
                fantasy_points=160.8,
                fantasy_ppg=10.7,
                position_finish=28,
                current_season=True,
                key_stats=(("Rush Yards", "740"), ("Rec Yards", "288")),
                achievements=(),
            ),
            HistoricalSeason(
                season=2024,
                age=25,
                games=17,
                fantasy_points=140.0,
                fantasy_ppg=8.2,
                position_finish=32,
                current_season=False,
                key_stats=(("Rush Yards", "600"),),
                achievements=(),
            ),
        ),
        achievements=(),
        source_note="fixture",
    )
    html = career_timeline_html(resume, expanded=True)
    assert "player-dossier-timeline-metrics" in html
    assert "10.7 PPG" in html
    assert "160.8 PPR points · 10.7 PPG · Rush Yards 740" not in html


def test_app_css_budget_and_pqv_css_remain_route_owned():
    assert len(APP_CSS) < 390_000
    assert PLAYER_QUICK_VIEW_CSS not in APP_CSS
    assert "st.rerun()" not in gm_orb_row_css()
    overlay = (ROOT / "app.py").read_text(encoding="utf-8")
    sheet = overlay.split("def render_mobile_destination_sheet", 1)[1].split(
        "def render_mobile_navigation_shell", 1
    )[0]
    assert "st.rerun()" not in sheet
