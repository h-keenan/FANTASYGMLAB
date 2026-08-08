"""Decision-change history contracts — session-scoped Founder Beta."""

from __future__ import annotations

from pathlib import Path

from modules import decision_change_history as dch
from modules import notification_center as nc
from modules import recommendation_lifecycle as lifecycle
from modules import session_integrity


ROOT = Path(__file__).resolve().parents[1]


def _trade_tile(*, rec_id: str, target: str, action: str = "Buy need-position upgrade"):
    return {
        "label": "Top Trade Opportunity",
        "value": target,
        "note": "You move from TE surplus.",
        "recommendation_id": rec_id,
        "route_key": "trade_hub",
        "route_player_id": "6794",
        "recommendation_narrative": {
            "recommendation_id": rec_id,
            "kind": "trade",
            "action": action,
            "target_label": target,
            "reason": "You move from TE surplus.",
            "confidence_label": "Medium",
            "is_active_recommendation": True,
        },
    }


def _waiver_tile(*, rec_id: str, target: str):
    return {
        "label": "Top Waiver Opportunity",
        "value": target,
        "note": "Available now.",
        "recommendation_id": rec_id,
        "route_key": "waivers",
        "player_id": "4046",
        "recommendation_narrative": {
            "recommendation_id": rec_id,
            "kind": "waiver",
            "action": "Add",
            "target_label": target,
            "reason": "Available role.",
            "confidence_label": "High",
            "is_active_recommendation": True,
        },
    }


def test_identical_rerun_produces_zero_history_events():
    session: dict = {}
    tiles = [_trade_tile(rec_id="t1", target="Rhamondre Stevenson")]
    nc.publish_activity_inventory(session, tiles, league_id="L1", roster_id="1", context_fingerprint="fp1")
    assert dch.list_decision_events(session, league_id="L1") == ()
    nc.publish_activity_inventory(session, tiles, league_id="L1", roster_id="1", context_fingerprint="fp1")
    assert dch.list_decision_events(session, league_id="L1") == ()


def test_same_recommendation_regenerated_produces_zero_events():
    session: dict = {}
    tiles = [_trade_tile(rec_id="t1", target="Rhamondre Stevenson")]
    nc.publish_activity_inventory(session, tiles, league_id="L1", context_fingerprint="fp1")
    # Same meaning, fresh dict objects.
    tiles2 = [_trade_tile(rec_id="t1", target="Rhamondre Stevenson")]
    nc.publish_activity_inventory(session, tiles2, league_id="L1", context_fingerprint="fp1")
    assert dch.list_decision_events(session, league_id="L1") == ()


def test_new_top_priority_records_one_event():
    session: dict = {}
    first = [_trade_tile(rec_id="jacobs", target="Josh Jacobs")]
    nc.publish_activity_inventory(session, first, league_id="L1", context_fingerprint="fp1")
    second = [_trade_tile(rec_id="rhamondre", target="Rhamondre Stevenson")]
    nc.publish_activity_inventory(session, second, league_id="L1", context_fingerprint="fp2")
    events = dch.list_decision_events(session, league_id="L1")
    assert events
    headlines = {event.summary_headline for event in events}
    assert "Top priority changed" in headlines or any(
        "leading" in event.summary_detail.casefold() for event in events
    )


def test_recommendation_action_change_records_event():
    session: dict = {}
    first = [_trade_tile(rec_id="t1", target="Player X", action="Monitor")]
    nc.publish_activity_inventory(session, first, league_id="L1", context_fingerprint="fp1")
    second = [_trade_tile(rec_id="t1", target="Player X", action="Add")]
    nc.publish_activity_inventory(session, second, league_id="L1", context_fingerprint="fp1")
    events = dch.list_decision_events(session, league_id="L1")
    assert any(
        "action changed" in event.summary_headline.casefold()
        or "moved from" in event.summary_detail.casefold()
        for event in events
    )


def test_recommendation_disappears_records_resolved_event():
    session: dict = {}
    first = [
        _trade_tile(rec_id="t1", target="Keep"),
        _waiver_tile(rec_id="w1", target="Brashard Smith"),
    ]
    nc.publish_activity_inventory(session, first, league_id="L1", context_fingerprint="fp1")
    second = [_trade_tile(rec_id="t1", target="Keep")]
    nc.publish_activity_inventory(session, second, league_id="L1", context_fingerprint="fp1")
    events = dch.list_decision_events(session, league_id="L1")
    assert any(
        event.reason == lifecycle.MATERIAL_CHANGE_RESOLVED
        and "no longer" in event.summary_detail.casefold()
        for event in events
    )


