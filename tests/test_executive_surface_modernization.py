"""Executive surface modernization contracts (PR #137)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_modernization_document_exists():
    doc = (ROOT / "docs" / "executive-surface-modernization.md").read_text(encoding="utf-8")
    for section in (
        "Legacy Surface Inventory",
        "Consistency Matrix",
        "Remaining legacy count",
        "Explicit confirmation",
    ):
        assert section in doc
    assert "d487bcdd9d1b31e7cea2c5a27a92826050a7a233" in doc
