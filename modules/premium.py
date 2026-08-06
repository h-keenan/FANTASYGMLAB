from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

import streamlit as st

from modules import app_config


FREE = "free"
PREMIUM = "premium"
PREMIUM_OVERRIDE_ENV = "DYNASTYGM_PREMIUM_OVERRIDE"
PREMIUM_OVERRIDE_SECRET = "DYNASTYGM_PREMIUM_OVERRIDE"
DEBUG_AUTH_ENV = "DYNASTYGM_DEBUG_AUTH"
DEBUG_AUTH_SECRET = "DYNASTYGM_DEBUG_AUTH"
ENTITLEMENT_FIELD = "entitlement"


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _safe_text(value).casefold() in {"1", "true", "yes", "on", "premium", "pro", "paid"}


def _lookup_secret(secrets: Any, key: str) -> Any:
    return app_config.config_value(key, secrets=secrets)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def premium_override_enabled(*, environ: dict | None = None, secrets: Any = None) -> bool:
    """Local/dev-only premium override. Never store payment data here."""
    if not app_config.customer_unsafe_debug_allowed(environ=environ, secrets=secrets):
        return False
    return _truthy(app_config.config_value(PREMIUM_OVERRIDE_ENV, environ=environ, secrets=secrets))


def debug_auth_enabled(*, environ: dict | None = None, secrets: Any = None) -> bool:
    """Developer-only auth/entitlement diagnostics gate."""
    if not app_config.customer_unsafe_debug_allowed(environ=environ, secrets=secrets):
        return False
    return _truthy(app_config.config_value(DEBUG_AUTH_ENV, environ=environ, secrets=secrets))


def _extract_settings(account: dict | None = None, user_settings: dict | None = None) -> dict:
    merged: dict[str, Any] = {}
    for source in (account, user_settings):
        if not _is_mapping(source):
            continue
        nested = source.get("settings")
        if _is_mapping(nested):
            merged.update(nested)
        merged.update(source)
    return merged


def _session_sources(session_state: Any) -> dict[str, dict]:
    state = session_state if _is_mapping(session_state) else {}
    auth_session = state.get("auth_session") if _is_mapping(state.get("auth_session")) else {}
    auth_user = state.get("auth_user") if _is_mapping(state.get("auth_user")) else {}
    has_authenticated_user = bool(_safe_text(auth_session.get("user_id") or auth_user.get("id")))
    account_profile = (
        state.get("account_profile")
        if has_authenticated_user and _is_mapping(state.get("account_profile"))
        else {}
    )
    account_user_settings = (
        state.get("account_user_settings")
        if has_authenticated_user and _is_mapping(state.get("account_user_settings"))
        else {}
    )
    return {
        "auth_session": auth_session,
        "auth_user": auth_user,
        "account_profile": account_profile,
        "account_user_settings": account_user_settings,
    }


