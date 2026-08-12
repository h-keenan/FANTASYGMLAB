"""Pre-launch onboarding: email confirmation contract + welcome IA + guest frame gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules import auth_supabase
from modules import marketing_landing


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ACCOUNT_UI = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")


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


def test_auth_storage_js_consumes_confirmation_callback():
    assert "consumeAuthCallback" in ACCOUNT_UI
    assert "auth_callback" in ACCOUNT_UI
    assert "token_hash" in ACCOUNT_UI
    assert "fetch_auth_user" in ACCOUNT_UI or "verify_email_token_hash" in (
        ROOT / "modules" / "auth_supabase.py"
    ).read_text(encoding="utf-8")


def test_confirmation_card_copy_is_check_your_email():
    auth_src = (ROOT / "modules" / "auth_supabase.py").read_text(encoding="utf-8")
    assert "Check your email" in auth_src
    assert "not active yet" in auth_src
    assert "If an account can be created" in auth_src
    assert "Already have an account? Sign in" in ACCOUNT_UI
    assert "Use a different email" in ACCOUNT_UI
    assert "Continue as guest" in ACCOUNT_UI


def test_welcome_cold_paint_defers_feature_lists():
    cold = marketing_landing.landing_hero_html() + marketing_landing.landing_body_html(
        billing_configured=False
    )
    assert brand_name_in(cold)
    assert marketing_landing.HERO_VALUE in cold
    assert marketing_landing.TRUST_LINE in cold
    assert "What it does" not in cold
    assert "Next step" not in cold
    assert "Free includes" not in cold
    detail = marketing_landing.landing_body_html(
        billing_configured=False, detail=True, include_pricing=True
    )
    assert "What it does" in detail
    assert "Free includes" in detail


def brand_name_in(html: str) -> bool:
    from modules import brand_identity

    return brand_identity.PRODUCT_NAME in html


def test_welcome_cta_hierarchy_source():
    landing = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
    assert landing.count("st.columns(2)") >= 1
    assert "landing_primary_cta" in landing
    assert "landing_secondary_cta" in landing
    # Pricing is tertiary text control, not a third equal hero column.
    assert "st.columns(3)" not in landing


def test_guest_no_league_skips_prepared_frame_build():
    assert 'prepared_frame_signature = "guest_no_league"' in APP
    assert "no_selected_league" in APP
    # ensure_players remains gated inside selected_league branch
    hydrate = APP.split("# --- Football hydration", 1)[1].split(
        "# Enrich strategy/ranks after prepared frame", 1
    )[0]
    assert "if not selected_league_id:" in hydrate
    assert "get_or_build_valued_ranked_frame" in hydrate
    # Builder only in the else/selected branch
    assert hydrate.index("if not selected_league_id:") < hydrate.index(
        "get_or_build_valued_ranked_frame"
    )


def test_anonymous_isolation_still_preserved():
    from modules import session_isolation

    state = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
    }
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is True
