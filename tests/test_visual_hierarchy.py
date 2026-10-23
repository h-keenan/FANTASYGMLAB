"""Contracts for executive visual hierarchy (presentation only)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_executive_shell_docs_describe_single_command_bar():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "single executive command bar" in docs
