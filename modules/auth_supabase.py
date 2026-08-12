from __future__ import annotations

import os
import time
from typing import Any

import requests

from modules import app_config
from modules import auth_restore_lifecycle
from modules import performance
from modules import session_integrity


AUTH_USER_KEY = "auth_user"
AUTH_SESSION_KEY = "auth_session"
AUTH_EMAIL_KEY = "auth_email"
ACCOUNT_MODE_KEY = "account_mode"
DURABLE_AUTH_STORAGE_KEY = "dynastygm_supabase_auth_v2"
DURABLE_AUTH_LEGACY_STORAGE_KEYS = ("dynastygm_supabase_auth",)
DURABLE_AUTH_PENDING_SAVE_KEY = "_supabase_durable_auth_pending_save"
DURABLE_AUTH_PENDING_CLEAR_KEY = "_supabase_durable_auth_pending_clear"
CONFIRMATION_REQUIRED_KEY = "account_confirmation_required"
CONFIRMATION_EMAIL_KEY = "account_confirmation_email"
CONFIRMATION_RESEND_TS_KEY = "account_confirmation_resend_ts"
CONFIRMATION_RESEND_COOLDOWN_SECONDS = 60


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _secret_lookup(secrets: Any, key: str) -> str:
    return app_config.config_value(key, secrets=secrets)


def get_supabase_config(*, secrets: Any = None, environ: dict | None = None) -> dict:
    url = app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets)
    anon_key = app_config.config_value("SUPABASE_ANON_KEY", environ=environ, secrets=secrets)
    return {
        "enabled": bool(url and anon_key),
        "url": url.rstrip("/"),
        "anon_key": anon_key,
    }


