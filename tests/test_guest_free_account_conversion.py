"""Guest → free-account conversion contracts (#224)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import launch_analytics


ROOT = Path(__file__).resolve().parents[1]


def test_guest_events_are_tracked_and_block_username_pii():
    assert "guest_signup_prompt_seen" in launch_analytics.TRACKED_EVENTS
    assert "guest_league_selected" in launch_analytics.TRACKED_EVENTS
    assert "prompt_surface" in launch_analytics.ALLOWED_PROP_KEYS
    assert "username" in launch_analytics.BLOCKED_PROP_KEYS
    assert "email" in launch_analytics.BLOCKED_PROP_KEYS


def test_docs_guest_funnel_exists():
    doc = ROOT / "docs" / "guest-free-account-conversion.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "Save your front office" in text
    assert "FREE ACCOUNT BENEFITS" in text or "Free account benefits" in text
