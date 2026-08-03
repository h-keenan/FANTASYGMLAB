from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys

import pytest

from modules.context_integrity import (
    SurfaceContext,
    access_tiers_share_analysis,
    validate_surface_contexts,
)


ROOT = Path(__file__).resolve().parents[1]
SURFACES = ("Dashboard", "Trade Hub", "Waivers", "Live Draft", "League Intelligence", "Player Explorer")


def _context(surface: str, **changes) -> SurfaceContext:
    values = dict(
        surface=surface, league_id="league-a", roster_id="7",
        score_field="dynasty_score", valuation_context="balanced|settings-v1",
        player_source="players-snapshot-v3",
    )
    values.update(changes)
    return SurfaceContext(**values)


def test_all_named_surfaces_accept_one_identical_analysis_context():
    report = validate_surface_contexts(_context(surface) for surface in SURFACES)
    assert report.valid
    assert report.surfaces == SURFACES
    assert json.loads(report.to_json())["valid"] is True


@pytest.mark.parametrize("field,value", [
    ("league_id", "league-b"), ("roster_id", "9"),
    ("score_field", "value_score"), ("valuation_context", "other"),
    ("player_source", "stale-snapshot"),
])
def test_any_cross_surface_context_drift_fails_closed(field, value):
    report = validate_surface_contexts([_context("Dashboard"), _context("Trade Hub", **{field: value})])
    assert not report.valid
    assert report.violations[0].code == f"context_{field}_mismatch"


def test_context_model_is_frozen():
    context = _context("Dashboard")
    with pytest.raises(FrozenInstanceError):
        context.league_id = "league-b"


def test_free_and_premium_may_differ_in_access_not_analysis():
    board = [
        {"idea_id": "a", "tag": "Add", "score": 90, "reasoning_summary": "Need"},
        {"idea_id": "b", "tag": "Watch", "score": 80, "reasoning_summary": "Depth"},
    ]
    assert access_tiers_share_analysis(board[:1], board)
    changed = [dict(board[0], score=91), board[1]]
    assert not access_tiers_share_analysis(changed[:1], board)


def test_analysis_signature_preserves_zero_as_a_real_value():
    free = [{"idea_id": "a", "value": 0, "score": 91, "reasoning_summary": "Even"}]
    premium = [{"idea_id": "a", "value": 0, "score": 12, "reasoning_summary": "Even"}]
    assert access_tiers_share_analysis(free, premium)


def test_repository_integrity_audit_passes():
    result = subprocess.run(
        [sys.executable, "scripts/audit_context_integrity.py"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["valid"] is True


def test_trade_entitlement_is_applied_after_generation_and_trust():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    trade = source[source.index("def render_top_trade_opportunities()") : source.index("def render_search_around_player()")]
    assert trade.index("cached_trade_ideas(") < trade.index("enforce_cached_trade_ideas(")
    assert trade.index("enforce_cached_trade_ideas(") < trade.index("trade_hub_entitlement_presentation(")