def auth_headers(config: dict, access_token: str = "") -> dict:
    token = _safe_text(access_token) or _safe_text(config.get("anon_key"))
    return {
        "apikey": _safe_text(config.get("anon_key")),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def is_configured(config: dict | None) -> bool:
    return bool(config and config.get("enabled") and config.get("url") and config.get("anon_key"))


def _safe_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    message = (
        payload.get("msg")
        or payload.get("message")
        or payload.get("error_description")
        or payload.get("error")
    )
    code = _safe_text(payload.get("error_code") or payload.get("code"))
    text = _safe_text(message, "Supabase request failed.")
    if code and code.casefold() not in text.casefold():
        return f"{text} [{code}]"
    return text


def classify_auth_error(
    error: str,
    *,
    status_code: int | None = None,
    exception_type: str = "",
) -> dict[str, str]:
    """Map provider failures to safe UX categories (no secrets)."""

    text = _safe_text(error).casefold()
    exc = _safe_text(exception_type).casefold()
    category = "provider_error"
    user_message = "Account service is temporarily unavailable. Try again."

    if not text or "not configured" in text:
        category = "not_configured"
        user_message = "Accounts are not configured yet. Continue as a guest."
    elif any(
        marker in text or marker in exc
        for marker in (
            "could not reach",
            "name or service not known",
            "nameresolutionerror",
            "failed to resolve",
            "connectionerror",
            "timed out",
            "timeout",
            "unreachable",
        )
    ):
        category = "provider_unreachable"
        user_message = "Account service is temporarily unavailable. Try again."
    elif auth_error_requires_email_confirmation(error):
        category = "email_confirmation"
        user_message = "Check your email to finish creating your account."
    elif any(
        marker in text
        for marker in (
            "already been registered",
            "already registered",
            "user_already_exists",
            "email_exists",
            "already exists",
        )
    ):
        category = "duplicate_user"
        user_message = "An account already exists for that email. Sign in instead."
    elif any(
        marker in text
        for marker in (
            "password",
            "weak_password",
            "at least",
            "too short",
            "characters",
        )
    ) and "email" not in text[:20]:
        category = "invalid_password"
        # Prefer provider wording when it already states a requirement.
        cleaned = _safe_text(error)
        user_message = (
            cleaned
            if "password" in cleaned.casefold()
            else "Password does not meet the requirements. Use at least 6 characters."
        )
    elif any(marker in text for marker in ("valid email", "invalid email", "email address")):
        category = "invalid_email"
        user_message = "Enter a valid email address."
    elif any(marker in text for marker in ("rate limit", "too many", "over_request")):
        category = "rate_limited"
        user_message = "Too many attempts. Wait a moment and try again."
    elif status_code == 422 or "validation" in text:
        category = "validation"
        user_message = "Check your email and password, then try again."

    code = ""
    if "[" in _safe_text(error) and _safe_text(error).endswith("]"):
        code = _safe_text(error)[_safe_text(error).rfind("[") + 1 : -1]

    return {
        "category": category,
        "user_message": user_message,
        "error_code": code,
        "message_category": category,
    }


def signup_user_message(error: str) -> str:
    return classify_auth_error(error)["user_message"]


def signin_user_message(error: str) -> str:
    classified = classify_auth_error(error)
    if classified["category"] == "email_confirmation":
        return "Confirm your email, then sign in."
    if classified["category"] in {"provider_unreachable", "not_configured", "rate_limited"}:
        return classified["user_message"]
    return "Could not sign in with that email and password."


def log_auth_operation_diagnostic(
    *,
    operation: str,
    category: str,
    status_code: int | None = None,
    error_code: str = "",
    duration_ms: float | None = None,
    auth_user_created: bool | None = None,
    profile_bootstrap_ran: bool | None = None,
    durable_session_write: bool | None = None,
) -> None:
    """Diagnostics-only structured auth event — never logs email/tokens/bodies."""

    payload = {
        "kind": "auth_operation",
        "auth_operation": _safe_text(operation, "unknown")[:32],
        "result_category": _safe_text(category, "unknown")[:48],
        "http_status": status_code,
        "error_code": _safe_text(error_code)[:64],
        "duration_ms": None if duration_ms is None else round(float(duration_ms), 1),
        "auth_user_created": auth_user_created,
        "profile_bootstrap_ran": profile_bootstrap_ran,
        "durable_session_write": durable_session_write,
    }
    try:
        print(f"DYNASTYGM_AUTH {payload}", flush=True)
    except Exception:
        pass


def sign_up(config: dict, email: str, password: str) -> tuple[dict | None, str]:
    if not is_configured(config):
        log_auth_operation_diagnostic(
            operation="signup",
            category="not_configured",
            auth_user_created=False,
            profile_bootstrap_ran=False,
            durable_session_write=False,
        )
        return None, "Accounts are not configured."
    clean_email = _safe_text(email)
    clean_password = _safe_text(password)
    if not clean_email or "@" not in clean_email:
        log_auth_operation_diagnostic(
            operation="signup",
            category="invalid_email",
            auth_user_created=False,
        )
        return None, "Enter a valid email address."
    if len(clean_password) < 6:
        log_auth_operation_diagnostic(
            operation="signup",
            category="invalid_password",
            auth_user_created=False,
        )
        return None, "Password must be at least 6 characters."
    started = time.perf_counter()
    status_code: int | None = None
    try:
        with performance.time_block("supabase_auth_signup", category="supabase"):
            response = requests.post(
                f"{config['url']}/auth/v1/signup",
                headers=auth_headers(config),
                json={"email": clean_email, "password": clean_password},
                timeout=15,
            )
        status_code = int(response.status_code)
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        classified = classify_auth_error(
            "Could not reach Supabase Auth.",
            exception_type=type(exc).__name__,
        )
        log_auth_operation_diagnostic(
            operation="signup",
            category=classified["category"],
            duration_ms=duration_ms,
            auth_user_created=False,
            profile_bootstrap_ran=False,
            durable_session_write=False,
        )
        return None, "Could not reach Supabase Auth."
    duration_ms = (time.perf_counter() - started) * 1000
    if response.status_code >= 400:
        error = _safe_error(response)
        classified = classify_auth_error(error, status_code=status_code)
        log_auth_operation_diagnostic(
            operation="signup",
            category=classified["category"],
            status_code=status_code,
            error_code=classified.get("error_code", ""),
            duration_ms=duration_ms,
            auth_user_created=False,
            profile_bootstrap_ran=False,
            durable_session_write=False,
        )
        return None, error
    payload = response.json()
    session = session_from_auth_payload(payload if isinstance(payload, dict) else {})
    created = bool(session.get("user_id"))
    confirmation = signup_requires_email_confirmation(payload if isinstance(payload, dict) else {})
    log_auth_operation_diagnostic(
        operation="signup",
        category="email_confirmation" if confirmation else "success",
        status_code=status_code,
        duration_ms=duration_ms,
        auth_user_created=created,
        profile_bootstrap_ran=False,
        durable_session_write=False,
    )
    return payload, ""


def sign_in(config: dict, email: str, password: str) -> tuple[dict | None, str]:
    if not is_configured(config):
        return None, "Accounts are not configured."
    started = time.perf_counter()
    status_code: int | None = None
    try:
        with performance.time_block("supabase_auth_signin", category="supabase"):
            response = requests.post(
                f"{config['url']}/auth/v1/token?grant_type=password",
                headers=auth_headers(config),
                json={"email": email, "password": password},
                timeout=15,
            )
        status_code = int(response.status_code)
    except Exception as exc:
        classified = classify_auth_error(
            "Could not reach Supabase Auth.",
            exception_type=type(exc).__name__,
        )
        log_auth_operation_diagnostic(
            operation="signin",
            category=classified["category"],
            duration_ms=(time.perf_counter() - started) * 1000,
            auth_user_created=False,
        )
        return None, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        error = _safe_error(response)
        classified = classify_auth_error(error, status_code=status_code)
        log_auth_operation_diagnostic(
            operation="signin",
            category=classified["category"],
            status_code=status_code,
            error_code=classified.get("error_code", ""),
            duration_ms=(time.perf_counter() - started) * 1000,
            auth_user_created=False,
        )
        return None, error
    log_auth_operation_diagnostic(
        operation="signin",
        category="success",
        status_code=status_code,
        duration_ms=(time.perf_counter() - started) * 1000,
        auth_user_created=True,
    )
    return response.json(), ""


def resend_signup_confirmation(config: dict, email: str) -> tuple[bool, str]:
    if not is_configured(config):
        return False, "Accounts are not configured."
    clean_email = _safe_text(email)
    if not clean_email:
        return False, "Enter your email address before requesting another confirmation email."
    try:
        with performance.time_block("supabase_auth_resend_confirmation", category="supabase"):
            response = requests.post(
                f"{config['url']}/auth/v1/resend",
                headers=auth_headers(config),
                json={"type": "signup", "email": clean_email},
                timeout=15,
            )
    except Exception:
        return False, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return False, _safe_error(response)
    return True, ""


def sign_out(config: dict, access_token: str) -> str:
    if not is_configured(config) or not access_token:
        return ""
    try:
        with performance.time_block("supabase_auth_logout", category="supabase"):
            response = requests.post(
                f"{config['url']}/auth/v1/logout",
                headers=auth_headers(config, access_token),
                timeout=15,
            )
    except Exception:
        return "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return _safe_error(response)
    return ""


def refresh_auth_session(config: dict, refresh_token: str) -> tuple[dict | None, str]:
    if not is_configured(config):
        return None, "Accounts are not configured."
    token = _safe_text(refresh_token)
    if not token:
        return None, "No refresh token is available."
    try:
        with performance.time_block("supabase_auth_refresh", category="supabase"):
            response = requests.post(
                f"{config['url']}/auth/v1/token?grant_type=refresh_token",
                headers=auth_headers(config),
                json={"refresh_token": token},
                timeout=15,
            )
    except Exception:
        return None, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return None, _safe_error(response)
    return response.json(), ""


def session_from_auth_payload(payload: dict | None) -> dict:
    data = payload if isinstance(payload, dict) else {}
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    access_token = _safe_text(data.get("access_token"))
    refresh_token = _safe_text(data.get("refresh_token"))
    expires_at = data.get("expires_at")
    expires_in = data.get("expires_in")
    email = _safe_text(user.get("email") or data.get("email"))
    user_id = _safe_text(user.get("id") or data.get("id") or data.get("user_id"))
    return {
        "user": user,
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "expires_in": expires_in,
        "token_type": _safe_text(data.get("token_type"), "bearer"),
    }


def signup_requires_email_confirmation(payload: dict | None) -> bool:
    session = session_from_auth_payload(payload)
    user = session.get("user") if isinstance(session.get("user"), dict) else {}
    return bool(user) and not bool(session.get("access_token"))


def auth_error_requires_email_confirmation(error: str) -> bool:
    text = _safe_text(error).casefold()
    confirmation_markers = (
        "email not confirmed",
        "email_not_confirmed",
        "not confirmed",
        "confirm your email",
        "email confirmation",
    )
    return any(marker in text for marker in confirmation_markers)


def mark_confirmation_required(session_state: dict, email: str = "") -> None:
    session_state[CONFIRMATION_REQUIRED_KEY] = True
    if _safe_text(email):
        session_state[CONFIRMATION_EMAIL_KEY] = _safe_text(email)


def clear_confirmation_required(session_state: dict) -> None:
    for key in (CONFIRMATION_REQUIRED_KEY, CONFIRMATION_EMAIL_KEY, CONFIRMATION_RESEND_TS_KEY):
        session_state.pop(key, None)


def current_auth_session(session_state: dict) -> dict:
    session = session_state.get(AUTH_SESSION_KEY)
    return session if isinstance(session, dict) else {}


def current_user_id(session_state: dict) -> str:
    session = current_auth_session(session_state)
    user = session_state.get(AUTH_USER_KEY)
    user_dict = user if isinstance(user, dict) else {}
    return _safe_text(session.get("user_id") or user_dict.get("id"))


def current_access_token(session_state: dict) -> str:
    return _safe_text(current_auth_session(session_state).get("access_token"))


def _normalized_expires_at(value: Any, *, expires_in: Any = None, now: int | None = None) -> int:
    try:
        expires_at = int(float(value))
    except Exception:
        expires_at = 0
    if expires_at > 0:
        return expires_at
    try:
        ttl = int(float(expires_in))
    except Exception:
        ttl = 0
    if ttl > 0:
        return int(now or time.time()) + ttl
    return 0


def access_token_expired(session: dict, *, now: int | None = None, skew_seconds: int = 60) -> bool:
    expires_at = _normalized_expires_at(
        session.get("expires_at"),
        expires_in=session.get("expires_in"),
        now=now,
    )
    if expires_at <= 0:
        return False
    return expires_at <= int(now or time.time()) + int(skew_seconds)


def durable_auth_payload(payload_or_session: dict | None, *, now: int | None = None) -> dict:
    session = session_from_auth_payload(payload_or_session)
    expires_at = _normalized_expires_at(
        session.get("expires_at"),
        expires_in=session.get("expires_in"),
        now=now,
    )
    return {
        "user": session.get("user") if isinstance(session.get("user"), dict) else {},
        "user_id": _safe_text(session.get("user_id")),
        "email": _safe_text(session.get("email")),
        "access_token": _safe_text(session.get("access_token")),
        "refresh_token": _safe_text(session.get("refresh_token")),
        "expires_at": expires_at,
        "token_type": _safe_text(session.get("token_type"), "bearer"),
    }


def durable_payload_valid(payload: dict | None) -> bool:
    data = payload if isinstance(payload, dict) else {}
    return bool(
        _safe_text(data.get("access_token"))
        and _safe_text(data.get("refresh_token"))
        and (_safe_text(data.get("user_id")) or isinstance(data.get("user"), dict))
    )


def queue_durable_auth_save(session_state: dict, payload_or_session: dict | None) -> None:
    payload = durable_auth_payload(payload_or_session)
    if durable_payload_valid(payload):
        session_state[DURABLE_AUTH_PENDING_SAVE_KEY] = payload


def queue_durable_auth_clear(session_state: dict) -> None:
    session_state[DURABLE_AUTH_PENDING_CLEAR_KEY] = True
    session_state.pop(DURABLE_AUTH_PENDING_SAVE_KEY, None)


def restore_auth_payload(
    config: dict,
    session_state: dict,
    stored_payload: dict | None,
) -> tuple[bool, str, bool]:
    payload = stored_payload if isinstance(stored_payload, dict) else {}
    if not durable_payload_valid(payload):
        return False, "", False
    session = durable_auth_payload(payload)
    # Identical restore: do not wipe workspace, refetch, or re-queue durable save.
    if auth_restore_lifecycle.is_identical_auth_payload(session_state, session) and current_user_id(
        session_state
    ):
        return False, "", False
    refreshed = False
    if access_token_expired(session):
        refreshed_payload, error = refresh_auth_session(config, session.get("refresh_token", ""))
        if error:
            queue_durable_auth_clear(session_state)
            auth_restore_lifecycle.clear_restore_lifecycle(session_state)
            return False, error, False
        session = durable_auth_payload(refreshed_payload)
        refreshed = True
        # After refresh the fingerprint changes; continue apply as a material update.
    apply_auth_payload(session_state, session)
    queue_durable_auth_save(session_state, session)
    return True, "", refreshed


def apply_auth_payload(session_state: dict, payload: dict) -> dict:
    session = session_from_auth_payload(payload)
    user = session.get("user") if isinstance(session.get("user"), dict) else {}
    new_user_id = _safe_text(session.get("user_id") or user.get("id"))
    prior_user_id = current_user_id(session_state)
    identical = auth_restore_lifecycle.is_identical_auth_payload(session_state, session)
    # Account binding changed (guest→account or account→account): drop prior workspace.
    # Preserve #145 hygiene — identical same-account restore must not wipe.
    if new_user_id and new_user_id != prior_user_id:
        auth_restore_lifecycle.clear_restore_lifecycle(session_state)
        session_integrity.clear_account_bound_transient_state(session_state)
        try:
            from modules import launch_analytics

            launch_analytics.clear_analytics_session(session_state)
        except Exception:
            pass
        for key in (
            "account_saved_leagues_cache",
            "active_league_context",
            "selected_league_id",
            "selected_league_name",
            "selected_team_roster_id",
            "my_roster_id",
            "username",
            "selected_platform",
            "active_platform",
            "_effective_entitlement",
        ):
            session_state.pop(key, None)
        for key in list(session_state.keys()):
            text = str(key)
            if text.startswith("_league_"):
                session_state.pop(key, None)
            if text.startswith("_supabase_profile_loaded_"):
                session_state.pop(key, None)
            if text.startswith("_supabase_auto_resume_attempted_"):
                session_state.pop(key, None)
    elif identical and prior_user_id:
        # Same identity + same tokens already applied — keep session bindings.
        return current_auth_session(session_state) or session
    session_state[AUTH_SESSION_KEY] = session
    session_state[AUTH_USER_KEY] = user
    session_state[AUTH_EMAIL_KEY] = session.get("email", "")
    session_state[ACCOUNT_MODE_KEY] = "account"
    clear_confirmation_required(session_state)
    auth_restore_lifecycle.mark_auth_fingerprint(session_state, session)
    auth_restore_lifecycle.advance_phase(
        session_state,
        auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
    )
    return session


def clear_auth_session(session_state: dict) -> None:
    for key in (AUTH_USER_KEY, AUTH_SESSION_KEY, AUTH_EMAIL_KEY):
        session_state.pop(key, None)
    for key in (
        "account_profile",
        "account_profile_status",
        "account_profile_error",
        "account_user_settings",
        "account_user_settings_error",
        "auth_restore_last_status",
        "auth_restore_last_result",
        "auth_restore_last_reason",
        "auth_restore_last_refreshed",
        CONFIRMATION_REQUIRED_KEY,
        CONFIRMATION_EMAIL_KEY,
        CONFIRMATION_RESEND_TS_KEY,
        # Prevent prior-account league/entitlement chrome from surviving logout.
        "account_saved_leagues_cache",
        "active_league_context",
        "selected_league_id",
        "selected_league_name",
        "selected_team_roster_id",
        "my_roster_id",
        "username",
        "selected_platform",
        "active_platform",
        "_effective_entitlement",
    ):
        session_state.pop(key, None)
    for key in list(session_state.keys()):
        text = str(key)
        if text.startswith("_supabase_profile_loaded_"):
            session_state.pop(key, None)
        if text.startswith("_supabase_user_settings_loaded_"):
            session_state.pop(key, None)
        if text.startswith("_supabase_auto_resume_attempted_"):
            session_state.pop(key, None)
        if text.startswith("_league_"):
            session_state.pop(key, None)
        if text.startswith("_guest_signup_dismissed_"):
            session_state.pop(key, None)
        if text.startswith("_guest_signup_prompt_seen_"):
            session_state.pop(key, None)
    session_state.pop("_guest_auth_resume", None)
    session_state.pop("_guest_auth_dialog_open", None)
    session_state.pop("_guest_auth_dialog_mode", None)
    session_state.pop("_guest_auth_dialog_surface", None)
    try:
        from modules import premium_conversion

        premium_conversion.clear_checkout_intent(session_state)
    except Exception:
        session_state.pop("_premium_checkout_intent", None)
        session_state.pop("_premium_resume_checkout", None)
    auth_restore_lifecycle.clear_restore_lifecycle(session_state)
    try:
        from modules import startup_cold_path

        startup_cold_path.clear_football_context_flags(session_state)
    except Exception:
        pass
    try:
        from modules import game_plan_truth_canon

        game_plan_truth_canon.clear_canon(session_state)
    except Exception:
        session_state.pop("_game_plan_truth_canon", None)
    # Drop overlays, recommendation narrative, workflow return, and identity caches
    # so guest mode cannot inherit the prior account workspace.
    session_integrity.clear_account_bound_transient_state(session_state)
    try:
        from modules import launch_analytics

        launch_analytics.clear_analytics_session(session_state)
    except Exception:
        pass
    session_state[ACCOUNT_MODE_KEY] = "guest"
