"""Regression tests for the canonical recommendation narrative contract."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from modules import canonical_recommendation_narrative as crn
from modules import notification_center
from modules import player_quick_view


ROOT = Path(__file__).resolve().parents[1]


def _trade_idea(**overrides):
    idea = {
        "partner_roster_id": "roster-2",
        "partner_team_name": "Partner FC",
        "tag": "Acquire Player X",
        "their_player": "Player X",
        "my_score": 4200,
        "their_score": 4500,
        "trade_gain": 300,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "High",
        "hub_target_fit_reason": "Adds immediate lineup production at WR.",
        "fit_summary": "Adds immediate lineup production at WR.",
        "reasoning_summary": "Adds immediate lineup production at WR.",
        "rationale": "Adds immediate lineup production at WR.",
        "hub_partner_reason": "Partner has RB surplus and needs youth.",
        "trade_confidence_summary": "High confidence under plausible market conditions.",
        "send_assets": [
            {
                "asset_type": "player",
                "player_id": "send-1",
                "name": "Outgoing RB",
            }
        ],
        "receive_assets": [
            {
                "asset_type": "player",
                "player_id": "recv-x",
                "name": "Player X",
            }
        ],
    }
    idea.update(overrides)
    return idea


def test_same_trade_narrative_agrees_across_dashboard_trade_hub_and_pqv():
    idea = _trade_idea()
    shared_kwargs = dict(
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
        target_reason="Adds immediate lineup production at WR.",
        partner_reason="Partner has RB surplus and needs youth.",
        confidence_reason="High confidence under plausible market conditions.",
        confidence_label="High",
        value_verdict="Fair",
        value_delta="+300",
        health_context={"risk": False},
    )
    dashboard = crn.build_trade_narrative(idea, source_surface="dashboard", **shared_kwargs)
    trade_hub = crn.build_trade_narrative(idea, source_surface="trade_hub", **shared_kwargs)
    pqv = crn.build_trade_narrative(idea, source_surface="player_quick_view", **shared_kwargs)

    assert crn.narratives_agree(dashboard, trade_hub)
    assert crn.narratives_agree(trade_hub, pqv)
    fields = [
        crn.consumer_fields(dashboard),
        crn.consumer_fields(trade_hub),
        crn.consumer_fields(pqv),
    ]
    for key in (
        "action",
        "reason",
        "risk",
        "confidence_label",
        "expected_outcome",
        "league_id",
        "roster_id",
    ):
        assert {item[key] for item in fields} == {fields[0][key]}


def test_league_switch_clears_narrative_provenance():
    idea = _trade_idea()
    narrative = crn.build_trade_narrative(
        idea,
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
        source_surface="trade_hub",
        target_reason="Adds immediate lineup production at WR.",
    )
    state = {}
    crn.bind_narrative(state, narrative)
    assert crn.load_narrative(state) is not None

    # Simulate league-switch hygiene: clear narrative key.
    state.pop(crn.NARRATIVE_SESSION_KEY, None)
    assert crn.resolve_narrative_for_player(
        state,
        player_id="recv-x",
        league_id="league-b",
    ) is None

    # Stale prior-league payload must not resolve under a new league.
    crn.bind_narrative(state, narrative)
    assert (
        crn.resolve_narrative_for_player(
            state,
            player_id="recv-x",
            league_id="league-b",
        )
        is None
    )


def test_pqv_presentation_keeps_full_reason_by_default():
    reason = (
        "Player is deep on the depth chart and mostly profiles as insurance "
        "behind a locked-in starter but still has receiving upside"
    )
    narrative = crn.build_neutral_player_narrative(
        {
            "player_id": "p-full",
            "name": "Full Reason",
            "opportunity_explanation": reason,
        },
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
        analysis_note=reason,
    )
    presentation = narrative.pqv_presentation()
    assert presentation["summary"] == narrative.reason
    assert "…" not in presentation["summary"]
    shortened = narrative.pqv_presentation(limit=40)
    assert shortened["summary"].endswith("…")
    assert shortened["summary"] != presentation["summary"]


def test_cached_trade_hub_board_resolves_same_narrative_from_idea_fields():
    idea = _trade_idea()
    # Cached boards still carry the idea object; narrative is derived from it.
    cached_board = [dict(idea), dict(idea)]
    first = crn.build_trade_narrative(
        cached_board[0],
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
        source_surface="trade_hub",
        target_reason=idea["hub_target_fit_reason"],
        confidence_label="High",
    )
    second = crn.build_trade_narrative(
        cached_board[1],
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
        source_surface="trade_hub",
        target_reason=idea["hub_target_fit_reason"],
        confidence_label="High",
    )
    assert first.recommendation_id == second.recommendation_id
    assert crn.narratives_agree(first, second)


def test_free_and_premium_share_underlying_narrative_for_accessible_items():
    idea = _trade_idea()
    free_narrative = crn.build_trade_narrative(
        idea,
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
        source_surface="dashboard",
        target_reason=idea["hub_target_fit_reason"],
        confidence_label="High",
    )
    premium_narrative = crn.build_trade_narrative(
        idea,
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
        source_surface="trade_hub",
        target_reason=idea["hub_target_fit_reason"],
        confidence_label="High",
    )
    assert crn.narratives_agree(free_narrative, premium_narrative)
    # Entitlement may hide items, never rewrite accessible narrative facts.
    assert free_narrative.action == premium_narrative.action
    assert free_narrative.reason == premium_narrative.reason
    assert free_narrative.risk == premium_narrative.risk
    assert free_narrative.confidence_label == premium_narrative.confidence_label


def test_no_recommendation_ordering_or_trust_math_in_narrative_module():
    source = (ROOT / "modules" / "canonical_recommendation_narrative.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "enforce_trade_board",
        "build_trade_ideas",
        "trade_idea_score",
        "apply_active_valuation",
        "trust_engine",
    )
    for token in forbidden:
        assert token not in source


def test_audit_document_exists_with_required_sections():
    docs = (
        ROOT / "docs" / "canonical-recommendation-narrative-audit.md"
    ).read_text(encoding="utf-8")
    for section in (
        "Previous narrative sources",
        "Canonical model",
        "Consumer map",
        "Provenance flow",
        "Inconsistencies found",
        "Inconsistencies fixed",
        "Remaining risks",
        "Retained builders",
    ):
        assert section in docs
