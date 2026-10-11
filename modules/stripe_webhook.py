from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import requests

from modules import app_config
from modules import stripe_billing


class StripeWebhookUpdateError(RuntimeError):
    pass


# Process-local Stripe event_id cache. Duplicate deliveries within the TTL skip
# a second Supabase PATCH; entitlement semantics remain idempotent either way.
_RECENT_EVENT_TTL_SECONDS = 6 * 60 * 60
_recent_event_ids: dict[str, float] = {}
_recent_event_lock = Lock()


def _remember_event_id(event_id: str) -> None:
    clean = _safe_text(event_id)
    if not clean:
        return
    now = datetime.now(timezone.utc).timestamp()
    with _recent_event_lock:
        cutoff = now - _RECENT_EVENT_TTL_SECONDS
        stale = [key for key, seen_at in _recent_event_ids.items() if seen_at < cutoff]
        for key in stale:
            _recent_event_ids.pop(key, None)
        _recent_event_ids[clean] = now


def _event_id_already_processed(event_id: str) -> bool:
    clean = _safe_text(event_id)
    if not clean:
        return False
    now = datetime.now(timezone.utc).timestamp()
    with _recent_event_lock:
        seen_at = _recent_event_ids.get(clean)
        if seen_at is None:
            return False
        if now - seen_at > _RECENT_EVENT_TTL_SECONDS:
            _recent_event_ids.pop(clean, None)
            return False
        return True


def clear_processed_event_ids_for_tests() -> None:
    with _recent_event_lock:
        _recent_event_ids.clear()


@dataclass(frozen=True)
class SupabaseWebhookConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)

    @property
    def redacted(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "has_url": bool(self.url),
            "has_service_role_key": bool(self.service_role_key),
        }


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _config_value(key: str, *, environ: dict | None = None, secrets: Any = None) -> str:
    return app_config.config_value(key, environ=environ, secrets=secrets)


