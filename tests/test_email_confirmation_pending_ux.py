"""Pending email confirmation UX after unconfirmed signup."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import auth_supabase
from modules import account_ui
from modules import session_isolation


def test_top_level_signup_user_requires_confirmation():
    """Raw GoTrue confirm-email response is often a bare user object."""

    payload = {
        "id": "user-1",
        "email": "founder@example.com",
        "email_confirmed_at": None,
        "confirmation_sent_at": "2026-08-12T20:00:00Z",
        "aud": "authenticated",
        "role": "authenticated",
    }
    assert auth_supabase.extract_auth_user(payload)["id"] == "user-1"
    assert auth_supabase.signup_requires_email_confirmation(payload) is True
    assert auth_supabase.session_is_authenticated_for_app(payload) is False


def test_nested_null_session_requires_confirmation():
    payload = {
        "user": {
            "id": "user-2",
            "email": "a@b.c",
            "email_confirmed_at": None,
            "confirmation_sent_at": "2026-08-12T20:00:00Z",
        },
        "session": None,
    }
    assert auth_supabase.signup_requires_email_confirmation(payload) is True
    assert auth_supabase.session_is_authenticated_for_app(payload) is False


def test_enter_pending_clears_auth_and_sets_canonical_state():
    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "x", "user_id": "u"},
        auth_supabase.AUTH_USER_KEY: {"id": "u"},
        auth_supabase.AUTH_EMAIL_KEY: "a@b.c",
        auth_supabase.ACCOUNT_MODE_KEY: "account",
    }
    pending = auth_supabase.enter_pending_email_confirmation(
        state,
        "founder@example.com",
        payload={
            "id": "user-1",
            "email": "founder@example.com",
            "email_confirmed_at": None,
            "confirmation_sent_at": "2026-08-12T20:00:00Z",
        },
    )
    assert pending["pending"] is True
    assert pending["email_masked"] == "f***@example.com"
    assert pending["confirmation_evidence"] == "definite_new_unconfirmed"
    assert pending["confirmation_sent"] is True
    assert auth_supabase.is_pending_email_confirmation(state) is True
    assert auth_supabase.current_user_id(state) == ""
    assert state.get(auth_supabase.ACCOUNT_MODE_KEY) == "guest"
    assert state.get(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY) is True


def test_signup_path_enters_pending_for_top_level_user():
    config = {"enabled": True, "url": "https://proj.supabase.co", "anon_key": "sb_publishable_x"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "user-9",
        "email": "new@example.com",
        "email_confirmed_at": None,
        "confirmation_sent_at": "2026-08-12T21:00:00Z",
    }
    with patch("modules.auth_supabase.requests.post", return_value=mock_response):
        with patch(
            "modules.auth_supabase.email_redirect_to",
            return_value="https://app.fantasygmlab.com",
        ):
            payload, error = auth_supabase.sign_up(config, "new@example.com", "StrongPass1!")
    assert error == ""
    assert auth_supabase.signup_requires_email_confirmation(payload) is True
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(state, "new@example.com", payload=payload)
    assert auth_supabase.is_pending_email_confirmation(state)
    assert not auth_supabase.current_user_id(state)


def test_mobile_auth_entry_replaces_form_when_pending():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    state: dict = {}
    # No payload → ambiguous evidence → enumeration-safe copy (no false “we sent”).
    auth_supabase.enter_pending_email_confirmation(state, "user@example.com")
    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ) as markdown, patch.object(account_ui.st, "button", return_value=False), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "success"), patch.object(account_ui.st, "warning"), patch.object(
        account_ui.st, "info"
    ):
        actions = account_ui.render_mobile_auth_entry(config=config)
    html = " ".join(str(c.args[0]) for c in markdown.call_args_list if c.args)
    assert "Check your email" in html
    assert "data-fgl-pending-email-confirmation" in html
    assert "not signed in" in html.casefold()
    assert "If an account can be created" in html
    assert "We sent a confirmation" not in html
    assert actions["logged_in"] is False
    assert actions["continue_guest"] is False


def test_use_different_email_clears_pending():
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(state, "a@b.c")
    auth_supabase.clear_pending_email_confirmation(state)
    assert auth_supabase.is_pending_email_confirmation(state) is False
    assert auth_supabase.PENDING_EMAIL_CONFIRMATION_KEY not in state


def test_confirmed_callback_clears_pending():
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(state, "a@b.c")
    payload = {
        "access_token": "tok",
        "refresh_token": "ref",
        "user": {
            "id": "u1",
            "email": "a@b.c",
            "email_confirmed_at": "2026-08-12T22:00:00Z",
        },
    }
    auth_supabase.apply_auth_payload(state, payload)
    assert auth_supabase.current_user_id(state) == "u1"
    assert auth_supabase.is_pending_email_confirmation(state) is False


def test_guest_dialog_pending_signup_keeps_dialog_open():
    """In-league soft-prompt signup must keep the dialog so the check-email card can mount."""

    source = Path(__file__).resolve().parents[1].joinpath(
        "modules", "guest_conversion.py"
    ).read_text(encoding="utf-8")
    dialog_fn = source.split("def render_guest_auth_dialog", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "is_pending_email_confirmation" in dialog_fn
    assert "render_confirmation_required_card" in dialog_fn
    import re

    pending_blocks = re.findall(
        r"enter_pending_email_confirmation\([\s\S]*?st\.rerun\(\)",
        dialog_fn,
    )
    assert pending_blocks
    for block in pending_blocks:
        assert "close_auth_dialog()" not in block


def test_email_confirm_callback_consumes_guest_resume():
    source = Path(__file__).resolve().parents[1].joinpath(
        "modules", "account_ui.py"
    ).read_text(encoding="utf-8")
    region = source.split("email_confirm_callback", 1)[1].split(
        "if isinstance(status, dict)", 1
    )[0]
    assert "peek_guest_resume" in region
    assert "finish_auth_from_guest" in region
    assert 'surface="email_confirm"' in region


def test_anonymous_isolation_while_pending():
    state = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
    }
    auth_supabase.enter_pending_email_confirmation(state, "a@b.c")
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is True
    assert not auth_supabase.current_user_id(state)
