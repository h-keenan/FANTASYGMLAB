import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from modules import premium
from modules import premium_benefits
from modules import stripe_billing
from modules import stripe_webhook
from services import stripe_webhook_service


class _DurableSupabaseStub:
    """Minimal stateful model of the PostgREST conditional PATCH contract."""

    def __init__(self):
        self.created = None
        self.event_id = ""
        self.entitlement = premium.FREE
        self.effective_mutations = 0

    def patch(self, _url, **kwargs):
        payload = kwargs["json"]
        incoming_created = datetime.fromisoformat(payload["stripe_event_created_at"])
        incoming_id = payload["stripe_event_id"]
        predicate = kwargs["params"]["or"]
        applies = self.created is None or self.created < incoming_created
        if self.created == incoming_created and payload["entitlement"] == premium.FREE:
            applies = (
                incoming_id != self.event_id
                and f"stripe_event_id.neq.{incoming_id}" in predicate
            )
        if incoming_id == self.event_id:
            applies = False
        if applies:
            self.created = incoming_created
            self.event_id = incoming_id
            self.entitlement = payload["entitlement"]
            self.effective_mutations += 1
        return SimpleNamespace(status_code=204)


class TestStripeBilling(unittest.TestCase):
    def test_missing_config_degrades_gracefully(self):
        config = stripe_billing.load_stripe_config(environ={}, secrets={})

        self.assertFalse(config.configured)
        self.assertFalse(stripe_billing.stripe_configured(environ={}, secrets={}))
        self.assertFalse(config.redacted["configured"])
        self.assertNotIn("secret", str(config.redacted).casefold())

    def test_test_mode_config_loads_from_env_without_exposing_values(self):
        config = stripe_billing.load_stripe_config(
            environ={
                "STRIPE_SECRET_KEY": "sk_test_123",
                "STRIPE_WEBHOOK_SECRET": "whsec_123",
                "STRIPE_PRICE_MONTHLY": "price_month",
                "STRIPE_PRICE_ANNUAL": "price_year",
            },
            secrets={},
        )

        self.assertTrue(config.configured)
        self.assertTrue(config.webhook_configured)
        self.assertEqual(config.redacted["mode"], "test")
        self.assertNotIn("sk_test_123", str(config.redacted))

    def test_live_secret_key_is_not_considered_configured(self):
        config = stripe_billing.load_stripe_config(
            environ={
                "STRIPE_SECRET_KEY": "sk_live_not_allowed",
                "STRIPE_PRICE_MONTHLY": "price_month",
                "STRIPE_PRICE_ANNUAL": "price_year",
            },
            secrets={},
        )

        self.assertFalse(config.configured)

    def test_live_mode_requires_explicit_mode_and_matching_secret(self):
        config = stripe_billing.load_stripe_config(
            environ={
                "STRIPE_BILLING_MODE": "live",
                "STRIPE_SECRET_KEY": "sk_live_123",
                "STRIPE_WEBHOOK_SECRET": "whsec_123",
                "STRIPE_PRICE_MONTHLY": "price_month",
                "STRIPE_PRICE_ANNUAL": "price_year",
            },
            secrets={},
        )

        self.assertTrue(config.configured)
        self.assertTrue(config.secret_mode_configured)
        self.assertEqual(config.redacted["mode"], "live")
        self.assertEqual(stripe_billing.stripe_live_billing_status(environ={
            "STRIPE_BILLING_MODE": "live",
            "STRIPE_SECRET_KEY": "sk_live_123",
            "STRIPE_PRICE_MONTHLY": "price_month",
            "STRIPE_PRICE_ANNUAL": "price_year",
        }, secrets={}), "ON")

    def test_checkout_requires_logged_in_user(self):
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_123",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.create_checkout_session(
                config=config,
                user_id="",
                email="user@example.com",
                interval=stripe_billing.MONTHLY,
            )

    def test_checkout_session_uses_interval_price_and_supabase_metadata(self):
        created = Mock(return_value=SimpleNamespace(url="https://checkout.test/session"))
        fake_stripe = SimpleNamespace(
            api_key="",
            checkout=SimpleNamespace(Session=SimpleNamespace(create=created)),
        )
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_123",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            session = stripe_billing.create_checkout_session(
                config=config,
                user_id="user-1",
                email="user@example.com",
                interval=stripe_billing.ANNUAL,
            )

        self.assertEqual(session.url, "https://checkout.test/session")
        kwargs = created.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price"], "price_year")
        self.assertEqual(kwargs["metadata"]["supabase_user_id"], "user-1")
        self.assertEqual(kwargs["metadata"]["billing_interval"], stripe_billing.ANNUAL)
        self.assertEqual(kwargs["metadata"]["plan_interval"], stripe_billing.ANNUAL)
        self.assertNotIn("entitlement", kwargs["metadata"])
        self.assertEqual(kwargs["subscription_data"]["metadata"]["supabase_user_id"], "user-1")
        self.assertEqual(kwargs["client_reference_id"], "user-1")
        self.assertTrue(str(kwargs["idempotency_key"]).startswith("fgl-checkout-user-1-annual"))
        self.assertTrue(kwargs["allow_promotion_codes"])

    def _session_kwargs(self, **extra):
        created = Mock(return_value=SimpleNamespace(client_secret="cs", url=None))
        fake_stripe = SimpleNamespace(api_key="", checkout=SimpleNamespace(Session=SimpleNamespace(create=created)))
        config = stripe_billing.StripeBillingConfig(secret_key="sk_test_123", price_monthly="p_m", price_annual="p_y")
        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            stripe_billing.create_checkout_session(
                config=config, user_id="user-1", interval=stripe_billing.ANNUAL, ui_mode="embedded", **extra
            )
        return created.call_args.kwargs

    def test_checkout_prefills_customer_email_when_no_customer(self):
        kwargs = self._session_kwargs(email="user@example.com")
        self.assertEqual(kwargs["customer_email"], "user@example.com")
        self.assertNotIn("customer", kwargs)

    def test_checkout_uses_customer_never_both(self):
        kwargs = self._session_kwargs(email="user@example.com", customer_id="cus_1")
        self.assertEqual(kwargs["customer"], "cus_1")
        self.assertNotIn("customer_email", kwargs)

    def test_checkout_without_email_or_customer_sends_neither(self):
        kwargs = self._session_kwargs(email="")
        self.assertNotIn("customer", kwargs)
        self.assertNotIn("customer_email", kwargs)

    def test_checkout_idempotency_key_changes_with_email(self):
        a = self._session_kwargs(email="a@example.com")["idempotency_key"]
        b = self._session_kwargs(email="b@example.com")["idempotency_key"]
        self.assertNotEqual(a, b)

    # Zach, 2026-10-19: "We need to try to embed stripe so theres not a
    # million redirectes"
    def test_checkout_session_embedded_mode_uses_return_url_not_success_cancel(self):
        created = Mock(return_value=SimpleNamespace(client_secret="cs_test_embedded", url=None))
        fake_stripe = SimpleNamespace(
            api_key="",
            checkout=SimpleNamespace(Session=SimpleNamespace(create=created)),
        )
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_123",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            session = stripe_billing.create_checkout_session(
                config=config,
                user_id="user-1",
                email="user@example.com",
                interval=stripe_billing.MONTHLY,
                ui_mode="embedded",
                return_url="https://app.test/premium?billing=success",
            )

        self.assertEqual(session.client_secret, "cs_test_embedded")
        kwargs = created.call_args.kwargs
        self.assertEqual(kwargs["ui_mode"], "embedded")
        self.assertEqual(kwargs["return_url"], "https://app.test/premium?billing=success")
        self.assertNotIn("success_url", kwargs)
        self.assertNotIn("cancel_url", kwargs)
        # Promo codes, metadata, idempotency, trial -- everything else about
        # the session stays identical to the hosted-mode path.
        self.assertTrue(kwargs["allow_promotion_codes"])
        self.assertEqual(kwargs["metadata"]["supabase_user_id"], "user-1")

    def test_checkout_session_hosted_mode_never_sends_ui_mode_or_return_url(self):
        created = Mock(return_value=SimpleNamespace(url="https://checkout.test/session"))
        fake_stripe = SimpleNamespace(
            api_key="",
            checkout=SimpleNamespace(Session=SimpleNamespace(create=created)),
        )
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_123",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            stripe_billing.create_checkout_session(
                config=config,
                user_id="user-1",
                email="user@example.com",
                interval=stripe_billing.MONTHLY,
            )

        kwargs = created.call_args.kwargs
        self.assertNotIn("ui_mode", kwargs)
        self.assertNotIn("return_url", kwargs)
        self.assertIn("success_url", kwargs)
        self.assertIn("cancel_url", kwargs)

    def test_fetch_live_plan_details_returns_none_when_not_configured(self):
        stripe_billing.reset_price_display_cache_for_tests()
        config = stripe_billing.StripeBillingConfig()

        self.assertIsNone(stripe_billing.fetch_live_plan_details(config))
        self.assertEqual(
            stripe_billing.plan_display_details(config),
            stripe_billing.DEFAULT_PLAN_DETAILS,
        )

    def test_fetch_live_plan_details_reads_real_price_objects(self):
        stripe_billing.reset_price_display_cache_for_tests()
        retrieve = Mock(
            side_effect=lambda price_id: {
                "price_month": SimpleNamespace(
                    unit_amount=499, currency="usd", recurring=SimpleNamespace(interval="month")
                ),
                "price_year": SimpleNamespace(
                    unit_amount=2499, currency="usd", recurring=SimpleNamespace(interval="year")
                ),
            }[price_id]
        )
        fake_stripe = SimpleNamespace(api_key="", Price=SimpleNamespace(retrieve=retrieve))
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_live_fetch",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            details = stripe_billing.fetch_live_plan_details(config)

        self.assertEqual(details[stripe_billing.MONTHLY], ("Monthly", "$4.99", "per month"))
        self.assertEqual(details[stripe_billing.ANNUAL], ("Annual", "$24.99", "per year"))
        self.assertEqual(retrieve.call_count, 2)

    def test_fetch_live_plan_details_includes_front_office_when_configured(self):
        stripe_billing.reset_price_display_cache_for_tests()
        retrieve = Mock(
            side_effect=lambda price_id: {
                "price_month": SimpleNamespace(
                    unit_amount=499, currency="usd", recurring=SimpleNamespace(interval="month")
                ),
                "price_year": SimpleNamespace(
                    unit_amount=2499, currency="usd", recurring=SimpleNamespace(interval="year")
                ),
                "price_fo_year": SimpleNamespace(
                    unit_amount=9999, currency="usd", recurring=SimpleNamespace(interval="year")
                ),
            }[price_id]
        )
        fake_stripe = SimpleNamespace(api_key="", Price=SimpleNamespace(retrieve=retrieve))
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_fo_fetch",
            price_monthly="price_month",
            price_annual="price_year",
            price_front_office_annual="price_fo_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            details = stripe_billing.fetch_live_plan_details(config)

        self.assertEqual(
            details[stripe_billing.FRONT_OFFICE_ANNUAL], ("Annual", "$99.99", "per year")
        )
        self.assertEqual(retrieve.call_count, 3)

    def test_fetch_live_plan_details_omits_front_office_when_not_configured(self):
        stripe_billing.reset_price_display_cache_for_tests()
        retrieve = Mock(
            return_value=SimpleNamespace(
                unit_amount=499, currency="usd", recurring=SimpleNamespace(interval="month")
            )
        )
        fake_stripe = SimpleNamespace(api_key="", Price=SimpleNamespace(retrieve=retrieve))
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_no_fo",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            details = stripe_billing.fetch_live_plan_details(config)

        self.assertNotIn(stripe_billing.FRONT_OFFICE_ANNUAL, details)

    def test_fetch_live_plan_details_caches_within_ttl(self):
        stripe_billing.reset_price_display_cache_for_tests()
        retrieve = Mock(
            return_value=SimpleNamespace(
                unit_amount=499, currency="usd", recurring=SimpleNamespace(interval="month")
            )
        )
        fake_stripe = SimpleNamespace(api_key="", Price=SimpleNamespace(retrieve=retrieve))
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_cache",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            first = stripe_billing.fetch_live_plan_details(config, now=1_000.0)
            second = stripe_billing.fetch_live_plan_details(config, now=1_000.0 + 60)

        self.assertEqual(first, second)
        # One call per price on the first fetch only — the second fetch, well
        # inside the TTL, must be served from cache rather than hitting Stripe
        # again on every page render.
        self.assertEqual(retrieve.call_count, 2)

    def test_fetch_live_plan_details_refetches_after_ttl_expires(self):
        stripe_billing.reset_price_display_cache_for_tests()
        retrieve = Mock(
            return_value=SimpleNamespace(
                unit_amount=499, currency="usd", recurring=SimpleNamespace(interval="month")
            )
        )
        fake_stripe = SimpleNamespace(api_key="", Price=SimpleNamespace(retrieve=retrieve))
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_ttl",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            stripe_billing.fetch_live_plan_details(config, now=1_000.0)
            stripe_billing.fetch_live_plan_details(config, now=1_000.0 + 10 * 60)

        self.assertEqual(retrieve.call_count, 4)

    def test_plan_display_details_falls_back_when_stripe_api_call_fails(self):
        stripe_billing.reset_price_display_cache_for_tests()
        fake_stripe = SimpleNamespace(
            api_key="",
            Price=SimpleNamespace(retrieve=Mock(side_effect=RuntimeError("network unreachable"))),
        )
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_failure",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            details = stripe_billing.plan_display_details(config)

        self.assertEqual(details, stripe_billing.DEFAULT_PLAN_DETAILS)

    def test_plan_display_details_falls_back_when_stripe_package_missing(self):
        stripe_billing.reset_price_display_cache_for_tests()
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_missing_pkg",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": None}):
            details = stripe_billing.plan_display_details(config)

        self.assertEqual(details, stripe_billing.DEFAULT_PLAN_DETAILS)

    def test_live_checkout_requires_explicit_live_mode_and_keeps_server_identity(self):
        created = Mock(return_value=SimpleNamespace(url="https://checkout.stripe.com/session"))
        fake_stripe = SimpleNamespace(
            api_key="",
            checkout=SimpleNamespace(Session=SimpleNamespace(create=created)),
        )
        config = stripe_billing.StripeBillingConfig(
            billing_mode="live",
            secret_key="sk_live_123",
            price_monthly="price_live_month",
            price_annual="price_live_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            stripe_billing.create_checkout_session(
                config=config,
                user_id="authenticated-user",
                email="user@example.com",
                interval=stripe_billing.MONTHLY,
            )

        kwargs = created.call_args.kwargs
        self.assertEqual(kwargs["line_items"], [{"price": "price_live_month", "quantity": 1}])
        self.assertEqual(kwargs["client_reference_id"], "authenticated-user")
        self.assertEqual(kwargs["metadata"]["supabase_user_id"], "authenticated-user")
        self.assertNotIn("entitlement", kwargs["metadata"])

    def test_customer_portal_requires_stripe_customer_id(self):
        config = stripe_billing.StripeBillingConfig(secret_key="sk_test_123")

        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.create_customer_portal_session(config=config, stripe_customer_id="")

    def test_webhook_maps_active_subscription_to_premium(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "customer": "cus_123",
                        "status": "active",
                        "metadata": {"supabase_user_id": "user-1"},
                    }
                },
            }
        )

        self.assertEqual(action["user_id"], "user-1")
        self.assertEqual(action["entitlement"], stripe_billing.RAW_PRO)
        self.assertEqual(action["stripe_customer_id"], "cus_123")

    def test_webhook_maps_canceled_subscription_to_free(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "customer": "cus_123",
                        "status": "canceled",
                        "metadata": {"supabase_user_id": "user-1"},
                    }
                },
            }
        )

        self.assertEqual(action["entitlement"], premium.FREE)

    def test_invalid_webhook_signature_is_rejected(self):
        class FakeWebhook:
            @staticmethod
            def construct_event(*_args, **_kwargs):
                raise ValueError("bad signature")

        fake_stripe = SimpleNamespace(Webhook=FakeWebhook)
        config = stripe_billing.StripeBillingConfig(webhook_secret="whsec_123")

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            with self.assertRaises(stripe_billing.BillingConfigurationError):
                stripe_billing.construct_stripe_event("{}", "sig", config=config)

    def test_missing_webhook_secret_is_rejected(self):
        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.construct_stripe_event("{}", "sig", config=stripe_billing.StripeBillingConfig())

    def test_live_mode_webhook_event_is_rejected(self):
        class FakeWebhook:
            @staticmethod
            def construct_event(*_args, **_kwargs):
                return {"id": "evt_live", "livemode": True, "type": "customer.subscription.updated"}

        fake_stripe = SimpleNamespace(Webhook=FakeWebhook)
        config = stripe_billing.StripeBillingConfig(secret_key="sk_test_123", webhook_secret="whsec_123")

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            with self.assertRaises(stripe_billing.BillingConfigurationError):
                stripe_billing.construct_stripe_event("{}", "sig", config=config)

    def test_live_mode_webhook_event_is_accepted_only_with_explicit_live_config(self):
        class FakeWebhook:
            @staticmethod
            def construct_event(*_args, **_kwargs):
                return {"id": "evt_live", "livemode": True, "type": "customer.subscription.updated"}

        fake_stripe = SimpleNamespace(Webhook=FakeWebhook)
        config = stripe_billing.StripeBillingConfig(
            billing_mode="live",
            secret_key="sk_live_123",
            webhook_secret="whsec_123",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            event = stripe_billing.construct_stripe_event("{}", "sig", config=config)

        self.assertTrue(event["livemode"])

    def test_live_secret_key_webhook_config_is_rejected(self):
        config = stripe_billing.StripeBillingConfig(secret_key="sk_live_not_allowed", webhook_secret="whsec_123")

        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.construct_stripe_event("{}", "sig", config=config)

    def test_checkout_session_completed_reads_supabase_user_id_metadata(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_123",
                        "customer": "cus_123",
                        "status": "complete",
                        "subscription": "sub_123",
                        "metadata": {"supabase_user_id": "user-1"},
                    }
                },
            }
        )

        self.assertEqual(action["user_id"], "user-1")
        self.assertEqual(action["entitlement"], stripe_billing.RAW_PRO)
        self.assertEqual(action["stripe_subscription_id"], "sub_123")

    def test_customer_metadata_user_id_fallback_is_supported(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "status": "trialing",
                        "customer": {
                            "id": "cus_123",
                            "metadata": {"supabase_user_id": "user-from-customer"},
                        },
                    }
                },
            }
        )

        self.assertEqual(action["user_id"], "user-from-customer")
        self.assertEqual(action["entitlement"], stripe_billing.RAW_PRO)

    def test_price_id_is_extracted_from_subscription_items(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "status": "active",
                        "metadata": {"supabase_user_id": "user-1"},
                        "items": {"data": [{"price": {"id": "price_month"}}]},
                    }
                },
            }
        )

        self.assertEqual(action["stripe_price_id"], "price_month")

    def test_payment_failed_maps_to_free(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "invoice.payment_failed",
                "data": {
                    "object": {
                        "id": "in_123",
                        "status": "open",
                        "metadata": {"supabase_user_id": "user-1"},
                    }
                },
            }
        )

        self.assertEqual(action["entitlement"], premium.FREE)

    def test_past_due_subscription_update_does_not_auto_downgrade(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "status": "past_due",
                        "metadata": {"supabase_user_id": "user-1"},
                    }
                },
            }
        )

        self.assertEqual(action["entitlement"], "")

    def test_invoice_payment_succeeded_with_subscription_metadata_maps_premium(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "id": "evt_123",
                "type": "invoice.payment_succeeded",
                "data": {
                    "object": {
                        "id": "in_123",
                        "paid": True,
                        "subscription_details": {"metadata": {"supabase_user_id": "user-1"}},
                        "customer": "cus_123",
                        "subscription": "sub_123",
                        "lines": {"data": [{"price": {"id": "price_month"}}]},
                    }
                },
            }
        )

        self.assertEqual(action["event_id"], "evt_123")
        self.assertEqual(action["user_id"], "user-1")
        self.assertEqual(action["entitlement"], stripe_billing.RAW_PRO)
        self.assertEqual(action["stripe_price_id"], "price_month")

    def test_supabase_update_payload_targets_entitlement_and_stripe_fields(self):
        payload = stripe_webhook.build_profile_entitlement_payload(
            {
                "entitlement": stripe_billing.RAW_PRO,
                "stripe_customer_id": "cus_123",
                "stripe_subscription_id": "sub_123",
                "stripe_subscription_status": "active",
                "stripe_price_id": "price_month",
                "event_id": "evt_123",
                "event_created": "1700000000",
            }
        )

        self.assertEqual(payload["entitlement"], stripe_billing.RAW_PRO)
        self.assertEqual(payload["stripe_customer_id"], "cus_123")
        self.assertEqual(payload["stripe_subscription_status"], "active")
        self.assertIn("premium_updated_at", payload)
        self.assertEqual(payload["stripe_event_id"], "evt_123")
        self.assertIn("stripe_event_created_at", payload)

    def test_supabase_update_helper_patches_correct_profile_row(self):
        response = SimpleNamespace(status_code=204)
        session = SimpleNamespace(patch=Mock(return_value=response))
        config = stripe_webhook.SupabaseWebhookConfig(
            url="https://example.supabase.co",
            service_role_key="service-key",
        )

        ok, error = stripe_webhook.update_profile_entitlement(
            config=config,
            request_session=session,
            action={
                "user_id": "user-1",
                "entitlement": stripe_billing.RAW_PRO,
                "stripe_customer_id": "cus_123",
            },
        )

        self.assertTrue(ok)
        self.assertFalse(error)
        call = session.patch.call_args
        self.assertIn("/rest/v1/profiles?user_id=eq.user-1", call.args[0])
        self.assertEqual(call.kwargs["json"]["entitlement"], stripe_billing.RAW_PRO)
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer service-key")

    def test_supabase_update_orders_verified_events_durably(self):
        response = SimpleNamespace(status_code=204)
        session = SimpleNamespace(patch=Mock(return_value=response))
        config = stripe_webhook.SupabaseWebhookConfig(
            url="https://example.supabase.co",
            service_role_key="service-key",
        )

        ok, error = stripe_webhook.update_profile_entitlement(
            config=config,
            request_session=session,
            action={
                "user_id": "user-1",
                "entitlement": premium.FREE,
                "event_id": "evt_cancel",
                "event_created": "1700000001",
            },
        )

        self.assertTrue(ok)
        self.assertFalse(error)
        ordering = session.patch.call_args.kwargs["params"]["or"]
        self.assertIn("stripe_event_created_at.is.null", ordering)
        self.assertIn("stripe_event_created_at.lt.2023-", ordering)
        self.assertGreaterEqual(ordering.count("stripe_event_id.neq.evt_cancel"), 2)

    def test_durable_ordering_handles_duplicate_older_newer_and_equal_second(self):
        config = stripe_webhook.SupabaseWebhookConfig(
            url="https://example.supabase.co",
            service_role_key="service-key",
        )

        def apply(store, *, event_id, created, entitlement):
            return stripe_webhook.update_profile_entitlement(
                config=config,
                request_session=store,
                action={
                    "user_id": "user-1",
                    "event_id": event_id,
                    "event_created": str(created),
                    "entitlement": entitlement,
                },
            )

        duplicate = _DurableSupabaseStub()
        apply(duplicate, event_id="evt_same", created=1_700_000_000, entitlement=stripe_billing.RAW_PRO)
        apply(duplicate, event_id="evt_same", created=1_700_000_000, entitlement=stripe_billing.RAW_PRO)
        self.assertEqual(duplicate.effective_mutations, 1)

        ordered = _DurableSupabaseStub()
        apply(ordered, event_id="evt_new", created=1_700_000_001, entitlement=stripe_billing.RAW_PRO)
        apply(ordered, event_id="evt_old", created=1_700_000_000, entitlement=premium.FREE)
        self.assertEqual(ordered.entitlement, stripe_billing.RAW_PRO)
        apply(ordered, event_id="evt_newer", created=1_700_000_002, entitlement=premium.FREE)
        self.assertEqual(ordered.entitlement, premium.FREE)

        grant_then_revoke = _DurableSupabaseStub()
        apply(grant_then_revoke, event_id="evt_grant", created=1_700_000_000, entitlement=stripe_billing.RAW_PRO)
        apply(grant_then_revoke, event_id="evt_revoke", created=1_700_000_000, entitlement=premium.FREE)
        self.assertEqual(grant_then_revoke.entitlement, premium.FREE)

        revoke_then_grant = _DurableSupabaseStub()
        apply(revoke_then_grant, event_id="evt_revoke", created=1_700_000_000, entitlement=premium.FREE)
        apply(revoke_then_grant, event_id="evt_grant", created=1_700_000_000, entitlement=stripe_billing.RAW_PRO)
        self.assertEqual(revoke_then_grant.entitlement, premium.FREE)

    def test_supabase_update_requires_user_id_and_supported_entitlement(self):
        config = stripe_webhook.SupabaseWebhookConfig(url="https://example.supabase.co", service_role_key="service-key")

        ok, error = stripe_webhook.update_profile_entitlement(
            config=config,
            action={"entitlement": stripe_billing.RAW_PRO},
        )
        self.assertFalse(ok)
        self.assertIn("Supabase user id", error)

        ok, error = stripe_webhook.update_profile_entitlement(
            config=config,
            action={"user_id": "user-1", "entitlement": "gold"},
        )
        self.assertFalse(ok)
        self.assertIn("supported entitlement", error)

    def test_missing_supabase_billing_columns_return_deployment_error(self):
        response = Mock(status_code=400)
        response.json.return_value = {"message": "column profiles.stripe_customer_id does not exist"}
        session = SimpleNamespace(patch=Mock(return_value=response))
        config = stripe_webhook.SupabaseWebhookConfig(url="https://example.supabase.co", service_role_key="service-key")

        ok, error = stripe_webhook.update_profile_entitlement(
            config=config,
            request_session=session,
            action={
                "user_id": "user-1",
                "entitlement": stripe_billing.RAW_PRO,
                "stripe_customer_id": "cus_123",
            },
        )

        self.assertFalse(ok)
        self.assertIn("docs/supabase_stripe_billing.sql", error)

    def test_process_verified_webhook_updates_supabase_after_signature_verification(self):
        class FakeWebhook:
            @staticmethod
            def construct_event(*_args, **_kwargs):
                return {
                    "livemode": False,
                    "type": "customer.subscription.updated",
                    "data": {
                        "object": {
                            "id": "sub_123",
                            "customer": "cus_123",
                            "status": "active",
                            "metadata": {"supabase_user_id": "user-1"},
                        }
                    },
                }

        fake_stripe = SimpleNamespace(Webhook=FakeWebhook)
        response = SimpleNamespace(status_code=204)
        session = SimpleNamespace(patch=Mock(return_value=response))

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            result = stripe_webhook.process_verified_stripe_webhook(
                payload="{}",
                signature="sig",
                stripe_config=stripe_billing.StripeBillingConfig(
                    secret_key="sk_test_123",
                    webhook_secret="whsec_123",
                ),
                supabase_config=stripe_webhook.SupabaseWebhookConfig(
                    url="https://example.supabase.co",
                    service_role_key="service-key",
                ),
                request_session=session,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"]["entitlement"], stripe_billing.RAW_PRO)
        self.assertEqual(session.patch.call_args.kwargs["json"]["entitlement"], stripe_billing.RAW_PRO)

    def test_live_webhook_grants_only_for_a_configured_price(self):
        class FakeWebhook:
            event_price = "price_month"

            @classmethod
            def construct_event(cls, *_args, **_kwargs):
                return {
                    "id": f"evt_live_{cls.event_price}",
                    "livemode": True,
                    "type": "customer.subscription.updated",
                    "data": {"object": {
                        "id": "sub_123",
                        "status": "active",
                        "metadata": {"supabase_user_id": "user-1"},
                        "items": {"data": [{"price": {"id": cls.event_price}}]},
                    }},
                }

        fake_stripe = SimpleNamespace(Webhook=FakeWebhook)
        response = SimpleNamespace(status_code=204)
        session = SimpleNamespace(patch=Mock(return_value=response))
        config = stripe_billing.StripeBillingConfig(
            billing_mode="live",
            secret_key="sk_live_123",
            webhook_secret="whsec_123",
            price_monthly="price_month",
            price_annual="price_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            accepted = stripe_webhook.process_verified_stripe_webhook(
                payload="{}",
                signature="sig",
                stripe_config=config,
                supabase_config=stripe_webhook.SupabaseWebhookConfig(
                    url="https://example.supabase.co", service_role_key="service-key"
                ),
                request_session=session,
            )
            FakeWebhook.event_price = "price_unrelated"
            rejected = stripe_webhook.process_verified_stripe_webhook(
                payload="{}",
                signature="sig",
                stripe_config=config,
                supabase_config=stripe_webhook.SupabaseWebhookConfig(
                    url="https://example.supabase.co", service_role_key="service-key"
                ),
                request_session=session,
            )

        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["action"]["entitlement"], stripe_billing.RAW_PRO)
        self.assertTrue(rejected["skipped"])
        self.assertEqual(rejected["action"]["entitlement"], "")
        self.assertEqual(session.patch.call_count, 1)

    def test_verified_webhook_duplicate_event_is_idempotent_patch(self):
        action = {
            "event_id": "evt_repeat",
            "user_id": "user-1",
            "entitlement": stripe_billing.RAW_PRO,
            "stripe_customer_id": "cus_123",
            "stripe_subscription_id": "sub_123",
            "stripe_subscription_status": "active",
        }
        response = SimpleNamespace(status_code=204)
        session = SimpleNamespace(patch=Mock(return_value=response))
        config = stripe_webhook.SupabaseWebhookConfig(url="https://example.supabase.co", service_role_key="service-key")

        first = stripe_webhook.update_profile_entitlement(config=config, action=action, request_session=session)
        second = stripe_webhook.update_profile_entitlement(config=config, action=action, request_session=session)

        self.assertEqual(first, (True, ""))
        self.assertEqual(second, (True, ""))
        self.assertEqual(session.patch.call_count, 2)


    def test_webhook_health_endpoint(self):
        self.assertEqual(stripe_webhook_service.health(), {"status": "ok"})

    def test_webhook_endpoint_rejects_missing_signature(self):
        import asyncio

        request = SimpleNamespace(body=AsyncMock(return_value=b"{}"))

        with self.assertRaises(Exception) as ctx:
            asyncio.run(stripe_webhook_service.stripe_webhook_endpoint(request, stripe_signature=None))

        self.assertIn("Missing Stripe signature", str(ctx.exception))

    def test_webhook_endpoint_processes_verified_event(self):
        import asyncio

        request = SimpleNamespace(body=AsyncMock(return_value=b"{}"))
        with (
            patch.object(stripe_webhook_service.stripe_billing, "load_stripe_config", return_value=stripe_billing.StripeBillingConfig(secret_key="sk_test_123", webhook_secret="whsec_123")),
            patch.object(stripe_webhook_service.stripe_webhook, "load_supabase_webhook_config", return_value=stripe_webhook.SupabaseWebhookConfig(url="https://example.supabase.co", service_role_key="service-key")),
            patch.object(
                stripe_webhook_service.stripe_webhook,
                "process_verified_stripe_webhook",
                return_value={
                    "ok": True,
                    "event_id": "evt_123",
                    "action": {
                        "entitlement": stripe_billing.RAW_PRO,
                        "stripe_subscription_status": "active",
                    },
                },
            ) as process,
        ):
            response = asyncio.run(stripe_webhook_service.stripe_webhook_endpoint(request, stripe_signature="sig"))

        process.assert_called_once()
        self.assertEqual(response.body.decode("utf-8").count("premium"), 1)

    def test_render_services_keep_service_role_backend_only(self):
        render_yaml = Path("render.yaml").read_text(encoding="utf-8")

        self.assertIn("fantasygm-lab-stripe-webhook", render_yaml)
        web_block, backend_block = render_yaml.split("  - type: web", 2)[1:]
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", web_block)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", backend_block)
        self.assertIn("uvicorn services.stripe_webhook_service:app", backend_block)


