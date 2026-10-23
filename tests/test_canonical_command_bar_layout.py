"""Geometry contracts for the canonical executive command-bar layout."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_contract_doc_exists():
    text = (
        ROOT / "docs" / "canonical-command-bar-layout-contract.md"
    ).read_text(encoding="utf-8")
    for heading in (
        "Previous competing contracts",
        "Root cause",
        "Final primitive",
        "CSS removed",
        "Responsive rules",
        "Remaining limitations",
    ):
        assert heading in text
    assert "0c5ba3387e87004deaa6a859d9f7a97e69ef47e4" in text
