"""Canonical player portrait crop, fallback, and Trade Ideas hierarchy."""

from __future__ import annotations

import re
from pathlib import Path

from modules.app_styles import APP_CSS
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS, compact_asset_html
from modules.football_asset_styles import FOOTBALL_ASSET_CSS
from modules.portrait_normalization import card_focus_x
from modules.player_profile_ui import avatar_html, player_headshot_preset
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS
from modules.trade_visual_language import exchange_marker_html


ROOT = Path(__file__).resolve().parents[1]
PORTRAIT_SOURCES = (
    ROOT / "modules" / "app_styles.py",
    ROOT / "modules" / "football_asset_styles.py",
    ROOT / "modules" / "compact_fantasy_assets.py",
    ROOT / "modules" / "player_profile_ui.py",
    ROOT / "modules" / "player_quick_view_styles.py",
    ROOT / "modules" / "trade_hub_ui.py",
)


def test_headshot_variants_map_surfaces_without_gemstone_names():
    assert player_headshot_preset("player-quick-view-avatar") == "profile"
    assert player_headshot_preset("player-profile-hero") == "profile"
    assert player_headshot_preset("trade-avatar") == "standard"
    assert player_headshot_preset("dg-compact-asset-avatar") == "standard"
    assert player_headshot_preset("scan-card-avatar") == "standard"
    assert player_headshot_preset("compact-player-avatar") == "standard"
    assert player_headshot_preset("dg-compact-asset-avatar--chip") == "compact"
    assert player_headshot_preset("compact-player-row") == "compact"
    html = avatar_html("https://sleepercdn.com/content/nfl/players/4046.jpg", "JH", "trade-avatar")
    assert "dg-player-headshot--standard" in html
    for family in ("diamond", "amethyst", "ruby", "graphite"):
        assert family not in html
        assert family not in FOOTBALL_ASSET_CSS


def test_standard_card_crop_is_cover_with_systemic_focus():
    assert "object-fit: cover !important" in APP_CSS
    assert "object-position: var(--dg-headshot-focus-x, 50%) var(--dg-headshot-focus) !important" in APP_CSS
    assert "--dg-headshot-focus: 22%" in APP_CSS
    assert "--dg-headshot-focus: 18%" in APP_CSS
    assert "--dg-headshot-focus: 20%" in APP_CSS
    assert "object-fit: contain !important" not in APP_CSS
    assert "object-position: center bottom !important" not in APP_CSS
    assert "transform: scale(var(--dg-headshot-scale)) !important" in APP_CSS
    assert "transform-origin: var(--dg-headshot-focus-x, 50%) var(--dg-headshot-focus) !important" in APP_CSS
    football = FOOTBALL_ASSET_CSS.replace(" ", "")
    compact = COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    focus = card_focus_x().replace(" ", "")
    assert "object-fit:cover" in football
    assert f"object-position:var(--dg-headshot-focus-x,{focus})var(--dg-headshot-focus,18%)" in football
    assert "object-fit:cover" in compact
    assert f"object-position:var(--dg-headshot-focus-x,{focus})var(--dg-headshot-focus,18%)" in compact
    assert "object-fit: cover" in TRADE_SUMMARY_COMPONENT_CSS
    assert f"object-position: var(--dg-headshot-focus-x, {card_focus_x()})" in TRADE_SUMMARY_COMPONENT_CSS
    assert "--dg-headshot-focus:22%" in PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "--dg-headshot-scale:1.65" in PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "--dg-headshot-scale: 1.16" in APP_CSS
    assert ".dg-player-headshot--standard" in APP_CSS


def test_no_per_player_portrait_offsets_or_sleeper_id_maps():
    css_blob = "\n".join(
        (
            APP_CSS,
            FOOTBALL_ASSET_CSS,
            COMPACT_FANTASY_ASSET_CSS,
            PLAYER_QUICK_VIEW_CSS,
            TRADE_SUMMARY_COMPONENT_CSS,
        )
    )
    assert re.search(r"object-position[^;]*4046", css_blob) is None
    assert "[data-player-id" not in css_blob
    assert ".player-jalen" not in css_blob.casefold()
    assert "HURTS_OFFSET" not in css_blob
    assert "PLAYER_OBJECT_POSITION" not in css_blob
    python_blob = "\n".join(path.read_text(encoding="utf-8") for path in PORTRAIT_SOURCES)
    assert "sleeper-id-specific" not in python_blob.casefold()
    assert "object_position_by_player" not in python_blob


def test_fallback_initials_hide_when_image_node_exists():
    loaded = avatar_html("https://example.com/ok.png", "JH", "player-avatar")
    assert "dg-player-headshot-fallback" in loaded
    assert "dg-player-headshot-image" in loaded
    assert "onerror=\"this.remove()\"" in loaded
    missing = avatar_html("", "JH", "player-avatar")
    assert "<img" not in missing
    assert ">JH<" in missing
    assert ":has(img.dg-player-headshot-image) .dg-player-headshot-fallback" in APP_CSS
    assert ":has(img.dg-player-headshot-image) .dg-player-headshot-fallback" in FOOTBALL_ASSET_CSS


def test_tier_frame_is_a_thin_ring_not_a_padded_window():
    assert "0 0 0 1px var(--dg-tier-a)" in FOOTBALL_ASSET_CSS
    assert "0 0 0 2px var(--dg-tier-a)" in FOOTBALL_ASSET_CSS
    assert "0 0 0 3px" not in FOOTBALL_ASSET_CSS
    assert "inset 0 0 0 4px" not in FOOTBALL_ASSET_CSS


def test_trade_idea_card_hierarchy_is_partner_then_exchange_then_why():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    start = source.index('<div class="trade-summary-partner-kicker">Trade with</div>')
    end = source.index("Review package</div>") + len("Review package")
    card = source[start:end]
    assert card.index("Trade with") < card.index("trade-summary-title")
    assert card.index("You send") < card.index("You receive")
    assert card.index("You receive") < card.index(">Balance<")
    assert card.index(">Balance<") < card.index("trade-summary-why")
    assert card.index("trade-summary-why") < card.index("Review package")
    assert "Review package →" not in card
    assert "Sending" not in card
    assert "Receiving" not in card
    marker = exchange_marker_html()
    assert "tvl-sr" in marker
    assert marker.count("FOR") == 1
    assert "tvl-sr'>FOR<" in marker.replace(" ", "") or "tvl-sr'>FOR</span>" in marker
    assert ".trade-summary-value .tvl-edge-cap { display: none; }" in TRADE_SUMMARY_COMPONENT_CSS


def test_compact_trade_rows_keep_identity_without_role_age_stack():
    html = compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "4046",
            "name": "Jalen Hurts",
            "position": "QB",
            "team": "PHI",
            "age": 27,
            "role": "Core Starter",
            "score": 5000,
        },
        size="compact",
        show_value=False,
        show_role=False,
    )
    assert "Jalen Hurts" in html
    assert "QB · PHI" in html
    assert "Age 27" in html
    assert "Core Starter" not in html
    assert "5000" not in html
    assert "dg-player-headshot--standard" in html
