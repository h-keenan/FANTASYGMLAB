"""Guard app.py against accidental UTF-8 BOM reintroduction."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UTF8_BOM = b"\xef\xbb\xbf"
EXPECTED_PREFIX = b"import time as _bootstrap_time"


def test_app_py_has_no_utf8_bom_and_starts_with_bootstrap_import():
    payload = (ROOT / "app.py").read_bytes()
    assert not payload.startswith(UTF8_BOM), "app.py must be UTF-8 without a BOM"
    assert payload.startswith(EXPECTED_PREFIX), payload[:40]
    # utf-8-sig readers hide this defect; keep a bytes-level check in CI.
    assert "\ufeff" not in (ROOT / "app.py").read_text(encoding="utf-8")
