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


def _lookup_secret(secrets: Any, key: str) -> Any:
    return app_config.config_value(key, secrets=secrets)


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
    base = config.url.rstrip("/")
    return f"{base}/rest/v1/profiles?user_id=eq.{_safe_text(user_id)}"


def build_profile_entitlement_payload(action: dict[str, str]) -> dict[str, str]:
    entitlement = _safe_text(action.get("entitlement")).casefold()
    if entitlement and entitlement not in {"free", "premium"}:
        raise StripeWebhookUpdateError("Stripe event did not produce a supported entitlement update.")
    payload: dict[str, str] = {
        "premium_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if entitlement in {"free", "premium"}:
        payload["entitlement"] = entitlement
    optional_fields = {
        "stripe_customer_id": action.get("stripe_customer_id"),
        "stripe_subscription_id": action.get("stripe_subscription_id"),
        "stripe_subscription_status": action.get("stripe_subscription_status"),
        "stripe_price_id": action.get("stripe_price_id"),
    }
    for key, value in optional_fields.items():
        clean_value = _safe_text(value)
        if clean_value:
            payload[key] = clean_value
    if "entitlement" not in payload and len(payload) == 1:
        # Only timestamp — treat as no-op skip rather than a failed update.
        raise StripeWebhookUpdateError("noop")
    return payload


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
                "entitlement",
            )
        ):
            return False, (
                "Supabase profiles billing columns are missing. "
                "Run docs/supabase_stripe_billing.sql before enabling the Stripe webhook."
            )
        return False, "Supabase entitlement update failed."
    return True, ""


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
    if entitlement not in {"free", "premium"}:
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
    return {
        "ok": ok,
        "skipped": False,
        "error": error,
        "event_id": event_id,
        "action": action if ok else {key: action.get(key, "") for key in ("user_id", "entitlement", "reason")},
    }
