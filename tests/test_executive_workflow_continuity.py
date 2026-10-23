"""Executive workflow continuity contracts — presentation only."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audit_document_exists():
    doc = (ROOT / "docs" / "executive-workflow-continuity-audit.md").read_text(
        encoding="utf-8"
    )
    for section in (
        "Workflow journeys",
        "Before navigation map",
        "After navigation map",
        "Dead ends removed",
        "Duplicate transitions removed",
        "Remaining workflow friction",
        "Future opportunities",
        "Cross-page state",
    ):
        assert section in doc