def load_supabase_webhook_config(*, environ: dict | None = None, secrets: Any = None) -> SupabaseWebhookConfig:
    return SupabaseWebhookConfig(
        url=_config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=_config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _supabase_error_message(response: Any) -> str:
    try:
        data = response.json()
    except Exception:
        data = {}
    if isinstance(data, dict):
        for key in ("message", "hint", "details", "code"):
            value = _safe_text(data.get(key))
            if value:
                return value
    return _safe_text(getattr(response, "text", ""), "")


def _profile_update_url(config: SupabaseWebhookConfig, user_id: str) -> str:
    from modules import auth_supabase

    base = auth_supabase.normalize_supabase_project_url(config.url)
    return f"{base}/rest/v1/profiles?user_id=eq.{_safe_text(user_id)}"


SUPPORTED_ENTITLEMENT_VALUES = {"free", "premium", "front_office"}


def build_profile_entitlement_payload(action: dict[str, str]) -> dict[str, str]:
    entitlement = _safe_text(action.get("entitlement")).casefold()
    if entitlement and entitlement not in SUPPORTED_ENTITLEMENT_VALUES:
        raise StripeWebhookUpdateError("Stripe event did not produce a supported entitlement update.")
    payload: dict[str, str] = {
        "premium_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if entitlement in SUPPORTED_ENTITLEMENT_VALUES:
        payload["entitlement"] = entitlement
    optional_fields = {
        "stripe_customer_id": action.get("stripe_customer_id"),
        "stripe_subscription_id": action.get("stripe_subscription_id"),
        "stripe_subscription_status": action.get("stripe_subscription_status"),
        "stripe_price_id": action.get("stripe_price_id"),
        "stripe_event_id": action.get("event_id"),
    }
    for key, value in optional_fields.items():
        clean_value = _safe_text(value)
        if clean_value:
            payload[key] = clean_value
    event_created = _safe_text(action.get("event_created"))
    if event_created:
        try:
            payload["stripe_event_created_at"] = datetime.fromtimestamp(
                float(event_created), tz=timezone.utc
            ).isoformat()
        except (TypeError, ValueError, OverflowError) as exc:
            raise StripeWebhookUpdateError("Stripe event timestamp is invalid.") from exc
    if "entitlement" not in payload and len(payload) == 1:
        # Only timestamp — treat as no-op skip rather than a failed update.
        raise StripeWebhookUpdateError("noop")
    return payload


def _durable_event_ordering_params(payload: dict[str, str]) -> dict[str, str]:
    """Build the atomic PostgREST ordering guard for one entitlement event.

    Stripe timestamps have one-second resolution. At an equal timestamp, only a
    distinct revocation may advance state; an ambiguous grant must fail closed.
    Event ids are identity only and are never treated as chronologically ordered.
    """

    created_at = _safe_text(payload.get("stripe_event_created_at"))
    event_id = _safe_text(payload.get("stripe_event_id"))
    if not created_at:
        return {}
    identity_guard = (
        f"or(stripe_event_id.is.null,stripe_event_id.neq.{event_id})"
        if event_id
        else ""
    )
    clauses = [
        (
            f"and(stripe_event_created_at.is.null,{identity_guard})"
            if identity_guard
            else "stripe_event_created_at.is.null"
        ),
        (
            f"and(stripe_event_created_at.lt.{created_at},{identity_guard})"
            if identity_guard
            else f"stripe_event_created_at.lt.{created_at}"
        ),
    ]
    if _safe_text(payload.get("entitlement")).casefold() == "free" and event_id:
        clauses.append(
            "and("
            f"stripe_event_created_at.eq.{created_at},"
            "or(stripe_event_id.is.null,"
            f"stripe_event_id.neq.{event_id})"
            ")"
        )
    return {"or": f"({','.join(clauses)})"}


def update_profile_entitlement(
    *,
    config: SupabaseWebhookConfig,
    action: dict[str, str],
    request_session: Any = requests,
) -> tuple[bool, str]:
    if not config.configured:
        return False, "Supabase webhook update is not configured."
    user_id = _safe_text(action.get("user_id"))
    if not user_id:
        return False, "Stripe event did not include a Supabase user id."
    try:
        payload = build_profile_entitlement_payload(action)
    except StripeWebhookUpdateError as exc:
        if str(exc) == "noop":
            return True, ""
        return False, str(exc)
    # Past-due / indeterminate events leave entitlement blank on purpose.
    # Skip the PATCH so Stripe does not receive HTTP 500 retries.
    if "entitlement" not in payload:
        return True, ""
    try:
        request_kwargs: dict[str, Any] = {}
        ordering_params = _durable_event_ordering_params(payload)
        if ordering_params:
            request_kwargs["params"] = ordering_params
        response = request_session.patch(
            _profile_update_url(config, user_id),
            headers={
                "apikey": config.service_role_key,
                "Authorization": f"Bearer {config.service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=15,
            **request_kwargs,
        )
    except Exception:
        return False, "Could not reach Supabase profiles table."
    if response.status_code >= 400:
        message = _supabase_error_message(response)
        lowered = message.casefold()
        if "column" in lowered and any(
            column in lowered
            for column in (
                "stripe_customer_id",
                "stripe_subscription_id",
                "stripe_subscription_status",
                "stripe_price_id",
                "premium_updated_at",
                "stripe_event_id",
                "stripe_event_created_at",
                "entitlement",
            )
        ):
            return False, (
                "Supabase profiles billing columns are missing. "
                "Run docs/supabase_stripe_billing.sql before enabling the Stripe webhook."
            )
        return False, "Supabase entitlement update failed."
    return True, ""


def _resolve_billing_interval(
    price_id: str, *, stripe_config: stripe_billing.StripeBillingConfig
) -> str:
    """Best-effort interval label for analytics only — never raises.

    Read-only comparison against the already-loaded StripeBillingConfig's
    price ids; does not touch modules.stripe_billing's structure (that
    module's entitlement/config rework is owned by a separate change).
    """

    clean = _safe_text(price_id)
    if not clean:
        return ""
    if clean == _safe_text(stripe_config.price_monthly):
        return stripe_billing.MONTHLY
    if clean == _safe_text(stripe_config.price_annual):
        return stripe_billing.ANNUAL
    return ""


def _track_subscription_lifecycle(
    action: dict[str, str], *, stripe_config: stripe_billing.StripeBillingConfig
) -> None:
    """Relaunch analytics for subscription activation / trial / churn.

    Fires only after update_profile_entitlement has durably persisted the
    transition (caller passes the already-confirmed action), on the
    canonical modules.launch_analytics.track_event primitive — same
    fail-soft, never-raise, never-block pattern used by every other call
    site in the app. A tracking failure here must never affect the
    webhook's own HTTP response to Stripe.
    """

    try:
        from modules import launch_analytics

        user_id = _safe_text(action.get("user_id"))
        entitlement = _safe_text(action.get("entitlement")).casefold()
        # `reason` is the raw Stripe event type, optionally suffixed with
        # ":cancel_at_period_end" (see map_stripe_event_to_entitlement) —
        # strip that suffix to get the base event type for branching.
        base_event_type = _safe_text(action.get("reason")).split(":")[0]
        status = _safe_text(action.get("stripe_subscription_status")).casefold()
        event_id = _safe_text(action.get("event_id"))
        state: dict[str, Any] | None = {"auth_session": {"user_id": user_id}} if user_id else None

        if entitlement == "premium" and base_event_type in {
            "checkout.session.completed",
            "customer.subscription.created",
        }:
            interval = _resolve_billing_interval(
                action.get("stripe_price_id", ""), stripe_config=stripe_config
            )
            event_name = "trial_started" if status == "trialing" else "subscribed"
            launch_analytics.track_event(
                event_name,
                props=launch_analytics.build_context_props(
                    state,
                    source_surface="stripe_webhook",
                    extra={"tier": "premium", "interval": interval},
                ),
                once_key=event_id,
                state=state,
            )
        if (
            entitlement == "free"
            and base_event_type in stripe_billing.INACTIVE_ENTITLEMENT_EVENTS
        ):
            launch_analytics.track_event(
                "churned",
                props=launch_analytics.build_context_props(
                    state,
                    source_surface="stripe_webhook",
                    extra={"tier": "premium", "reason": base_event_type},
                ),
                once_key=event_id,
                state=state,
            )
    except Exception:
        pass


def process_verified_stripe_webhook(
    *,
    payload: bytes | str,
    signature: str,
    stripe_config: stripe_billing.StripeBillingConfig,
    supabase_config: SupabaseWebhookConfig,
    request_session: Any = requests,
) -> dict[str, Any]:
    action = stripe_billing.handle_stripe_webhook(payload, signature, config=stripe_config)
    event_id = _safe_text(action.get("event_id"))
    if event_id and _event_id_already_processed(event_id):
        return {
            "ok": True,
            "skipped": True,
            "duplicate": True,
            "error": "",
            "event_id": event_id,
            "action": action,
        }
    entitlement = _safe_text(action.get("entitlement")).casefold()
    if entitlement in {"premium", "front_office"} and stripe_config.billing_mode == "live":
        allowed_prices = {
            _safe_text(stripe_config.price_monthly),
            _safe_text(stripe_config.price_annual),
            _safe_text(stripe_config.price_pro_annual_launch_week),
            _safe_text(stripe_config.price_front_office_annual),
        } - {""}
        event_price = _safe_text(action.get("stripe_price_id"))
        if not allowed_prices or event_price not in allowed_prices:
            # A signed event is necessary but not sufficient to grant paid
            # access: production grants must also belong to an explicitly
            # configured plan for *some* tier.
            return {
                "ok": True,
                "skipped": True,
                "error": "",
                "event_id": event_id,
                "action": {**action, "entitlement": ""},
            }
    if entitlement not in SUPPORTED_ENTITLEMENT_VALUES:
        if event_id:
            _remember_event_id(event_id)
        return {
            "ok": True,
            "skipped": True,
            "error": "",
            "event_id": event_id,
            "action": action,
        }
    ok, error = update_profile_entitlement(
        config=supabase_config,
        action=action,
        request_session=request_session,
    )
    if ok and event_id:
        _remember_event_id(event_id)
    if ok:
        _track_subscription_lifecycle(action, stripe_config=stripe_config)
    return {
        "ok": ok,
        "skipped": False,
        "error": error,
        "event_id": event_id,
        "action": action if ok else {key: action.get(key, "") for key in ("user_id", "entitlement", "reason")},
    }
