from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Mapping


LOCAL_SECRETS_PATH = Path("local_secrets") / "secrets.toml"
LOCAL_BASE_URL = "http://localhost:8501"
PRODUCTION_BASE_URL = "https://app.fantasygmlab.com"
PRODUCTION_MARKETING_URL = "https://fantasygmlab.com"
TRUE_CONFIG_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_CONFIG_VALUES = frozenset({"", "0", "false", "no", "off"})

WEB_APP_CONFIG_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_BILLING_MODE",
    "STRIPE_PRICE_MONTHLY",
    "STRIPE_PRICE_ANNUAL",
    "STRIPE_CUSTOMER_PORTAL_RETURN_URL",
    "STRIPE_CHECKOUT_SUCCESS_URL",
    "STRIPE_CHECKOUT_CANCEL_URL",
    "APP_BASE_URL",
    "DYNASTYGM_BUILD",
    "DYNASTYGM_SHOW_EXPERIMENTAL",
    "DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY",
    "DYNASTYGM_EXPERIMENTAL_GM_TARGETS",
    "DYNASTYGM_EXPERIMENTAL_SHARE_CARDS",
    "DYNASTYGM_LAUNCH_ANALYTICS",
)

BACKEND_ONLY_CONFIG_KEYS = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "STRIPE_WEBHOOK_SECRET",
)

OPTIONAL_DEV_CONFIG_KEYS = (
    "DYNASTYGM_PREMIUM_OVERRIDE",
    "DYNASTYGM_DEBUG_AUTH",
    "DYNASTYGM_DEBUG_PERF",
    "DYNASTYGM_DEBUG_UI",
    "DYNASTYGM_DEV_RELOAD_MODULES",
    "DYNASTYGM_SHOW_DEV_DESTINATIONS",
)

# Required on managed Streamlit hosts. Absence must not look like a local guest install.
MANAGED_WEB_REQUIRED_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
)

# Must never be present on the Streamlit web process (webhook service only).
MANAGED_WEB_FORBIDDEN_KEYS = BACKEND_ONLY_CONFIG_KEYS

# Founder ops visibility. Intentionally separate from customer-unsafe debug locks so
# founders can enable the ops dashboard on Render without unlocking Performance Report.
FOUNDER_OPS_CONFIG_KEY = "DYNASTYGM_FOUNDER_OPS"

# Explicit escape hatch only. Never set on customer-facing Render services.
ALLOW_PROD_DEBUG_KEY = "DYNASTYGM_ALLOW_PROD_DEBUG"


class ProductionConfigurationError(RuntimeError):
    """Managed-host configuration is incomplete or unsafe. Message must never include secret values."""


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _url_is_loopback(url: str) -> bool:
    text = _safe_text(url).casefold()
    if not text:
        return False
    return any(
        marker in text
        for marker in (
            "://localhost",
            "://127.0.0.1",
            "://[::1]",
            "://0.0.0.0",
        )
    )


def _secret_lookup(secrets: Any, key: str) -> str:
    if secrets is None:
        return ""
    try:
        value = secrets.get(key)
    except Exception:
        return ""
    if _safe_text(value):
        return _safe_text(value)
    for group_name in ("app", "supabase", "stripe", "backend_only", "local_flags"):
        try:
            group = secrets.get(group_name)
        except Exception:
            group = None
        if isinstance(group, dict) and _safe_text(group.get(key)):
            return _safe_text(group.get(key))
    return ""


def load_local_secrets(path: str | Path = LOCAL_SECRETS_PATH) -> dict[str, Any]:
    secrets_path = Path(path)
    if not secrets_path.exists() or not secrets_path.is_file():
        return {}
    try:
        with secrets_path.open("rb") as handle:
            payload = tomllib.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _nested_config_value(payload: dict[str, Any], key: str) -> str:
    direct = _safe_text(payload.get(key))
    if direct:
        return direct
    for group_name in ("app", "supabase", "stripe", "backend_only", "local_flags"):
        group = payload.get(group_name)
        if isinstance(group, dict):
            value = _safe_text(group.get(key))
            if value:
                return value
    return ""


def config_value(
    key: str,
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
    local_secrets_path: str | Path = LOCAL_SECRETS_PATH,
) -> str:
    env = environ if environ is not None else os.environ
    env_value = _safe_text(env.get(key))
    if env_value:
        return env_value

    streamlit_value = _secret_lookup(secrets, key)
    if streamlit_value:
        return streamlit_value

    local_value = _nested_config_value(load_local_secrets(local_secrets_path), key)
    if local_value:
        return local_value
    return ""



def config_bool(
    key: str,
    *,
    default: bool = False,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
    local_secrets_path: str | Path = LOCAL_SECRETS_PATH,
) -> bool:
    """Read a boolean flag at call time from environment, Streamlit secrets, or local config."""
    raw = config_value(
        key,
        environ=environ,
        secrets=secrets,
        local_secrets_path=local_secrets_path,
    ).casefold()
    if raw in TRUE_CONFIG_VALUES:
        return True
    if raw in FALSE_CONFIG_VALUES:
        return False
    return bool(default)


