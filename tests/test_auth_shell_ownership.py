"""Auth shell ownership + signup error taxonomy contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules import auth_supabase


ROOT = Path(__file__).resolve().parents[1]


def test_signup_classifies_unreachable_provider():
    classified = auth_supabase.classify_auth_error(
        "Could not reach Supabase Auth.",
        exception_type="NameResolutionError",
    )
    assert classified["category"] == "provider_unreachable"
    assert "temporarily unavailable" in classified["user_message"].casefold()


def test_signup_classifies_duplicate_user():
    classified = auth_supabase.classify_auth_error(
        "User already registered [user_already_exists]"
    )
    assert classified["category"] == "duplicate_user"
    assert "already exists" in classified["user_message"].casefold()
    assert "Sign in" in classified["user_message"]


def test_signup_classifies_password_and_email_validation():
    assert auth_supabase.signup_user_message("Password should be at least 8 characters")
    weak = auth_supabase.classify_auth_error("Password should be at least 8 characters")
    assert weak["category"] == "invalid_password"
    assert weak["user_message"] == "Password should be at least 8 characters."
    email = auth_supabase.classify_auth_error("Unable to validate email address")
    assert email["category"] == "invalid_email"


def test_signup_does_not_echo_raw_password_provider_errors():
    leaked = auth_supabase.classify_auth_error(
        "Password hashing failed at bcrypt [unexpected_failure]"
    )
    assert leaked["category"] == "invalid_password"
    assert "bcrypt" not in leaked["user_message"].casefold()
    assert "hashing" not in leaked["user_message"].casefold()
    assert "unexpected_failure" not in leaked["user_message"].casefold()


def test_signup_unreachable_host_returns_safe_error_and_diagnostic(capsys):
    config = {"enabled": True, "url": "https://otsbideskqceaojfzgbt.supabase.co", "anon_key": "anon"}
    with patch("modules.auth_supabase.requests.post", side_effect=ConnectionError("DNS")):
        payload, error = auth_supabase.sign_up(config, "user@example.com", "TestPass123!")
    assert payload is None
    assert error == "Could not reach Supabase Auth."
    assert "temporarily unavailable" in auth_supabase.signup_user_message(error).casefold()
    logged = capsys.readouterr().out
    assert "DYNASTYGM_AUTH" in logged
    assert "provider_unreachable" in logged
    assert "otsbideskqceaojfzgbt.supabase.co" in logged
    assert "ConnectionError" in logged
    assert "user@example.com" not in logged
    assert "TestPass123!" not in logged
    assert "anon" not in logged.split("DYNASTYGM_AUTH", 1)[1]


def test_signup_does_not_claim_unavailable_for_generic_client_errors():
    classified = auth_supabase.classify_auth_error("GoTrue rejected the request", status_code=400)
    assert classified["category"] == "provider_error"
    assert "temporarily unavailable" not in classified["user_message"].casefold()


def test_signup_classifies_smtp_captcha_and_unavailable_5xx():
    smtp = auth_supabase.classify_auth_error("Error sending confirmation email [smtp_send_failed]")
    assert smtp["category"] == "smtp_failure"
    assert "confirmation email" in smtp["user_message"].casefold()
    captcha = auth_supabase.classify_auth_error("captcha_failed", status_code=400)
    assert captcha["category"] == "captcha"
    five = auth_supabase.classify_auth_error("unexpected_failure", status_code=500)
    assert five["category"] == "provider_unavailable"
    assert "temporarily unavailable" in five["user_message"].casefold()


def test_signup_client_validation_before_network():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    with patch("modules.auth_supabase.requests.post") as post:
        payload, error = auth_supabase.sign_up(config, "not-an-email", "x")
    assert payload is None
    assert "email" in error.casefold()
    post.assert_not_called()
    payload, error = auth_supabase.sign_up(config, "user@example.com", "123")
    assert payload is None
    assert "6 characters" in error.casefold()
    post.assert_not_called()
