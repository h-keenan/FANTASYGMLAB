"""Stripe billing helpers with an explicit test/live runtime boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from modules import app_config


CONFIG_KEYS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_BILLING_MODE",
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

# Fallback display values only — used whenever a live Stripe Price lookup is
# unavailable (billing not configured, package missing, or the API call
# fails). plan_display_details() always prefers the real Price objects when
# it can reach them; this dict exists so a pricing-display hiccup never
# breaks the Premium page. Keep these roughly in sync with the real Stripe
# Dashboard prices, but they are not the source of truth for what is charged.
DEFAULT_PLAN_DETAILS: dict[str, tuple[str, str, str]] = {
    MONTHLY: ("Monthly", "$3.99", "per month"),
    ANNUAL: ("Annual", "$19.99", "per year"),
}

_PRICE_DISPLAY_CACHE_TTL_SECONDS = 5 * 60
_price_display_cache: dict[str, tuple[float, dict[str, tuple[str, str, str]]]] = {}
_price_display_cache_lock = Lock()

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
    billing_mode: str = "test"
    secret_key: str = ""
    webhook_secret: str = ""
    price_monthly: str = ""
    price_annual: str = ""
    customer_portal_return_url: str = ""
    checkout_success_url: str = ""
    checkout_cancel_url: str = ""
    app_base_url: str = app_config.LOCAL_BASE_URL

    @property
    def secret_mode_configured(self) -> bool:
        return bool(
            self.billing_mode in {"test", "live"}
            and self.secret_key.startswith(f"sk_{self.billing_mode}_")
        )

    @property
    def configured(self) -> bool:
        return bool(
            self.secret_mode_configured
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
            "mode": self.billing_mode if self.configured else "missing_or_mismatched",
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
        billing_mode=_safe_text(values["STRIPE_BILLING_MODE"]).casefold() or "test",
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
      READY — test-mode checkout configured
      ON — explicitly configured live-mode checkout
    """
    config = load_stripe_config(environ=environ, secrets=secrets)
    if config.configured:
        return "ON" if config.billing_mode == "live" else "READY"
    return "OFF"


def price_id_for_interval(config: StripeBillingConfig, interval: str) -> str:
    interval_key = _safe_text(interval).casefold()
    if interval_key == MONTHLY:
        return config.price_monthly
    if interval_key == ANNUAL:
        return config.price_annual
    raise BillingConfigurationError("Unknown billing interval.")


def _require_config(config: StripeBillingConfig) -> None:
    if not config.configured:
        raise BillingConfigurationError("Stripe billing mode and secret key do not match.")


def _stripe_module():
    try:
        import stripe  # type: ignore
    except Exception as exc:
        raise BillingUnavailableError("Stripe package is not installed in this environment.") from exc
    return stripe


def _price_field(price_obj: Any, name: str) -> Any:
    if isinstance(price_obj, dict):
        return price_obj.get(name)
    return getattr(price_obj, name, None)


def _format_price_amount(unit_amount: Any, currency: str) -> str:
    try:
        amount = int(unit_amount) / 100
    except (TypeError, ValueError):
        return ""
    currency_code = _safe_text(currency).upper() or "USD"
    symbol = "$" if currency_code == "USD" else f"{currency_code} "
    return f"{symbol}{amount:,.2f}"


def _price_display_tuple(label: str, price_obj: Any, fallback_cadence: str) -> tuple[str, str, str]:
    price_text = _format_price_amount(
        _price_field(price_obj, "unit_amount"),
        _safe_text(_price_field(price_obj, "currency")),
    )
    if not price_text:
        raise BillingUnavailableError("Stripe price is missing a usable unit amount.")
    recurring = _price_field(price_obj, "recurring")
    interval = _safe_text(_price_field(recurring, "interval")) if recurring is not None else ""
    cadence = f"per {interval}" if interval else fallback_cadence
    return (label, price_text, cadence)


def _price_cache_key(config: StripeBillingConfig) -> str:
    # Hash the secret key rather than storing it verbatim as a cache key.
    secret_fingerprint = hashlib.sha256(config.secret_key.encode("utf-8")).hexdigest()[:16]
    return f"{config.billing_mode}:{secret_fingerprint}:{config.price_monthly}:{config.price_annual}"


def fetch_live_plan_details(
    config: StripeBillingConfig,
    *,
    now: float | None = None,
) -> dict[str, tuple[str, str, str]] | None:
    """Real Stripe Price objects (label, price, cadence) for display.

    Cached in-process for a few minutes per (mode, secret, price-id) so this
    never hits Stripe on every page render. Returns None — and never raises —
    when Stripe isn't configured, the package is unavailable, or the API call
    fails for any reason; callers must fall back to a hardcoded default so a
    pricing-display hiccup never breaks the Premium page.
    """
    if not config.secret_mode_configured or not config.price_monthly or not config.price_annual:
        return None
    cache_key = _price_cache_key(config)
    current_time = now if now is not None else datetime.now(timezone.utc).timestamp()
    with _price_display_cache_lock:
        cached = _price_display_cache.get(cache_key)
        if cached and current_time - cached[0] < _PRICE_DISPLAY_CACHE_TTL_SECONDS:
            return cached[1]
    try:
        stripe = _stripe_module()
        stripe.api_key = config.secret_key
        monthly_price = stripe.Price.retrieve(config.price_monthly)
        annual_price = stripe.Price.retrieve(config.price_annual)
        details = {
            MONTHLY: _price_display_tuple("Monthly", monthly_price, "per month"),
            ANNUAL: _price_display_tuple("Annual", annual_price, "per year"),
        }
    except Exception:
        return None
    with _price_display_cache_lock:
        _price_display_cache[cache_key] = (current_time, details)
    return details


def plan_display_details(config: StripeBillingConfig) -> dict[str, tuple[str, str, str]]:
    """(label, price, cadence) per billing interval for the Premium page.

    Prefers the real Stripe Price objects (`fetch_live_plan_details`, briefly
    cached) so displayed pricing cannot silently drift from what Stripe
    actually charges; falls back to DEFAULT_PLAN_DETAILS whenever the live
    lookup is unavailable. Never raises.
    """
    return fetch_live_plan_details(config) or dict(DEFAULT_PLAN_DETAILS)


def reset_price_display_cache_for_tests() -> None:
    with _price_display_cache_lock:
        _price_display_cache.clear()


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
    _require_config(config)
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
    if not config.secret_mode_configured:
        raise BillingConfigurationError("Stripe billing mode and secret key do not match.")
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
    if config.secret_key and not config.secret_mode_configured:
        raise BillingConfigurationError("Stripe billing mode and secret key do not match.")
    stripe = _stripe_module()
    try:
        event = stripe.Webhook.construct_event(payload, signature, config.webhook_secret)
    except Exception as exc:
        raise BillingConfigurationError("Invalid Stripe webhook signature.") from exc
    if isinstance(event, dict) and bool(event.get("livemode")) != (config.billing_mode == "live"):
        raise BillingConfigurationError("Stripe event mode does not match the configured billing mode.")
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
        "event_created": _safe_text(event.get("created")),
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
