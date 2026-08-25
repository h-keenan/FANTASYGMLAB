"""Canonical signed-in truth vs profile/expired-session banners."""

from __future__ import annotations

from modules import account_store
from modules import auth_supabase
from modules import guest_conversion


def test_header_and_banner_agree_when_profile_jwt_fails_but_session_is_live():
    state = {
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "user-1",
            "access_token": "live-token",
            "refresh_token": "refresh",
            "expires_at": 9999999999,
        },
        auth_supabase.AUTH_USER_KEY: {"id": "user-1", "email": "a@b.c"},
    }
    assert auth_supabase.session_is_signed_in(state) is True
    assert guest_conversion.guest_account_label(state) == "Signed in"
    notice = account_store.profile_status_notice(
        profile_status="error",
        profile_error="JWT expired",
        session_authenticated=True,
    )
    assert "session expired" not in notice.casefold()
    assert "premium stays locked" in notice.casefold()


def test_expired_access_token_is_not_signed_in_and_requires_sign_in():
    state = {
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "user-1",
            "access_token": "stale-token",
            "refresh_token": "refresh",
            "expires_at": 1,
        },
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
    }
    assert auth_supabase.current_user_id(state) == "user-1"
    assert auth_supabase.session_is_signed_in(state) is False
    assert guest_conversion.guest_account_label(state) == guest_conversion.GUEST_STATE_LABEL
    notice = account_store.profile_status_notice(
        profile_status="error",
        profile_error="JWT expired",
        session_authenticated=False,
    )
    assert notice == account_store.SESSION_EXPIRED_COPY


def test_generic_session_word_does_not_claim_expiry():
    text = account_store.customer_safe_error(
        "Could not load session preferences from storage.",
        context="profile",
        session_authenticated=True,
    )
    assert "session expired" not in text.casefold()
