"""Anonymous account-league isolation — P0 session boundary regressions."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from modules import auth_supabase
from modules import session_integrity
from modules import session_isolation

ROOT = Path(__file__).resolve().parents[1]


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_session_isolation_imports_without_auth_first():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from modules import session_isolation; print(session_isolation.GUEST_LEAGUE_ORIGIN_KEY)",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "_guest_league_origin"
    """Anonymous fresh session must not keep an account-derived selected league."""

    state = _Session(
        {
            "selected_league_id": "1353858597108350976",
            "selected_league_name": "Should Not Leak",
            "my_roster_id": "9",
            "username": "Harryhard",
            "_identity_established": True,
            "_league_selection_established": True,
            # Missing guest origin ⇒ treat as account leak.
        }
    )
    assert auth_supabase.current_user_id(state) in ("", None)
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is True
    assert state.get("selected_league_id") in (None, "")
    assert "selected_league_name" not in state or not state.get("selected_league_name")
    assert "my_roster_id" not in state
    assert "username" not in state
    assert session_isolation.anonymous_must_not_carry_account_league(state)


def test_anonymous_strip_clears_private_account_caches():
    state = _Session(
        {
            "selected_league_id": "1353858597108350976",
            "selected_league_name": "Should Not Leak",
            "_gm_targets_cache_ids": {"p1"},
            "_gm_targets_cache_rows": [{"player_id": "p1"}],
            "_gm_targets_cache_league": "1353858597108350976",
            "_gm_targets_hydrated_league": "1353858597108350976",
            "_effective_entitlement": "premium",
            "activity_inbox_snapshot": {"items": [1]},
            "trade_hub_focus_player_id_1353858597108350976": "p1",
        }
    )
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is True
    assert "_gm_targets_cache_ids" not in state
    assert "_gm_targets_cache_rows" not in state
    assert "_effective_entitlement" not in state
    assert "activity_inbox_snapshot" not in state
    assert "trade_hub_focus_player_id_1353858597108350976" not in state


def test_guest_mid_import_keeps_identity_sentinels():
    state = _Session(
        {
            "username": "guest_manager",
            "leagues_for_user": [{"league_id": "lg-1", "name": "League One"}],
            "_identity_established": True,
            "_league_selection_established": False,
        }
    )
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is False
    assert state.get("_identity_established") is True
    assert state.get("username") == "guest_manager"
    assert session_isolation.anonymous_must_not_carry_account_league(state)


def test_unsigned_empty_session_still_drops_stale_identity_sentinels():
    state = _Session(
        {
            "_identity_established": True,
            "_league_selection_established": True,
        }
    )
    session_isolation.enforce_anonymous_account_league_boundary(state)
    assert "_identity_established" not in state
    assert "_league_selection_established" not in state


def test_anonymous_explicit_guest_import_is_preserved():
    state = _Session(
        {
            "selected_league_id": "guest-league-1",
            "selected_league_name": "Guest League",
            "username": "guest_manager",
            session_isolation.GUEST_LEAGUE_ORIGIN_KEY: session_isolation.GUEST_LEAGUE_ORIGIN_EXPLICIT,
        }
    )
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is False
    assert state["selected_league_id"] == "guest-league-1"
    assert session_isolation.anonymous_must_not_carry_account_league(state)


def test_accounts_json_current_cannot_restore_into_anonymous_session():
    """Even with both legacy sentinels, disk singleton must not populate league."""

    session = _Session(
        {
            "_identity_established": True,
            "_league_selection_established": True,
        }
    )
    with patch("streamlit.session_state", session), patch(
        "app.get_current_account",
        return_value={
            "name": "1",
            "username": "Harryhard",
            "league_id": "1353858597108350976",
        },
    ), patch("app.get_user_roster_id", return_value=None), patch(
        "app._persist_active_account_context"
    ):
        import app

        context = app.resolve_active_league_context()

    assert context["username"] == ""
    assert context["selected_league_id"] is None
    assert session.get("selected_league_id") in (None, "")


def test_user_a_league_does_not_appear_for_user_b_or_guest():
    session_a = _Session(
        {
            auth_supabase.AUTH_SESSION_KEY: {
                "user_id": "user-a",
                "email": "a@example.com",
                "access_token": "tok-a",
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-a"},
            "selected_league_id": "league-a",
            "selected_league_name": "League A",
            session_isolation.GUEST_LEAGUE_ORIGIN_KEY: session_isolation.GUEST_LEAGUE_ORIGIN_AUTH,
        }
    )
    session_b = _Session(
        {
            auth_supabase.AUTH_SESSION_KEY: {
                "user_id": "user-b",
                "email": "b@example.com",
                "access_token": "tok-b",
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-b"},
            "selected_league_id": "league-b",
            "selected_league_name": "League B",
            session_isolation.GUEST_LEAGUE_ORIGIN_KEY: session_isolation.GUEST_LEAGUE_ORIGIN_AUTH,
        }
    )
    guest = _Session()

    # Process-warm: both authenticated sessions keep their own leagues.
    assert session_isolation.enforce_anonymous_account_league_boundary(session_a)["stripped"] is False
    assert session_isolation.enforce_anonymous_account_league_boundary(session_b)["stripped"] is False
    assert session_a["selected_league_id"] == "league-a"
    assert session_b["selected_league_id"] == "league-b"

    # Inject A's league into guest (simulating the production leak).
    guest["selected_league_id"] = session_a["selected_league_id"]
    guest["selected_league_name"] = session_a["selected_league_name"]
    guest["_league_selection_established"] = True
    guest["_identity_established"] = True
    stripped = session_isolation.enforce_anonymous_account_league_boundary(guest)
    assert stripped["stripped"] is True
    assert guest.get("selected_league_id") in (None, "")
    assert session_a["selected_league_id"] == "league-a"


def test_logout_clears_account_league_and_origin():
    state = _Session(
        {
            auth_supabase.AUTH_SESSION_KEY: {
                "user_id": "user-a",
                "email": "a@example.com",
                "access_token": "tok-a",
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-a"},
            auth_supabase.AUTH_EMAIL_KEY: "a@example.com",
            "selected_league_id": "league-a",
            "selected_league_name": "League A",
            "my_roster_id": "3",
            "username": "manager_a",
            session_isolation.GUEST_LEAGUE_ORIGIN_KEY: session_isolation.GUEST_LEAGUE_ORIGIN_AUTH,
            "_identity_established": True,
            "_league_selection_established": True,
        }
    )
    auth_supabase.clear_auth_session(state)
    assert auth_supabase.current_user_id(state) in ("", None)
    assert state.get("selected_league_id") in (None, "")
    assert session_isolation.GUEST_LEAGUE_ORIGIN_KEY not in state
    assert "_identity_established" not in state
    # Boundary stays clean for the post-logout guest session.
    assert session_isolation.enforce_anonymous_account_league_boundary(state)["stripped"] is False
    assert session_isolation.anonymous_must_not_carry_account_league(state)


def test_shell_header_memo_does_not_cross_identity_without_session_league():
    """Header league text is driven by session selected_league_id, not process memo."""

    from modules import application_shell

    shell = application_shell.ExecutiveWorkspaceShell(
        page_title="Dashboard",
        page_note="",
        league_name="Leaked League Name",
        team_name="",
        platform="Sleeper",
        account_label="Browsing as guest",
        entitlement_label="",
        has_league=False,
        authenticated=False,
    )
    html = application_shell.executive_workspace_shell_html(shell)
    assert "No league selected" in html
    assert "Leaked League Name" not in html


def test_guest_import_does_not_leak_into_second_guest_session():
    guest_one = _Session()
    session_isolation.mark_explicit_guest_league_import(guest_one)
    guest_one["selected_league_id"] = "guest-1"
    guest_one["selected_league_name"] = "Guest One"

    guest_two = _Session()
    # Simulate accidental copy of guest_one league without origin.
    guest_two["selected_league_id"] = guest_one["selected_league_id"]
    guest_two["selected_league_name"] = guest_one["selected_league_name"]

    assert session_isolation.enforce_anonymous_account_league_boundary(guest_one)["stripped"] is False
    assert session_isolation.enforce_anonymous_account_league_boundary(guest_two)["stripped"] is True
    assert guest_one["selected_league_id"] == "guest-1"
    assert guest_two.get("selected_league_id") in (None, "")


@pytest.mark.parametrize("sessions", [1, 3, 5, 10])
def test_concurrent_session_matrix_anonymous_stays_empty(sessions: int):
    """Process-warm / session-cold: N anonymous sessions never inherit A."""

    authenticated = _Session(
        {
            auth_supabase.AUTH_SESSION_KEY: {
                "user_id": "user-a",
                "access_token": "tok-a",
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-a"},
            "selected_league_id": "league-a",
            session_isolation.GUEST_LEAGUE_ORIGIN_KEY: session_isolation.GUEST_LEAGUE_ORIGIN_AUTH,
        }
    )
    guests = [_Session() for _ in range(sessions)]
    session_isolation.enforce_anonymous_account_league_boundary(authenticated)
    for guest in guests:
        # Warm process: guest somehow sees A's league id (the bug).
        guest["selected_league_id"] = authenticated["selected_league_id"]
        result = session_isolation.enforce_anonymous_account_league_boundary(guest)
        assert result["stripped"] is True
        assert guest.get("selected_league_id") in (None, "")
    assert authenticated["selected_league_id"] == "league-a"


def test_isolation_diagnostics_never_include_raw_secrets():
    state = _Session(
        {
            auth_supabase.AUTH_SESSION_KEY: {
                "user_id": "user-a",
                "email": "secret@example.com",
                "access_token": "super-secret-token",
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-a"},
            "selected_league_id": "league-secret",
            "selected_league_name": "Secret League Name",
            "_startup_session_id": "abcd1234",
        }
    )
    snap = session_isolation.build_isolation_diagnostics(state, restore_phase="LEAGUE_RESTORED")
    blob = str(snap)
    assert "secret@example.com" not in blob
    assert "super-secret-token" not in blob
    assert "Secret League Name" not in blob
    assert "league-secret" not in blob
    assert snap["account_digest"] != "NONE"
    assert snap["selected_league_digest"] != "NONE"
    assert snap["startup_session_id"] == "abcd1234"


def test_clear_account_bound_transient_drops_guest_origin():
    state = _Session(
        {
            session_isolation.GUEST_LEAGUE_ORIGIN_KEY: session_isolation.GUEST_LEAGUE_ORIGIN_AUTH,
            session_isolation.ISOLATION_DIAGNOSTICS_KEY: {"x": 1},
        }
    )
    session_integrity.clear_account_bound_transient_state(state)
    assert session_isolation.GUEST_LEAGUE_ORIGIN_KEY not in state
    assert session_isolation.ISOLATION_DIAGNOSTICS_KEY not in state


def test_unsigned_persist_skips_accounts_json_mutation():
    session = _Session({"username": "guest_user"})
    with patch("streamlit.session_state", session), patch("app.upsert_account") as upsert:
        import app

        app._persist_active_account_context(username="guest_user", league_id="league-x")
    upsert.assert_not_called()
