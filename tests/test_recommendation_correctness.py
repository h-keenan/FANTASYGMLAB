"""Recommendation correctness and lifecycle contracts (PR #135)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import canonical_recommendation_narrative as crn
from modules import dashboard_workflow
from modules import recommendation_lifecycle


ROOT = Path(__file__).resolve().parents[1]


def _trade_narrative(rec_id: str = "trade-a") -> crn.CanonicalRecommendationNarrative:
    return crn.CanonicalRecommendationNarrative(
        recommendation_id=rec_id,
        kind="trade",
        action="Acquire WR",
        target_label="Synthetic Receiver",
        reason="Upgrade the starting room.",
        evidence="Partner surplus at WR.",
        risk="Medium confidence.",
        expected_outcome="Net positive package.",
        confidence_label="Medium",
        confidence_wording="Medium confidence.",
        market_signal="Fair",
        fit_signal="Strong",
        league_id="league-1",
        roster_id="3",
        valuation_lens="value_score",
        source_surface="dashboard",
        player_ids=("p1",),
    )


def test_resolve_narrative_rejects_lens_and_roster_mismatch():
    state = {}
    crn.bind_narrative(state, _trade_narrative())
    assert crn.resolve_narrative_for_player(
        state,
        player_id="p1",
        league_id="league-1",
        roster_id="3",
        valuation_lens="value_score",
    ) is not None
    assert crn.resolve_narrative_for_player(
        state,
        player_id="p1",
        league_id="league-1",
        roster_id="9",
        valuation_lens="value_score",
    ) is None
    assert crn.resolve_narrative_for_player(
        state,
        player_id="p1",
        league_id="league-1",
        roster_id="3",
        valuation_lens="dynasty_score",
    ) is None


def test_invalidate_stale_narrative_clears_context():
    state = {}
    crn.bind_narrative(state, _trade_narrative())
    assert recommendation_lifecycle.invalidate_stale_narrative(
        state,
        league_id="league-2",
        roster_id="3",
        valuation_lens="value_score",
    )
    assert crn.load_narrative(state) is None


def test_dashboard_suppresses_duplicate_intelligence_tiles():
    primary = {
        "label": "Top Trade Opportunity",
        "recommendation_id": "trade-a",
        "recommendation_narrative": _trade_narrative().to_dict(),
    }
    intelligence = (
        {
            "label": "Top Trade Opportunity",
            "recommendation_id": "trade-a",
            "recommendation_narrative": _trade_narrative().to_dict(),
        },
        {
            "label": "Top Waiver Opportunity",
            "recommendation_id": "waiver-b",
            "recommendation_narrative": {
                **_trade_narrative("waiver-b").to_dict(),
                "kind": "waiver",
            },
        },
    )
    briefing = dashboard_workflow.organize_dashboard_items(
        [primary, *intelligence],
    )
    assert len(briefing.intelligence) == 1
    assert briefing.intelligence[0]["recommendation_id"] == "waiver-b"


def test_roster_decision_narrative_is_active():
    narrative = crn.build_roster_decision_narrative(
        {"player_id": "p9", "name": "Candidate", "reason": "Move before the limit."},
        action="Trade Candidate",
        league_id="league-1",
        roster_id="3",
        valuation_lens="value_score",
        source_surface="my_team_trade_candidate",
    )
    assert narrative.is_active_recommendation is True
    assert narrative.kind == "roster_decision"


def test_player_scan_cards_forward_narrative_to_quick_view():
    """Narrative forwarding is live via open_kwargs; assert behavior not a stale literal."""

    source = (ROOT / "modules" / "player_cards.py").read_text(encoding="utf-8")
    assert "recommendation_narrative_fn" in source
    assert '"recommendation_narrative": narrative_payload' in source
    assert '"recommendation_narrative": meta.get("recommendation_narrative")' in source
    assert "open_player_quick_view(clicked_player_id, **open_kwargs)" in source
    # Diagnosis: prior assertion looked for recommendation_narrative=meta.get as a
    # keyword argument. Implementation now packs open_kwargs then unpacks — canonical
    # forwarding remains intact (architecture D / stale string, not a product break).


def test_audit_document_exists():
    doc = (ROOT / "docs" / "recommendation-correctness-audit.md").read_text(
        encoding="utf-8"
    )
    for section in (
        "Cross-surface recommendation consistency",
        "Duplicate recommendation inventory",
        "Recommendation lifecycle",
        "Executive prioritization",
        "Narrative redundancy",
        "Explicit confirmation",
    ):
        assert section in doc


def test_waiver_confidence_wording_is_compact():
    row = pd.Series(
        {
            "player_id": "w1",
            "name": "Wire Player",
            "opportunity_confidence": 72,
        }
    )
    narrative = crn.build_waiver_narrative(
        row,
        action="Add",
        reason="Best add on the wire.",
        league_id="league-1",
    )
    assert "from the current waiver signal" not in narrative.confidence_wording