def is_managed_cloud_host(*, environ: Mapping[str, Any] | None = None) -> bool:
    """True on Render (and similar) managed hosts where customer traffic is served."""

    env = os.environ if environ is None else environ
    render_flag = _safe_text(env.get("RENDER")).casefold()
    if render_flag in TRUE_CONFIG_VALUES:
        return True
    if _safe_text(env.get("RENDER_SERVICE_ID")):
        return True
    if _safe_text(env.get("RENDER_EXTERNAL_URL")):
        return True
    return False


def customer_unsafe_debug_allowed(
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
    local_secrets_path: str | Path = LOCAL_SECRETS_PATH,
) -> bool:
    """Allow developer diagnostics / overrides.

    Local and CI remain opt-in via normal debug flags. On managed cloud hosts those
    customer-unsafe tools stay off unless ``DYNASTYGM_ALLOW_PROD_DEBUG`` is explicitly set.
    """

    if not is_managed_cloud_host(environ=environ):
        return True
    return config_bool(
        ALLOW_PROD_DEBUG_KEY,
        environ=environ,
        secrets=secrets,
        local_secrets_path=local_secrets_path,
    )

def managed_web_config_issues(
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
    local_secrets_path: str | Path = LOCAL_SECRETS_PATH,
) -> tuple[str, ...]:
    """Return redacted issue codes for the Streamlit web process on managed hosts.

    Empty when not a managed host, or when required production config is present
    and backend-only secrets are absent. Does not call providers.
    """

    if not is_managed_cloud_host(environ=environ):
        return ()
    issues: list[str] = []
    for key in MANAGED_WEB_REQUIRED_KEYS:
        if not config_value(
            key,
            environ=environ,
            secrets=secrets,
            local_secrets_path=local_secrets_path,
        ):
            issues.append(f"missing_{key.lower()}")
    configured_base = config_value(
        "APP_BASE_URL",
        environ=environ,
        secrets=secrets,
        local_secrets_path=local_secrets_path,
    )
    if configured_base and _url_is_loopback(configured_base):
        issues.append("app_base_url_loopback")
    for key in MANAGED_WEB_FORBIDDEN_KEYS:
        if config_value(
            key,
            environ=environ,
            secrets=secrets,
            local_secrets_path=local_secrets_path,
        ):
            issues.append(f"forbidden_{key.lower()}_on_web")
    return tuple(issues)


def enforce_managed_web_config(
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
    local_secrets_path: str | Path = LOCAL_SECRETS_PATH,
) -> None:
    """Fail closed on managed hosts when required config is missing or unsafe.

    Local/CI remain unconstrained so contributors can run without credentials.
    """

    issues = managed_web_config_issues(
        environ=environ,
        secrets=secrets,
        local_secrets_path=local_secrets_path,
    )
    if not issues:
        return
    raise ProductionConfigurationError(
        "Production configuration is incomplete or unsafe ("
        + ", ".join(issues)
        + "). Set required Render env vars for the Streamlit service and keep "
        "webhook-only secrets off this process. The app will not run as a guest/dev install."
    )


def app_base_url(
    *,
    environ: dict | None = None,
    secrets: Any = None,
    local_secrets_path: str | Path = LOCAL_SECRETS_PATH,
) -> str:
    configured = config_value(
        "APP_BASE_URL",
        environ=environ,
        secrets=secrets,
        local_secrets_path=local_secrets_path,
    ).rstrip("/")
    if configured:
        return configured
    # Managed hosts must never fall back to localhost (auth/Stripe return URLs).
    if is_managed_cloud_host(environ=environ):
        return PRODUCTION_BASE_URL
    return LOCAL_BASE_URL


def stripe_return_url(path: str, *, base_url: str = "") -> str:
    clean_base = _safe_text(base_url).rstrip("/") or LOCAL_BASE_URL
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{clean_base}{clean_path}"


def redacted_config_status(
    *,
    environ: dict | None = None,
    secrets: Any = None,
    local_secrets_path: str | Path = LOCAL_SECRETS_PATH,
) -> dict[str, bool | str]:
    return {
        "supabase_configured": bool(config_value("SUPABASE_URL", environ=environ, secrets=secrets, local_secrets_path=local_secrets_path))
        and bool(config_value("SUPABASE_ANON_KEY", environ=environ, secrets=secrets, local_secrets_path=local_secrets_path)),
        "stripe_checkout_configured": bool(config_value("STRIPE_SECRET_KEY", environ=environ, secrets=secrets, local_secrets_path=local_secrets_path))
        and bool(config_value("STRIPE_PRICE_MONTHLY", environ=environ, secrets=secrets, local_secrets_path=local_secrets_path))
        and bool(config_value("STRIPE_PRICE_ANNUAL", environ=environ, secrets=secrets, local_secrets_path=local_secrets_path)),
        "stripe_webhook_configured": bool(config_value("STRIPE_WEBHOOK_SECRET", environ=environ, secrets=secrets, local_secrets_path=local_secrets_path)),
        "backend_service_role_configured": bool(config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets, local_secrets_path=local_secrets_path)),
        "app_base_url": app_base_url(environ=environ, secrets=secrets, local_secrets_path=local_secrets_path),
        "managed_web_ok": not bool(
            managed_web_config_issues(
                environ=environ,
                secrets=secrets,
                local_secrets_path=local_secrets_path,
            )
        ),
    }
