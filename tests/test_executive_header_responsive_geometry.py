"""Contracts for executive header responsive geometry (#185 family)."""

from __future__ import annotations

from pathlib import Path

from modules import notification_center


ROOT = Path(__file__).resolve().parents[1]


def test_geometry_contract_doc_exists():
    doc = (ROOT / "docs" / "executive-header-responsive-geometry.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "Root cause",
        "Responsive contract",
        "Breakpoint behavior",
        "Command sizing",
        "Chevron",
        "CSS ownership",
        "Performance",
        "Remaining limitations",
    ):
        assert heading in doc
    assert "da23e67dea9b2fffa488157631893868d9b8cf33" in doc
