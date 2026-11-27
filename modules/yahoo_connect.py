"""Server side of "Connect Yahoo": signed OAuth state, callback, token upkeep.

Flow (docs/yahoo-import.md):

1. ``POST /v1/yahoo/oauth/start`` (signed-in user) -> :func:`build_start_url`
   returns Yahoo's authorize URL carrying a signed, expiring ``state`` that
   names the user and where to send them back (web or the app).
2. Yahoo redirects the browser to ``/v1/yahoo/oauth/callback`` (no FantasyDesk
   session cookie is available there, so the signed state is the identity).
   :func:`complete_callback` verifies the state, exchanges the code, stores the
   encrypted tokens and returns the URL to bounce the user back to.
3. :func:`get_access_token` hands the league loader a fresh access token,
   refreshing (and storing Yahoo's possibly rotated refresh token) when the
   1 hour access token is near expiry.

Nothing here logs a token, a code or the client secret.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any
from urllib.parse import urlencode

from modules import yahoo_credentials
from modules.platforms import yahoo_oauth

# Must match, character for character, the redirect URI registered on the Yahoo app.
DEFAULT_REDIRECT_URI = "https://api.fantasygmlab.com/v1/yahoo/oauth/callback"
DEFAULT_WEB_BASE = "https://app.fantasygmlab.com"
WEB_RETURN_PATH = "/connect-league"
APP_RETURN_URL = "fantasygmlab://yahoo"
STATE_TTL_SECONDS = 10 * 60
ACCESS_SKEW_SECONDS = 120
RETURN_TARGETS = ("web", "app")

ERROR_MESSAGES = {
    "not_configured": "Connecting Yahoo isn't available right now.",
    "denied": "Yahoo sign-in was cancelled. Tap Connect Yahoo to try again.",
    "bad_state": "That Yahoo sign-in link expired. Tap Connect Yahoo to start again.",
    "exchange_failed": "Yahoo didn't accept the sign-in. Tap Connect Yahoo to try again.",
    "storage_failed": "We couldn't save your Yahoo connection. Please try again in a moment.",
    "reconnect_needed": "Your Yahoo connection expired. Tap Connect Yahoo to sign in again.",
}


def redirect_uri() -> str:
    return os.environ.get("YAHOO_REDIRECT_URI", "").strip() or DEFAULT_REDIRECT_URI


def _web_base() -> str:
    return (os.environ.get("APP_BASE_URL", "").strip() or DEFAULT_WEB_BASE).rstrip("/")


def available() -> bool:
    return yahoo_credentials.client_configured() and yahoo_credentials.is_configured()


# --- signed state --------------------------------------------------------------


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _state_key() -> bytes:
    secret = os.environ.get("YAHOO_CLIENT_SECRET", "").strip()
    return hashlib.sha256(b"yahoo-oauth-state-v1:" + secret.encode("utf-8")).digest()


def sign_state(user_id: str, return_to: str, *, now: float | None = None) -> str:
    target = return_to if return_to in RETURN_TARGETS else "web"
    payload = json.dumps(
        {"u": str(user_id), "r": target, "n": secrets.token_hex(8), "e": int((now or time.time()) + STATE_TTL_SECONDS)},
        separators=(",", ":"),
    ).encode("utf-8")
    mac = hmac.new(_state_key(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(mac)}"


def verify_state(state: str, *, now: float | None = None) -> dict[str, str] | None:
    """``{"user_id", "return_to"}`` for a genuine, unexpired state, else None."""

    try:
        body, _, sig = str(state or "").partition(".")
        payload = _unb64(body)
        if not hmac.compare_digest(_unb64(sig), hmac.new(_state_key(), payload, hashlib.sha256).digest()):
            return None
        data = json.loads(payload)
        if float(data["e"]) < (now or time.time()):
            return None
        user_id = str(data["u"])
        target = str(data["r"])
    except Exception:
        return None
    if not user_id or target not in RETURN_TARGETS:
        return None
    return {"user_id": user_id, "return_to": target}


# --- start / callback ----------------------------------------------------------


def build_start_url(user_id: str, return_to: str) -> str:
    return yahoo_oauth.build_authorization_url(
        redirect_uri=redirect_uri(),
        state=sign_state(user_id, return_to),
        client_id=os.environ.get("YAHOO_CLIENT_ID", "").strip(),
    )


def return_url(target: str, *, connected: bool, reason: str = "") -> str:
    params = {"status": "connected"} if connected else {"status": "error", "reason": reason or "exchange_failed"}
    if target == "app":
        return f"{APP_RETURN_URL}?{urlencode(params)}"
    web = {"yahoo": params["status"], **({"yahoo_reason": params["reason"]} if "reason" in params else {})}
    return f"{_web_base()}{WEB_RETURN_PATH}?{urlencode(web)}"


def complete_callback(config: dict, *, code: str, state: str, error: str = "") -> str:
    """Finish the OAuth round trip and return the URL to send the browser to."""

    verified = verify_state(state)
    if verified is None:
        return return_url("web", connected=False, reason="bad_state")
    target, user_id = verified["return_to"], verified["user_id"]
    if error or not code:
        return return_url(target, connected=False, reason="denied")
    if not available():
        return return_url(target, connected=False, reason="not_configured")
    try:
        token = yahoo_oauth.exchange_code_for_token(
            code=code,
            redirect_uri=redirect_uri(),
            client_id=os.environ.get("YAHOO_CLIENT_ID", "").strip(),
            client_secret=os.environ.get("YAHOO_CLIENT_SECRET", "").strip(),
        )
    except yahoo_oauth.YahooOAuthError:
        return return_url(target, connected=False, reason="exchange_failed")
    if not token.refresh_token:
        return return_url(target, connected=False, reason="exchange_failed")
    try:
        yahoo_credentials.save(
            config,
            "",  # server-side write: needs SUPABASE_SERVICE_ROLE_KEY (no user session exists on the callback)
            user_id=user_id,
            credentials=_credentials_from_token(token),
        )
    except yahoo_credentials.YahooCredentialError:
        return return_url(target, connected=False, reason="storage_failed")
    return return_url(target, connected=True)


def _credentials_from_token(token: yahoo_oauth.YahooOAuthToken, fallback_refresh: str = "") -> yahoo_credentials.YahooCredentials:
    return yahoo_credentials.YahooCredentials(
        refresh_token=token.refresh_token or fallback_refresh,
        access_token=token.access_token,
        access_expires_at=token.obtained_at + token.expires_in,
        yahoo_guid=token.yahoo_guid,
    )


# --- token upkeep --------------------------------------------------------------

_refresh_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(user_id: str) -> threading.Lock:
    with _locks_guard:
        return _refresh_locks.setdefault(user_id, threading.Lock())


def get_access_token(
    config: dict, access_token: str, *, user_id: str, force_refresh: bool = False
) -> tuple[str | None, str]:
    """``(yahoo_access_token, "")`` or ``(None, reason)``.

    ``reason`` is ``not_connected``, ``reconnect_needed`` (Yahoo refused the
    refresh token: the user must sign in again) or ``yahoo_unavailable``."""

    if not yahoo_credentials.is_configured() or not yahoo_credentials.client_configured():
        return None, "not_configured"
    with _lock_for(user_id):
        creds = yahoo_credentials.load(config, access_token, user_id=user_id)
        if creds is None:
            return None, "not_connected"
        if not force_refresh and creds.access_token and creds.access_expires_at - ACCESS_SKEW_SECONDS > time.time():
            return creds.access_token, ""
        try:
            token = yahoo_oauth.refresh_access_token(
                refresh_token=creds.refresh_token,
                client_id=os.environ.get("YAHOO_CLIENT_ID", "").strip(),
                client_secret=os.environ.get("YAHOO_CLIENT_SECRET", "").strip(),
                redirect_uri=redirect_uri(),
            )
        except yahoo_oauth.YahooOAuthError as exc:
            if exc.status_code in (400, 401):
                return None, "reconnect_needed"
            return None, "yahoo_unavailable"
        fresh = _credentials_from_token(token, fallback_refresh=creds.refresh_token)
        if not fresh.yahoo_guid:
            fresh = yahoo_credentials.YahooCredentials(
                fresh.refresh_token, fresh.access_token, fresh.access_expires_at, creds.yahoo_guid
            )
        try:
            yahoo_credentials.save(config, access_token, user_id=user_id, credentials=fresh)
        except yahoo_credentials.YahooCredentialError:
            # A rotated refresh token we couldn't store would lock the user out next hour; surface it.
            return None, "yahoo_unavailable"
        return fresh.access_token, ""
