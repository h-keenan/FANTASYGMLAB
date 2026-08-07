"""Founder Beta launch verification: payments, entitlements, feedback, security."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

from modules import auth_supabase, feedback, launch_analytics, premium, stripe_billing, stripe_webhook


ROOT = Path(__file__).resolve().parents[1]


def test_entitlement_sql_blocks_client_insert_self_grant_and_allows_service_role():
    for relative in (
        "docs/supabase_accounts.sql",
        "docs/supabase_profile_entitlement.sql",
        "docs/supabase_entitlement_security_hardening.sql",
    ):
        sql = (ROOT / relative).read_text(encoding="utf-8").casefold()
        assert "service_role" in sql
        assert "tg_op = 'insert'" in sql or 'tg_op = "insert"' in sql or "tg_op = 'INSERT'".casefold() in sql
        assert "new.entitlement := 'free'" in sql
        assert "before insert or update" in sql


def test_feedback_sql_is_rls_protected_and_founder_reviewable():
    sql = (ROOT / "docs/supabase_feedback.sql").read_text(encoding="utf-8")
    lowered = sql.casefold()
    assert "create table if not exists public.feedback_reports" in lowered
    assert "enable row level security" in lowered
    assert "feedback_insert_own" in lowered
    assert "feedback_insert_guest" in lowered
    assert "auth.uid() = user_id" in lowered
    assert "user_id is null" in lowered
    assert "table editor" in lowered


def test_feedback_categories_cover_launch_taxonomy():
    categories = feedback.GLOBAL_FEEDBACK_CATEGORIES
    assert "Bug or broken page" in categories
    assert "Confusing page" in categories
    assert "Bad recommendation" in categories
    assert "Feature request" in categories
    assert "Billing or Premium" in categories
    assert "Other feedback" in categories


def test_feedback_context_omits_email_and_tokens():
    payload = feedback.feedback_context_payload(
        current_page="trade_hub",
        platform="Sleeper",
        league_id="league-1",
        league_name="Secret League",
        user_id="user-1",
        email="user@example.com",
        entitlement="premium",
        viewport_width=390,
    )
    assert payload["auth_state"] == "signed_in"
    assert payload["viewport_category"] == "mobile"
    assert payload["entitlement"] == "premium"
    assert "email" not in payload
    assert "league_name" not in payload
    report = feedback.build_global_feedback_report(
        category="Bug or broken page",
        message="Broken",
        context={**payload, "access_token": "secret", "email": "user@example.com"},
        email="user@example.com",
        can_contact=False,
    )
    assert "access_token" not in report["context"]
    assert report["email"] == ""


def test_feedback_supabase_insert_uses_authenticated_row(monkeypatch):
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        response = Mock()
        response.status_code = 201
        return response

    monkeypatch.setattr(feedback.requests, "post", fake_post)
    report = feedback.build_global_feedback_report(
        category="Feature request",
        message="Add export",
        context={"page": "dashboard", "user_id": "user-1"},
        can_contact=False,
    )
    report["user_id"] = "user-1"
    saved, error = feedback.append_feedback_report_supabase(
        report,
        config={"url": "https://example.supabase.co", "anon_key": "anon", "enabled": True},
        access_token="user-jwt",
    )
    assert saved is True
    assert error == ""
    assert calls["json"]["user_id"] == "user-1"
    assert calls["json"]["category"] == "Feature request"
    assert "feedback_reports" in calls["url"]


def test_past_due_webhook_is_successful_noop(monkeypatch):
    action = stripe_billing.map_stripe_event_to_entitlement(
        {
            "id": "evt_past_due",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_1",
                    "status": "past_due",
                    "metadata": {"supabase_user_id": "user-1"},
                }
            },
        }
    )
    assert action["entitlement"] == ""

    monkeypatch.setattr(
        stripe_billing,
        "handle_stripe_webhook",
        lambda *args, **kwargs: action,
    )
    result = stripe_webhook.process_verified_stripe_webhook(
        payload=b"{}",
        signature="sig",
        stripe_config=stripe_billing.StripeBillingConfig(
            secret_key="sk_test_1",
            webhook_secret="whsec_1",
            price_monthly="price_m",
            price_annual="price_a",
        ),
        supabase_config=stripe_webhook.SupabaseWebhookConfig(
            url="https://example.supabase.co",
            service_role_key="service",
        ),
        request_session=Mock(),
    )
    assert result["ok"] is True
    assert result["skipped"] is True


def test_cancel_at_period_end_keeps_premium_while_active():
    action = stripe_billing.map_stripe_event_to_entitlement(
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_1",
                    "status": "active",
                    "cancel_at_period_end": True,
                    "metadata": {"supabase_user_id": "user-1"},
                }
            },
        }
    )
    assert action["entitlement"] == premium.PREMIUM
    assert action["cancel_at_period_end"] == "true"


def test_checkout_includes_idempotency_key(monkeypatch):
    created = Mock(return_value=Mock(url="https://checkout.test/session"))
    fake_stripe = Mock()
    fake_stripe.checkout.Session.create = created
    monkeypatch.setattr(stripe_billing, "_stripe_module", lambda: fake_stripe)
    stripe_billing.create_checkout_session(
        config=stripe_billing.StripeBillingConfig(
            secret_key="sk_test_123",
            price_monthly="price_month",
            price_annual="price_year",
        ),
        user_id="user-1",
        email="user@example.com",
        interval=stripe_billing.MONTHLY,
    )
    assert "idempotency_key" in created.call_args.kwargs
    assert created.call_args.kwargs["idempotency_key"].startswith("fgl-checkout-user-1-monthly")


def test_logout_clears_league_session_chrome():
    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "x"},
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
        auth_supabase.AUTH_EMAIL_KEY: "user@example.com",
        "selected_league_id": "league-1",
        "selected_league_name": "Old League",
        "username": "olduser",
        "active_league_context": {"selected_league_id": "league-1"},
        "account_saved_leagues_cache": [{"league_id": "league-1"}],
        "account_profile": {"entitlement": "premium"},
        "_identity_established": True,
        "_effective_entitlement": "premium",
        "player_quick_view_player_id": "4046",
        "canonical_recommendation_narrative": {"recommendation_id": "r1"},
        "trade_send_assets": [{"player_id": "1"}],
    }
    auth_supabase.clear_auth_session(state)
    assert "selected_league_id" not in state
    assert "active_league_context" not in state
    assert "username" not in state
    assert "account_profile" not in state
    assert "_identity_established" not in state
    assert "_effective_entitlement" not in state
    assert "player_quick_view_player_id" not in state
    assert "canonical_recommendation_narrative" not in state
    assert "trade_send_assets" not in state
    assert state[auth_supabase.ACCOUNT_MODE_KEY] == "guest"


def test_launch_analytics_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(launch_analytics, "ENABLED", False)
    monkeypatch.setattr(launch_analytics, "analytics_enabled", lambda **kwargs: False)
    monkeypatch.setattr(launch_analytics, "ANALYTICS_PATH", str(tmp_path / "events.jsonl"))
    assert launch_analytics.track_event("dashboard_reached") is False
    assert not (tmp_path / "events.jsonl").exists()


def test_launch_analytics_records_safe_events(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setattr(launch_analytics, "ENABLED", True)
    monkeypatch.setattr(launch_analytics, "ANALYTICS_PATH", str(path))
    launch_analytics._SESSION_EMITTED.clear()
    assert launch_analytics.track_event(
        "checkout_started",
        props={"interval": "monthly", "email": "secret@example.com"},
        once_key="user-1",
    )
    assert launch_analytics.track_event(
        "checkout_started",
        props={"interval": "monthly"},
        once_key="user-1",
    ) is False
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["event"] == "checkout_started"
    assert "email" not in row["props"]


def test_render_yaml_keeps_service_role_off_streamlit():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    streamlit_block, webhook_block = text.split("fantasygm-lab-stripe-webhook", 1)
    assert "SUPABASE_SERVICE_ROLE_KEY" not in streamlit_block
    assert "SUPABASE_SERVICE_ROLE_KEY" in webhook_block
    assert "STRIPE_WEBHOOK_SECRET" not in streamlit_block.split("fantasygm-lab-stripe-webhook")[0]
    assert "DYNASTYGM_SHOW_EXPERIMENTAL" in streamlit_block


def test_launch_verification_doc_exists():
    doc = (ROOT / "docs/founder-beta-launch-verification.md").read_text(encoding="utf-8")
    assert "Ready after listed manual configuration" in doc
    assert "docs/supabase_feedback.sql" in doc
    assert "docs/supabase_entitlement_security_hardening.sql" in doc
