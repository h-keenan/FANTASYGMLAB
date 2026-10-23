"""Contracts for Alerts anchored dropdown restoration (PR #153)."""

from __future__ import annotations

from pathlib import Path

from modules import notification_center as nc


ROOT = Path(__file__).resolve().parents[1]


def test_dropdown_contract_document_exists():
    doc = (
        ROOT / "docs" / "notification-dropdown-restoration-contract.md"
    ).read_text(encoding="utf-8")
    for section in (
        "Root cause",
        "Final responsive notification-surface contract",
        "Interaction integrity",
        "Overlay layering",
        "Automated validation",
        "Trade Hub first-useful-result",
    ):
        assert section in doc
