"""Stripe billing helpers with an explicit test/live runtime boundary.

Three billing tiers now (mirrors modules.premium.PRO / FRONT_OFFICE — this
module intentionally does NOT import modules.premium: that module imports
streamlit, and this file is also imported by services/stripe_webhook_service.py,
a separate backend-only FastAPI process that has no reason to depend on
Streamlit. Tier names are therefore plain string literals here, kept in
sync with modules.premium by convention and by the shared test suite, not
by a shared import):

  - "pro": GM Pro. Monthly or annual, 7-day Stripe trial on both (trial
    mechanics live entirely in the Stripe subscription object via
    `trial_period_days` — see create_checkout_session).
  - "front_office": Front Office. Annual only.

Price-ID configuration: STRIPE_PRICE_PRO_MONTHLY / STRIPE_PRICE_PRO_ANNUAL
are the canonical Pro price-id config keys. The pre-3-tier keys
STRIPE_PRICE_MONTHLY / STRIPE_PRICE_ANNUAL remain supported as fallbacks
for either direction — whichever is set wins if only one is — so an
already-deployed environment variable keeps working unchanged through the
rollout. STRIPE_PRICE_FRONT_OFFICE_ANNUAL and
STRIPE_PRICE_PRO_ANNUAL_LAUNCH_WEEK are new, Pro/Front-Office-specific, no
legacy alias needed. Any of these may be unset in this environment (the
product owner has not created the real Stripe Prices yet); every lookup
that needs one fails closed with a clear BillingConfigurationError rather
than silently charging the wrong tier or falling through to a different
price.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from modules import app_config


CONFIG_KEYS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_BILLING_MODE",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_MONTHLY",
    "STRIPE_PRICE_ANNUAL",
    "STRIPE_PRICE_PRO_MONTHLY",
    "STRIPE_PRICE_PRO_ANNUAL",
    "STRIPE_PRICE_PRO_ANNUAL_LAUNCH_WEEK",
    "STRIPE_PRICE_FRONT_OFFICE_ANNUAL",
    "STRIPE_CUSTOMER_PORTAL_RETURN_URL",
    "STRIPE_CHECKOUT_SUCCESS_URL",
    "STRIPE_CHECKOUT_CANCEL_URL",
    "APP_BASE_URL",
)

MONTHLY = "monthly"
ANNUAL = "annual"
# Distinct key from ANNUAL (which means Pro Annual throughout this module's
# plan_display_details/fetch_live_plan_details dicts) — Front Office is a
# separate priced tier, not another Pro interval.
FRONT_OFFICE_ANNUAL = "front_office_annual"

# Billing tiers. Kept as local literals rather than importing
# modules.premium — see module docstring.
TIER_PRO = "pro"
TIER_FRONT_OFFICE = "front_office"

# Raw values written to/read from Supabase `profiles.entitlement` by the
# webhook (see map_stripe_event_to_entitlement / build_profile_entitlement_payload).
# RAW_PRO is deliberately "premium", not "pro" — see module docstring.
# modules.premium normalizes these into its own PRO/FRONT_OFFICE/FREE
# constants for every web caller; these are the wire-format values.
RAW_FREE = "free"
RAW_PRO = "premium"
RAW_FRONT_OFFICE = "front_office"

# GM Pro's Stripe-native trial, both intervals.
PRO_TRIAL_DAYS = 7

# Launch Week promo: $29.99 GM Pro annual, Oct 12 00:00 CT through
# Oct 18 23:59 CT. A pure function of wall-clock time + config — no
# scheduled job, no feature flag to forget to flip back off.
_LAUNCH_WEEK_TZ = ZoneInfo("America/Chicago")
LAUNCH_WEEK_START = datetime(2026, 10, 12, 0, 0, 0, tzinfo=_LAUNCH_WEEK_TZ)
LAUNCH_WEEK_END = datetime(2026, 10, 18, 23, 59, 59, tzinfo=_LAUNCH_WEEK_TZ)


def launch_week_active(*, now: datetime | None = None) -> bool:
    """True only inside the Launch Week promo window (Oct 12-18 CT)."""

    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return LAUNCH_WEEK_START <= current <= LAUNCH_WEEK_END

# Fallback display values only — used whenever a live Stripe Price lookup is
# unavailable (billing not configured, package missing, or the API call
# fails). plan_display_details() always prefers the real Price objects when
# it can reach them; this dict exists so a pricing-display hiccup never
# breaks the Premium page. Keep these roughly in sync with the real Stripe
# Dashboard prices, but they are not the source of truth for what is charged.
DEFAULT_PLAN_DETAILS: dict[str, tuple[str, str, str]] = {
    MONTHLY: ("Monthly", "$3.99", "per month"),
    ANNUAL: ("Annual", "$19.99", "per year"),
    FRONT_OFFICE_ANNUAL: ("Annual", "$99.99", "per year"),
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
    # GM Pro prices. Field names kept as `price_monthly`/`price_annual`
    # (not renamed to `price_pro_*`) so every existing call site/test that
    # constructs StripeBillingConfig(price_monthly=..., price_annual=...)
    # keeps working unchanged — these ARE the Pro-tier prices now, read
    # from STRIPE_PRICE_PRO_MONTHLY/STRIPE_PRICE_PRO_ANNUAL with the
    # pre-3-tier STRIPE_PRICE_MONTHLY/STRIPE_PRICE_ANNUAL as a fallback.
    # See load_stripe_config.
    price_monthly: str = ""
    price_annual: str = ""
    # New in the 3-tier model. No legacy alias needed — these tiers/prices
    # did not exist before.
    price_pro_annual_launch_week: str = ""
    price_front_office_annual: str = ""
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
        # Front Office / Launch Week prices are optional extras — GM Pro's
        # monthly+annual prices are the only ones required for "billing is
        # configured at all" (matches pre-3-tier behavior exactly).
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
            "has_front_office_annual_price": bool(self.price_front_office_annual),
            "has_launch_week_price": bool(self.price_pro_annual_launch_week),
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
    # STRIPE_PRICE_PRO_MONTHLY/ANNUAL are canonical; STRIPE_PRICE_MONTHLY/ANNUAL
    # remain a working fallback either direction so an already-deployed env
    # var does not go dark mid-rollout.
    price_monthly = values["STRIPE_PRICE_PRO_MONTHLY"] or values["STRIPE_PRICE_MONTHLY"]
    price_annual = values["STRIPE_PRICE_PRO_ANNUAL"] or values["STRIPE_PRICE_ANNUAL"]
    return StripeBillingConfig(
        billing_mode=_safe_text(values["STRIPE_BILLING_MODE"]).casefold() or "test",
        secret_key=values["STRIPE_SECRET_KEY"],
        webhook_secret=values["STRIPE_WEBHOOK_SECRET"],
        price_monthly=price_monthly,
        price_annual=price_annual,
        price_pro_annual_launch_week=values["STRIPE_PRICE_PRO_ANNUAL_LAUNCH_WEEK"],
        price_front_office_annual=values["STRIPE_PRICE_FRONT_OFFICE_ANNUAL"],
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
    """Back-compat: Pro-tier price only. Prefer price_id_for_plan."""

    interval_key = _safe_text(interval).casefold()
    if interval_key == MONTHLY:
        return config.price_monthly
    if interval_key == ANNUAL:
        return config.price_annual
    raise BillingConfigurationError("Unknown billing interval.")


def price_id_for_plan(
    config: StripeBillingConfig,
    tier: str,
    interval: str,
    *,
    now: datetime | None = None,
) -> str:
    """Resolve the Stripe Price id for a (tier, interval) pair.

    Fails closed with a clear BillingConfigurationError whenever the
    requested tier/interval combination has no price id configured —
    never falls through to a different tier's or interval's price, which
    would silently charge the wrong amount.
    """

    tier_key = _safe_text(tier).casefold() or TIER_PRO
    interval_key = _safe_text(interval).casefold()

    if tier_key == TIER_FRONT_OFFICE:
        if interval_key not in ("", ANNUAL):
            raise BillingConfigurationError("Front Office billing is annual-only.")
        if not config.price_front_office_annual:
            raise BillingConfigurationError("Front Office annual price is not configured.")
        return config.price_front_office_annual

    if tier_key != TIER_PRO:
        raise BillingConfigurationError(f"Unknown billing tier: {tier_key!r}.")

    if interval_key == MONTHLY:
        if not config.price_monthly:
            raise BillingConfigurationError("GM Pro monthly price is not configured.")
        return config.price_monthly

    if interval_key == ANNUAL:
        if launch_week_active(now=now) and config.price_pro_annual_launch_week:
            return config.price_pro_annual_launch_week
        if not config.price_annual:
            raise BillingConfigurationError("GM Pro annual price is not configured.")
        return config.price_annual

    raise BillingConfigurationError("Unknown billing interval.")


def _require_config(config: StripeBillingConfig) -> None:
    if not config.configured:
        raise BillingConfigurationError("Stripe billing mode and secret key do not match.")


def _require_checkout_runtime(config: StripeBillingConfig) -> None:
    """Checkout precondition: just a valid secret for the active mode.

    Deliberately *not* `config.configured` — that also requires GM Pro's
    monthly+annual prices specifically, which would wrongly block a
    Front-Office-only checkout even when `price_front_office_annual` is
    set. The specific (tier, interval) price is validated separately by
    `price_id_for_plan`, which fails closed on its own.
    """

    if not config.secret_mode_configured:
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
    return (
        f"{config.billing_mode}:{secret_fingerprint}:{config.price_monthly}:"
        f"{config.price_annual}:{config.price_front_office_annual}"
    )


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
        # Front Office is optional — Pro's own display must not fail or
        # drop just because Front Office isn't configured in some
        # environment (e.g. a test deploy that only has Pro prices set).
        if config.price_front_office_annual:
            front_office_price = stripe.Price.retrieve(config.price_front_office_annual)
            details[FRONT_OFFICE_ANNUAL] = _price_display_tuple("Annual", front_office_price, "per year")
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
    tier: str = TIER_PRO,
    success_url: str = "",
    cancel_url: str = "",
    trial_days: int | None = None,
    now: datetime | None = None,
):
    """Start a Stripe Checkout session for the given (tier, interval).

    `tier` defaults to GM Pro — every pre-3-tier caller keeps charging the
    same plan it always did. Front Office checkout must pass
    tier="front_office" explicitly (and interval is ignored/annual-only —
    see price_id_for_plan).

    `trial_days` defaults to PRO_TRIAL_DAYS for GM Pro (both intervals,
    per the pricing spec) and to no trial for any other tier; pass 0
    explicitly to force no trial on a Pro checkout. Trial mechanics are
    entirely Stripe-native (`subscription_data.trial_period_days`) — this
    function does not track trial state locally.
    """

    _require_checkout_runtime(config)
    clean_user_id = _safe_text(user_id)
    if not clean_user_id:
        raise BillingConfigurationError("Checkout requires a logged-in user id.")
    tier_key = _safe_text(tier).casefold() or TIER_PRO
    price_id = price_id_for_plan(config, tier_key, interval, now=now)
    stripe = _stripe_module()
    stripe.api_key = config.secret_key
    subscription_data: dict[str, Any] = {"metadata": {"supabase_user_id": clean_user_id}}
    resolved_trial_days = (
        trial_days if trial_days is not None else (PRO_TRIAL_DAYS if tier_key == TIER_PRO else 0)
    )
    if resolved_trial_days and resolved_trial_days > 0:
        subscription_data["trial_period_days"] = int(resolved_trial_days)
    return stripe.checkout.Session.create(
        mode="subscription",
        customer_email=_safe_text(email) or None,
        line_items=[{"price": price_id, "quantity": 1}],
        allow_promotion_codes=True,
        success_url=_safe_text(success_url or config.checkout_success_url)
        or app_config.stripe_return_url("/?page=premium&billing=success", base_url=config.app_base_url),
        cancel_url=_safe_text(cancel_url or config.checkout_cancel_url)
        or app_config.stripe_return_url("/?page=premium&billing=cancel", base_url=config.app_base_url),
        client_reference_id=clean_user_id,
        # Reduce duplicate checkouts for the same user+interval+price.
        idempotency_key=f"fgl-checkout-{clean_user_id}-{_safe_text(interval).casefold()}-{price_id}"[:255],
        metadata={
            "supabase_user_id": clean_user_id,
            "billing_interval": _safe_text(interval).casefold(),
            "plan_interval": _safe_text(interval).casefold(),
            "billing_tier": tier_key,
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


def map_stripe_event_to_entitlement(
    event: dict,
    *,
    config: StripeBillingConfig | None = None,
) -> dict[str, str]:
    """Resolve one Stripe event to a Supabase `profiles.entitlement` write.

    Returns the raw value to store, not a modules.premium tier constant:
    "free", "premium" (the legacy name — still what gets stored for GM
    Pro; see modules/premium.py's docstring for why), or "front_office".

    `config` is optional and, when omitted, this behaves exactly as the
    pre-3-tier version did (every active/trialing subscription resolves
    "premium") — every existing direct caller/test of this function that
    does not pass a config keeps its exact prior behavior. When a config
    IS given, an active subscription whose price id matches
    `config.price_front_office_annual` resolves "front_office" instead;
    any other recognized or unrecognized active price still resolves
    "premium" (GM Pro is the default paid tier for anything not
    explicitly Front Office — this mirrors how price_id_for_plan treats
    an unspecified tier).

    A `trialing` subscription status is included in the same active set
    as `active` — Stripe's own trial state already resolves the paid tier
    here, matching the "trial resolves as the target tier before first
    payment" requirement; no separate trial-tracking state is kept.
    """

    event_type = _safe_text(event.get("type"))
    obj = _event_object(event)
    user_id = _metadata_user_id(obj)
    subscription_status = _safe_text(obj.get("status")).casefold()
    if event_type.startswith("invoice."):
        subscription_status = _invoice_subscription_status(obj)
    customer_id = _stripe_id(obj.get("customer"))
    subscription_id = _stripe_id(obj.get("subscription") or obj.get("id"))
    event_price_id = _stripe_price_id(obj)

    entitlement = ""
    reason = event_type
    cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    if event_type in ACTIVE_ENTITLEMENT_EVENTS:
        if not subscription_status or subscription_status in {"active", "trialing", "paid", "complete"}:
            entitlement = "premium"
            if (
                config is not None
                and config.price_front_office_annual
                and event_price_id
                and event_price_id == config.price_front_office_annual
            ):
                entitlement = "front_office"
            if cancel_at_period_end and subscription_status in {"active", "trialing"}:
                reason = f"{event_type}:cancel_at_period_end"
    if event_type == "invoice.payment_failed":
        # Fail closed: unpaid invoices revoke paid access until a later success event.
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
        "stripe_price_id": event_price_id,
        "cancel_at_period_end": "true" if cancel_at_period_end else "false",
    }


def handle_stripe_webhook(payload: bytes | str, signature: str, *, config: StripeBillingConfig) -> dict[str, str]:
    event = construct_stripe_event(payload, signature, config=config)
    return map_stripe_event_to_entitlement(event, config=config)


def parse_test_event(payload: bytes | str) -> dict:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)
