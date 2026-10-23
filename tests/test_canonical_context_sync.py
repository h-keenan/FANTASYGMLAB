"""Regression contracts for canonical context synchronization."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def test_docs_cover_dependency_map_and_risks():
    docs = (ROOT / "docs" / "canonical-context-synchronization-audit.md").read_text(
        encoding="utf-8"
    )
    assert "Context dependency diagram" in docs
    assert "State ownership table" in docs
    assert "Navigation flow diagram" in docs
    assert "role_map" in docs
    assert "Remaining architectural risks" in docs
    assert "No football logic" in docs or "No football logic" in docs
