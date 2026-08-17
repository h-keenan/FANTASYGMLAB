"""Player tier portrait identity — presentation mapping only."""

from __future__ import annotations

from pathlib import Path

from modules import football_assets, player_quick_view, player_tier_identity
from modules.app_styles import APP_CSS
from modules.football_asset_styles import FOOTBALL_ASSET_CSS
from modules.player_tier_identity import (
    PLAYER_TIER_LADDER,
    DEFAULT_PLAYER_TIER,
    portrait_frame_mode,
    resolve_player_tier_identity,
)


ROOT = Path(__file__).resolve().parents[1]


def test_ladder_has_seven_semantic_tiers_and_hidden_visual_families():
    assert [tier.tier_id for tier in PLAYER_TIER_LADDER] == [
        "generational",
        "elite",
        "impact_starter",
        "starter",
        "contributor",
        "committee_role",
        "depth_developmental",
    ]
    assert [tier.rank_order for tier in PLAYER_TIER_LADDER] == [1, 2, 3, 4, 5, 6, 7]
    families = [tier.visual_family for tier in PLAYER_TIER_LADDER]
    assert families == [
        "diamond",
        "amethyst",
        "ruby",
        "gold",
        "silver",
        "bronze",
        "graphite",
    ]


def test_stored_valuation_bands_map_one_to_one_without_math():
    mapping = {
        "Elite": "generational",
        "Star": "elite",
        "Core Starter": "impact_starter",
        "Starter": "starter",
        "Contributor": "contributor",
        "Depth": "committee_role",
        "Developmental": "depth_developmental",
        "Development": "depth_developmental",
    }
    for stored, expected in mapping.items():
        identity = resolve_player_tier_identity(stored_tier=stored)
        assert identity.tier_id == expected
        assert identity is player_tier_identity.PLAYER_TIER_BY_ID[expected]


def test_muddy_elite_contributor_normalizes_to_elite_not_a_new_band():
    identity = resolve_player_tier_identity(stored_tier="Elite Contributor")
    assert identity.tier_id == "elite"
    assert identity.semantic_label == "Elite"


def test_role_opportunity_text_does_not_become_a_valuation_tier():
    for label in (
        "Committee Back",
        "Backup With Upside",
        "Workhorse",
        "Elite Opportunity",
    ):
        identity = resolve_player_tier_identity(stored_tier=label)
        assert identity == DEFAULT_PLAYER_TIER


def test_unknown_and_missing_classification_fall_back_to_depth():
    assert resolve_player_tier_identity(None).tier_id == "depth_developmental"
    assert resolve_player_tier_identity({}).tier_id == "depth_developmental"
    assert resolve_player_tier_identity({"player_tier": ""}).tier_id == "depth_developmental"
    assert resolve_player_tier_identity(stored_tier="???").tier_id == "depth_developmental"


def test_player_row_player_tier_takes_precedence_over_empty_aliases():
    row = {"player_tier": "Star", "tier": "Developmental", "role_label": "Committee Back"}
    identity = resolve_player_tier_identity(row)
    assert identity.tier_id == "elite"
    assert identity.semantic_label == "Elite"


def test_portrait_size_rule_full_ring_none():
    assert portrait_frame_mode(size_rem=5.5) == "full"
    assert portrait_frame_mode(size_rem=3.5) == "full"
    assert portrait_frame_mode(size_px=44) == "ring"
    assert portrait_frame_mode(size_rem=2.75) == "ring"
    assert portrait_frame_mode(size_rem=2.25) == "ring"
    assert portrait_frame_mode(size_px=24) == "none"
    assert portrait_frame_mode(size_rem=1.5) == "none"


def test_pqv_hero_owns_one_semantic_label_and_full_frame():
    identity = resolve_player_tier_identity(stored_tier="Star")
    html = player_quick_view.pqv_hero_html(
        avatar_html=(
            "<div class='player-quick-view-avatar dg-player-headshot'>"
            "<span class='dg-player-headshot-fallback'>BR</span>"
            "<img class='dg-player-headshot-image' src='photo.png' alt=''>"
            "</div>"
        ),
        name="Bijan Robinson",
        position="RB",
        team="ATL",
        age_text="24",
        role_label="Elite Opportunity",
        identity=identity,
        include_tier_legend=True,
    )
    assert "pqv-hero-portrait dg-tier-frame dg-tier-frame--elite dg-tier-frame--full" in html
    assert html.count("pqv-hero-tier") == 1
    assert ">ELITE<" in html
    assert "Player tier: Elite" in html
    assert "Amethyst" not in html
    assert "Ruby Player" not in html
    assert html.count("Elite Opportunity") == 1
    assert "Player tiers" in html
    assert html.count("dg-tier-frame--elite") >= 1


