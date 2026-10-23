"""Contracts for unifying the executive command surface (PR follow-up polish)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docs_describe_one_continuous_command_surface():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "executive command surface" in docs
    assert "not stacked separate headers" in docs
