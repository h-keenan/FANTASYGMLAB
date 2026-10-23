"""Transitional UI / CSS consolidation contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_consolidation_document_exists():
    doc = ROOT / "docs" / "transitional-ui-css-consolidation.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    for marker in (
        "Transitional classes before / after",
        "CSS ownership map",
        "Override chains eliminated",
        "Table / disclosure decision",
        "Remaining intentional style debt",
    ):
        assert marker in text
