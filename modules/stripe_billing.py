"""Stripe test-mode billing helpers.

Live billing is not enabled; this module only accepts Stripe test-mode keys.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from modules import app_config


CONFIG_KEYS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_MONTHLY",
    "STRIPE_PRICE_ANNUAL",
    "STRIPE_CUSTOMER_PORTAL_RETURN_URL",
    "STRIPE_CHECKOUT_SUCCESS_URL",
    "STRIPE_CHECKOUT_CANCEL_URL",
    "APP_BASE_URL",
)

MONTHLY = "monthly"
ANNUAL = "annual"
ACTIVE_ENTITLEMENT_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "invoice.payment_succeeded",
}
INACTIVE_ENTITLEMENT_EVENTS = {
    "customer.subscription.deleted",
}


class BillingConfigurationError(RuntimeError):
    pass


class BillingUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class StripeBillingConfig:
    secret_key: str = ""
    webhook_secret: str = ""
    price_monthly: str = ""
    price_annual: str = ""
    customer_portal_return_url: str = ""
    checkout_success_url: str = ""
    checkout_cancel_url: str = ""
    app_base_url: str = app_config.LOCAL_BASE_URL

    @property
    def configured(self) -> bool:
        return bool(
            self.secret_key
            and self.secret_key.startswith("sk_test_")
            and self.price_monthly
            and self.price_annual
        )

    @property
    def webhook_configured(self) -> bool:
        return bool(self.webhook_secret and self.webhook_secret.startswith("whsec_"))

    @property
    def redacted(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "webhook_configured": self.webhook_configured,
            "mode": "test" if self.secret_key.startswith("sk_test_") else "missing_or_not_test",
            "has_monthly_price": bool(self.price_monthly),
            "has_annual_price": bool(self.price_annual),
            "has_customer_portal_return_url": bool(self.customer_portal_return_url),
            "has_checkout_success_url": bool(self.checkout_success_url),
            "has_checkout_cancel_url": bool(self.checkout_cancel_url),
            "app_base_url": self.app_base_url,
        }


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _config_value(key: str, *, environ: dict | None = None, secrets: Any = None) -> str:
    return app_config.config_value(key, environ=environ, secrets=secrets)


def load_stripe_config(*, environ: dict | None = None, secrets: Any = None) -> StripeBillingConfig:
    values = {key: _config_value(key, environ=environ, secrets=secrets) for key in CONFIG_KEYS}
    return StripeBillingConfig(
        secret_key=values["STRIPE_SECRET_KEY"],
        webhook_secret=values["STRIPE_WEBHOOK_SECRET"],
        price_monthly=values["STRIPE_PRICE_MONTHLY"],
        price_annual=values["STRIPE_PRICE_ANNUAL"],
        customer_portal_return_url=values["STRIPE_CUSTOMER_PORTAL_RETURN_URL"],
        checkout_success_url=values["STRIPE_CHECKOUT_SUCCESS_URL"],
        checkout_cancel_url=values["STRIPE_CHECKOUT_CANCEL_URL"],
        app_base_url=app_config.app_base_url(environ=environ, secrets=secrets),
    )


def stripe_configured(*, environ: dict | None = None, secrets: Any = None) -> bool:
    return load_stripe_config(environ=environ, secrets=secrets).configured


def stripe_live_billing_status(
    *,
    environ: dict | None = None,
    secrets: Any = None,
) -> str:
    """Launch checklist flag for live charging — never silently ON.

    Returns:
      OFF — no usable Stripe secret / prices (includes rejected live secrets)
      READY — test-mode checkout configured; no live charge path
      ON — reserved; current code never enables live charging
    """
    config = load_stripe_config(environ=environ, secrets=secrets)
    key = _safe_text(config.secret_key)
    live_prefix = "sk_" + "live_"
    if key.startswith(live_prefix):
        # Live keys are rejected by checkout/webhook paths; treat as not enabled.
        return "OFF"
    if config.configured:
        return "READY"
    return "OFF"


def price_id_for_interval(config: StripeBillingConfig, interval: str) -> str:
    interval_key = _safe_text(interval).casefold()
    if interval_key == MONTHLY:
        return config.price_monthly
    if interval_key == ANNUAL:
        return config.price_annual
    raise BillingConfigurationError("Unknown billing interval.")


def _require_test_config(config: StripeBillingConfig) -> None:
    if not config.configured:
        raise BillingConfigurationError("Stripe test billing is not configured.")
    if not config.secret_key.startswith("sk_test_"):
        raise BillingConfigurationError("Only Stripe test-mode secret keys are allowed.")


def _stripe_module():
    try:
        import stripe  # type: ignore
    except Exception as exc:
        raise BillingUnavailableError("Stripe package is not installed in this environment.") from exc
    return stripe


def create_checkout_session(
    *,
    config: StripeBillingConfig,
    user_id: str,
    email: str,
    interval: str,
    success_url: str = "",
    cancel_url: str = "",
    trial_days: int | None = None,
):
    _require_test_config(config)
    clean_user_id = _safe_text(user_id)
    if not clean_user_id:
        raise BillingConfigurationError("Checkout requires a logged-in user id.")
    price_id = price_id_for_interval(config, interval)
    stripe = _stripe_module()
    stripe.api_key = config.secret_key
    subscription_data: dict[str, Any] = {"metadata": {"supabase_user_id": clean_user_id}}
    if trial_days and trial_days > 0:
        subscription_data["trial_period_days"] = int(trial_days)
    return stripe.checkout.Session.create(
        mode="subscription",
        customer_email=_safe_text(email) or None,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=_safe_text(success_url or config.checkout_success_url)
        or app_config.stripe_return_url("/?page=premium&billing=success", base_url=config.app_base_url),
        cancel_url=_safe_text(cancel_url or config.checkout_cancel_url)
        or app_config.stripe_return_url("/?page=premium&billing=cancel", base_url=config.app_base_url),
        client_reference_id=clean_user_id,
        # Reduce duplicate Founder Beta checkouts for the same user+interval.
        idempotency_key=f"fgl-checkout-{clean_user_id}-{_safe_text(interval).casefold()}-{price_id}"[:255],
        metadata={
            "supabase_user_id": clean_user_id,
            "billing_interval": _safe_text(interval).casefold(),
            "plan_interval": _safe_text(interval).casefold(),
        },
        subscription_data=subscription_data,
    )


def create_customer_portal_session(
    *,
    config: StripeBillingConfig,
    stripe_customer_id: str,
    return_url: str = "",
):
    if not config.secret_key.startswith("sk_test_"):
        raise BillingConfigurationError("Only Stripe test-mode customer portal sessions are allowed.")
    customer_id = _safe_text(stripe_customer_id)
    if not customer_id:
        raise BillingConfigurationError("Customer portal requires a Stripe customer id.")
    stripe = _stripe_module()
    stripe.api_key = config.secret_key
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=_safe_text(return_url or config.customer_portal_return_url)
        or app_config.stripe_return_url("/?page=premium", base_url=config.app_base_url),
    )


def construct_stripe_event(payload: bytes | str, signature: str, *, config: StripeBillingConfig) -> dict:
    if not config.webhook_configured:
        raise BillingConfigurationError("Stripe webhook secret is not configured.")
    if config.secret_key and not config.secret_key.startswith("sk_test_"):
        raise BillingConfigurationError("Only Stripe test-mode webhooks are allowed.")
    stripe = _stripe_module()
    try:
        event = stripe.Webhook.construct_event(payload, signature, config.webhook_secret)
    except Exception as exc:
        raise BillingConfigurationError("Invalid Stripe webhook signature.") from exc
    if isinstance(event, dict) and event.get("livemode"):
        raise BillingConfigurationError("Live-mode Stripe events are not accepted by this test webhook handler.")
    return event


def _event_object(event: dict) -> dict:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    return obj


def _metadata_user_id(obj: dict) -> str:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    subscription_metadata = obj.get("subscription_details", {}).get("metadata", {}) if isinstance(obj.get("subscription_details"), dict) else {}
    customer = obj.get("customer") if isinstance(obj.get("customer"), dict) else {}
    customer_metadata = customer.get("metadata") if isinstance(customer.get("metadata"), dict) else {}
    return _safe_text(
        metadata.get("supabase_user_id")
        or subscription_metadata.get("supabase_user_id")
        or customer_metadata.get("supabase_user_id")
        or obj.get("client_reference_id")
    )


def _stripe_price_id(obj: dict) -> str:
    direct_price = obj.get("price")
    if isinstance(direct_price, dict):
        price_id = _safe_text(direct_price.get("id"))
        if price_id:
            return price_id
    items = obj.get("items") if isinstance(obj.get("items"), dict) else {}
    item_data = items.get("data") if isinstance(items.get("data"), list) else []
    for item in item_data:
        if not isinstance(item, dict):
            continue
        price = item.get("price") if isinstance(item.get("price"), dict) else {}
        price_id = _safe_text(price.get("id"))
        if price_id:
            return price_id
    lines = obj.get("lines") if isinstance(obj.get("lines"), dict) else {}
    line_data = lines.get("data") if isinstance(lines.get("data"), list) else []
    for line in line_data:
        if not isinstance(line, dict):
            continue
        price = line.get("price") if isinstance(line.get("price"), dict) else {}
        price_id = _safe_text(price.get("id"))
        if price_id:
            return price_id
    return ""


def _stripe_id(value: Any) -> str:
    if isinstance(value, dict):
        return _safe_text(value.get("id"))
    return _safe_text(value)


def _invoice_subscription_status(obj: dict) -> str:
    billing_reason = _safe_text(obj.get("billing_reason")).casefold()
    paid = obj.get("paid")
    status = _safe_text(obj.get("status")).casefold()
    if paid is True or status == "paid":
        return "active"
    if billing_reason:
        return status or billing_reason
    return status


def map_stripe_event_to_entitlement(event: dict) -> dict[str, str]:
    event_type = _safe_text(event.get("type"))
    obj = _event_object(event)
    user_id = _metadata_user_id(obj)
    subscription_status = _safe_text(obj.get("status")).casefold()
    if event_type.startswith("invoice."):
        subscription_status = _invoice_subscription_status(obj)
    customer_id = _stripe_id(obj.get("customer"))
    subscription_id = _stripe_id(obj.get("subscription") or obj.get("id"))

    entitlement = ""
    reason = event_type
    cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    if event_type in ACTIVE_ENTITLEMENT_EVENTS:
        if not subscription_status or subscription_status in {"active", "trialing", "paid", "complete"}:
            entitlement = "premium"
            if cancel_at_period_end and subscription_status in {"active", "trialing"}:
                reason = f"{event_type}:cancel_at_period_end"
    if event_type == "invoice.payment_failed":
        # Fail closed: unpaid invoices revoke Premium until a later success event.
        entitlement = "free"
    if event_type in INACTIVE_ENTITLEMENT_EVENTS or subscription_status in {"canceled", "unpaid", "incomplete_expired"}:
        entitlement = "free"

    return {
        "event_id": _safe_text(event.get("id")),
        "user_id": user_id,
        "entitlement": entitlement,
        "reason": reason,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_subscription_status": subscription_status,
        "stripe_price_id": _stripe_price_id(obj),
        "cancel_at_period_end": "true" if cancel_at_period_end else "false",
    }


def handle_stripe_webhook(payload: bytes | str, signature: str, *, config: StripeBillingConfig) -> dict[str, str]:
    event = construct_stripe_event(payload, signature, config=config)
    return map_stripe_event_to_entitlement(event)


def parse_test_event(payload: bytes | str) -> dict:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)
