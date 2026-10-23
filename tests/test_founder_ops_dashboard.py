"""Founder Ops dashboard access and read-only contract tests."""

from __future__ import annotations

from pathlib import Path

from modules.ui_architecture import (
    PLATFORM_DESTINATIONS,
    current_platform_destinations,
    mobile_primary_destinations,
)


ROOT = Path(__file__).resolve().parents[1]


def test_founder_ops_destination_is_hidden_by_default():
    keys = {page.key for page in current_platform_destinations(False)}
    assert "founder_ops" not in keys
    primary = {page.key for page in mobile_primary_destinations(False)}
    assert "founder_ops" not in primary


def test_founder_ops_destination_requires_explicit_flag():
    hidden = {page.key for page in current_platform_destinations(False, show_founder_ops=False)}
    shown = {page.key for page in current_platform_destinations(False, show_founder_ops=True)}
    assert "founder_ops" not in hidden
    assert "founder_ops" in shown
    page = next(item for item in PLATFORM_DESTINATIONS if item.key == "founder_ops")
    assert page.category == "FOUNDER_OPS"
    assert page.beta_visible is False
