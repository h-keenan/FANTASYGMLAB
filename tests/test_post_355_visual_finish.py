"""Post-#355 production visual finish contracts. Presentation only."""

from __future__ import annotations

import re
from pathlib import Path

from modules.app_styles import APP_CSS
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.player_quick_view import career_dossier_html, career_glance_html
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.semantic_glyphs import gm_orb_row_css
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]
PORTRAIT_OWNERS = (
    ROOT / "modules" / "app_styles.py",
    ROOT / "modules" / "player_quick_view_styles.py",
    ROOT / "modules" / "player_profile_ui.py",
    ROOT / "modules" / "compact_fantasy_assets.py",
    ROOT / "modules" / "football_asset_styles.py",
    ROOT / "modules" / "trade_hub_ui.py",
)


def test_large_pqv_portrait_fill_is_systemic_not_player_specific():
    profile = APP_CSS.split(".dg-player-headshot--profile", 1)[1][:220]
    standard = APP_CSS.split(".dg-player-headshot--standard", 1)[1][:220]
    assert "--dg-headshot-scale: 1.65" in profile
    assert "--dg-headshot-focus: 22%" in profile
    assert "--dg-headshot-scale: 1.16" in standard
    assert "--dg-headshot-focus: 18%" in standard
    pqv = PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "--dg-headshot-scale:1.65" in pqv
    assert "--dg-headshot-focus:22%" in pqv
    assert "transform-origin:centervar(--dg-headshot-focus,22%)" in pqv
    assert "object-fit:cover!important" in pqv
    assert "inset:0!important" in pqv
    blob = "\n".join(path.read_text(encoding="utf-8") for path in PORTRAIT_OWNERS)
    assert re.search(r"object-position[^;]*(11566|8228|tracy)", blob, re.I) is None
    assert "[data-player-id" not in PLAYER_QUICK_VIEW_CSS
    assert "sleeper-id" not in blob.casefold()
    assert "tyrone-tracy" not in blob.casefold()


def test_standard_trade_idea_portraits_remain_52px_baseline():
    css = (COMPACT_FANTASY_ASSET_CSS + TRADE_SUMMARY_COMPONENT_CSS).replace(" ", "")
    assert "dg-compact-asset--standard{--size-asset-standard:3.25rem" in css
    assert "--dg-headshot-scale: 1.16" in APP_CSS
    assert ".dg-player-headshot--standard" in APP_CSS


def test_orb_icon_and_label_share_tight_left_tokens():
    row = gm_orb_row_css().replace(" ", "")
    overlay = MOBILE_INTERACTION_OVERLAY_CSS.replace(" ", "")
    assert "--dg-orb-glyph-inset:var(--space-sm)" in row
    assert "--dg-orb-glyph-gap:var(--space-sm)" in row
    assert "--dg-orb-glyph-slot:1.25rem" in row
    assert "button::before" in gm_orb_row_css()
    assert "left:var(--dg-orb-glyph-inset)" not in row
    start = "padding-inline-start:calc(var(--dg-orb-glyph-inset)+var(--dg-orb-glyph-slot)+var(--dg-orb-glyph-gap))"
    assert start not in row
    assert start not in overlay
    assert 'content:"CURRENT"!important' in overlay
    assert "content:\"›\"!important" in overlay or 'content:"›"!important' in overlay


def test_career_glance_label_and_value_are_stacked_not_concatenated():
    html = career_glance_html(years_exp=2, badges=(), position="RB")
    assert "EXPERIENCE" not in html
    assert ">Experience<" in html or ">Experience</span>" in html
    assert "<span>" in html and "<strong>" in html
    assert "2 NFL seasons" in html
    assert "Experience2" not in html.replace(" ", "")
    css = PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert ".pqv-career-glance-cell{display:grid;gap:var(--space-2xs)" in css
    dossier = career_dossier_html(years_exp=2, badges=(), position="RB")
    assert "pqv-career-glance-cell" in dossier
    assert "Experience2" not in dossier.replace(" ", "")


def test_actions_use_compact_primary_plus_secondary_grid():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = app[
        app.index("def render_player_quick_view_content(") : app.index(
            "def render_player_detail_content("
        )
    ]
    assert 'key=f"pqv_actions_{player_id}"' in pqv
    assert 'key=f"pqv_actions_secondary_{player_id}"' in pqv
    assert '"Untouchable"' in pqv
    assert "Mark as Untouchable" not in pqv
    assert "compact=True" in pqv
    assert 'button_label="Share"' in pqv
    css = PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "st-key-pqv_actions_" in css
    assert "st-key-pqv_actions_secondary_" in css or "stHorizontalBlock" in css
    assert "min-height:var(--touch-target-min)!important" in css


def test_more_details_has_single_bio_and_advanced_ownership():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = app[
        app.index("def render_player_quick_view_content(") : app.index(
            "def render_player_detail_content("
        )
    ]
    assert pqv.count("pqv-more-group-title'>Bio") == 0
    assert pqv.count("pqv-more-group-title'>Model") == 0
    assert "Career &amp; Stats" in pqv
    assert pqv.count('"Advanced analysis"') == 1
    bio = (ROOT / "modules" / "player_quick_view.py").read_text(encoding="utf-8")
    assert 'dossier_section_heading_html("Bio")' in bio


def test_advanced_analysis_odd_final_cell_spans_intentionally_on_mobile():
    css = PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert ".pqv-model-matrix{display:grid" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert ".pqv-model-cell:last-child:nth-child(odd){grid-column:1/-1}" in css
    desktop = PLAYER_QUICK_VIEW_CSS.split("@media (min-width: 1024px)", 1)[1]
    assert "grid-template-columns:repeat(5,minmax(0,1fr))" in desktop.replace(" ", "")
    assert "grid-column:auto" in desktop.replace(" ", "")
