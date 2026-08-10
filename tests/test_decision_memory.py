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


def test_first_baseline_creates_no_session_events_and_persists_baseline_only():
    session = _premium_session()
    env = {dm.EXPERIMENT_ENV_KEY: "1"}
    writes: list[tuple] = []

    def fake_upsert(config, token, table, payload, *, on_conflict):
        writes.append((table, payload.get("event_id"), on_conflict))
        return True, ""

    with (
        patch.object(dm, "experiment_enabled", return_value=True),
        patch.object(dm, "can_access_history", return_value=True),
        patch.object(dm.account_store, "upsert_row", side_effect=fake_upsert),
        patch.object(dm.account_store, "fetch_rows", return_value=([], "")),
        patch.object(dm.account_store, "delete_rows", return_value=(True, "")),
        patch.object(dm.auth_supabase, "is_configured", return_value=True),
        patch.object(dm, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}),
    ):
        tiles = [_trade_tile(rec_id="t1", target="Josh Jacobs")]
        nc.publish_activity_inventory(
            session,
            tiles,
            league_id="L1",
            roster_id="1",
            context_fingerprint="fp1",
            supabase_config={"enabled": True, "url": "x", "anon_key": "y"},
        )
        assert dch.list_decision_events(session, league_id="L1") == ()
        assert any(table == dm.BASELINES_TABLE for table, _, _ in writes)
        assert not any(table == dm.EVENTS_TABLE for table, _, _ in writes)


def test_material_change_persists_event_and_identical_rerun_writes_zero_new_events():
    session = _premium_session()
    writes: list[str] = []

    def fake_upsert(config, token, table, payload, *, on_conflict):
        if table == dm.EVENTS_TABLE:
            writes.append(payload["event_id"])
        return True, ""

    with (
        patch.object(dm, "experiment_enabled", return_value=True),
        patch.object(dm, "can_access_history", return_value=True),
        patch.object(dm.account_store, "upsert_row", side_effect=fake_upsert),
        patch.object(dm.account_store, "fetch_rows", return_value=([], "")),
        patch.object(dm.account_store, "delete_rows", return_value=(True, "")),
        patch.object(dm.auth_supabase, "is_configured", return_value=True),
        patch.object(dm, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}),
    ):
        first = [_trade_tile(rec_id="jacobs", target="Josh Jacobs")]
        nc.publish_activity_inventory(
            session, first, league_id="L1", context_fingerprint="fp1",
            supabase_config={"enabled": True},
        )
        second = [_trade_tile(rec_id="rhamondre", target="Rhamondre Stevenson")]
        nc.publish_activity_inventory(
            session, second, league_id="L1", context_fingerprint="fp2",
            supabase_config={"enabled": True},
        )
        assert len(writes) >= 1
        first_batch = list(writes)
        nc.publish_activity_inventory(
            session, second, league_id="L1", context_fingerprint="fp2",
            supabase_config={"enabled": True},
        )
        # Session dedupe + identical inventory → no additional event upserts.
        assert writes == first_batch


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


def test_hydrate_from_durable_baseline_enables_cross_session_compare():
    session = _premium_session()
    baseline = {
        "material_signatures": {"jacobs": "sig-a"},
        "prior_snapshots": {
            "jacobs": dch.DecisionStateSnapshot(
                recommendation_id="jacobs",
                target_label="Josh Jacobs",
                material_signature="sig-a",
                category="Trades",
                destination="trade_hub",
            ).to_dict()
        },
        "top_recommendation_id": "jacobs",
    }
    with (
        patch.object(dm, "experiment_enabled", return_value=True),
        patch.object(dm, "can_access_history", return_value=True),
        patch.object(dm.account_store, "fetch_rows", return_value=([baseline], "")),
        patch.object(dm.auth_supabase, "is_configured", return_value=True),
        patch.object(dm, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}),
    ):
        assert dm.hydrate_session_from_durable(session, league_id="L1") is True
        assert session[lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY]["jacobs"] == "sig-a"

    writes: list[str] = []

    def fake_upsert(config, token, table, payload, *, on_conflict):
        if table == dm.EVENTS_TABLE:
            writes.append(payload["event_id"])
        return True, ""

    with (
        patch.object(dm, "experiment_enabled", return_value=True),
        patch.object(dm, "can_access_history", return_value=True),
        patch.object(dm.account_store, "upsert_row", side_effect=fake_upsert),
        patch.object(dm.account_store, "fetch_rows", return_value=([], "")),
        patch.object(dm.account_store, "delete_rows", return_value=(True, "")),
        patch.object(dm.auth_supabase, "is_configured", return_value=True),
        patch.object(dm, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}),
    ):
        tiles = [_trade_tile(rec_id="rhamondre", target="Rhamondre Stevenson")]
        nc.publish_activity_inventory(
            session, tiles, league_id="L1", context_fingerprint="fp-new",
            supabase_config={"enabled": True},
        )
        assert writes, "cross-session change should emit durable events"
        assert dch.list_decision_events(session, league_id="L1")


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


def test_destination_never_resurrects_stale_narrative_contract():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    opener = source[
        source.index("def _open_decision_change_event(") : source.index(
            "def _open_home_command_route("
        )
        if "def _open_home_command_route(" in source
        else source.index("def _open_decision_change_event(") + 800
    ]
    # Fallback: search nearby
    start = source.index("def _open_decision_change_event(")
    opener = source[start : start + 1200]
    assert "recommendation_narrative=None" in opener
    assert "Never resurrects" in opener or "never resurrect" in opener.casefold()


def test_identical_football_inputs_unaffected_by_decision_memory_flag():
    """Decision Memory must not alter inventory signatures or recommendation ids."""

    tiles = [_trade_tile(rec_id="t1", target="Josh Jacobs")]
    off_session: dict = {}
    on_session = _premium_session()

    nc.publish_activity_inventory(off_session, tiles, league_id="L1", context_fingerprint="fp")
    with (
        patch.object(dm, "experiment_enabled", return_value=True),
        patch.object(dm, "can_access_history", return_value=True),
        patch.object(dm.account_store, "upsert_row", return_value=(True, "")),
        patch.object(dm.account_store, "fetch_rows", return_value=([], "")),
        patch.object(dm.account_store, "delete_rows", return_value=(True, "")),
        patch.object(dm.auth_supabase, "is_configured", return_value=True),
        patch.object(dm, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}),
    ):
        nc.publish_activity_inventory(
            on_session, tiles, league_id="L1", context_fingerprint="fp",
            supabase_config={"enabled": True},
        )

    off_sigs = off_session.get(lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY)
    on_sigs = on_session.get(lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY)
    assert off_sigs == on_sigs
    off_snap = off_session.get(nc.ACTIVITY_INBOX_SNAPSHOT_KEY) or {}
    on_snap = on_session.get(nc.ACTIVITY_INBOX_SNAPSHOT_KEY) or {}
    assert off_snap.get("material_signatures") == on_snap.get("material_signatures")
    assert [r.get("recommendation_id") for r in off_snap.get("records") or []] == [
        r.get("recommendation_id") for r in on_snap.get("records") or []
    ]


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


def test_ui_marks_decision_memory_and_preserves_free_what_changed():
    source = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")
    assert "View Decision Memory →" in source
    assert "decision_memory.can_access_history" in source
    assert "render_premium_lock" in source
    assert "Free users always keep session What Changed value" in source
    assert "data-decision-memory-discovery=" in source
    assert "Premium keeps durable history" in source
