"""Canonical player portrait crop, fallback, and Trade Ideas hierarchy."""

from __future__ import annotations

import re
from pathlib import Path

from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS, compact_asset_html
from modules.portrait_normalization import card_focus_x
from modules.player_profile_ui import avatar_html, player_headshot_preset
from modules.trade_visual_language import exchange_marker_html


ROOT = Path(__file__).resolve().parents[1]


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
