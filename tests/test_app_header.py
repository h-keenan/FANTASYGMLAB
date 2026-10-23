"""Legacy app_header module was removed; executive shell owns identity chrome."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_app_header_module_removed():
    assert not (ROOT / "modules" / "app_header.py").exists()
