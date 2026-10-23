"""3-day Pro free trial: checkout params, eligibility, webhook transitions."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modules import revenuecat_billing, revenuecat_webhook, stripe_billing, stripe_webhook

NOW = int(time.time())
FUTURE = NOW + 3 * 86400
PAST = NOW - 3600


def _config(**kw):
    base = dict(secret_key="sk_test_1", price_monthly="price_m", price_annual="price_a")
    base.update(kw)
    return stripe_billing.StripeBillingConfig(**base)


def _checkout(config, **kw):
    created = Mock(return_value=SimpleNamespace(url="https://checkout.test/s"))
    fake = SimpleNamespace(api_key="", checkout=SimpleNamespace(Session=SimpleNamespace(create=created)))
    with patch.dict(sys.modules, {"stripe": fake}):
        stripe_billing.create_checkout_session(
            config=config, user_id="u1", email="a@b.co", interval="monthly", **kw
        )
    return created.call_args.kwargs


def test_trial_days_env_default_disable_and_junk():
    assert stripe_billing.load_stripe_config(environ={}).trial_days == 3
    assert stripe_billing.load_stripe_config(environ={"STRIPE_TRIAL_DAYS": "0"}).trial_days == 0
    assert stripe_billing.load_stripe_config(environ={"STRIPE_TRIAL_DAYS": "5"}).trial_days == 5
    assert stripe_billing.load_stripe_config(environ={"STRIPE_TRIAL_DAYS": "abc"}).trial_days == 0


def test_checkout_has_three_day_trial_with_card_up_front():
    kwargs = _checkout(_config())
    assert kwargs["subscription_data"]["trial_period_days"] == 3
    assert kwargs["payment_method_collection"] == "always"
    assert kwargs["subscription_data"]["trial_settings"]["end_behavior"]["missing_payment_method"] == "cancel"


def test_checkout_no_trial_when_disabled_or_ineligible():
    assert "trial_period_days" not in _checkout(_config(trial_days=0))["subscription_data"]
    kwargs = _checkout(_config(), trial_eligible=False)
    assert "trial_period_days" not in kwargs["subscription_data"]
    assert kwargs["payment_method_collection"] == "always"


def test_eligibility_one_trial_per_account():
    cfg = _config()
    assert stripe_billing.trial_eligible(cfg, profile={}, check_stripe=False)
    assert not stripe_billing.trial_eligible(cfg, profile={"stripe_customer_id": "cus_1"}, check_stripe=False)
    assert not stripe_billing.trial_eligible(cfg, profile={"revenuecat_app_user_id": "u"}, check_stripe=False)
    assert not stripe_billing.trial_eligible(cfg, profile={"trial_ends_at": "2026-01-01"}, check_stripe=False)
    assert not stripe_billing.trial_eligible(_config(trial_days=0), profile={}, check_stripe=False)
    assert not stripe_billing.trial_eligible(cfg, tier="front_office", profile={}, check_stripe=False)


def test_eligibility_stripe_history_and_lookup_failure_fail_closed():
    cfg = _config()
    fake = SimpleNamespace(
        api_key="",
        Customer=SimpleNamespace(list=Mock(return_value={"data": [{"id": "cus_old"}]})),
        Subscription=SimpleNamespace(list=Mock(return_value={"data": [{"id": "sub_old"}]})),
    )
    with patch.dict(sys.modules, {"stripe": fake}):
        assert not stripe_billing.trial_eligible(cfg, email="a@b.co", profile={})
    fresh = SimpleNamespace(
        api_key="",
        Customer=SimpleNamespace(list=Mock(return_value={"data": []})),
        Subscription=SimpleNamespace(list=Mock()),
    )
    with patch.dict(sys.modules, {"stripe": fresh}):
        assert stripe_billing.trial_eligible(cfg, email="a@b.co", profile={})
    boom = SimpleNamespace(api_key="", Customer=SimpleNamespace(list=Mock(side_effect=RuntimeError("x"))))
    with patch.dict(sys.modules, {"stripe": boom}):
        assert not stripe_billing.trial_eligible(cfg, email="a@b.co", profile={})


def _sub_event(etype, status, *, trial_end=FUTURE, previous=None, **extra):
    obj = {
        "id": "sub_1",
        "customer": "cus_1",
        "status": status,
        "trial_end": trial_end,
        "metadata": {"supabase_user_id": "u1"},
        "items": {"data": [{"price": {"id": "price_m"}}]},
        **extra,
    }
    data = {"object": obj}
    if previous is not None:
        data["previous_attributes"] = {"status": previous}
    return {"id": f"evt_{etype}_{status}", "type": etype, "created": NOW, "data": data}


def test_checkout_completed_with_trial_grants_pro_and_tags_started():
    event = {
        "id": "evt_c",
        "type": "checkout.session.completed",
        "created": NOW,
        "data": {
            "object": {
                "id": "cs_1",
                "status": "complete",
                "payment_status": "no_payment_required",
                "customer": "cus_1",
                "subscription": "sub_1",
                "client_reference_id": "u1",
            }
        },
    }
    action = stripe_billing.map_stripe_event_to_entitlement(event, config=_config())
    assert action["entitlement"] == "premium"
    assert action["trial_transition"] == "started"


def test_trialing_grants_with_trial_end_then_active_converts():
    created = stripe_billing.map_stripe_event_to_entitlement(_sub_event("customer.subscription.created", "trialing"))
    assert created["entitlement"] == "premium"
    assert created["trial_transition"] == "started"
    assert created["stripe_trial_end"].startswith(datetime.fromtimestamp(FUTURE, tz=timezone.utc).isoformat()[:19])
    converted = stripe_billing.map_stripe_event_to_entitlement(
        _sub_event("customer.subscription.updated", "active", previous="trialing")
    )
    assert converted["entitlement"] == "premium"
    assert converted["trial_transition"] == "converted"
    assert converted["stripe_trial_end"] == ""


def test_trialing_to_canceled_and_unpaid_revoke():
    for status in ("canceled", "unpaid", "past_due"):
        action = stripe_billing.map_stripe_event_to_entitlement(
            _sub_event("customer.subscription.updated", status, previous="trialing")
        )
        assert action["entitlement"] == "free", status
        assert action["trial_transition"] == "canceled"
    deleted = stripe_billing.map_stripe_event_to_entitlement(
        _sub_event("customer.subscription.deleted", "canceled", trial_end=PAST + 10, ended_at=PAST + 20)
    )
    assert deleted["entitlement"] == "free"
    assert deleted["trial_transition"] == "canceled"


def test_trial_end_without_payment_never_grants():
    stale = stripe_billing.map_stripe_event_to_entitlement(
        _sub_event("customer.subscription.updated", "trialing", trial_end=PAST)
    )
    assert stale["entitlement"] == "free"
    assert stale["stripe_trial_end"] == ""
    failed = stripe_billing.map_stripe_event_to_entitlement(
        {
            "id": "evt_f",
            "type": "invoice.payment_failed",
            "created": NOW,
            "data": {"object": {"customer": "cus_1", "subscription": "sub_1", "status": "open"}},
        }
    )
    assert failed["entitlement"] == "free"


def test_profile_payload_sets_and_clears_trial_end():
    trial = stripe_billing.map_stripe_event_to_entitlement(_sub_event("customer.subscription.created", "trialing"))
    assert stripe_webhook.build_profile_entitlement_payload(trial)["trial_ends_at"]
    active = stripe_billing.map_stripe_event_to_entitlement(
        _sub_event("customer.subscription.updated", "active", previous="trialing")
    )
    payload = stripe_webhook.build_profile_entitlement_payload(active)
    assert "trial_ends_at" in payload and payload["trial_ends_at"] is None
    checkout = stripe_billing.map_stripe_event_to_entitlement(
        {
            "id": "e",
            "type": "checkout.session.completed",
            "created": NOW,
            "data": {"object": {"status": "complete", "customer": "c", "client_reference_id": "u1"}},
        }
    )
    assert "trial_ends_at" not in stripe_webhook.build_profile_entitlement_payload(checkout)


def test_patch_retries_without_trial_column_when_migration_missing():
    calls = []

    def patch_fn(url, **kw):
        calls.append(kw["json"])
        if "trial_ends_at" in kw["json"]:
            return SimpleNamespace(
                status_code=400, json=lambda: {"message": "column trial_ends_at does not exist"}, text=""
            )
        return SimpleNamespace(status_code=204, json=lambda: {}, text="")

    action = stripe_billing.map_stripe_event_to_entitlement(_sub_event("customer.subscription.created", "trialing"))
    ok, err = stripe_webhook.update_profile_entitlement(
        config=stripe_webhook.SupabaseWebhookConfig(url="https://x.supabase.co", service_role_key="k"),
        action=action,
        request_session=SimpleNamespace(patch=patch_fn),
    )
    assert ok and not err
    assert len(calls) == 2 and "trial_ends_at" not in calls[1] and calls[1]["entitlement"] == "premium"


def test_stripe_trial_lifecycle_analytics(monkeypatch):
    seen = []
    from modules import launch_analytics

    monkeypatch.setattr(launch_analytics, "track_event", lambda name, **kw: seen.append((name, kw["props"])) or True)
    stripe_webhook._track_subscription_lifecycle(
        {
            "user_id": "u1",
            "entitlement": "premium",
            "reason": "customer.subscription.updated",
            "stripe_subscription_status": "active",
            "trial_transition": "converted",
            "event_id": "e1",
            "stripe_subscription_id": "sub_1",
        },
        stripe_config=_config(),
    )
    assert [n for n, _ in seen] == ["feature_use"]
    assert seen[0][1]["feature"] == "trial" and seen[0][1]["action"] == "converted"


def _rc_event(etype, period, **extra):
    return {
        "id": f"rc_{etype}",
        "type": etype,
        "app_user_id": "u1",
        "environment": "SANDBOX",
        "period_type": period,
        "store": "APP_STORE",
        "expiration_at_ms": FUTURE * 1000,
        "event_timestamp_ms": NOW * 1000,
        **extra,
    }


def _rc_map(event, active_keys):
    cfg = revenuecat_billing.RevenueCatBillingConfig(secret_key="sk", project_id="p")
    with patch.object(revenuecat_billing, "fetch_active_entitlement_lookup_keys", return_value=active_keys):
        return revenuecat_billing.map_revenuecat_event(event, config=cfg)


def test_revenuecat_trial_started_active_with_expiry():
    action = _rc_map(_rc_event("INITIAL_PURCHASE", "TRIAL"), {"premium"})
    assert action["entitlement"] == "premium"
    assert action["trial_transition"] == "started"
    assert action["trial_ends_at"].startswith(datetime.fromtimestamp(FUTURE, tz=timezone.utc).isoformat()[:19])
    assert action["platform"] == "ios"
    payload = revenuecat_webhook.build_profile_entitlement_payload(action)
    assert payload["trial_ends_at"] == action["trial_ends_at"]


def test_revenuecat_conversion_clears_trial_and_expiry_revokes():
    converted = _rc_map(_rc_event("RENEWAL", "NORMAL", is_trial_conversion=True), {"premium"})
    assert converted["entitlement"] == "premium"
    assert converted["trial_transition"] == "converted"
    assert revenuecat_webhook.build_profile_entitlement_payload(converted)["trial_ends_at"] is None
    expired = _rc_map(_rc_event("EXPIRATION", "TRIAL"), set())
    assert expired["entitlement"] == "free"
    assert expired["trial_transition"] == "canceled"
    cancelled = _rc_map(_rc_event("CANCELLATION", "TRIAL"), {"premium"})
    assert cancelled["entitlement"] == "premium"  # still in trial until it expires
    assert cancelled["trial_transition"] == "canceled"


def test_revenuecat_non_trial_events_untouched():
    action = _rc_map(
        {"id": "x", "type": "INITIAL_PURCHASE", "app_user_id": "u1", "environment": "SANDBOX"}, {"premium"}
    )
    assert "trial_transition" not in action
    assert "trial_ends_at" not in revenuecat_webhook.build_profile_entitlement_payload(action)
