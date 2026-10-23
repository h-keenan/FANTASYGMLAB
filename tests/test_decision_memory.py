"""Experimental Decision Memory — durable persistence contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import decision_change_history as dch
from modules import decision_memory as dm
from modules import notification_center as nc
from modules import premium
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


def _premium_session(**extra) -> dict:
    session = {
        "auth_session": {"user_id": "11111111-1111-1111-1111-111111111111", "access_token": "tok"},
        "auth_user": {"id": "11111111-1111-1111-1111-111111111111"},
        "account_profile": {"entitlement": premium.PREMIUM},
    }
    session.update(extra)
    return session


def test_kill_switch_defaults_on():
    assert dm.experiment_enabled(environ={}) is True
    assert dm.experiment_enabled(environ={dm.EXPERIMENT_ENV_KEY: "0"}) is False
    assert dm.experiment_enabled(environ={dm.EXPERIMENT_ENV_KEY: "1"}) is True


def test_free_cannot_access_history_even_when_experiment_on():
    session = {
        "auth_session": {"user_id": "u1", "access_token": "tok"},
        "auth_user": {"id": "u1"},
        "account_profile": {"entitlement": premium.FREE},
    }
    env = {dm.EXPERIMENT_ENV_KEY: "1"}
    assert dm.can_access_history(session, environ=env) is False
    assert dm.can_show_discovery(session, environ=env) is True
    assert dm.should_sync_durable(session, environ=env) is False


def test_premium_can_access_when_experiment_on():
    session = _premium_session()
    env = {dm.EXPERIMENT_ENV_KEY: "1"}
    assert dm.can_access_history(session, environ=env) is True
    assert dm.should_sync_durable(session, environ=env) is True


def test_anonymous_cannot_access():
    env = {dm.EXPERIMENT_ENV_KEY: "1"}
    assert dm.can_access_history({}, environ=env) is False
    assert dm.can_show_discovery({}, environ=env) is False


def test_deterministic_event_id_stable_across_tabs():
    change = lifecycle.InventoryChange(
        recommendation_id="rec-1",
        prior_state=lifecycle.LIFECYCLE_CURRENT,
        next_state=lifecycle.LIFECYCLE_CURRENT,
        reason=lifecycle.MATERIAL_CHANGE_PRIORITY,
    )
    prior = {"rec-1": dch.DecisionStateSnapshot(recommendation_id="rec-1", target_label="A", material_signature="sig").to_dict()}
    current = {"rec-1": dch.DecisionStateSnapshot(recommendation_id="rec-1", target_label="B", material_signature="sig2", priority_rank=0).to_dict()}
    a = dch.events_from_inventory_changes(
        (change,),
        prior_snapshots=prior,
        current_snapshots=current,
        league_id="L1",
    )
    b = dch.events_from_inventory_changes(
        (change,),
        prior_snapshots=prior,
        current_snapshots=current,
        league_id="L1",
    )
    assert a and b and a[0].event_id == b[0].event_id
    row = dm.event_to_row(a[0], user_id="u1")
    assert row["event_id"] == a[0].event_id
    assert row["user_id"] == "u1"


def test_missing_table_fails_safely():
    session = _premium_session()
    with (
        patch.object(dm, "experiment_enabled", return_value=True),
        patch.object(dm, "can_access_history", return_value=True),
        patch.object(
            dm.account_store,
            "upsert_row",
            return_value=(False, "relation does not exist"),
        ),
        patch.object(dm.auth_supabase, "is_configured", return_value=True),
        patch.object(dm, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}),
    ):
        event = dch.DecisionChangeEvent(
            event_id="e1",
            recommendation_id="r1",
            league_id="L1",
            roster_id="1",
            timestamp=1.0,
            lifecycle_transition="none->current",
            reason=lifecycle.MATERIAL_CHANGE_RECOMMENDATION,
            category="Trades",
            target_label="X",
            player_id="",
            destination="trade_hub",
            previous_state=None,
            current_state=None,
        )
        result = dm.persist_after_transition(
            session,
            new_events=(event,),
            signatures={"r1": "sig"},
            snapshots={},
            league_id="L1",
        )
        assert result["wrote_events"] == 0
        assert session.get(dm.SESSION_UNAVAILABLE_KEY) is True
        # Subsequent syncs short-circuit.
        assert dm.should_sync_durable(session, environ={dm.EXPERIMENT_ENV_KEY: "1"}) is False


def test_prune_overflow_issues_one_batched_delete_not_one_per_row():
    """Regression test: retention pruning used to issue one DELETE request
    per overflow event_id (up to 50 sequential Supabase round trips for a
    single prune pass). It must now collapse those into one request using
    PostgREST's `event_id=in.(...)` filter."""

    overflow_rows = [{"event_id": f"ev{i}", "created_at": "2020-01-01"} for i in range(37)]
    delete_calls: list[str] = []

    def fake_delete_rows(config, token, table, *, query, timing_label="supabase_delete_rows", timeout=8):
        delete_calls.append(query)
        return True, ""

    def fake_fetch_rows(config, token, table, *, user_id, extra_query="", timing_label="", timeout=8):
        if "offset=" in extra_query:
            return overflow_rows, ""
        return [], ""

    with (
        patch.object(dm.account_store, "delete_rows", side_effect=fake_delete_rows),
        patch.object(dm.account_store, "fetch_rows", side_effect=fake_fetch_rows),
    ):
        dm._prune_expired_events(
            {"enabled": True, "url": "x", "anon_key": "y"},
            "token",
            user_id="u1",
            league_id="L1",
        )

    # First call is the age-based (created_at < cutoff) delete, unchanged.
    # Second call is the overflow prune — exactly one request, carrying
    # every overflow id in a single `in.(...)` filter.
    assert len(delete_calls) == 2
    overflow_query = delete_calls[1]
    assert "event_id=in.(" in overflow_query
    for row in overflow_rows:
        assert row["event_id"] in overflow_query


