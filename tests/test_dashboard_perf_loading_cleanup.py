"""Dashboard performance + loading-state ownership contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import dashboard_loading_state as dls


ROOT = Path(__file__).resolve().parents[1]


def test_no_new_blanket_overlay_or_sleep():
    src = (ROOT / "modules" / "dashboard_loading_state.py").read_text(encoding="utf-8")
    assert "sleep(" not in src
    assert "dg-startup-shell" not in src
    # Policy is clear-then-hydrate, not cosmetic opacity override of Streamlit stale.
    assert "opacity: 1 !important" not in src
    assert ".element-container" not in src