class TestThreeTierBilling(unittest.TestCase):
    """GM Pro / Front Office price resolution, Launch Week promo, trials."""

    def test_launch_week_window_is_oct_12_through_18_ct(self):
        before = datetime(2026, 10, 11, 23, 59, 59, tzinfo=timezone.utc)  # 6:59pm CT Oct 11
        start = datetime(2026, 10, 12, 5, 0, 0, tzinfo=timezone.utc)  # midnight CT Oct 12
        end = datetime(2026, 10, 19, 4, 59, 59, tzinfo=timezone.utc)  # 11:59:59pm CT Oct 18
        after = datetime(2026, 10, 19, 5, 0, 1, tzinfo=timezone.utc)  # just past midnight CT Oct 19

        self.assertFalse(stripe_billing.launch_week_active(now=before))
        self.assertTrue(stripe_billing.launch_week_active(now=start))
        self.assertTrue(stripe_billing.launch_week_active(now=end))
        self.assertFalse(stripe_billing.launch_week_active(now=after))

    def test_price_id_for_plan_resolves_pro_monthly_and_annual(self):
        config = stripe_billing.StripeBillingConfig(
            price_monthly="price_pro_month",
            price_annual="price_pro_year",
        )

        self.assertEqual(
            stripe_billing.price_id_for_plan(config, "pro", stripe_billing.MONTHLY),
            "price_pro_month",
        )
        self.assertEqual(
            stripe_billing.price_id_for_plan(config, "pro", stripe_billing.ANNUAL),
            "price_pro_year",
        )

    def test_price_id_for_plan_uses_launch_week_price_only_during_window(self):
        config = stripe_billing.StripeBillingConfig(
            price_monthly="price_pro_month",
            price_annual="price_pro_year",
            price_pro_annual_launch_week="price_launch_week_promo",
        )
        during = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        outside = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)

        self.assertEqual(
            stripe_billing.price_id_for_plan(config, "pro", stripe_billing.ANNUAL, now=during),
            "price_launch_week_promo",
        )
        self.assertEqual(
            stripe_billing.price_id_for_plan(config, "pro", stripe_billing.ANNUAL, now=outside),
            "price_pro_year",
        )

    def test_price_id_for_plan_front_office_is_annual_only(self):
        config = stripe_billing.StripeBillingConfig(price_front_office_annual="price_fo_year")

        self.assertEqual(
            stripe_billing.price_id_for_plan(config, "front_office", stripe_billing.ANNUAL),
            "price_fo_year",
        )
        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.price_id_for_plan(config, "front_office", stripe_billing.MONTHLY)

    def test_price_id_for_plan_fails_closed_when_price_missing(self):
        empty_config = stripe_billing.StripeBillingConfig()

        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.price_id_for_plan(empty_config, "pro", stripe_billing.MONTHLY)
        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.price_id_for_plan(empty_config, "front_office", stripe_billing.ANNUAL)
        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.price_id_for_plan(empty_config, "gold_tier", stripe_billing.ANNUAL)

    def test_pro_specific_env_keys_take_priority_over_legacy_keys(self):
        config = stripe_billing.load_stripe_config(
            environ={
                "STRIPE_PRICE_MONTHLY": "legacy_month",
                "STRIPE_PRICE_ANNUAL": "legacy_year",
                "STRIPE_PRICE_PRO_MONTHLY": "pro_month",
                "STRIPE_PRICE_PRO_ANNUAL": "pro_year",
                "STRIPE_PRICE_FRONT_OFFICE_ANNUAL": "fo_year",
                "STRIPE_PRICE_PRO_ANNUAL_LAUNCH_WEEK": "launch_week_year",
            },
            secrets={},
        )

        self.assertEqual(config.price_monthly, "pro_month")
        self.assertEqual(config.price_annual, "pro_year")
        self.assertEqual(config.price_front_office_annual, "fo_year")
        self.assertEqual(config.price_pro_annual_launch_week, "launch_week_year")

    def test_legacy_env_keys_still_work_when_pro_specific_keys_are_unset(self):
        config = stripe_billing.load_stripe_config(
            environ={
                "STRIPE_SECRET_KEY": "sk_test_123",
                "STRIPE_PRICE_MONTHLY": "legacy_month",
                "STRIPE_PRICE_ANNUAL": "legacy_year",
            },
            secrets={},
        )

        self.assertEqual(config.price_monthly, "legacy_month")
        self.assertEqual(config.price_annual, "legacy_year")
        self.assertTrue(config.configured)

    def test_checkout_session_defaults_to_pro_with_seven_day_trial_both_intervals(self):
        for interval in (stripe_billing.MONTHLY, stripe_billing.ANNUAL):
            created = Mock(return_value=SimpleNamespace(url="https://checkout.test/session"))
            fake_stripe = SimpleNamespace(
                api_key="",
                checkout=SimpleNamespace(Session=SimpleNamespace(create=created)),
            )
            config = stripe_billing.StripeBillingConfig(
                secret_key="sk_test_123",
                price_monthly="price_month",
                price_annual="price_year",
            )

            with patch.dict(sys.modules, {"stripe": fake_stripe}):
                stripe_billing.create_checkout_session(
                    config=config,
                    user_id="user-1",
                    email="user@example.com",
                    interval=interval,
                    now=datetime(2026, 11, 1, tzinfo=timezone.utc),
                )

            kwargs = created.call_args.kwargs
            self.assertEqual(
                kwargs["subscription_data"]["trial_period_days"], stripe_billing.PRO_TRIAL_DAYS
            )
            self.assertEqual(kwargs["metadata"]["billing_tier"], "pro")

    def test_checkout_session_front_office_has_no_trial_and_uses_annual_price(self):
        created = Mock(return_value=SimpleNamespace(url="https://checkout.test/session"))
        fake_stripe = SimpleNamespace(
            api_key="",
            checkout=SimpleNamespace(Session=SimpleNamespace(create=created)),
        )
        config = stripe_billing.StripeBillingConfig(
            secret_key="sk_test_123",
            price_front_office_annual="price_fo_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            stripe_billing.create_checkout_session(
                config=config,
                user_id="user-1",
                email="user@example.com",
                interval=stripe_billing.ANNUAL,
                tier="front_office",
                now=datetime(2026, 11, 1, tzinfo=timezone.utc),
            )

        kwargs = created.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price"], "price_fo_year")
        self.assertNotIn("trial_period_days", kwargs["subscription_data"])
        self.assertEqual(kwargs["metadata"]["billing_tier"], "front_office")

    def test_checkout_session_fails_closed_when_front_office_price_unset(self):
        config = stripe_billing.StripeBillingConfig(secret_key="sk_test_123")

        with self.assertRaises(stripe_billing.BillingConfigurationError):
            stripe_billing.create_checkout_session(
                config=config,
                user_id="user-1",
                email="user@example.com",
                interval=stripe_billing.ANNUAL,
                tier="front_office",
            )

    def test_webhook_resolves_front_office_when_price_matches_configured_price(self):
        config = stripe_billing.StripeBillingConfig(price_front_office_annual="price_fo_year")
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "customer": "cus_123",
                        "status": "active",
                        "metadata": {"supabase_user_id": "user-1"},
                        "items": {"data": [{"price": {"id": "price_fo_year"}}]},
                    }
                },
            },
            config=config,
        )

        self.assertEqual(action["entitlement"], "front_office")

    def test_webhook_resolves_pro_for_trialing_subscription(self):
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "customer": "cus_123",
                        "status": "trialing",
                        "metadata": {"supabase_user_id": "user-1"},
                    }
                },
            }
        )

        self.assertEqual(action["entitlement"], stripe_billing.RAW_PRO)

    def test_webhook_without_config_defaults_unmatched_price_to_pro(self):
        # Back-compat: a caller that never passes a config (as every test
        # above this class does) must see exactly the old behavior.
        action = stripe_billing.map_stripe_event_to_entitlement(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "customer": "cus_123",
                        "status": "active",
                        "metadata": {"supabase_user_id": "user-1"},
                        "items": {"data": [{"price": {"id": "price_unknown"}}]},
                    }
                },
            }
        )

        self.assertEqual(action["entitlement"], stripe_billing.RAW_PRO)

    def test_live_webhook_accepts_front_office_price_and_rejects_unconfigured_one(self):
        class FakeWebhook:
            event_price = "price_fo_year"

            @classmethod
            def construct_event(cls, *_args, **_kwargs):
                return {
                    "id": f"evt_live_{cls.event_price}",
                    "livemode": True,
                    "type": "customer.subscription.updated",
                    "data": {"object": {
                        "id": "sub_123",
                        "status": "active",
                        "metadata": {"supabase_user_id": "user-1"},
                        "items": {"data": [{"price": {"id": cls.event_price}}]},
                    }},
                }

        fake_stripe = SimpleNamespace(Webhook=FakeWebhook)
        response = SimpleNamespace(status_code=204)
        session = SimpleNamespace(patch=Mock(return_value=response))
        config = stripe_billing.StripeBillingConfig(
            billing_mode="live",
            secret_key="sk_live_123",
            webhook_secret="whsec_123",
            price_monthly="price_month",
            price_annual="price_year",
            price_front_office_annual="price_fo_year",
        )

        with patch.dict(sys.modules, {"stripe": fake_stripe}):
            accepted = stripe_webhook.process_verified_stripe_webhook(
                payload="{}",
                signature="sig",
                stripe_config=config,
                supabase_config=stripe_webhook.SupabaseWebhookConfig(
                    url="https://example.supabase.co", service_role_key="service-key"
                ),
                request_session=session,
            )

        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["action"]["entitlement"], "front_office")

    def test_build_profile_entitlement_payload_accepts_front_office(self):
        payload = stripe_webhook.build_profile_entitlement_payload(
            {"entitlement": "front_office", "event_id": "evt_1", "event_created": "1700000000"}
        )

        self.assertEqual(payload["entitlement"], "front_office")


if __name__ == "__main__":
    unittest.main()