def test_logout_clears_memory_session_not_requiring_durable_delete():
    session = _premium_session()
    session[dm.SESSION_CACHE_EVENTS_KEY] = [{"event_id": "x"}]
    session[dm.SESSION_CACHE_LEAGUE_KEY] = "L1"
    session[dm.SESSION_HYDRATED_KEY] = "L1"
    session_integrity.clear_account_bound_transient_state(session)
    assert dm.SESSION_CACHE_EVENTS_KEY not in session
    assert dm.SESSION_HYDRATED_KEY not in session


def test_league_isolation_in_merged_history():
    session = _premium_session()
    session[dch.DECISION_HISTORY_EVENTS_KEY] = [
        dch.DecisionChangeEvent(
            event_id="a",
            recommendation_id="r1",
            league_id="L1",
            roster_id="1",
            timestamp=2.0,
            lifecycle_transition="none->current",
            reason=lifecycle.MATERIAL_CHANGE_RECOMMENDATION,
            category="Trades",
            target_label="A",
            player_id="",
            destination="trade_hub",
            previous_state=None,
            current_state=None,
            summary_headline="New trade opportunity",
        ).to_dict(),
        dch.DecisionChangeEvent(
            event_id="b",
            recommendation_id="r2",
            league_id="L2",
            roster_id="1",
            timestamp=3.0,
            lifecycle_transition="none->current",
            reason=lifecycle.MATERIAL_CHANGE_RECOMMENDATION,
            category="Trades",
            target_label="B",
            player_id="",
            destination="trade_hub",
            previous_state=None,
            current_state=None,
            summary_headline="New trade opportunity",
        ).to_dict(),
    ]
    session[dch.DECISION_HISTORY_ACCOUNT_SCOPE_KEY] = dch._account_scope(session)
    session[dch.DECISION_HISTORY_LEAGUE_SCOPE_KEY] = "L1"
    with patch.object(dm, "can_access_history", return_value=False):
        events = dm.merged_history_events(session, league_id="L1")
    assert all(event.league_id == "L1" for event in events)


def test_migration_sql_enables_rls_and_idempotency():
    sql = (ROOT / "docs" / "supabase_decision_memory.sql").read_text(encoding="utf-8")
    assert "decision_memory_events" in sql
    assert "decision_memory_baselines" in sql
    assert "enable row level security" in sql
    assert "auth.uid() = user_id" in sql
    assert "primary key (user_id, event_id)" in sql
    assert "primary key (user_id, league_id)" in sql
    assert "on delete cascade" in sql.casefold()
    assert "to anon" not in sql  # fail closed for anonymous
