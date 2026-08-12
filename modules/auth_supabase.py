from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

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
# Canonical pending-confirmation state (not authenticated).
PENDING_EMAIL_CONFIRMATION_KEY = "pending_email_confirmation"
ACCOUNT_SIGNUP_CHECK_EMAIL_KEY = "account_signup_check_email"

# Accidental dashboard copy-paste suffixes. Auth must hit GoTrue at /auth/v1/*,
# never PostgREST under /rest/v1/* (that returns 404 PGRST125).
_PROJECT_URL_SUFFIXES = (
    "/rest/v1",
    "/auth/v1",
    "/rest",
    "/auth",
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _secret_lookup(secrets: Any, key: str) -> str:
    return app_config.config_value(key, secrets=secrets)


def normalize_supabase_project_url(url: str) -> str:
    """Reduce any pasted project/REST/Auth URL to the project origin.

    Render/dashboard operators often paste `https://<ref>.supabase.co/rest/v1`.
    Naive joins then produce `/rest/v1/auth/v1/signup`, which PostgREST rejects
    with PGRST125 ("Invalid path is specified in request URL").
    """

    text = _safe_text(url)
    if not text:
        return ""
    # Drop fragments/query; keep scheme+host(+port)+path for suffix stripping.
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        path = (parsed.path or "").rstrip("/")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        text = f"{origin}{path}" if path else origin
    else:
        text = text.rstrip("/")
    lowered = text.casefold()
    changed = True
    while changed:
        changed = False
        for suffix in _PROJECT_URL_SUFFIXES:
            if lowered.endswith(suffix):
                text = text[: -len(suffix)].rstrip("/")
                lowered = text.casefold()
                changed = True
                break
    return text.rstrip("/")


def auth_api_url(config: dict, path: str) -> str:
    """Canonical GoTrue URL: `{project_origin}/auth/v1/{path}`."""

    base = normalize_supabase_project_url(_safe_text(config.get("url")))
    clean = _safe_text(path).lstrip("/")
    if clean.casefold().startswith("auth/v1/"):
        clean = clean[8:]
    return f"{base}/auth/v1/{clean}"


def rest_api_url(config: dict, table: str, query: str = "") -> str:
    """Canonical PostgREST URL: `{project_origin}/rest/v1/{table}[?query]`."""

    base = normalize_supabase_project_url(_safe_text(config.get("url")))
    table_name = _safe_text(table).lstrip("/")
    url = f"{base}/rest/v1/{table_name}"
    clean_query = _safe_text(query)
    return f"{url}?{clean_query}" if clean_query else url


def sanitized_request_path(url: str) -> str:
    """Path (+ safe query keys) for diagnostics/tests — never host secrets/tokens."""

    parsed = urlparse(_safe_text(url))
    path = parsed.path or "/"
    if not parsed.query:
        return path
    blocked = {"apikey", "access_token", "refresh_token", "token", "authorization"}
    pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in blocked
    ]
    encoded = urlencode(pairs)
    return f"{path}?{encoded}" if encoded else path


def is_new_api_key_format(key: str) -> bool:
    """True for sb_publishable_ / sb_secret_ keys (not legacy JWT anon keys)."""

    text = _safe_text(key)
    return text.startswith("sb_publishable_") or text.startswith("sb_secret_")


def looks_like_jwt(token: str) -> bool:
    text = _safe_text(token)
    if not text or text.startswith("sb_"):
        return False
    parts = text.split(".")
    return len(parts) == 3 and all(parts)


def get_supabase_config(*, secrets: Any = None, environ: dict | None = None) -> dict:
    url = app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets)
    anon_key = app_config.config_value("SUPABASE_ANON_KEY", environ=environ, secrets=secrets)
    return {
        "enabled": bool(url and anon_key),
        "url": normalize_supabase_project_url(url),
        "anon_key": anon_key,
    }


