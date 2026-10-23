"""Pre-launch onboarding: email confirmation contract + welcome IA + guest frame gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules import auth_supabase


ROOT = Path(__file__).resolve().parents[1]


def test_signup_without_session_requires_confirmation():
    payload = {"user": {"id": "u1", "email": "a@b.c", "email_confirmed_at": None}}
    assert auth_supabase.signup_requires_email_confirmation(payload) is True
    assert auth_supabase.session_is_authenticated_for_app(payload) is False


def test_signup_with_unconfirmed_session_is_not_authenticated():
    payload = {
        "access_token": "tok",
        "refresh_token": "ref",
        "user": {"id": "u1", "email": "a@b.c", "email_confirmed_at": None},
    }
    assert auth_supabase.signup_requires_email_confirmation(payload) is True
    assert auth_supabase.session_is_authenticated_for_app(payload) is False
    state: dict = {}
    assert auth_supabase.apply_auth_payload(state, payload) == {}
    assert state.get(auth_supabase.CONFIRMATION_REQUIRED_KEY) is True
    assert not auth_supabase.current_user_id(state)


def test_confirmed_session_is_authenticated():
    payload = {
        "access_token": "tok",
        "refresh_token": "ref",
        "user": {
            "id": "u1",
            "email": "a@b.c",
            "email_confirmed_at": "2026-08-12T00:00:00Z",
        },
    }
    assert auth_supabase.signup_requires_email_confirmation(payload) is False
    assert auth_supabase.session_is_authenticated_for_app(payload) is True
    state: dict = {}
    session = auth_supabase.apply_auth_payload(state, payload)
    assert session.get("user_id") == "u1"
    assert auth_supabase.current_user_id(state) == "u1"


def test_signup_posts_email_redirect_to(monkeypatch):
    config = {
        "enabled": True,
        "url": "https://proj.supabase.co",
        "anon_key": "sb_publishable_test",
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "user": {"id": "u1", "email": "new@example.com", "email_confirmed_at": None},
    }
    with patch("modules.auth_supabase.requests.post", return_value=mock_response) as post:
        with patch(
            "modules.auth_supabase.email_redirect_to",
            return_value="https://app.fantasygmlab.com",
        ):
            payload, error = auth_supabase.sign_up(config, "new@example.com", "StrongPass1!")
    assert error == ""
    assert auth_supabase.signup_requires_email_confirmation(payload) is True
    body = post.call_args.kwargs["json"]
    assert body["email_redirect_to"] == "https://app.fantasygmlab.com"


def brand_name_in(html: str) -> bool:
    from modules import brand_identity

    return brand_identity.PRODUCT_NAME in html
