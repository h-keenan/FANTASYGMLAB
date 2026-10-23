"""League Rankings product clarity — presentation only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import league_display


ROOT = Path(__file__).resolve().parents[1]


def test_clarity_audit_doc_exists():
    doc = ROOT / "docs" / "league-overview-product-clarity-audit.md"
    text = doc.read_text(encoding="utf-8")
    assert "Most / Least Draft Capital" in text
    assert "League Insights" in text
    assert "Before section inventory" in text
