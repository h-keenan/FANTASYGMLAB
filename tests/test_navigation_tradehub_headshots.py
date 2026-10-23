from __future__ import annotations

import re
from pathlib import Path

from modules.player_profile_ui import avatar_html, player_headshot_preset


ROOT = Path(__file__).resolve().parents[1]


def test_headshot_presets_are_shared_and_bounded():
    assert player_headshot_preset("trade-avatar") == "standard"
    assert player_headshot_preset("compact-player-row") == "compact"
    assert player_headshot_preset("player-avatar") == "standard"
    assert player_headshot_preset("player-profile-hero") == "profile"
    html = avatar_html("https://example.com/player.png", "AB", "trade-avatar")
    assert "dg-player-headshot" in html
    assert "dg-player-headshot--standard" in html
    assert "dg-player-headshot-image" in html
    assert "onload=" not in html
    assert "onerror=" not in html
    assert "dg-player-headshot-fallback" in html


def test_headshot_fallback_remains_centered_and_uses_shared_preset():
    html = avatar_html("", "AB", "player-avatar")
    assert "dg-player-headshot--standard" in html
    assert "dg-player-headshot-fallback" in html
    assert ">AB<" in html
    assert "<img" not in html
