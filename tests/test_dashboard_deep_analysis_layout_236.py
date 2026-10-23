"""Dashboard Deep Analysis layout regression (#236)."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "dashboard-deep-analysis-layout-236.md"


def test_doc_records_root_cause_and_qa_miss():
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert "home-quick-actions-shell" in text
    assert "fixture" in text.casefold() or "harness" in text.casefold()
    assert "dual" in text.casefold() or "double" in text.casefold()
