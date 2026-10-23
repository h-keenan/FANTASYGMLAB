"""Canonical signed-in truth vs profile/expired-session banners."""

from __future__ import annotations

from modules import account_store
from modules import auth_supabase


def test_generic_session_word_does_not_claim_expiry():
    text = account_store.customer_safe_error(
        "Could not load session preferences from storage.",
        context="profile",
        session_authenticated=True,
    )
    assert "session expired" not in text.casefold()
