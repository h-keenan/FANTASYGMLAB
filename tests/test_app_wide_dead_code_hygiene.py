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


def test_app_does_not_import_unused_mobile_destination_helpers():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "mobile_primary_destinations" not in source
    assert "mobile_secondary_destinations" not in source


def test_hygiene_doc_and_audit_script_exist():
    doc = ROOT / "docs" / "app-wide-dead-code-repository-hygiene.md"
    text = doc.read_text(encoding="utf-8")
    assert "Proven dead" in text or "Class A" in text
    assert "age_model" in text
    assert "CURRENT_PAGE_REGISTRY" in text
    assert (ROOT / "scripts" / "audit_unused_modules.py").exists()


def test_unused_module_scan_is_clean():
    from scripts.audit_unused_modules import main
    import io
    from contextlib import redirect_stdout

    captured = io.StringIO()
    with redirect_stdout(captured):
        main()
    output = captured.getvalue()
    assert "UNUSED_MODULE_CANDIDATES 0" in output
