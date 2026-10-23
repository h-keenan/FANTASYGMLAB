"""Pending email confirmation UX after unconfirmed signup."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import auth_supabase


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
