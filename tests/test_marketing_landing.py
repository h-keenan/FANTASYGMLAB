"""Public marketing landing contracts."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity, launch_analytics, premium_benefits


ROOT = Path(__file__).resolve().parents[1]


def test_landing_analytics_events_are_allowlisted():
    for event in (
        "landing_viewed",
        "primary_cta_clicked",
        "secondary_cta_clicked",
        "pricing_viewed",
        "signup_started",
    ):
        assert event in launch_analytics.TRACKED_EVENTS


def test_marketing_assets_exist():
    required = (
        "dashboard.jpg",
        "trade-share.jpg",
        "waiver-share.jpg",
        "player-share.jpg",
        "decision-memory.jpg",
        "dashboard-desktop.jpg",
        "README.md",
    )
    for name in required:
        path = ROOT / "assets" / "marketing" / name
        assert path.exists(), name
        assert path.stat().st_size > 40, name
