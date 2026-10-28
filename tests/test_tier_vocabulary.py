"""Audit C4: one tier vocabulary for API, UI, SEO pages and the live draft board."""

import re
from pathlib import Path

import pandas as pd

from modules import live_draft, player_tier_identity, player_tiers

ROOT = Path(__file__).resolve().parent.parent
LABELS = {t.semantic_label for t in player_tier_identity.PLAYER_TIER_LADDER}


def test_every_stored_tier_maps_to_a_ladder_label():
    for stored in player_tiers.PLAYER_TIERS:
        assert player_tier_identity.is_known_stored_tier(stored), stored
        assert player_tier_identity.tier_display_label(stored) in LABELS
    # "Elite" in storage is the top tier; it is displayed Generational everywhere.
    assert player_tier_identity.tier_display_label("Elite") == "Generational"
    assert player_tier_identity.tier_display_label("Star") == "Elite"


def test_pool_percentile_uses_the_stored_profiles_cut_points():
    thresholds = dict(player_tiers.DEFAULT_PLAYER_TIER_PROFILE["thresholds"])
    top_share = 1.0 - thresholds["Elite"]
    assert player_tier_identity.stored_tier_for_pool_percentile(top_share * 0.5) == "Elite"
    assert player_tier_identity.stored_tier_for_pool_percentile(0.999) == "Developmental"
    seen = {player_tier_identity.stored_tier_for_pool_percentile(p / 200) for p in range(1, 201)}
    assert seen <= set(player_tiers.PLAYER_TIERS)


def test_live_draft_board_speaks_the_same_vocabulary():
    # The board carries STORED names (clients resolve them like every tier);
    # the draft no longer cuts its own ladder (Upside, 3/10/25/50/78%).
    assert live_draft._tier_for_rank(1, 100, "Elite") == "Elite"
    assert live_draft._tier_for_rank(1, 100, "Star") == "Star"
    seen = {live_draft._tier_for_rank(r, 300) for r in range(1, 301)}
    assert seen <= set(player_tiers.PLAYER_TIERS) and "Upside" not in seen
    # ...and the text a user reads for them is the one ladder:
    assert {player_tier_identity.tier_display_label(t) for t in seen} <= LABELS
    assert live_draft._tier_for_rank(50, 100, "Workhorse") in player_tiers.PLAYER_TIERS  # descriptor -> percentile


def _ts_table(path: str, name: str) -> dict[str, str]:
    text = (ROOT / path).read_text()
    start = text.index(f"const {name}")
    block = text[start : text.index("};", start)]
    pairs = re.findall(r"^\s*['\"]?([^'\":\n]+?)['\"]?:\s*['\"]([a-z_]+)['\"],", block, re.M)
    return {k.strip(): v for k, v in pairs}


def test_python_and_both_ts_tables_agree():
    py = {k.replace("_", " "): v for k, v in player_tier_identity.STORED_PLAYER_TIER_TO_ID.items()}
    for path, name in (
        ("web-next/src/lib/playerTier.ts", "STORED_TIER_TO_ID"),
        ("mobile/src/lib/playerTier.ts", "STORED_TIER_TO_ID"),
    ):
        ts = {k.replace("_", " "): v for k, v in _ts_table(path, name).items()}
        assert ts == py, f"{path} tier synonym table drifted from modules/player_tier_identity.py"
    for path in ("web-next/src/lib/playerTier.ts", "mobile/src/lib/playerTier.ts"):
        text = (ROOT / path).read_text()
        for tier in player_tier_identity.PLAYER_TIER_LADDER:
            assert f'semanticLabel: "{tier.semantic_label}"' in text or f"semanticLabel: '{tier.semantic_label}'" in text, (path, tier.tier_id)
