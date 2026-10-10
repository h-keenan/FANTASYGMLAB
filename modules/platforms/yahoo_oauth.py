"""Yahoo Fantasy Sports OAuth2 client (spike scaffolding — see runbook).

STATUS: NOT EXERCISED AGAINST THE LIVE YAHOO API.

This module implements Yahoo's documented OAuth2 Authorization Code flow so a
human with real Yahoo Developer credentials can finish the integration spike
described in ``docs/yahoo-oauth-integration-spike-runbook.md``. Every URL,
parameter name, and request shape below was taken from Yahoo's current
published developer documentation at the time this was written (Yahoo has a
documented history of changing this API, so re-check the sources in the
runbook before relying on this long-term):

  * Authorization endpoint, required/optional params:
    https://developer.yahoo.com/oauth2/guide/flows_authcode/
  * Token endpoint, Basic-auth client authentication, token response shape:
    https://developer.yahoo.com/oauth2/guide/flows_authcode/
  * App registration (Fantasy Sports read scope is selected at app-creation
    time on Yahoo's side, not passed as an OAuth ``scope`` parameter):
    https://developer.yahoo.com/apps/create/

No code path in this module has been run against a real Yahoo Developer
app, a real Yahoo account, or a real user consent screen — this sandboxed
environment has no live internet access and no real Yahoo credentials. The
request/response shapes are believed correct per the documentation above,
but only a human completing step-by-step the runbook can confirm that Yahoo
actually behaves as documented today.

Credentials are read from environment variables (via ``modules.app_config``,
so Streamlit secrets / local_secrets.toml also work locally) and are never
hardcoded here:

  * ``YAHOO_CLIENT_ID``     — Consumer Key from the Yahoo Developer app.
  * ``YAHOO_CLIENT_SECRET`` — Consumer Secret from the Yahoo Developer app.
  * ``YAHOO_REDIRECT_URI``  — Must exactly match a redirect URI registered
    on the app (optional here; callers may also pass redirect_uri directly).
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode

import requests

from modules.app_config import config_value

AUTHORIZATION_ENDPOINT = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_ENDPOINT = "https://api.login.yahoo.com/oauth2/get_token"

CLIENT_ID_ENV_KEY = "YAHOO_CLIENT_ID"
CLIENT_SECRET_ENV_KEY = "YAHOO_CLIENT_SECRET"
REDIRECT_URI_ENV_KEY = "YAHOO_REDIRECT_URI"


class YahooOAuthError(RuntimeError):
    """Raised for OAuth configuration problems or a failed token request.

    Message text must never include the client secret or a real token value.
    """


@dataclass
class YahooOAuthToken:
    """Parsed token-endpoint response.

    Field names mirror Yahoo's documented token response body:
    ``access_token``, ``token_type`` (``bearer``), ``expires_in`` (seconds),
    ``refresh_token``, and ``xoauth_yahoo_guid`` (the user's Yahoo GUID).
    """

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    yahoo_guid: str
    obtained_at: float
    raw: dict[str, Any]

    def is_expired(self, *, skew_seconds: int = 60) -> bool:
        """True once the token is within ``skew_seconds`` of its documented expiry."""
        if self.expires_in <= 0:
            return True
        return time.time() >= (self.obtained_at + self.expires_in - skew_seconds)

    @classmethod
    def from_response(cls, payload: Mapping[str, Any], *, obtained_at: float | None = None) -> "YahooOAuthToken":
        access_token = str(payload.get("access_token") or "")
        if not access_token:
            raise YahooOAuthError("Yahoo token response did not include an access_token.")
        return cls(
            access_token=access_token,
            refresh_token=str(payload.get("refresh_token") or ""),
            token_type=str(payload.get("token_type") or "bearer"),
            expires_in=_safe_int(payload.get("expires_in"), 3600),
            yahoo_guid=str(payload.get("xoauth_yahoo_guid") or ""),
            obtained_at=obtained_at if obtained_at is not None else time.time(),
            raw=dict(payload),
        )


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _client_id(client_id: str | None, *, environ: Mapping[str, Any] | None = None) -> str:
    value = client_id or config_value(CLIENT_ID_ENV_KEY, environ=environ)
    if not value:
        raise YahooOAuthError(
            f"{CLIENT_ID_ENV_KEY} is not configured. Set it to the Consumer Key from the "
            "Yahoo Developer app (see docs/yahoo-oauth-integration-spike-runbook.md)."
        )
    return value


def _client_secret(client_secret: str | None, *, environ: Mapping[str, Any] | None = None) -> str:
    value = client_secret or config_value(CLIENT_SECRET_ENV_KEY, environ=environ)
    if not value:
        raise YahooOAuthError(
            f"{CLIENT_SECRET_ENV_KEY} is not configured. Set it to the Consumer Secret from "
            "the Yahoo Developer app (see docs/yahoo-oauth-integration-spike-runbook.md)."
        )
    return value


def _redirect_uri(redirect_uri: str | None, *, environ: Mapping[str, Any] | None = None) -> str:
    value = redirect_uri or config_value(REDIRECT_URI_ENV_KEY, environ=environ)
    if not value:
        raise YahooOAuthError(
            f"redirect_uri was not provided and {REDIRECT_URI_ENV_KEY} is not configured. "
            "It must exactly match a redirect URI registered on the Yahoo Developer app."
        )
    return value


def build_authorization_url(
    *,
    redirect_uri: str | None = None,
    state: str | None = None,
    language: str | None = None,
    client_id: str | None = None,
    environ: Mapping[str, Any] | None = None,
) -> str:
    """Build the URL to send the user's browser to for Yahoo's consent screen.

    Per https://developer.yahoo.com/oauth2/guide/flows_authcode/ the
    authorization endpoint accepts GET with ``client_id``, ``redirect_uri``,
    and ``response_type=code`` required, plus optional ``state`` (CSRF guard,
    strongly recommended) and ``language``. Fantasy Sports read access itself
    is selected when the app is registered (see the runbook), not passed as
    an OAuth ``scope`` query parameter — Yahoo's Fantasy Sports API does not
    document a separate ``scope`` parameter on this endpoint.
    """

    params: dict[str, str] = {
        "client_id": _client_id(client_id, environ=environ),
        "redirect_uri": _redirect_uri(redirect_uri, environ=environ),
        "response_type": "code",
    }
    if state:
        params["state"] = state
    if language:
        params["language"] = language
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def _basic_auth_header(client_id: str, client_secret: str) -> dict[str, str]:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def _post_token_request(
    data: dict[str, str],
    *,
    client_id: str,
    client_secret: str,
    session: Any = None,
    timeout: int = 20,
) -> YahooOAuthToken:
    http = session or requests
    headers = {
        **_basic_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        response = http.post(TOKEN_ENDPOINT, data=data, headers=headers, timeout=timeout)
    except Exception as exc:  # pragma: no cover - network error path, exercised via mocks
        raise YahooOAuthError(f"Could not reach Yahoo's token endpoint: {exc}") from exc
    return _parse_token_response(response)


def _parse_token_response(response: Any) -> YahooOAuthToken:
    status_code = getattr(response, "status_code", None)
    try:
        response.raise_for_status()
    except Exception as exc:
        body = _safe_response_text(response)
        raise YahooOAuthError(
            f"Yahoo's token endpoint returned an error (status {status_code}): {body}"
        ) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise YahooOAuthError("Yahoo's token endpoint did not return JSON as documented.") from exc
    if not isinstance(payload, dict):
        raise YahooOAuthError("Yahoo's token endpoint returned an unexpected (non-object) JSON body.")
    return YahooOAuthToken.from_response(payload)


def _safe_response_text(response: Any) -> str:
    try:
        text = response.text
    except Exception:
        return "<no response body>"
    return str(text)[:500]


def exchange_code_for_token(
    *,
    code: str,
    redirect_uri: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    environ: Mapping[str, Any] | None = None,
    session: Any = None,
    timeout: int = 20,
) -> YahooOAuthToken:
    """Exchange an authorization ``code`` (from the redirect_uri callback) for tokens.

    POSTs ``application/x-www-form-urlencoded`` to the token endpoint with
    ``grant_type=authorization_code``, ``redirect_uri``, and ``code``, using
    HTTP Basic auth (base64 ``client_id:client_secret``) exactly as Yahoo's
    authorization-code-flow documentation specifies.
    """

    if not code:
        raise YahooOAuthError("code is required to exchange for a token.")
    cid = _client_id(client_id, environ=environ)
    secret = _client_secret(client_secret, environ=environ)
    data = {
        "grant_type": "authorization_code",
        "redirect_uri": _redirect_uri(redirect_uri, environ=environ),
        "code": code,
    }
    return _post_token_request(data, client_id=cid, client_secret=secret, session=session, timeout=timeout)


def refresh_access_token(
    *,
    refresh_token: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    environ: Mapping[str, Any] | None = None,
    session: Any = None,
    timeout: int = 20,
) -> YahooOAuthToken:
    """Exchange a refresh token for a new access token.

    Same endpoint as the initial exchange, with ``grant_type=refresh_token``
    and ``refresh_token`` in place of ``code``/``redirect_uri``, per Yahoo's
    documented refresh flow.
    """

    if not refresh_token:
        raise YahooOAuthError("refresh_token is required to refresh an access token.")
    cid = _client_id(client_id, environ=environ)
    secret = _client_secret(client_secret, environ=environ)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    return _post_token_request(data, client_id=cid, client_secret=secret, session=session, timeout=timeout)


def ensure_fresh_token(
    token: YahooOAuthToken,
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    environ: Mapping[str, Any] | None = None,
    session: Any = None,
    timeout: int = 20,
) -> YahooOAuthToken:
    """Return ``token`` unchanged if still valid, otherwise refresh it."""

    if not token.is_expired():
        return token
    return refresh_access_token(
        refresh_token=token.refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        environ=environ,
        session=session,
        timeout=timeout,
    )
