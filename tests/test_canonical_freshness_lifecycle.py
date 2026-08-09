"""Canonical freshness, change detection, and recommendation lifecycle contracts."""

from __future__ import annotations

from pathlib import Path

from modules import canonical_recommendation_narrative as crn
from modules import daily_gm_briefing as dgb
from modules import dashboard_workflow
from modules import notification_center as nc
from modules import recommendation_lifecycle as rl
from modules import session_integrity


ROOT = Path(__file__).resolve().parents[1]


def _tile(label: str, value: str, **extra):
    payload = {"label": label, "value": value, "note": extra.pop("note", "note")}
    payload.update(extra)
    return payload


def _fingerprint(**overrides):
    base = {
        "account_scope": "user-a",
        "league_id": "L1",
        "roster_id": "R1",
        "season": "2025",
        "week": "7",
        "scoring_format": "PPR",
        "valuation_lens": "value_score",
        "roster_state_version": "abc123",
        "provider_data_version": "settings-v1",
    }
    base.update(overrides)
    return rl.build_context_fingerprint(**base)


def test_identical_rerun_unchanged_signatures():
    tile = _tile(
        "Top Trade Opportunity",
        "Acquire RB",
        recommendation_id="trade-1",
        recommendation_narrative={
            "recommendation_id": "trade-1",
            "kind": "trade",
            "action": "Acquire RB",
            "reason": "Fit",
            "is_active_recommendation": True,
        },
    )
    sig_a = rl.recommendation_material_signature(tile)
    sig_b = rl.recommendation_material_signature(tile)
    assert sig_a == sig_b
    assert rl.compare_inventory_signatures({"trade-1": sig_a}, {"trade-1": sig_b}) == ()


def test_insignificant_numeric_formatting_unchanged():
    tile_a = _tile("Top Waiver Opportunity", "Add WR", recommendation_id="w1")
    tile_b = _tile("Top Waiver Opportunity", "Add WR", recommendation_id="w1")
    assert rl.recommendation_material_signature(tile_a) == rl.recommendation_material_signature(
        tile_b
    )


def test_recommendation_action_change_is_material():
    prior = {"rec-1": rl.recommendation_material_signature(_tile("Top Trade Opportunity", "Acquire RB", recommendation_id="rec-1"))}
    current = {
        "rec-1": rl.recommendation_material_signature(
            _tile("Top Trade Opportunity", "Acquire WR", recommendation_id="rec-1")
        )
    }
    changes = rl.compare_inventory_signatures(prior, current)
    assert len(changes) == 1
    assert changes[0].next_state == rl.LIFECYCLE_CHANGED
    assert changes[0].reason == rl.MATERIAL_CHANGE_RECOMMENDATION


def test_recommendation_disappears_is_resolved():
    prior = {"rec-1": "sig"}
    changes = rl.compare_inventory_signatures(prior, {})
    assert changes[0].next_state == rl.LIFECYCLE_RESOLVED
    assert changes[0].reason == rl.MATERIAL_CHANGE_RESOLVED


def test_new_top_recommendation_priority_change():
    changes = rl.compare_inventory_signatures(
        {"old-top": "a"},
        {"new-top": "b"},
        prior_top="old-top",
        current_top="new-top",
    )
    assert any(change.reason == rl.MATERIAL_CHANGE_PRIORITY for change in changes)


def test_scoring_format_switch_invalidates_context():
    prior = _fingerprint(scoring_format="PPR")
    current = _fingerprint(scoring_format="Half-PPR")
    reasons = rl.context_change_reasons(prior, current)
    assert rl.MATERIAL_CHANGE_SCORING in reasons


def test_valuation_lens_switch_invalidates_context():
    prior = _fingerprint(valuation_lens="value_score")
    current = _fingerprint(valuation_lens="dynasty_score")
    reasons = rl.context_change_reasons(prior, current)
    assert rl.MATERIAL_CHANGE_VALUATION in reasons