def test_duplicate_lifecycle_sync_does_not_duplicate_events():
    session: dict = {}
    first = [_trade_tile(rec_id="jacobs", target="Josh Jacobs")]
    nc.publish_activity_inventory(session, first, league_id="L1", context_fingerprint="fp1")
    second = [_trade_tile(rec_id="rhamondre", target="Rhamondre Stevenson")]
    nc.publish_activity_inventory(session, second, league_id="L1", context_fingerprint="fp2")
    count = len(dch.list_decision_events(session, league_id="L1"))
    nc.publish_activity_inventory(session, second, league_id="L1", context_fingerprint="fp2")
    assert len(dch.list_decision_events(session, league_id="L1")) == count


def test_league_switch_hides_prior_league_history():
    session: dict = {}
    nc.publish_activity_inventory(
        session,
        [_trade_tile(rec_id="t1", target="A")],
        league_id="L1",
        context_fingerprint="fp1",
    )
    nc.publish_activity_inventory(
        session,
        [_trade_tile(rec_id="t2", target="B")],
        league_id="L1",
        context_fingerprint="fp2",
    )
    assert dch.list_decision_events(session, league_id="L1")
    dch.clear_decision_history(session)
    assert dch.list_decision_events(session, league_id="L1") == ()


def test_account_switch_and_logout_clear_history():
    session: dict = {
        dch.DECISION_HISTORY_EVENTS_KEY: [
            dch.DecisionChangeEvent(
                event_id="e1",
                recommendation_id="r1",
                league_id="L1",
                roster_id="1",
                timestamp=1.0,
                lifecycle_transition="current->changed",
                reason="priority_changed",
                category="Trades",
                target_label="X",
                player_id="",
                destination="trade_hub",
                previous_state=None,
                current_state=None,
                summary_headline="Top priority changed",
                summary_detail="detail",
                why_label="Recommendation priority changed",
            ).to_dict()
        ],
        dch.DECISION_HISTORY_ACCOUNT_SCOPE_KEY: "user-a",
        dch.DECISION_HISTORY_LEAGUE_SCOPE_KEY: "L1",
    }
    session_integrity.clear_account_bound_transient_state(session)
    assert dch.DECISION_HISTORY_EVENTS_KEY not in session
    lifecycle.clear_lifecycle_session_state(session)
    assert dch.list_decision_events(session) == ()


def test_destination_does_not_resurrect_stale_recommendation():
    event = dch.DecisionChangeEvent(
        event_id="e1",
        recommendation_id="r1",
        league_id="L1",
        roster_id="1",
        timestamp=1.0,
        lifecycle_transition="current->resolved",
        reason="recommendation_resolved",
        category="Waivers",
        target_label="Gone",
        player_id="4046",
        destination="waivers",
        previous_state={"target_label": "Gone"},
        current_state=None,
        summary_headline="Waiver opportunity resolved",
        summary_detail="Gone is no longer available in this league.",
        why_label="Player availability changed",
    )
    assert dch.destination_is_current(event)
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    opener = app.split("def _open_decision_change_event", 1)[1].split("\ndef ", 1)[0]
    assert "recommendation_narrative=None" in opener
    assert 'handoff_source="what_changed"' in opener


def test_inbox_and_what_changed_remain_semantically_distinct():
    doc = (ROOT / "docs" / "decision-change-history-contract.md").read_text(encoding="utf-8")
    assert "Today's Game Plan" in doc
    assert "Inbox" in doc
    assert "What Changed" in doc
    assert "activity/action-oriented" in doc.casefold() or "activity" in doc.casefold()
    assert "transition" in doc.casefold()


def test_events_from_inventory_changes_are_deterministic():
    prior = {
        "w1": {
            "recommendation_id": "w1",
            "category": "Waivers",
            "action": "Add",
            "target_label": "Brashard Smith",
            "title": "Brashard Smith",
            "confidence_band": "high",
            "priority_rank": 0,
            "destination": "waivers",
            "player_id": "4046",
            "material_signature": "sig-old",
        }
    }
    changes = (
        lifecycle.InventoryChange(
            recommendation_id="w1",
            prior_state=lifecycle.LIFECYCLE_CURRENT,
            next_state=lifecycle.LIFECYCLE_RESOLVED,
            reason=lifecycle.MATERIAL_CHANGE_RESOLVED,
        ),
    )
    first = dch.events_from_inventory_changes(
        changes,
        prior_snapshots=prior,
        current_snapshots={},
        league_id="L1",
        timestamp=100.0,
    )
    second = dch.events_from_inventory_changes(
        changes,
        prior_snapshots=prior,
        current_snapshots={},
        league_id="L1",
        timestamp=100.0,
    )
    assert first == second
    assert first[0].summary_headline == "Waiver opportunity resolved"
    assert first[0].event_id == second[0].event_id


