"""Authenticated, durable user-preference helpers."""

from __future__ import annotations

from collections.abc import Mapping

from modules import account_store
from modules import auth_supabase

ONBOARDING_DISMISSED_KEY = "dashboard_orientation_dismissed"


def preference_values(user_settings: Mapping[str, object] | None) -> dict:
    """Return a defensive copy of the persisted JSON settings object."""

    if not isinstance(user_settings, Mapping):
        return {}
    settings = user_settings.get("settings")
    return dict(settings) if isinstance(settings, Mapping) else {}


def onboarding_is_dismissed(user_settings: Mapping[str, object] | None) -> bool:
    return preference_values(user_settings).get(ONBOARDING_DISMISSED_KEY) is True


def with_onboarding_dismissal(
    user_settings: Mapping[str, object] | None,
    *,
    dismissed: bool,
) -> dict:
    """Merge the onboarding preference without replacing unrelated settings."""

    merged = preference_values(user_settings)
    if dismissed:
        merged[ONBOARDING_DISMISSED_KEY] = True
    else:
        merged.pop(ONBOARDING_DISMISSED_KEY, None)
    return {"settings": merged}


def persist_onboarding_preference(
    *,
    config: dict,
    access_token: str,
    user_id: str,
    current_settings: Mapping[str, object] | None,
    dismissed: bool,
) -> tuple[dict, str]:
    """Persist and return the complete sanitized user-settings row."""

    updated = with_onboarding_dismissal(current_settings, dismissed=dismissed)
    payload = account_store.build_user_settings_payload(
        user_id=user_id,
        settings=updated["settings"],
    )
    saved, error = account_store.upsert_user_settings(config, access_token, payload)
    if not saved:
        return dict(current_settings or {}), error
    return payload, ""


def refresh_authenticated_preferences(
    *,
    config: dict,
    session_state: dict,
    force: bool = False,
) -> str:
    """Load preferences once per authenticated session; return a safe error."""

    user_id = auth_supabase.current_user_id(session_state)
    access_token = auth_supabase.current_access_token(session_state)
    if not auth_supabase.is_configured(config) or not user_id or not access_token:
        session_state.pop("account_user_settings", None)
        return ""
    cache_key = f"_supabase_user_settings_loaded_{user_id}"
    if session_state.get(cache_key) and not force:
        return ""
    settings, error = account_store.fetch_user_settings(
        config,
        access_token,
        user_id=user_id,
    )
    if error:
        session_state["account_user_settings_error"] = error
        return error
    session_state["account_user_settings"] = settings
    session_state.pop("account_user_settings_error", None)
    session_state[cache_key] = True
    return ""


def persist_authenticated_onboarding(
    *,
    config: dict,
    session_state: dict,
    dismissed: bool,
) -> str:
    """Persist onboarding for the current account without a session-only fallback."""

    user_id = auth_supabase.current_user_id(session_state)
    access_token = auth_supabase.current_access_token(session_state)
    if not user_id or not access_token:
        return "Authentication is required."
    updated, error = persist_onboarding_preference(
        config=config,
        access_token=access_token,
        user_id=user_id,
        current_settings=session_state.get("account_user_settings"),
        dismissed=dismissed,
    )
    if not error:
        session_state["account_user_settings"] = updated
    return error
