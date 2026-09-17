"""Guards mobile/src/data/methodologyContent.json against drifting from modules.methodology_page.

Mirrors tests/test_mobile_legal_content_export.py for the same reason: the
mobile app bundles this content statically. If modules/methodology_page.py
changes, re-run scripts/export_methodology_content.py and commit the
result.
"""

from __future__ import annotations

import json

from scripts.export_methodology_content import build_export, OUTPUT_PATH


def test_bundled_methodology_content_matches_generator():
    committed = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    assert committed == build_export()
