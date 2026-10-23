"""Workflow UX correctness contracts for Founder Beta bug-fix sprint."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_ux_report_exists():
    text = (ROOT / "docs" / "founder-beta-workflow-ux-fixes.md").read_text(encoding="utf-8")
    assert "No football logic" in text or "no football logic" in text.casefold()
    assert "render_trade_hub_section_filter" in text
    assert "Dashboard Next Move" in text or "Next Moves" in text
