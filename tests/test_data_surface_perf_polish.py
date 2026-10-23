"""Data-surface polish + remaining performance contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from modules import dense_list_primitives
from modules import game_plan_package
from modules import league_display
from modules import waivers_logic


ROOT = Path(__file__).resolve().parents[1]
WAIVERS = (ROOT / "modules" / "waivers_logic.py").read_text(encoding="utf-8")
DRAFT = (ROOT / "modules" / "draft_center_cards.py").read_text(encoding="utf-8")


def test_dense_dual_rank_primitive_is_compact():
    html = dense_list_primitives.dense_dual_rank_html(power="#1", franchise="#4")
    assert "dg-dense-dual-rank" in html
    assert "#1" in html
    assert "#4" in html
    assert "Power" in html
    assert "Franchise" in html