def auth_headers(config: dict, access_token: str = "") -> dict:
    """Build Auth/Data API headers.

    Legacy JWT anon keys: `apikey` + `Authorization: Bearer <anon>` (supabase-js default).
    New `sb_publishable_` / `sb_secret_` keys: `apikey` only until a user JWT exists —
    Bearer with those keys is not a JWT and is rejected by the platform.
    """

    anon = _safe_text(config.get("anon_key"))
    headers = {
        "apikey": anon,
        "Content-Type": "application/json",
    }
    bearer = _safe_text(access_token)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    elif anon and not is_new_api_key_format(anon):
        headers["Authorization"] = f"Bearer {anon}"
    return headers


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
    elif "pgrst125" in text or (status_code == 404 and "invalid path" in text):
        # PostgREST path error — almost always means Auth hit /rest/v1/... by mistake.
        category = "invalid_api_path"
        user_message = "Account service is temporarily unavailable. Try again."

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
    if classified["category"] in {
        "provider_unreachable",
        "not_configured",
        "rate_limited",
        "invalid_api_path",
    }:
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
    request_path: str = "",
) -> None:
    """Diagnostics-only structured auth event — never logs email/tokens/bodies."""

    payload = {
        "kind": "auth_operation",
        "auth_operation": _safe_text(operation, "unknown")[:32],
        "result_category": _safe_text(category, "unknown")[:48],
        "http_status": status_code,
        "error_code": _safe_text(error_code)[:64],
        "request_path": _safe_text(request_path)[:160],
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
    request_url = auth_api_url(config, "signup")
    request_path = sanitized_request_path(request_url)
    redirect_to = email_redirect_to(config)
    signup_body: dict[str, Any] = {
        "email": clean_email,
        "password": clean_password,
    }
    if redirect_to:
        # GoTrue field — confirmation link returns to Site URL / allowlisted redirect.
        signup_body["email_redirect_to"] = redirect_to
    try:
        with performance.time_block("supabase_auth_signup", category="supabase"):
            response = requests.post(
                request_url,
                headers=auth_headers(config),
                json=signup_body,
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
            request_path=request_path,
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
            request_path=request_path,
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
        request_path=request_path,
    )
    return payload, ""


def sign_in(config: dict, email: str, password: str) -> tuple[dict | None, str]:
    if not is_configured(config):
        return None, "Accounts are not configured."
    started = time.perf_counter()
    status_code: int | None = None
    request_url = auth_api_url(config, "token?grant_type=password")
    request_path = sanitized_request_path(request_url)
    try:
        with performance.time_block("supabase_auth_signin", category="supabase"):
            response = requests.post(
                request_url,
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
            request_path=request_path,
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
            request_path=request_path,
        )
        return None, error
    log_auth_operation_diagnostic(
        operation="signin",
        category="success",
        status_code=status_code,
        duration_ms=(time.perf_counter() - started) * 1000,
        auth_user_created=True,
        request_path=request_path,
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
                auth_api_url(config, "resend"),
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
                auth_api_url(config, "logout"),
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
                auth_api_url(config, "token?grant_type=refresh_token"),
                headers=auth_headers(config),
                json={"refresh_token": token},
                timeout=15,
            )
    except Exception:
        return None, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return None, _safe_error(response)
    return response.json(), ""


def verify_email_token_hash(
    config: dict,
    *,
    token_hash: str,
    token_type: str = "signup",
) -> tuple[dict | None, str]:
    """Exchange a confirmation token_hash for a session (custom email templates)."""

    if not is_configured(config):
        return None, "Accounts are not configured."
    clean_hash = _safe_text(token_hash)
    clean_type = _safe_text(token_type, "signup") or "signup"
    if not clean_hash:
        return None, "Confirmation link is missing a token."
    try:
        with performance.time_block("supabase_auth_verify", category="supabase"):
            response = requests.post(
                auth_api_url(config, "verify"),
                headers=auth_headers(config),
                json={"type": clean_type, "token_hash": clean_hash},
                timeout=15,
            )
    except Exception:
        return None, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return None, _safe_error(response)
    payload = response.json()
    if not isinstance(payload, dict):
        return None, "Invalid confirmation response."
    if not session_is_authenticated_for_app(payload):
        return None, "Email is not confirmed yet."
    return payload, ""


def fetch_auth_user(config: dict, access_token: str) -> tuple[dict | None, str]:
    """Load the Auth user for an access token (confirmation callback enrichment)."""

    if not is_configured(config):
        return None, "Accounts are not configured."
    token = _safe_text(access_token)
    if not token:
        return None, "Missing access token."
    try:
        with performance.time_block("supabase_auth_user", category="supabase"):
            response = requests.get(
                auth_api_url(config, "user"),
                headers=auth_headers(config, token),
                timeout=15,
            )
    except Exception:
        return None, "Could not reach Supabase Auth."
    if response.status_code >= 400:
        return None, _safe_error(response)
    payload = response.json()
    return (payload if isinstance(payload, dict) else None), ""


def extract_auth_user(payload: dict | None) -> dict:
    """Normalize GoTrue signup/signin user objects.

    Confirm-email signup commonly returns either:
    - `{ "user": {...}, "session": null }` (supabase-js shape), or
    - a bare top-level user object with `id` / `email` / `confirmation_sent_at`
      and no nested `user` key (raw `/auth/v1/signup` response).
    """

    data = payload if isinstance(payload, dict) else {}
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    if user:
        return user
    nested_session = data.get("session")
    if isinstance(nested_session, dict):
        nested_user = nested_session.get("user")
        if isinstance(nested_user, dict) and nested_user:
            return nested_user
        # Session object may carry tokens with user elsewhere.
        if _safe_text(nested_session.get("access_token")):
            pass
    # Bare top-level user (no access_token at root).
    if _safe_text(data.get("access_token")):
        return {}
    if _safe_text(data.get("id")) and (
        "email" in data
        or "email_confirmed_at" in data
        or "confirmation_sent_at" in data
        or "confirmed_at" in data
    ):
        return {
            "id": data.get("id"),
            "email": data.get("email"),
            "email_confirmed_at": data.get("email_confirmed_at"),
            "confirmed_at": data.get("confirmed_at"),
            "confirmation_sent_at": data.get("confirmation_sent_at"),
            "aud": data.get("aud"),
            "role": data.get("role"),
            "identities": data.get("identities"),
            "app_metadata": data.get("app_metadata"),
            "user_metadata": data.get("user_metadata"),
        }
    return {}


def session_from_auth_payload(payload: dict | None) -> dict:
    data = payload if isinstance(payload, dict) else {}
    user = extract_auth_user(data)
    nested_session = data.get("session") if isinstance(data.get("session"), dict) else {}
    access_token = _safe_text(
        data.get("access_token") or nested_session.get("access_token")
    )
    refresh_token = _safe_text(
        data.get("refresh_token") or nested_session.get("refresh_token")
    )
    expires_at = data.get("expires_at")
    if expires_at in (None, "") and nested_session:
        expires_at = nested_session.get("expires_at")
    expires_in = data.get("expires_in")
    if expires_in in (None, "") and nested_session:
        expires_in = nested_session.get("expires_in")
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
        "token_type": _safe_text(
            data.get("token_type") or nested_session.get("token_type"),
            "bearer",
        ),
        "confirmation_sent_at": _safe_text(
            user.get("confirmation_sent_at") or data.get("confirmation_sent_at")
        ),
    }