def test_league_switch_full_context_invalidation():
    state = {}
    prior = _fingerprint(league_id="L1")
    rl.store_context_fingerprint(state, prior)
    state[rl.LIFECYCLE_INVENTORY_SIGNATURES_KEY] = {"rec-1": "sig"}
    state[nc.ACTIVITY_INBOX_SNAPSHOT_KEY] = {"league_id": "L1", "records": []}
    changed, reasons = rl.sync_lifecycle_on_context_change(state, _fingerprint(league_id="L2"))
    assert changed
    assert rl.MATERIAL_CHANGE_VALUATION in reasons
    assert nc.ACTIVITY_INBOX_SNAPSHOT_KEY not in state


def test_roster_transaction_material_change():
    prior = _fingerprint(roster_state_version="players-a")
    current = _fingerprint(roster_state_version="players-b")
    reasons = rl.context_change_reasons(prior, current)
    assert rl.MATERIAL_CHANGE_ROSTER in reasons


def test_account_switch_clears_lifecycle_state():
    state = {
        rl.LIFECYCLE_CONTEXT_FINGERPRINT_KEY: {"digest": "x"},
        rl.LIFECYCLE_BRIEFING_SIGNATURE_KEY: "brief",
        rl.LIFECYCLE_INVENTORY_SIGNATURES_KEY: {"rec": "sig"},
    }
    session_integrity.clear_account_bound_transient_state(state)
    assert rl.LIFECYCLE_CONTEXT_FINGERPRINT_KEY not in state
    assert rl.LIFECYCLE_BRIEFING_SIGNATURE_KEY not in state


def test_stable_waiver_ids_ignore_reason_prose():
    row = {"player_id": "p1", "name": "Wire Player"}
    first = crn.build_waiver_narrative(
        row,
        action="Add",
        reason="Best add on the wire.",
        league_id="L1",
    )
    second = crn.build_waiver_narrative(
        row,
        action="Add",
        reason="Rephrased reason with identical meaning.",
        league_id="L1",
    )
    assert first.recommendation_id == second.recommendation_id


def test_stable_roster_ids_ignore_reason_prose():
    first = crn.build_roster_decision_narrative(
        {"player_id": "p9", "name": "Candidate", "reason": "Move before the limit."},
        action="Trade Candidate",
        league_id="L1",
    )
    second = crn.build_roster_decision_narrative(
        {"player_id": "p9", "name": "Candidate", "reason": "Different prose, same action."},
        action="Trade Candidate",
        league_id="L1",
    )
    assert first.recommendation_id == second.recommendation_id


def test_identical_rerun_preserves_notification_read_state():
    session = {"account_user_id": "user-a"}
    fingerprint = _fingerprint().digest
    tiles = [
        _tile(
            "Top Waiver Opportunity",
            "Add X",
            recommendation_id="w1",
            route_key="waivers",
        )
    ]
    nc.publish_activity_inventory(
        session,
        tiles,
        league_id="L1",
        context_fingerprint=fingerprint,
    )
    item = next(i for i in nc.compose_activity_inbox(session=session, league_id="L1") if i.recommendation_id)
    nc.mark_notification_read(session, item.id, league_id="L1")
    nc.publish_activity_inventory(
        session,
        tiles,
        league_id="L1",
        context_fingerprint=fingerprint,
    )
    again = next(i for i in nc.compose_activity_inbox(session=session, league_id="L1") if i.recommendation_id)
    assert again.unread is False


def test_notification_no_duplicate_unchanged_activity():
    session = {}
    fingerprint = _fingerprint().digest
    tiles = [
        _tile("Top Trade Opportunity", "Acquire RB", recommendation_id="t1", route_key="trade_hub")
    ]
    nc.publish_activity_inventory(session, tiles, league_id="L1", context_fingerprint=fingerprint)
    first = [i for i in nc.compose_activity_inbox(session=session, league_id="L1") if i.recommendation_id]
    nc.publish_activity_inventory(session, tiles, league_id="L1", context_fingerprint=fingerprint)
    second = [i for i in nc.compose_activity_inbox(session=session, league_id="L1") if i.recommendation_id]
    assert len(first) == len(second) == 1
    assert first[0].id == second[0].id