def test_missing_photo_keeps_the_same_tier_frame():
    identity = resolve_player_tier_identity(stored_tier="Developmental")
    html = football_assets.player_card_html(
        football_assets.FootballPlayerAsset(
            player_id="p1",
            display_name="Depth Player",
            position="TE",
            team="CHI",
            prestige_label="Development",
            prestige_level="development",
        ),
        avatar_html=(
            "<div class='compact-player-avatar dg-player-headshot'>"
            "<span class='dg-player-headshot-fallback'>DP</span>"
            "</div>"
        ),
        identity=identity,
        tier_frame="full",
    )
    assert "dg-tier-frame--depth_developmental" in html
    assert "dg-player-headshot-fallback" in html
    assert "<img" not in html
    assert "Player tier: Depth / Developmental" in html


def test_my_team_roster_portrait_uses_canonical_frame_classes():
    identity = resolve_player_tier_identity(stored_tier="Elite")
    html = football_assets.player_card_html(
        football_assets.FootballPlayerAsset(
            player_id="p2",
            display_name="Cornerstone Quarterback With A Long Name",
            position="QB",
            team="PHI",
            prestige_label="Elite",
            prestige_level="elite",
        ),
        avatar_html="<div class='compact-player-avatar dg-player-headshot'><img class='dg-player-headshot-image' src='photo.png' alt=''></div>",
        identity=identity,
        tier_frame="full",
    )
    assert "dg-player-portrait" in html
    assert "dg-tier-frame--generational" in html
    assert "data-player-tier='generational'" in html
    assert "Diamond" not in html


def test_small_avatar_mode_is_none_and_css_has_chip_suppression():
    identity = resolve_player_tier_identity(stored_tier="Starter")
    classes = player_tier_identity.portrait_frame_classes(
        identity,
        base="dg-compact-asset-avatar",
        frame_mode=portrait_frame_mode(size_px=24),
    )
    assert "dg-tier-frame--none" in classes
    assert ".dg-compact-asset--chip .dg-tier-frame" in FOOTBALL_ASSET_CSS
    assert ".dg-tier-frame--none" in FOOTBALL_ASSET_CSS


def test_accessibility_label_exists_for_every_tier():
    for tier in PLAYER_TIER_LADDER:
        assert tier.accessibility_label == f"Player tier: {tier.semantic_label}"
        assert tier.visual_family not in tier.semantic_label
        assert tier.visual_family not in tier.short_label


def test_assign_player_tiers_thresholds_are_unchanged():
    from modules.player_tiers import DEFAULT_PLAYER_TIER_PROFILE, PLAYER_TIERS

    assert PLAYER_TIERS == (
        "Elite",
        "Star",
        "Core Starter",
        "Starter",
        "Contributor",
        "Depth",
        "Developmental",
    )
    assert DEFAULT_PLAYER_TIER_PROFILE["thresholds"] == (
        ("Elite", 0.992),
        ("Star", 0.975),
        ("Core Starter", 0.94),
        ("Starter", 0.84),
        ("Contributor", 0.66),
        ("Depth", 0.38),
        ("Developmental", 0.0),
    )


def test_identity_module_does_not_call_valuation_or_ai():
    source = (ROOT / "modules" / "player_tier_identity.py").read_text(encoding="utf-8")
    assert "assign_player_tiers(" not in source
    assert "st.rerun" not in source
    assert "openai" not in source.lower()


def test_frame_css_is_token_backed_and_not_player_specific():
    assert ".dg-tier-frame--generational" in FOOTBALL_ASSET_CSS
    assert ".dg-tier-frame--elite" in FOOTBALL_ASSET_CSS
    assert "Bijan" not in FOOTBALL_ASSET_CSS
    assert "Jeanty" not in FOOTBALL_ASSET_CSS
    assert "Hurts" not in FOOTBALL_ASSET_CSS
    assert "#" not in FOOTBALL_ASSET_CSS
    assert FOOTBALL_ASSET_CSS in APP_CSS
    assert "animation:" not in FOOTBALL_ASSET_CSS
    assert "pqv-hero-tier" in APP_CSS
