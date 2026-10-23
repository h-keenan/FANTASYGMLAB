"""Auth restore rerun consolidation contracts and identical-payload behavior."""

from pathlib import Path
from unittest.mock import patch

from modules import auth_restore_lifecycle
from modules import auth_supabase
from modules import startup_coordinator


ROOT = Path(__file__).resolve().parents[1]


def _auth_payload(user_id: str = "user-a", token: str = "access-a") -> dict:
    return {
        "user": {"id": user_id, "email": f"{user_id}@example.com"},
        "user_id": user_id,
        "email": f"{user_id}@example.com",
        "access_token": token,
        "refresh_token": f"refresh-{token}",
        "expires_at": 9999999999,
        "token_type": "bearer",
    }


def test_identical_auth_payload_skips_workspace_wipe_and_reapply():
    state: dict = {}
    first = _auth_payload()
    auth_supabase.apply_auth_payload(state, first)
    state["selected_league_id"] = "league-1"
    state["username"] = "keeper"
    state["account_profile"] = {"user_id": "user-a"}

    restored, error, refreshed = auth_supabase.restore_auth_payload(
        {"url": "https://example.supabase.co", "anon_key": "anon"},
        state,
        first,
    )
    assert restored is False
    assert error == ""
    assert refreshed is False
    assert state["selected_league_id"] == "league-1"
    assert state["username"] == "keeper"
    assert auth_restore_lifecycle.is_identical_auth_payload(state, first)


def test_account_switch_still_clears_prior_workspace():
    state: dict = {}
    auth_supabase.apply_auth_payload(state, _auth_payload("user-a", "token-a"))
    state["selected_league_id"] = "league-a"
    state["username"] = "alpha"
    state["_effective_entitlement"] = "premium"

    auth_supabase.apply_auth_payload(state, _auth_payload("user-b", "token-b"))
    assert "selected_league_id" not in state
    assert "username" not in state
    assert "_effective_entitlement" not in state
    assert auth_supabase.current_user_id(state) == "user-b"


def test_expired_token_clear_resets_lifecycle_memo():
    state: dict = {
        auth_restore_lifecycle.AUTH_FINGERPRINT_KEY: "stale",
        auth_restore_lifecycle.ENTITLEMENT_MEMO_KEY: "premium",
        auth_restore_lifecycle.ENTITLEMENT_MEMO_USER_KEY: "user-a",
    }
    expired = _auth_payload()
    expired["expires_at"] = 1
    with patch.object(
        auth_supabase,
        "refresh_auth_session",
        return_value=({}, "refresh failed"),
    ):
        restored, error, refreshed = auth_supabase.restore_auth_payload(
            {"url": "https://example.supabase.co", "anon_key": "anon"},
            state,
            expired,
        )
    assert restored is False
    assert error == "refresh failed"
    assert refreshed is False
    assert auth_restore_lifecycle.AUTH_FINGERPRINT_KEY not in state
    assert auth_restore_lifecycle.ENTITLEMENT_MEMO_KEY not in state
    assert state.get(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY) is True


def test_startup_run_counter_increments_per_script_execution():
    state: dict = {}
    first = auth_restore_lifecycle.begin_script_run(state)
    second = auth_restore_lifecycle.begin_script_run(state)
    assert first["startup_session_id"] == second["startup_session_id"]
    assert first["startup_run_number"] == 1
    assert second["startup_run_number"] == 2


def test_milestone_once_suppresses_duplicate_session_restored():
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    first = startup_coordinator.log_startup_milestone(
        state, "session_restored", started_at=0.0, once=True
    )
    second = startup_coordinator.log_startup_milestone(
        state, "session_restored", started_at=0.0, once=True
    )
    assert first is not None
    assert second is None
