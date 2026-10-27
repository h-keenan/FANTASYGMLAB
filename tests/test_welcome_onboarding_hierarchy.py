"""Welcome / onboarding funnel hierarchy — conversion clarity pass."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import auth_supabase


ROOT = Path(__file__).resolve().parents[1]


def test_static_landing_removes_duplicate_import_cta_block():
    html = (ROOT / "static" / "landing" / "index.html").read_text(encoding="utf-8")
    # Landing is sample-first since #1547/#1558: one primary CTA, no duplicate import block.
    assert html.count("Import your league") == 0
    assert html.count("Try a sample league") == 1
    assert 'id="get-started"' not in html
    assert "Next step" not in html
    assert "Next —" not in html
    assert html.index('id="how-it-works"') < html.index('id="pricing"')
