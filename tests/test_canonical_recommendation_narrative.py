"""Regression tests for the canonical recommendation narrative contract."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from modules import canonical_recommendation_narrative as crn
from modules import notification_center
from modules import player_quick_view
from modules.trade_hub_ui import _trade_idea_identity


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


def test_trade_recommendation_id_matches_trade_hub_identity_digest():
    idea = _trade_idea()
    expected = sha256(repr(_trade_idea_identity(idea)).encode("utf-8")).hexdigest()[:16]
    assert crn.trade_recommendation_id(idea) == expected


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


def test_player_without_recommendation_shows_neutral_context():
    neutral = crn.build_neutral_player_narrative(
        {
            "player_id": "solo-1",
            "name": "Solo Player",
            "opportunity_explanation": "Role is still forming on the depth chart.",
        },
        league_id="league-a",
        roster_id="roster-1",
        valuation_lens="value_score",
    )
    assert neutral.is_active_recommendation is False
    presentation = neutral.pqv_presentation()
    assert presentation["heading"] == "Player Context"
    assert presentation["action"] == ""
    assert "not an active recommendation" in presentation["context"].casefold()

    html = player_quick_view.recommendation_context_html(
        presentation["summary"],
        presentation["context"],
        action="Monitor",
        active_recommendation=False,
        recommendation_id=neutral.recommendation_id,
    )
    assert "Player Context" in html
    assert "Monitor" not in html
    assert "player-dossier-neutral-context" in html


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


def test_app_wiring_binds_and_clears_narrative_provenance():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "canonical_recommendation_narrative" in source
    assert "recommendation_narrative" in source
    assert "NARRATIVE_SESSION_KEY" in source
    assert "build_neutral_player_narrative" in source
    assert "visible_recommendation_for_player" in source
    assert "bind_pqv_owned_narrative" in source
    clearer = source[
        source.index("def _clear_player_quick_view(") : source.index(
            "def open_player_quick_view("
        )
    ]
    assert "clear_narrative" in clearer


def test_trade_hub_consumes_canonical_narrative_for_detail_and_pqv():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "build_trade_narrative" in source
    assert "recommendation_narrative" in source
    assert "bind_narrative" in source


def test_notification_summary_uses_canonical_narrative_when_present():
    idea = _trade_idea()
    narrative = crn.build_trade_narrative(
        idea,
        league_id="league-a",
        roster_id="roster-1",
        source_surface="notifications",
        target_reason="Adds immediate lineup production at WR.",
        confidence_label="High",
    )
    summary = notification_center.summary_from_recommendation_narrative(narrative)
    assert "Acquire Player X" in summary
    assert "immediate lineup" in summary.casefold()
    assert notification_center.summary_from_recommendation_narrative(None) == ""


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
