"""Conservative repository hygiene — proven-dead removals only."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dead_modules_removed():
    for relative in (
        "modules/age_model.py",
        "modules/news_factor.py",
        "modules/app_header.py",
        "modules/executive_visual_finalization_styles.py",
        "modules/executive_info_compression_styles.py",
    ):
        assert not (ROOT / relative).exists(), relative


def test_obsolete_page_registry_removed():
    source = (ROOT / "modules" / "ui_architecture.py").read_text(encoding="utf-8")
    assert "PLATFORM_DESTINATIONS" in source
    assert "CURRENT_PAGE_REGISTRY" not in source
    assert "current_primary_tabs" not in source
    assert "FUTURE_NAV_GROUPS" not in source
    assert "REUSABLE_SECTION_DEFINITIONS" not in source
    assert "DUPLICATE_SECTION_AUDIT" not in source
    assert "MIGRATION_PHASES" not in source
    assert "class FutureNavGroup" not in source
