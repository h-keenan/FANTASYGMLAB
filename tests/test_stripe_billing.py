import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from modules import premium
from modules import premium_page
from modules import stripe_billing
from modules import stripe_webhook
from services import stripe_webhook_service


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
        self.assertEqual(action["entitlement"], premium.PREMIUM)
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
        self.assertEqual(action["entitlement"], premium.PREMIUM)
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
        self.assertEqual(action["entitlement"], premium.PREMIUM)

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
        self.assertEqual(action["entitlement"], premium.PREMIUM)
        self.assertEqual(action["stripe_price_id"], "price_month")

    def test_supabase_update_payload_targets_entitlement_and_stripe_fields(self):
        payload = stripe_webhook.build_profile_entitlement_payload(
            {
                "entitlement": premium.PREMIUM,
                "stripe_customer_id": "cus_123",
                "stripe_subscription_id": "sub_123",
                "stripe_subscription_status": "active",
                "stripe_price_id": "price_month",
            }
        )

        self.assertEqual(payload["entitlement"], premium.PREMIUM)
        self.assertEqual(payload["stripe_customer_id"], "cus_123")
        self.assertEqual(payload["stripe_subscription_status"], "active")
        self.assertIn("premium_updated_at", payload)

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
                "entitlement": premium.PREMIUM,
                "stripe_customer_id": "cus_123",
            },
        )

        self.assertTrue(ok)
        self.assertFalse(error)
        call = session.patch.call_args
        self.assertIn("/rest/v1/profiles?user_id=eq.user-1", call.args[0])
        self.assertEqual(call.kwargs["json"]["entitlement"], premium.PREMIUM)
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer service-key")

    def test_supabase_update_requires_user_id_and_supported_entitlement(self):
        config = stripe_webhook.SupabaseWebhookConfig(url="https://example.supabase.co", service_role_key="service-key")

        ok, error = stripe_webhook.update_profile_entitlement(
            config=config,
            action={"entitlement": premium.PREMIUM},
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
                "entitlement": premium.PREMIUM,
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
        self.assertEqual(result["action"]["entitlement"], premium.PREMIUM)
        self.assertEqual(session.patch.call_args.kwargs["json"]["entitlement"], premium.PREMIUM)

    def test_verified_webhook_duplicate_event_is_idempotent_patch(self):
        action = {
            "event_id": "evt_repeat",
            "user_id": "user-1",
            "entitlement": premium.PREMIUM,
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

    def test_premium_page_copy_separates_now_and_future_without_guarantee(self):
        html = premium_page.premium_page_html(entitlement=premium.FREE)

        self.assertIn("Included now with Premium", html)
        self.assertIn("Possible future features", html)
        self.assertIn("not guaranteed", html)
        self.assertIn("Premium checkout will appear here once billing is enabled", html)
        self.assertNotIn("Subscribe now", html)

    def test_premium_page_shows_test_mode_copy_when_configured(self):
        html = premium_page.premium_page_html(
            entitlement=premium.FREE,
            billing_config=stripe_billing.StripeBillingConfig(
                secret_key="sk_test_123",
                price_monthly="price_month",
                price_annual="price_year",
            ),
        )

        self.assertIn("Secure Founder Premium checkout uses Stripe test mode", html)
        self.assertIn("no live charge will be made", html.casefold())
        self.assertIn("Live billing is not enabled", html)

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
                        "entitlement": premium.PREMIUM,
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


if __name__ == "__main__":
    unittest.main()