def test_dashboard_caps_recent_events():
    session: dict = {
        dch.DECISION_HISTORY_ACCOUNT_SCOPE_KEY: "anon",
        dch.DECISION_HISTORY_LEAGUE_SCOPE_KEY: "L1",
        dch.DECISION_HISTORY_EVENTS_KEY: [
            dch.DecisionChangeEvent(
                event_id=f"e{i}",
                recommendation_id=f"r{i}",
                league_id="L1",
                roster_id="1",
                timestamp=float(i),
                lifecycle_transition="current->changed",
                reason="recommendation_changed",
                category="Trades",
                target_label=f"P{i}",
                player_id="",
                destination="trade_hub",
                previous_state=None,
                current_state=None,
                summary_headline="Recommendation changed",
                summary_detail="detail",
                why_label=dch.FALLBACK_WHY,
            ).to_dict()
            for i in range(6)
        ],
    }
    assert len(dch.dashboard_events(session, league_id="L1")) == dch.MAX_DASHBOARD_EVENTS


def test_contract_document_exists():
    doc = (ROOT / "docs" / "decision-change-history-contract.md").read_text(encoding="utf-8")
    for section in (
        "Product boundary",
        "Event schema",
        "Lifecycle → event mapping",
        "Dedupe rules",
        "Deterministic summary rules",
        "Deep-link behavior",
        "Dashboard hierarchy",
        "Inbox relationship",
        "Persistence decision",
        "Mobile contract",
        "Performance impact",
        "Terminology findings",
    ):
        assert section in doc


def test_what_changed_css_is_route_scoped():
    ui = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")
    assert "DECISION_CHANGE_HISTORY_CSS" in ui
    app_styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "DECISION_CHANGE_HISTORY_CSS" not in app_styles


def test_decision_history_open_current_context_closes_dialog_first():
    ui = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")
    assert "def _open_current(event" in ui
    open_fn = ui[ui.index("def _open_current(event") : ui.index("title = \"Decision Memory\"")]
    assert "_close_flag(close_key)" in open_fn
    assert "open_event(event)" in open_fn
    assert open_fn.index("_close_flag(close_key)") < open_fn.index("open_event(event)")
    assert 'on_click=_open_current' in ui
    assert 'use_container_width=False' in ui
    assert "dg-decision-history-cta" in ui
    # Open/view history uses on_click callbacks, not body-path only.
    assert "on_click=_open_flag" in ui


def test_priority_rank_shift_produces_structured_summary():
    prior = dch.DecisionStateSnapshot(
        recommendation_id="rec-1",
        category=dch.CATEGORY_TRADE,
        action="Buy",
        target_label="Player A",
        confidence_band="medium",
        priority_rank=4,
    )
    current = dch.DecisionStateSnapshot(
        recommendation_id="rec-1",
        category=dch.CATEGORY_TRADE,
        action="Buy",
        target_label="Player A",
        confidence_band="medium",
        priority_rank=1,
    )
    change = lifecycle.InventoryChange(
        recommendation_id="rec-1",
        reason=lifecycle.MATERIAL_CHANGE_RECOMMENDATION,
        prior_state=lifecycle.LIFECYCLE_CURRENT,
        next_state=lifecycle.LIFECYCLE_CHANGED,
    )
    headline, detail = dch.deterministic_summary(change, prior=prior, current=current)
    assert headline == "Priority increased"
    assert "#4" in detail and "#1" in detail


def test_scoring_and_valuation_context_reasons_map_to_why_labels():
    assert dch.why_label_for_reason(
        lifecycle.MATERIAL_CHANGE_RECOMMENDATION,
        context_reasons=(lifecycle.MATERIAL_CHANGE_SCORING,),
    ) == "Scoring context changed"
    assert dch.why_label_for_reason(
        lifecycle.MATERIAL_CHANGE_RECOMMENDATION,
        context_reasons=(lifecycle.MATERIAL_CHANGE_VALUATION,),
    ) == "Strategy focus changed"
