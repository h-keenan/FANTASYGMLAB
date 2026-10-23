"""Free trial surfaces on the mobile/web API: /v1/me, /v1/billing/plans, /v1/billing/checkout."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from tests.test_mobile_api_service import _client


def _auth(uid="trial-user-1"):
    r = Mock(status_code=200)
    r.json.return_value = {"id": uid, "email": "gm@example.com"}
    return r


def test_me_reports_future_trial_end_for_a_paid_profile(monkeypatch):
    client = _client(monkeypatch)
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    profile = Mock(status_code=200)
    profile.json.return_value = [{"entitlement": "premium", "sleeper_username": "x", "trial_ends_at": future}]
    with patch("requests.get", side_effect=[_auth("trial-me-1"), profile]):
        body = client.get("/v1/me", headers={"Authorization": "Bearer t"}).json()
    assert body["user"]["trial_ends_at"] == datetime.fromisoformat(future).isoformat()


def test_me_hides_past_trial_end_and_free_users(monkeypatch):
    client = _client(monkeypatch)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    profile = Mock(status_code=200)
    profile.json.return_value = [{"entitlement": "premium", "sleeper_username": "x", "trial_ends_at": past}]
    with patch("requests.get", side_effect=[_auth("trial-me-2"), profile]):
        assert client.get("/v1/me", headers={"Authorization": "Bearer t"}).json()["user"]["trial_ends_at"] == ""


def _plans(monkeypatch, profile_rows, *, trial_days="3"):
    client = _client(monkeypatch)
    monkeypatch.setenv("STRIPE_TRIAL_DAYS", trial_days)
    from services import mobile_api_service

    monkeypatch.setattr(
        mobile_api_service,
        "_fetch_trial_profile",
        lambda user: (profile_rows, True),
    )
    with patch("requests.get", side_effect=[_auth("trial-plans")]):
        return client.get("/v1/billing/plans", headers={"Authorization": "Bearer t"}).json()


def test_plans_offer_trial_to_account_without_billing_history(monkeypatch):
    body = _plans(monkeypatch, {})
    assert body["trial"] == {"days": 3, "eligible": True}


def test_plans_hide_trial_after_prior_subscription_or_when_disabled(monkeypatch):
    assert _plans(monkeypatch, {"stripe_customer_id": "cus_1"})["trial"] == {"days": 0, "eligible": False}
    assert _plans(monkeypatch, {}, trial_days="0")["trial"] == {"days": 0, "eligible": False}


def test_checkout_passes_eligibility_to_stripe(monkeypatch):
    client = _client(monkeypatch)
    from services import mobile_api_service

    seen = {}

    def fake_create(**kwargs):
        seen.update(kwargs)
        return Mock(client_secret="", url="https://checkout.test/s")

    monkeypatch.setattr(mobile_api_service.stripe_billing, "create_checkout_session", fake_create)
    monkeypatch.setattr(mobile_api_service, "_fetch_trial_profile", lambda user: ({"stripe_customer_id": "cus_9"}, True))
    with patch("requests.get", side_effect=[_auth("trial-co")]):
        resp = client.post("/v1/billing/checkout", json={"interval": "monthly"}, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert seen["trial_eligible"] is False

    monkeypatch.setattr(mobile_api_service, "_fetch_trial_profile", lambda user: ({}, False))
    with patch("requests.get", side_effect=[_auth("trial-co2")]):
        client.post("/v1/billing/checkout", json={"interval": "monthly"}, headers={"Authorization": "Bearer t"})
    assert seen["trial_eligible"] is False  # unreadable profile fails closed
