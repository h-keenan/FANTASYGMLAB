from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from modules import stripe_billing


class StripeWebhookUpdateError(RuntimeError):
    pass


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
    if secrets is None:
        return None
    try:
        return secrets.get(key)
    except Exception:
        return None


def _config_value(key: str, *, environ: dict | None = None, secrets: Any = None) -> str:
    env = environ if isinstance(environ, dict) else os.environ
    return _safe_text(env.get(key) or _lookup_secret(secrets, key))


def load_supabase_webhook_config(*, environ: dict | None = None, secrets: Any = None) -> SupabaseWebhookConfig:
    return SupabaseWebhookConfig(
        url=_config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=_config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def build_profile_entitlement_payload(action: dict[str, str]) -> dict[str, str]:
    entitlement = _safe_text(action.get("entitlement")).casefold()
    if entitlement not in {"free", "premium"}:
        raise StripeWebhookUpdateError("Stripe event did not produce a supported entitlement update.")
    payload = {
        "entitlement": entitlement,
        "premium_updated_at": datetime.now(timezone.utc).isoformat(),
    }
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
    return payload


def _profile_update_url(config: SupabaseWebhookConfig, user_id: str) -> str:
    base = config.url.rstrip("/")
    return f"{base}/rest/v1/profiles?user_id=eq.{_safe_text(user_id)}"


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
        return False, str(exc)
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
    ok, error = update_profile_entitlement(
        config=supabase_config,
        action=action,
        request_session=request_session,
    )
    return {
        "ok": ok,
        "error": error,
        "action": action if ok else {key: action.get(key, "") for key in ("user_id", "entitlement", "reason")},
    }
