"""Auth restore rerun consolidation contracts and identical-payload behavior."""

from pathlib import Path
from unittest.mock import patch

import app
from modules import auth_restore_lifecycle
from modules import auth_supabase
from modules import startup_coordinator
from scripts import report_startup_waterfall


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


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


def test_auth_restore_does_not_force_immediate_rerun_before_profile():
    main = APP.index("def main():")
    auth_restore = APP.index('if auth_restore.get("restored"):', main)
    profile = APP.index('runtime_trace.mark("profile_lookup_complete")', auth_restore)
    auth_block = APP[auth_restore:profile]
    assert "st.rerun()" not in auth_block
    assert "clear_auth_pending_wait" in auth_block


def test_league_resume_no_longer_forces_explicit_rerun():
    call_site = APP.index("_maybe_auto_resume_supabase_league()", APP.index("def main():"))
    snippet = APP[call_site : call_site + 160]
    assert "st.rerun()" not in snippet


def test_post_usable_durable_save_rerun_is_deferred_after_football():
    dismiss = APP.index('runtime_trace.mark("first_usable_paint")')
    complete = APP.index("startup.complete()", dismiss)
    post = APP[complete : complete + 1200]
    assert "POST_USABLE_SAVE_AFTER_FOOTBALL_KEY" in post
    assert "st.rerun()" not in post
    remount = APP.index("post_usable_auth_save_rerun")
    assert "st.rerun()" in APP[remount : remount + 400]
    football = APP.index('"football_context_ready"')
    assert football < remount
    assert complete < football


def test_auth_pending_stop_remains_required():
    pending = APP.index('if auth_restore.get("pending") and startup.active:')
    stop = APP.index("st.stop()", pending)
    assert stop > pending
    assert stop < APP.index(
        "startup.advance(startup_coordinator.StartupPhase.PROFILE_LOADING)",
        pending,
    )


def test_session_restored_milestone_is_once_gated():
    idx = APP.index('"session_restored"')
    assert "once=True" in APP[idx : idx + 120]


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


def test_waterfall_groups_by_startup_session_and_run():
    text = "\n".join(
        [
            'DYNASTYGM_STARTUP {"kind":"startup_run","startup_session_id":"abc","startup_run_number":1,"restore_phase":"UNINITIALIZED"}',
            'DYNASTYGM_STARTUP {"kind":"startup_milestone","milestone":"auth_storage_requested","label":"Auth storage requested","elapsed_ms":20,"startup_session_id":"abc","startup_run_number":1}',
            'DYNASTYGM_STARTUP {"kind":"startup_run","startup_session_id":"abc","startup_run_number":2,"restore_phase":"STORAGE_PENDING"}',
            'DYNASTYGM_STARTUP {"kind":"startup_milestone","milestone":"session_restored","label":"Session restored","elapsed_ms":200,"startup_session_id":"abc","startup_run_number":2}',
            'DYNASTYGM_STARTUP {"kind":"startup_milestone","milestone":"loading_dismissed","label":"Loading dismissed","elapsed_ms":900,"startup_session_id":"abc","startup_run_number":2}',
        ]
    )
    rendered = report_startup_waterfall._render(report_startup_waterfall._parse_lines(text))
    assert "Startup session abc" in rendered
    assert "Run 1" in rendered
    assert "Run 2" in rendered
    assert "Session restored milestones: 1" in rendered
    assert "Script runs: 2" in rendered


def test_entitlement_refresh_is_memoized_for_same_user():
    state: dict = {}
    auth_supabase.apply_auth_payload(state, _auth_payload())
    state["account_profile"] = {"plan": "free"}
    with (
        patch.object(app.st, "session_state", state),
        patch.object(app.premium, "effective_entitlement", return_value="free") as entitlement,
        patch.object(app.auth_supabase, "current_user_id", return_value="user-a"),
    ):
        first = app.refresh_current_user_entitlement()
        second = app.refresh_current_user_entitlement()
    assert first == "free"
    assert second == "free"
    assert entitlement.call_count == 1


def test_loading_dismiss_prerequisites_remain_after_auth_ready():
    auth_ready = APP.index('"auth_ready"')
    dismiss = APP.index('runtime_trace.mark("first_usable_paint")')
    shell = APP.index('"shell_chrome_ready"')
    assert auth_ready < shell < dismiss
