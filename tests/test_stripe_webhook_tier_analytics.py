"""Regression coverage for _track_subscription_lifecycle's tier resolution.

Follow-up fix: PR #995 wired subscribed/trial_started/churned analytics but
hardcoded extra={"tier": "premium"} as a placeholder, written before the
3-tier entitlement model (PR #996) existed. That hardcode silently dropped
Front Office subscribers from the "subscribed"/"trial_started" events
entirely (their raw entitlement is "front_office", never "premium") and
mislabeled every tier value. This file pins the corrected behavior.
"""

from __future__ import annotations

from modules import premium, stripe_billing, stripe_webhook


def _config() -> stripe_billing.StripeBillingConfig:
    return stripe_billing.StripeBillingConfig(
        billing_mode="test",
        secret_key="sk_test_x",
        webhook_secret="whsec_x",
        price_monthly="price_monthly_x",
        price_annual="price_annual_x",
        customer_portal_return_url="https://example.com/portal",
        checkout_success_url="https://example.com/success",
        checkout_cancel_url="https://example.com/cancel",
        app_base_url="https://example.com",
    )


def _capture(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake_track_event(event_name, *, props, once_key=None, state=None):
        calls.append((event_name, dict(props or {})))

    monkeypatch.setattr(
        "modules.launch_analytics.track_event", fake_track_event
    )
    return calls


def test_pro_checkout_fires_subscribed_with_pro_tier(monkeypatch):
    calls = _capture(monkeypatch)
    stripe_webhook._track_subscription_lifecycle(
        {
            "user_id": "u1",
            "entitlement": "premium",
            "reason": "checkout.session.completed",
            "stripe_subscription_status": "active",
            "event_id": "evt_1",
            "stripe_price_id": "price_monthly_x",
        },
        stripe_config=_config(),
    )
    assert len(calls) == 1
    name, props = calls[0]
    assert name == "subscribed"
    assert props["tier"] == "pro"
    assert props["interval"] == "monthly"


def test_pro_trial_fires_trial_started(monkeypatch):
    calls = _capture(monkeypatch)
    stripe_webhook._track_subscription_lifecycle(
        {
            "user_id": "u1",
            "entitlement": "premium",
            "reason": "customer.subscription.created",
            "stripe_subscription_status": "trialing",
            "event_id": "evt_2",
            "stripe_price_id": "price_annual_x",
        },
        stripe_config=_config(),
    )
    assert len(calls) == 1
    name, props = calls[0]
    assert name == "trial_started"
    assert props["tier"] == "pro"
    assert props["interval"] == "annual"


def test_front_office_checkout_now_fires_subscribed(monkeypatch):
    """Regression: the pre-fix hardcode only matched entitlement == "premium",
    so a Front Office subscriber's raw "front_office" entitlement silently
    fired no analytics event at all."""
    calls = _capture(monkeypatch)
    stripe_webhook._track_subscription_lifecycle(
        {
            "user_id": "u2",
            "entitlement": "front_office",
            "reason": "checkout.session.completed",
            "stripe_subscription_status": "active",
            "event_id": "evt_3",
            "stripe_price_id": "",
        },
        stripe_config=_config(),
    )
    assert len(calls) == 1
    name, props = calls[0]
    assert name == "subscribed"
    assert props["tier"] == "front_office"
    assert props["interval"] == ""


def test_churned_event_does_not_fabricate_a_tier(monkeypatch):
    """Regression: the pre-fix hardcode always claimed tier="premium" on
    churn, even though the webhook payload only ever carries the user's NEW
    (free) entitlement, not which paid tier was actually lost."""
    calls = _capture(monkeypatch)
    stripe_webhook._track_subscription_lifecycle(
        {
            "user_id": "u3",
            "entitlement": "free",
            "reason": "customer.subscription.deleted",
            "stripe_subscription_status": "canceled",
            "event_id": "evt_4",
            "stripe_price_id": "",
        },
        stripe_config=_config(),
    )
    assert len(calls) == 1
    name, props = calls[0]
    assert name == "churned"
    assert props["reason"] == "customer.subscription.deleted"
    assert "tier" not in props


def test_canonical_tier_mapping_matches_premium_module():
    assert premium.canonical_tier("premium") == premium.PRO
    assert premium.canonical_tier("front_office") == premium.FRONT_OFFICE
