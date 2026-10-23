"""Focused Founder Beta brand & identity presentation tests."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity, premium, premium_benefits, startup_coordinator, trade_hub_presentation


def test_brand_constants_are_fantasygm_lab():
    assert brand_identity.PRODUCT_NAME == "FantasyDesk"
    assert brand_identity.PRODUCT_MARK == "FGL"
    assert brand_identity.EXPERIMENTAL_LABEL == "[EXPERIMENTAL]"
    # Founder Beta positioning is retired — plain subscription product now.
    assert not hasattr(brand_identity, "FOUNDER_BETA_LABEL")
    assert not hasattr(brand_identity, "FOUNDER_BETA_NOTE")
    assert not hasattr(brand_identity, "founder_beta_badge_html")
