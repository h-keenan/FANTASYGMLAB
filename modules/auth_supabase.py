from __future__ import annotations

import os
import time
from typing import Any

import requests


AUTH_USER_KEY = "auth_user"
AUTH_SESSION_KEY = "auth_session"
AUTH_EMAIL_KEY = "auth_email"
ACCOUNT_MODE_KEY = "account_mode"
DURABLE_AUTH_STORAGE_KEY = "dynastygm_supabase_auth"
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
    if secrets is None:
        return ""
    try:
        value = secrets.get(key)
    except Exception:
        value = None
    return _safe_text(value)


def get_supabase_config(*, secrets: Any = None, environ: dict | None = None) -> dict:
    env = environ if isinstance(environ, dict) else os.environ
    url = _secret_lookup(secrets, "SUPABASE_URL") or _safe_text(env.get("SUPABASE_URL"))
    anon_key = _secret_lookup(secrets, "SUPABASE_ANON_KEY") or _safe_text(env.get("SUPABASE_ANON_KEY"))
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
    message = payload.get("msg") or payload.get("message") or payload.get("error_description") or payload.get("error")
    return _safe_text(message, "Supabase request failed.")


def sign_up(config: dict, email: str, password: str) -> tuple[dict | None, str]:
    if not is_configured(config):
        return None, "Accounts are not configured."
    try:
        response = requests.post(
            f"{config['url']}/auth/v1/signup",
            headers=auth_headers(config),
            json={"email": email, "password": password},
            timeout=15,
        )
    except Exception:
        return None, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return None, _safe_error(response)
    return response.json(), ""


def sign_in(config: dict, email: str, password: str) -> tuple[dict | None, str]:
    if not is_configured(config):
        return None, "Accounts are not configured."
    try:
        response = requests.post(
            f"{config['url']}/auth/v1/token?grant_type=password",
            headers=auth_headers(config),
            json={"email": email, "password": password},
            timeout=15,
        )
    except Exception:
        return None, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return None, _safe_error(response)
    return response.json(), ""


def resend_signup_confirmation(config: dict, email: str) -> tuple[bool, str]:
    if not is_configured(config):
        return False, "Accounts are not configured."
    clean_email = _safe_text(email)
    if not clean_email:
        return False, "Enter your email address before requesting another confirmation email."
    try:
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
    refreshed = False
    if access_token_expired(session):
        refreshed_payload, error = refresh_auth_session(config, session.get("refresh_token", ""))
        if error:
            queue_durable_auth_clear(session_state)
            return False, error, False
        session = durable_auth_payload(refreshed_payload)
        refreshed = True
    apply_auth_payload(session_state, session)
    queue_durable_auth_save(session_state, session)
    return True, "", refreshed


def apply_auth_payload(session_state: dict, payload: dict) -> dict:
    session = session_from_auth_payload(payload)
    user = session.get("user") if isinstance(session.get("user"), dict) else {}
    session_state[AUTH_SESSION_KEY] = session
    session_state[AUTH_USER_KEY] = user
    session_state[AUTH_EMAIL_KEY] = session.get("email", "")
    session_state[ACCOUNT_MODE_KEY] = "account"
    clear_confirmation_required(session_state)
    return session


def clear_auth_session(session_state: dict) -> None:
    for key in (AUTH_USER_KEY, AUTH_SESSION_KEY, AUTH_EMAIL_KEY):
        session_state.pop(key, None)
    for key in (
        "account_profile",
        "account_profile_status",
        "account_profile_error",
        "account_user_settings",
        "auth_restore_last_status",
        "auth_restore_last_result",
        "auth_restore_last_reason",
        "auth_restore_last_refreshed",
        CONFIRMATION_REQUIRED_KEY,
        CONFIRMATION_EMAIL_KEY,
        CONFIRMATION_RESEND_TS_KEY,
    ):
        session_state.pop(key, None)
    for key in list(session_state.keys()):
        if str(key).startswith("_supabase_profile_loaded_"):
            session_state.pop(key, None)
    session_state[ACCOUNT_MODE_KEY] = "guest"