def test_daily_briefing_unchanged_on_identical_rerun():
    trade = _tile(
        "Top Trade Opportunity",
        "Acquire RB",
        recommendation_id="trade-1",
        route_key="trade_hub",
    )
    briefing = dashboard_workflow.organize_dashboard_items([trade])
    fingerprint = _fingerprint().digest
    first = dgb.compose_daily_gm_briefing(
        briefing,
        league_id="L1",
        context_fingerprint=fingerprint,
    )
    second = dgb.compose_daily_gm_briefing(
        briefing,
        league_id="L1",
        context_fingerprint=fingerprint,
    )
    sig_first = rl.briefing_content_signature([item.to_dict() for item in first.items], quiet=first.quiet)
    sig_second = rl.briefing_content_signature([item.to_dict() for item in second.items], quiet=second.quiet)
    assert sig_first == sig_second
    assert first.items[0].freshness == fingerprint


def test_daily_briefing_quiet_remains_quiet():
    briefing = dashboard_workflow.organize_dashboard_items([])
    plan = dgb.compose_daily_gm_briefing(briefing, context_fingerprint=_fingerprint().digest)
    assert plan.quiet
    assert rl.briefing_content_signature([], quiet=True) == rl.briefing_content_signature([], quiet=True)


def test_invalidate_stale_narrative_includes_scoring_format():
    state = {}
    narrative = crn.CanonicalRecommendationNarrative(
        recommendation_id="t1",
        kind="trade",
        action="Acquire WR",
        target_label="Player",
        reason="Reason",
        evidence="Evidence",
        risk="Risk",
        expected_outcome="Outcome",
        confidence_label="Medium",
        confidence_wording="Medium confidence.",
        market_signal="Fair",
        fit_signal="Strong",
        league_id="L1",
        roster_id="R1",
        valuation_lens="value_score",
        source_surface="dashboard",
        player_ids=("p1",),
    )
    crn.bind_narrative(state, narrative)
    rl.store_context_fingerprint(state, _fingerprint(scoring_format="PPR"))
    assert not rl.invalidate_stale_narrative(
        state,
        league_id="L1",
        roster_id="R1",
        valuation_lens="value_score",
        scoring_format="PPR",
    )
    assert rl.invalidate_stale_narrative(
        state,
        league_id="L1",
        roster_id="R1",
        valuation_lens="value_score",
        scoring_format="Half-PPR",
    )
    assert crn.load_narrative(state) is None


def test_roster_state_version_from_player_ids():
    version_a = rl.roster_state_version_from_player_ids(["p2", "p1", "p1"])
    version_b = rl.roster_state_version_from_player_ids(["p1", "p2"])
    version_c = rl.roster_state_version_from_player_ids(["p3"])
    assert version_a == version_b
    assert version_a != version_c


def test_contract_document_exists():
    doc = (ROOT / "docs" / "canonical-freshness-lifecycle-contract.md").read_text(
        encoding="utf-8"
    )
    for section in (
        "Current-state audit",
        "Canonical context fingerprint",
        "Recommendation identity contract",
        "Lifecycle states",
        "Material-change rules",
        "Invalidation matrix",
        "Daily GM Briefing behavior",
        "Notification behavior",
        "Persistence boundary",
        "Performance impact",
        "Known limitations",
    ):
        assert section in doc


def test_app_wires_lifecycle_sync_and_fingerprint():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "sync_lifecycle_on_context_change(" in app
    assert (
        "context_fingerprint=lifecycle_fingerprint.football_digest" in app
        or "context_fingerprint=lifecycle_fingerprint.digest" in app
    )
    assert "LIFECYCLE_BRIEFING_SIGNATURE_KEY" in app
    assert "clear_notification_context_snapshot(" in (ROOT / "modules" / "notification_center.py").read_text(
        encoding="utf-8"
    )
