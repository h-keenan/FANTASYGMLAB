"""Contracts for the Executive Command Header and Notification Center shell."""

from pathlib import Path

from modules import brand_identity, notification_center


ROOT = Path(__file__).resolve().parents[1]


def test_docs_describe_executive_command_header_and_notification_shell():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "Executive Command Header" in docs
    assert "Notification Center" in docs
    assert "GM Orb remains the primary full navigation" in docs
