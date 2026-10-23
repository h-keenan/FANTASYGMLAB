"""Core Founder Beta journey consistency — terminology, gates, and launch CTAs.

Retriggers Delivery Validation after an empty Actions runner allocation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import product_copy
from modules import ui_architecture


ROOT = Path(__file__).resolve().parents[1]
PREMIUM = (ROOT / "modules" / "premium_benefits.py").read_text(encoding="utf-8")


def test_product_copy_matches_platform_destination_labels():
    for key, label in (
        ("players", "Players"),
        ("trade_hub", "Trade Hub"),
        ("rankings", "League Rankings"),
        ("dashboard", "Dashboard"),
        ("my_team", "My Team"),
        ("waivers", "Waivers"),
    ):
        assert product_copy.destination_label(key) == label
        assert next(page.label for page in ui_architecture.PLATFORM_DESTINATIONS if page.key == key) == label


def test_premium_and_landing_use_full_trade_hub():
    assert "PREMIUM_FULL_TRADE_HUB" in PREMIUM
    assert product_copy.PREMIUM_FULL_TRADE_HUB == "Full Trade Hub"
    html = (ROOT / "static" / "landing" / "index.html").read_text(encoding="utf-8")
    assert "Full Trade Hub" in html
    assert "Full trade board" not in html
