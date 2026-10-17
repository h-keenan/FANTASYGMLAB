"""Guards web-next/src/data/legalContent.json against drifting from
mobile/src/data/legalContent.json — web-next's own page.tsx documents this
file as "copied verbatim from mobile/src/data/legalContent.json rather than
re-authored, so this app never drifts into a second, slightly-different
copy of binding legal text."

A real drift (web-next showing support@fantasygmlab.com while mobile
correctly showed support@fantasydesk.app) shipped silently because nothing
guarded this file — tests/test_mobile_legal_content_export.py only guards
mobile's copy against the Python generator, not web-next's copy against
mobile's. This test closes that gap.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOBILE_PATH = ROOT / "mobile" / "src" / "data" / "legalContent.json"
WEB_NEXT_PATH = ROOT / "web-next" / "src" / "data" / "legalContent.json"


def test_web_next_legal_content_matches_mobile_verbatim():
    mobile = json.loads(MOBILE_PATH.read_text(encoding="utf-8"))
    web_next = json.loads(WEB_NEXT_PATH.read_text(encoding="utf-8"))
    assert web_next == mobile
