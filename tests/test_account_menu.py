"""You-menu identity and canonical logout isolation."""

from __future__ import annotations

import time
from unittest.mock import patch

from modules import account_menu
from modules import account_ui
from modules import auth_supabase
from modules import founder_labs
from modules import session_integrity


FUTURE = int(time.time()) + 3600
PAST = int(time.time()) - 3600


def _signed(*, email: str, premium: bool = False, founder: bool = False, expired: bool = False):
    meta = {}
    if founder:
        meta = {"founder_ops": True, "dev_review": True}
    return {
        auth_supabase.AUTH_USER_KEY: {
            "id": "user-live",
            "email": email,
            "app_metadata": meta,
        },
        auth_supabase.AUTH_EMAIL_KEY: email,
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "user-live",
            "access_token": "token",
            "expires_at": PAST if expired else FUTURE,
        },
        "selected_league_id": "league-a",
        "account_profile": {"email": "stale@example.com", "entitlement": "premium"},
    }


def test_free_account_shows_live_email_not_stale_profile():
    state = _signed(email="free@example.com")
    identity = account_menu.account_identity(state, entitlement_label="Free")
    assert identity["signed_in"] is True
    assert identity["display_identity"] == "free@example.com"
    assert identity["entitlement_label"] == "Free"
    assert identity["internal_badge"] is False
    assert identity["founder_labs"] is False
    assert "user-live" not in str(identity)


def test_premium_account_shows_entitlement_without_founder_badge():
    state = _signed(email="paid@example.com", premium=True)
    identity = account_menu.account_identity(state, entitlement_label="Premium")
    assert identity["display_identity"] == "paid@example.com"
    assert identity["entitlement_label"] == "Premium"
    assert identity["internal_badge"] is False


def test_founder_account_shows_internal_badge_when_authorized():
    env = {"DYNASTYGM_DEV_REVIEW": "1", "DYNASTYGM_FOUNDER_OPS": "1"}
    state = _signed(email="founder@example.com", founder=True)
    identity = account_menu.account_identity(
        state, entitlement_label="Premium", environ=env
    )
    assert identity["founder_labs"] is True
    assert identity["founder_ops"] is True
    assert identity["internal_badge"] is True


def test_signed_out_and_expired_hide_identity_and_founder():
    env = {"DYNASTYGM_DEV_REVIEW": "1"}
    signed_out = {"account_profile": {"email": "stale@example.com"}}
    identity = account_menu.account_identity(
        signed_out, entitlement_label="Free", environ=env
    )
    assert identity["signed_in"] is False
    assert identity["display_identity"] == ""
    assert identity["internal_badge"] is False
    expired = _signed(email="founder@example.com", founder=True, expired=True)
    expired_id = account_menu.account_identity(
        expired, entitlement_label="Premium", environ=env
    )
    assert expired_id["signed_in"] is False
    assert expired_id["founder_labs"] is False


def test_logout_clears_founder_and_league_state():
    env = {"DYNASTYGM_DEV_REVIEW": "1"}
    state = _signed(email="founder@example.com", founder=True)
    state["platform_nav_page"] = "founder_labs"
    assert founder_labs.founder_labs_authorized(state, environ=env)
    with patch.object(auth_supabase, "sign_out", return_value=""):
        account_ui.complete_sign_out(state, config={"enabled": True})
    assert not auth_supabase.session_is_signed_in(state)
    assert not founder_labs.founder_labs_authorized(state, environ=env)
    assert not state.get("selected_league_id")
    identity = account_menu.account_identity(state, entitlement_label="Free", environ=env)
    assert identity["signed_in"] is False
    assert identity["founder_labs"] is False
    assert state.get("platform_nav_page") == "dashboard"


def test_account_switch_drops_prior_founder_visibility():
    env = {"DYNASTYGM_DEV_REVIEW": "1"}
    founder = _signed(email="founder@example.com", founder=True)
    session_integrity.clear_account_bound_transient_state(founder)
    normal = {
        auth_supabase.AUTH_USER_KEY: {"id": "user-2", "email": "normal@example.com", "app_metadata": {}},
        auth_supabase.AUTH_EMAIL_KEY: "normal@example.com",
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "user-2",
            "access_token": "other",
            "expires_at": FUTURE,
        },
    }
    identity = account_menu.account_identity(
        normal, entitlement_label="Free", environ=env
    )
    assert identity["display_identity"] == "normal@example.com"
    assert identity["founder_labs"] is False
    assert founder_labs.founder_labs_authorized(normal, environ=env) is False
