"""Guards mobile/src/data/legalContent.json against drifting from modules.legal_pages.

The mobile app bundles this content statically (no network dependency for
Terms/Privacy/About). If modules/legal_pages.py changes, re-run
scripts/export_legal_content.py and commit the result.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_legal_content import build_export, OUTPUT_PATH


ROOT = Path(__file__).resolve().parents[1]


def test_bundled_legal_content_matches_generator():
    committed = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    assert committed == build_export()


def test_bundled_legal_content_covers_all_legal_pages():
    from modules import legal_pages

    committed = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    assert set(committed["pages"]) == set(legal_pages.LEGAL_PAGES)
