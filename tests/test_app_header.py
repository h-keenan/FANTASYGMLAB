"""Legacy app_header module was removed; executive shell owns identity chrome."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_app_header_module_removed():
    assert not (ROOT / "modules" / "app_header.py").exists()


def test_executive_shell_is_the_identity_surface():
    source = (ROOT / "modules" / "application_shell.py").read_text(encoding="utf-8")
    assert "executive_workspace_shell_html" in source
    assert "dg-executive-shell" in source
