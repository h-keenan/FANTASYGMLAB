"""CSS / protobuf headroom recovery contracts."""

from __future__ import annotations

import re
from pathlib import Path

from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]

SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'

RETIRED_FAMILIES = (
    ".dg-application-workspace",
    ".dg-ops-rail",
    ".dg-workspace-page-title",
    ".trade-score-card",
    ".trade-why-grid",
    ".trade-explain-card",
    ".app-glass-panel",
    ".dg-glass-panel",
    ".app-chip",
    ".app-empty-state",
    ".app-card",
    ".app-section",
)


def test_audit_doc_exists():
    assert (ROOT / "docs" / "css-protobuf-headroom-recovery.md").exists()