def email_redirect_to(config: dict | None = None) -> str:
    """Canonical post-confirm return URL (production Site URL / APP_BASE_URL)."""

    try:
        return app_config.app_base_url()
    except Exception:
        return app_config.PRODUCTION_BASE_URL


def user_email_confirmed(user: dict | None) -> bool:
    """True when Supabase reports a confirmed email timestamp.

    Missing confirmation fields on older durable payloads are treated as confirmed
    so existing sessions keep working. Explicit null/empty fields mean unconfirmed.
    """

    data = user if isinstance(user, dict) else {}
    if _safe_text(data.get("email_confirmed_at") or data.get("confirmed_at")):
        return True
    if "email_confirmed_at" in data or "confirmed_at" in data:
        return False
    return True


def signup_requires_email_confirmation(payload: dict | None) -> bool:
    """True when signup created a user that is not yet a usable authenticated session.

    Trigger conditions (any):
    - user present, no access_token (Confirm Email ON — session null)
    - confirmation_sent_at set and email not confirmed
    - access_token present but email_confirmed_at explicitly empty/null
    - nested `session` is null/absent while user exists
    """

    data = payload if isinstance(payload, dict) else {}
    session = session_from_auth_payload(data)
    user = session.get("user") if isinstance(session.get("user"), dict) else {}
    if not user and not session.get("user_id"):
        return False
    if session.get("confirmation_sent_at") and not user_email_confirmed(user):
        return True
    if "session" in data and data.get("session") in (None, {}, ""):
        if session.get("user_id") or user:
            return not user_email_confirmed(user) or not session.get("access_token")
    if not session.get("access_token"):
        return True
    return not user_email_confirmed(user)


def session_is_authenticated_for_app(payload: dict | None) -> bool:
    """Authenticated usable account = access token + confirmed email."""

    session = session_from_auth_payload(payload)
    user = session.get("user") if isinstance(session.get("user"), dict) else {}
    if not session.get("access_token") or not session.get("user_id"):
        return False
    return user_email_confirmed(user)


def mask_email_for_display(email: str) -> str:
    text = _safe_text(email)
    if not text or "@" not in text:
        return text
    local, _, domain = text.partition("@")
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


