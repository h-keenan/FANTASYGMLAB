"""Contracts for Founder Beta first-user UX audit (presentation only)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "founder-beta-first-user-audit.md"


def test_first_user_audit_doc_exists_with_required_sections():
    text = DOC.read_text(encoding="utf-8")
    assert "Top 25 usability issues" in text
    assert "Confusing wording" in text
    assert "Hidden features" in text
    assert "Missed opportunities" in text
    assert "Remaining usability concerns" in text
    assert "Rollback boundary" in text
    assert "05815d537c70c89a41de2d3ca20b591cc67da13b" in text


def test_customer_facing_copy_uses_gm_language_not_engineering_jargon():
    trade_hub = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    premium_source = (ROOT / "modules" / "premium.py").read_text(encoding="utf-8")
    brand = (ROOT / "modules" / "brand_identity.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert ">Balance<" in trade_hub
    assert ">Value delta<" not in trade_hub
    assert "Strategy focus:" in trade_hub
    assert "Active lens:" not in trade_hub
    assert '"Strategy"' in trade_hub or "Strategy" in trade_hub
    assert "Team strategy — generates trade ideas" not in trade_hub
    assert "TRADE_SETUP_CAPTION" in trade_hub
    assert "TRADE_BOARD_EDUCATION" in trade_hub
    assert "Confidence reflects how believable the path looks" in trade_hub

    assert 'cta: str = "Upgrade to Premium"' in premium_source
    assert 'GM_ORB_LABEL = "GM"' in brand
    assert "Where to go" in app
    assert "More next moves" in app
    assert "Import your Sleeper league to see trade ideas" in app
    assert "All Destinations" not in app


def test_harness_markers_track_first_user_copy():
    validator = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")

    assert '"Balance"' in validator
    assert '"Where to go"' in validator
    assert "Balance" in harness
    assert "Where to go" in harness
