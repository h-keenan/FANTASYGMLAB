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
