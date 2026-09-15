"""RevenueCat billing helpers with an explicit test/live (sandbox/production) boundary.

Mirrors modules/stripe_billing.py's test/live boundary, but for RevenueCat.
RevenueCat webhooks are authenticated with a fixed Authorization header value
(configured by us in the RevenueCat dashboard) rather than an HMAC signature.

Entitlement is never inferred from the event payload's own fields — RevenueCat's
event taxonomy has many edge cases (refunds, billing-issue grace periods,
transfers). Instead every verified event triggers a fresh read of "what is
this customer entitled to right now" via RevenueCat's API, which is
idempotent and self-correcting regardless of event order or duplicate
delivery.
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

from modules import app_config


CONFIG_KEYS = (
    "REVENUECAT_SECRET_KEY",
    "REVENUECAT_PROJECT_ID",
    "REVENUECAT_WEBHOOK_AUTH_TOKEN",
    "REVENUECAT_BILLING_MODE",
    "REVENUECAT_ENTITLEMENT_LOOKUP_KEY",
)

DEFAULT_ENTITLEMENT_LOOKUP_KEY = "premium"


class BillingConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RevenueCatBillingConfig:
    billing_mode: str = "test"
    secret_key: str = ""
    project_id: str = ""
    webhook_auth_token: str = ""
    entitlement_lookup_key: str = DEFAULT_ENTITLEMENT_LOOKUP_KEY

    @property
    def webhook_configured(self) -> bool:
        return bool(self.webhook_auth_token)

    @property
    def api_configured(self) -> bool:
        return bool(self.secret_key and self.project_id)

    @property
    def expected_environment(self) -> str:
        return "PRODUCTION" if self.billing_mode == "live" else "SANDBOX"

    @property
    def redacted(self) -> dict[str, Any]:
        return {
            "webhook_configured": self.webhook_configured,
            "api_configured": self.api_configured,
            "mode": self.billing_mode,
            "expected_environment": self.expected_environment,
        }


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _config_value(key: str, *, environ: dict | None = None, secrets: Any = None) -> str:
    return app_config.config_value(key, environ=environ, secrets=secrets)


def load_revenuecat_config(*, environ: dict | None = None, secrets: Any = None) -> RevenueCatBillingConfig:
    values = {key: _config_value(key, environ=environ, secrets=secrets) for key in CONFIG_KEYS}
    return RevenueCatBillingConfig(
        billing_mode=_safe_text(values["REVENUECAT_BILLING_MODE"]).casefold() or "test",
        secret_key=values["REVENUECAT_SECRET_KEY"],
        project_id=values["REVENUECAT_PROJECT_ID"],
        webhook_auth_token=values["REVENUECAT_WEBHOOK_AUTH_TOKEN"],
        entitlement_lookup_key=(
            _safe_text(values["REVENUECAT_ENTITLEMENT_LOOKUP_KEY"]) or DEFAULT_ENTITLEMENT_LOOKUP_KEY
        ),
    )


def verify_webhook_authorization(authorization_header: str | None, *, config: RevenueCatBillingConfig) -> None:
    if not config.webhook_configured:
        raise BillingConfigurationError("RevenueCat webhook auth token is not configured.")
    provided = _safe_text(authorization_header)
    if not provided or not hmac.compare_digest(provided, config.webhook_auth_token):
        raise BillingConfigurationError("Invalid RevenueCat webhook authorization.")


def parse_webhook_payload(payload: bytes | str) -> dict:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    try:
        data = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise BillingConfigurationError("RevenueCat webhook payload is not valid JSON.") from exc
    event = data.get("event") if isinstance(data, dict) else None
    if not isinstance(event, dict):
        raise BillingConfigurationError("RevenueCat webhook payload is missing an event.")
    return event


def fetch_active_entitlement_lookup_keys(
    app_user_id: str,
    *,
    config: RevenueCatBillingConfig,
    request_session: Any = requests,
) -> set[str]:
    if not config.api_configured:
        raise BillingConfigurationError("RevenueCat API is not configured.")
    customer_id = quote(_safe_text(app_user_id), safe="")
    response = request_session.get(
        f"https://api.revenuecat.com/v2/projects/{config.project_id}/customers/{customer_id}/active_entitlements",
        headers={"Authorization": f"Bearer {config.secret_key}"},
        timeout=15,
    )
    if response.status_code == 404:
        return set()
    if response.status_code >= 400:
        raise BillingConfigurationError("Could not read RevenueCat customer entitlements.")
    data = response.json()
    items = data.get("items") if isinstance(data, dict) else []
    keys: set[str] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        for field in ("lookup_key", "id"):
            value = _safe_text(item.get(field))
            if value:
                keys.add(value)
    return keys


def map_revenuecat_event(
    event: dict,
    *,
    config: RevenueCatBillingConfig,
    request_session: Any = requests,
) -> dict[str, str]:
    event_id = _safe_text(event.get("id"))
    event_type = _safe_text(event.get("type"))
    app_user_id = _safe_text(event.get("app_user_id"))
    environment = _safe_text(event.get("environment")).upper()

    result: dict[str, str] = {
        "event_id": event_id,
        "event_type": event_type,
        "user_id": app_user_id,
        "environment": environment,
        "entitlement": "",
        "reason": event_type,
    }
    event_created_ms = event.get("event_timestamp_ms")
    if event_created_ms is not None:
        try:
            result["event_created_ms"] = str(int(event_created_ms))
        except (TypeError, ValueError):
            pass

    if event_type == "TEST":
        result["reason"] = "test_event"
        return result
    if environment and environment != config.expected_environment:
        result["reason"] = "environment_mismatch"
        return result
    if not app_user_id:
        result["reason"] = "missing_app_user_id"
        return result

    active_keys = fetch_active_entitlement_lookup_keys(app_user_id, config=config, request_session=request_session)
    result["entitlement"] = "premium" if config.entitlement_lookup_key in active_keys else "free"
    return result


def handle_revenuecat_webhook(
    payload: bytes | str,
    authorization_header: str | None,
    *,
    config: RevenueCatBillingConfig,
    request_session: Any = requests,
) -> dict[str, str]:
    verify_webhook_authorization(authorization_header, config=config)
    event = parse_webhook_payload(payload)
    return map_revenuecat_event(event, config=config, request_session=request_session)
