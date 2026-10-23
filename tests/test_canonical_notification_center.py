"""Canonical Notification Center composition and routing contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import daily_gm_briefing
from modules import dashboard_workflow
from modules import notification_center as nc


ROOT = Path(__file__).resolve().parents[1]


def _tile(label, value, **extra):
    payload = {"label": label, "value": value, "note": extra.pop("note", "note")}
    payload.update(extra)
    return payload


def _authed_session(**extra) -> dict:
    session = {
        "auth_session": {"user_id": "11111111-1111-1111-1111-111111111111", "access_token": "tok"},
        "auth_user": {"id": "11111111-1111-1111-1111-111111111111"},
    }
    session.update(extra)
    return session


def test_live_draft_route_from_cache():
    session = {"_cached_live_draft_active": True}
    items = nc.compose_activity_inbox(session=session, league_id="L1")
    draft = next(item for item in items if item.category == "DRAFT")
    assert draft.href_hint == "live_draft"


def test_account_switch_clears_notification_state():
    session = {
        "account_user_id": "a",
        nc.ACTIVITY_INBOX_SNAPSHOT_KEY: {"league_id": "L1", "records": []},
        nc.NOTIFICATION_READ_IDS_KEY: {"a|L1": ["x"]},
    }
    nc.clear_notification_session_state(session)
    assert nc.ACTIVITY_INBOX_SNAPSHOT_KEY not in session
    assert nc.NOTIFICATION_READ_IDS_KEY not in session


def test_no_football_score_helpers():
    source = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "notification_score" not in source
    assert "daily_briefing_score" not in source
    assert "Does not generate football" in source or "does not invent football" in source.casefold()


def test_mark_notification_read_writes_through_without_a_dismissed_column():
    session = _authed_session()
    writes: list[dict] = []

    def fake_upsert(config, token, table, payload, *, on_conflict):
        writes.append(payload)
        assert table == nc.NOTIFICATION_READ_STATE_TABLE
        assert on_conflict == "user_id,league_id,notification_id"
        return True, ""

    with (
        patch.object(nc.account_store, "upsert_row", side_effect=fake_upsert),
        patch.object(nc.auth_supabase, "is_configured", return_value=True),
        patch.object(nc, "_resolve_durable_config", return_value={"enabled": True}),
    ):
        nc.mark_notification_read(session, "rec:gamma", league_id="L1")

    assert len(writes) == 1
    assert "dismissed" not in writes[0]
    assert writes[0]["notification_id"] == "rec:gamma"
    assert writes[0]["league_id"] == "L1"


def test_dismiss_writes_dismissed_true_and_the_read_writethrough_cannot_reset_it():
    session = _authed_session()
    writes: list[dict] = []

    def fake_upsert(config, token, table, payload, *, on_conflict):
        writes.append(payload)
        return True, ""

    with (
        patch.object(nc.account_store, "upsert_row", side_effect=fake_upsert),
        patch.object(nc.auth_supabase, "is_configured", return_value=True),
        patch.object(nc, "_resolve_durable_config", return_value={"enabled": True}),
    ):
        nc.dismiss_notification(session, "rec:delta", league_id="L1")

    # dismiss_notification writes dismissed=True, then internally calls
    # mark_notification_read — whose own write-through omits the dismissed
    # column entirely so it can't regress this back to false.
    assert len(writes) == 2
    assert writes[0]["dismissed"] is True
    assert "dismissed" not in writes[1]


def test_migration_sql_rls_and_identity_contract():
    sql = (ROOT / "docs" / "supabase_notification_read_state.sql").read_text(encoding="utf-8")
    assert "notification_read_state" in sql
    assert "enable row level security" in sql
    assert "auth.uid() = user_id" in sql
    assert "primary key (user_id, league_id, notification_id)" in sql
    assert "on delete cascade" in sql.casefold()
    assert "to anon" not in sql
    assert "for update" in sql.casefold()


def test_contract_doc_exists():
    text = (ROOT / "docs" / "canonical-notification-center-contract.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "Architecture",
        "Notification model",
        "Canonical sources",
        "Routing matrix",
        "Stale-state behavior",
        "Read / unread",
        "Briefing vs Notification",
        "Performance",
        "Known limitations",
    ):
        assert heading in text
