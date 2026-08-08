"""Founder Beta launch marketing kit — assets stay off the app hot path."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "assets" / "marketing" / "launch"

REQUIRED = {
    "hero-1200x630.png": (1200, 630),
    "hero-mobile-1080x1350.png": (1080, 1350),
    "trade-feature.png": (1080, 1350),
    "game-plan-feature.png": (1080, 1350),
    "decision-memory-feature.png": (1080, 1350),
    "youtube-short-1-cover.png": (1080, 1920),
    "youtube-short-2-cover.png": (1080, 1920),
    "youtube-short-3-cover.png": (1080, 1920),
    "free-vs-premium.png": (1080, 1350),
    "reddit-dashboard.png": (1080, 1350),
    "discord-share-card.png": (1080, 1350),
    "og-founder-beta-launch.png": (1200, 630),
    "qr-fantasygmlab.png": (512, 512),
}


def test_launch_kit_doc_exists():
    doc = ROOT / "docs" / "founder-beta-launch-marketing-kit.md"
    text = doc.read_text(encoding="utf-8")
    assert "League-aware recommendations for dynasty managers" in text
    assert "Founder Beta is early access" in text
    assert "[EXPERIMENTAL]" in text
    assert "assets/marketing/launch/" in text


def test_launch_assets_exist_with_expected_dimensions():
    for name, expected in REQUIRED.items():
        path = LAUNCH / name
        assert path.exists(), name
        with Image.open(path) as image:
            assert image.size == expected, f"{name}: {image.size}"


def test_og_brand_asset_updated_with_positioning():
    path = ROOT / "assets" / "brand" / "og-founder-beta.png"
    assert path.exists()
    with Image.open(path) as image:
        assert image.size == (1200, 630)


def test_authenticated_app_does_not_reference_launch_assets():
    """Performance guard: launch kit must not enter Streamlit protobuf path."""
    forbidden = "assets/marketing/launch"
    for rel in (
        "app.py",
        "modules/marketing_landing.py",
        "modules/application_shell.py",
        "modules/startup_coordinator.py",
        "modules/brand_identity.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert forbidden not in text, rel


def test_marketing_landing_asset_dir_stays_legacy_folder():
    source = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
    assert "MARKETING_ASSET_DIR" in source
    assert ' / "marketing"' in source
    assert ' / "launch"' not in source


def test_generator_script_exists():
    assert (ROOT / "scripts" / "generate_launch_marketing_assets.py").exists()
    assert (ROOT / "scripts" / "capture_launch_screenshots.py").exists()
