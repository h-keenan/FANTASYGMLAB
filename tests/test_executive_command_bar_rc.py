"""Contracts for Executive Command Bar & Notification Center RC polish."""

from pathlib import Path

from modules import brand_identity, notification_center


ROOT = Path(__file__).resolve().parents[1]


def test_docs_describe_floating_executive_inbox():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "executive inbox" in docs
    assert "45–60%" in docs
    assert "internal scrolling" in docs
    assert "GM Orb remains the primary full navigation" in docs