def enter_pending_email_confirmation(
    session_state: dict,
    email: str = "",
    *,
    payload: dict | None = None,
) -> dict:
    """Enter canonical pending_email_confirmation — never authenticated."""

    session = session_from_auth_payload(payload)
    clean_email = _safe_text(email) or _safe_text(session.get("email"))
    pending = {
        "pending": True,
        "email": clean_email,
        "email_masked": mask_email_for_display(clean_email),
        "started_at": int(time.time()),
        "auth_user_created": bool(session.get("user_id")),
        "confirmation_sent": bool(
            session.get("confirmation_sent_at")
            or (payload or {}).get("confirmation_sent_at")
            or True
        ),
    }
    session_state[PENDING_EMAIL_CONFIRMATION_KEY] = pending
    session_state[CONFIRMATION_REQUIRED_KEY] = True
    session_state[ACCOUNT_SIGNUP_CHECK_EMAIL_KEY] = True
    if clean_email:
        session_state[CONFIRMATION_EMAIL_KEY] = clean_email
    # Strip any accidental auth bindings from a confused success path.
    for key in (AUTH_USER_KEY, AUTH_SESSION_KEY, AUTH_EMAIL_KEY):
        session_state.pop(key, None)
    session_state[ACCOUNT_MODE_KEY] = "guest"
    session_state.pop("account_saved_leagues_cache", None)
    session_state.pop("account_profile", None)
    session_state.pop("_effective_entitlement", None)
    queue_durable_auth_clear(session_state)
    log_auth_operation_diagnostic(
        operation="signup",
        category="email_confirmation",
        auth_user_created=pending["auth_user_created"],
        profile_bootstrap_ran=False,
        durable_session_write=False,
    )
    return pending


def is_pending_email_confirmation(session_state: dict) -> bool:
    pending = session_state.get(PENDING_EMAIL_CONFIRMATION_KEY)
    if isinstance(pending, dict) and pending.get("pending"):
        return True
    return bool(
        session_state.get(CONFIRMATION_REQUIRED_KEY)
        or session_state.get(ACCOUNT_SIGNUP_CHECK_EMAIL_KEY)
    )


def pending_confirmation_email(session_state: dict) -> str:
    pending = session_state.get(PENDING_EMAIL_CONFIRMATION_KEY)
    if isinstance(pending, dict) and _safe_text(pending.get("email")):
        return _safe_text(pending.get("email"))
    return _safe_text(session_state.get(CONFIRMATION_EMAIL_KEY))


def clear_pending_email_confirmation(session_state: dict) -> None:
    session_state.pop(PENDING_EMAIL_CONFIRMATION_KEY, None)
    session_state.pop(ACCOUNT_SIGNUP_CHECK_EMAIL_KEY, None)
    clear_confirmation_required(session_state)


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
    """Legacy flag helper — prefer enter_pending_email_confirmation for signup."""

    session_state[CONFIRMATION_REQUIRED_KEY] = True
    session_state[ACCOUNT_SIGNUP_CHECK_EMAIL_KEY] = True
    if _safe_text(email):
        session_state[CONFIRMATION_EMAIL_KEY] = _safe_text(email)
    pending = session_state.get(PENDING_EMAIL_CONFIRMATION_KEY)
    if not isinstance(pending, dict) or not pending.get("pending"):
        session_state[PENDING_EMAIL_CONFIRMATION_KEY] = {
            "pending": True,
            "email": _safe_text(email),
            "email_masked": mask_email_for_display(email),
            "started_at": int(time.time()),
            "auth_user_created": False,
            "confirmation_sent": True,
        }


def clear_confirmation_required(session_state: dict) -> None:
    for key in (
        CONFIRMATION_REQUIRED_KEY,
        CONFIRMATION_EMAIL_KEY,
        CONFIRMATION_RESEND_TS_KEY,
        PENDING_EMAIL_CONFIRMATION_KEY,
        ACCOUNT_SIGNUP_CHECK_EMAIL_KEY,
    ):
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
    user = session.get("user") if isinstance(session.get("user"), dict) else {}
    if user and not user_email_confirmed(user):
        queue_durable_auth_clear(session_state)
        enter_pending_email_confirmation(
            session_state,
            session.get("email", ""),
            payload=session,
        )
        return False, "Email is not confirmed yet.", False
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
    # Never promote unconfirmed signup into an authenticated account session.
    if session.get("access_token") and user and not user_email_confirmed(user):
        enter_pending_email_confirmation(
            session_state,
            session.get("email", ""),
            payload=payload if isinstance(payload, dict) else None,
        )
        return {}
    if not session.get("access_token") or not new_user_id:
        return current_auth_session(session_state) or session
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
    clear_pending_email_confirmation(session_state)
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
        PENDING_EMAIL_CONFIRMATION_KEY,
        ACCOUNT_SIGNUP_CHECK_EMAIL_KEY,
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
    try:
        from modules import dashboard_loading_state

        dashboard_loading_state.clear_on_logout(session_state)
    except Exception:
        pass
    # Drop overlays, recommendation narrative, workflow return, and identity caches
    # so guest mode cannot inherit the prior account workspace.
    session_integrity.clear_account_bound_transient_state(session_state)
    try:
        from modules import launch_analytics

        launch_analytics.clear_analytics_session(session_state)
    except Exception:
        pass
    session_state[ACCOUNT_MODE_KEY] = "guest"
