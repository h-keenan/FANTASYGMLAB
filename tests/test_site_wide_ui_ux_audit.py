"""Site-wide UI/UX audit contracts (PR #167)."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_site_wide_ui_ux_audit_doc_exists():
    doc = (ROOT / "docs" / "site-wide-ui-ux-audit.md").read_text(encoding="utf-8")
    assert "P0" in doc and "P1" in doc and "P2" in doc
    assert "terminology" in doc.casefold()
    assert "screenshot matrix" in doc.casefold() or "Screenshot matrix" in doc
    assert "No football" in doc or "no football" in doc.casefold()
    assert "Alerts" in doc
    assert "Your Next Move" in doc
