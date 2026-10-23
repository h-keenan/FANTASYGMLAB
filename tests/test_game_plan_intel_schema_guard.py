"""Dashboard Game Plan schema guard after #219 lightweight intelligence (#220)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from modules import game_plan_package


ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "game-plan-package-memo.md").read_text(encoding="utf-8")


def test_docs_cover_lightweight_intelligence_contract():
    assert "lightweight" in DOC.casefold()
    assert "roster_id" in DOC
    assert "select_roster_row" in DOC or "schema guard" in DOC.casefold()
