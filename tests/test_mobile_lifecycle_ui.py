"""POST-318 mobile lifecycle / render-ownership contracts."""

from __future__ import annotations

from pathlib import Path

from modules import startup_coordinator
from modules import trade_hub_first_useful


ROOT = Path(__file__).resolve().parents[1]
TRADE_HUB = (ROOT / "modules" / "trade_hub_presentation.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
LOADING = (ROOT / "modules" / "dashboard_loading_state.py").read_text(encoding="utf-8")


def test_presentation_board_peek_does_not_count_as_hit():
    state: dict = {}
    assert (
        trade_hub_first_useful.presentation_board_cached(state, signature="sig")
        is False
    )
    trade_hub_first_useful.get_or_build_presentation_board(
        state, signature="sig", builder=lambda: {"eligible_ideas": []}
    )
    assert trade_hub_first_useful.presentation_board_cached(state, signature="sig") is True
