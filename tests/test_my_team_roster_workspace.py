"""My Team roster workspace hierarchy — presentation only (#194 / #199)."""

from __future__ import annotations

from pathlib import Path

from modules.roster_needs import PositionNeedAssessment, TeamNeedsAssessment

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_finalization_doc_exists():
    doc = ROOT / "docs" / "my-team-roster-workspace-finalization.md"
    text = doc.read_text(encoding="utf-8")
    assert "Final hierarchy" in text
    assert "Roster Posture" in text
    assert "Position Groups" in text
    assert "Draft Capital" in text
    assert "suggest_optimal_lineup" in text or "projected" in text.lower()