def get_entitlement_debug(
    account: dict | None = None,
    user_settings: dict | None = None,
    *,
    account_profile: dict | None = None,
    session_state: dict | None = None,
    environ: dict | None = None,
    secrets: Any = None,
) -> dict[str, Any]:
    if premium_override_enabled(environ=environ, secrets=secrets):
        return {
            "entitlement": PREMIUM,
            "is_premium": True,
            "source": "dev_override",
            "source_field": PREMIUM_OVERRIDE_ENV,
            "raw_value": "enabled",
            "reason": "dev_override",
        }

    source_name = ""
    canonical_value = ""
    fallback_settings: dict[str, Any] = {}
    profile_status = ""
    profile_error = ""

    if _is_mapping(account_profile) and bool(account_profile):
        profile = _extract_settings(account_profile, {})
        fallback_settings.update(profile)
        if profile.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(profile.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account_profile.entitlement"
    elif _is_mapping(session_state):
        sources = _session_sources(session_state)
        auth_user = _extract_settings(sources["auth_user"], {})
        profile = _extract_settings(sources["account_profile"], {})
        account_settings = _extract_settings(sources["account_user_settings"], {})
        fallback_settings.update(auth_user)
        fallback_settings.update(account_settings)
        fallback_settings.update(profile)
        if profile.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(profile.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account_profile.entitlement"
        elif auth_user.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(auth_user.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "auth_user.entitlement"
        elif account_settings.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(account_settings.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account_user_settings.entitlement"
        profile_status = _safe_text(session_state.get("account_profile_status"))
        profile_error = _safe_text(session_state.get("account_profile_error"))
    else:
        account_settings = _extract_settings(account, {})
        user_setting_values = _extract_settings(user_settings, {})
        fallback_settings.update(user_setting_values)
        fallback_settings.update(account_settings)
        if account_settings.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(account_settings.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account.entitlement"
        elif user_setting_values.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(user_setting_values.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "user_settings.entitlement"

    if canonical_value:
        is_premium = canonical_value == PREMIUM
        return {
            "entitlement": PREMIUM if is_premium else FREE,
            "is_premium": is_premium,
            "source": source_name,
            "source_field": source_name,
            "raw_value": canonical_value,
            "reason": source_name,
            "profile_status": profile_status,
            "profile_error": profile_error,
        }

    tier = _safe_text(
        fallback_settings.get("subscription_tier")
        or fallback_settings.get("plan")
        or fallback_settings.get("tier")
    ).casefold()
    if tier in {"premium", "pro", "paid"}:
        return {
            "entitlement": PREMIUM,
            "is_premium": True,
            "source": "fallback_field",
            "source_field": "plan/tier",
            "raw_value": tier,
            "reason": "fallback_field",
            "profile_status": profile_status,
            "profile_error": profile_error,
        }

    for key in ("is_premium", "premium", "premium_enabled", "has_premium"):
        if _truthy(fallback_settings.get(key)):
            return {
                "entitlement": PREMIUM,
                "is_premium": True,
                "source": "fallback_field",
                "source_field": key,
                "raw_value": _safe_text(fallback_settings.get(key)),
                "reason": "fallback_field",
                "profile_status": profile_status,
                "profile_error": profile_error,
            }

    reason = "default_free"
    if profile_status == "missing":
        reason = "profile_missing"
    elif profile_status == "error":
        reason = "profile_error"
    return {
        "entitlement": FREE,
        "is_premium": False,
        "source": reason,
        "source_field": "",
        "raw_value": "",
        "reason": reason,
        "profile_status": profile_status,
        "profile_error": profile_error,
    }


def effective_entitlement(
    *,
    account_profile: dict | None = None,
    session_state: dict | None = None,
    environ: dict | None = None,
    secrets: Any = None,
) -> str:
    """Resolve the product entitlement from one authoritative source chain.

    Development override wins. In production, only the authenticated Supabase
    profile may grant Premium; absent or non-Premium profile data resolves Free.
    """
    if premium_override_enabled(environ=environ, secrets=secrets):
        return PREMIUM

    profile = account_profile if _is_mapping(account_profile) else None
    if profile is None and _is_mapping(session_state):
        profile = _session_sources(session_state).get("account_profile")
    if not _is_mapping(profile) or not profile:
        return FREE

    resolved = get_entitlement_debug(
        account_profile=profile,
        environ={},
        secrets=None,
    )
    return PREMIUM if resolved.get("entitlement") == PREMIUM else FREE


def get_user_entitlement(
    account: dict | None = None,
    user_settings: dict | None = None,
    *,
    account_profile: dict | None = None,
    session_state: dict | None = None,
    environ: dict | None = None,
    secrets: Any = None,
) -> str:
    return str(
        get_entitlement_debug(
            account,
            user_settings,
            account_profile=account_profile,
            session_state=session_state,
            environ=environ,
            secrets=secrets,
        ).get("entitlement", FREE)
    )


def is_premium_user(*args, **kwargs) -> bool:
    return get_user_entitlement(*args, **kwargs) == PREMIUM


def premium_enabled(*args, **kwargs) -> bool:
    return is_premium_user(*args, **kwargs)


def premium_badge_html(label: str = "Premium") -> str:
    return f"<span class='premium-badge'>{escape(_safe_text(label, 'Premium'))}</span>"


def render_premium_badge(label: str = "Premium") -> None:
    st.markdown(premium_badge_html(label), unsafe_allow_html=True)


def premium_lock_html(
    title: str,
    body: str = "",
    *,
    feature: str = "",
    cta: str = "Unlock with Premium",
) -> str:
    title_text = _safe_text(title, "Premium feature")
    body_text = _safe_text(body, "Upgrade later to unlock this deeper analysis.")
    feature_text = _safe_text(feature, "Premium")
    cta_text = _safe_text(cta, "Unlock with Premium")
    return (
        "<div class='premium-lock dg-preset-secondary'>"
        "<div class='premium-lock-top'>"
        f"{premium_badge_html(feature_text)}"
        f"<span class='premium-lock-cta'>{escape(cta_text)}</span>"
        "</div>"
        f"<div class='premium-lock-title'>{escape(title_text)}</div>"
        f"<div class='premium-lock-body'>{escape(body_text)}</div>"
        "</div>"
    )


def render_premium_lock(
    title: str,
    body: str = "",
    *,
    feature: str = "",
    cta: str = "Unlock with Premium",
) -> None:
    st.markdown(
        premium_lock_html(title, body, feature=feature, cta=cta),
        unsafe_allow_html=True,
    )
