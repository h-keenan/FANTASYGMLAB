"""Encrypted storage for a user's Yahoo Fantasy OAuth tokens.

Yahoo uses OAuth 2.0, so unlike ESPN the user never pastes a secret: they sign
in at Yahoo and we receive a refresh token (long lived) and an access token
(1 hour). Both are live credentials for that user's Yahoo account, so:

* Both are encrypted (Fernet) before they leave this process. Supabase only
  ever holds ciphertext. The key is ``YAHOO_CREDENTIAL_KEY`` or, when that is
  unset, the existing ``ESPN_CREDENTIAL_KEY`` (one Fernet key for per-user
  third-party secrets; rotating it just asks users to reconnect).
* The table (docs/supabase_yahoo_credentials.sql) is row-level secured to the
  owner; with SUPABASE_SERVICE_ROLE_KEY set, only the server reads it.
* This module never returns a token to any client and never logs one. Errors
  carry a stable reason code only.
* No key, or the table not yet created: the feature is simply off / the save
  fails with ``storage_failed``. Nothing is stored in the clear.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from modules import account_store, auth_supabase

TABLE = "yahoo_credentials"
KEY_ENV = "YAHOO_CREDENTIAL_KEY"
FALLBACK_KEY_ENV = "ESPN_CREDENTIAL_KEY"


@dataclass(frozen=True)
class YahooCredentials:
    refresh_token: str
    access_token: str = ""
    access_expires_at: float = 0.0  # unix seconds; 0 = unknown/expired
    yahoo_guid: str = ""

    def __repr__(self) -> str:  # never let a token land in a log line
        return "YahooCredentials(<redacted>)"


class YahooCredentialError(RuntimeError):
    """``reason`` is a stable code; the message never includes a token."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _fernet():
    key = os.environ.get(KEY_ENV, "").strip() or os.environ.get(FALLBACK_KEY_ENV, "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("utf-8"))
    except Exception:
        return None


def is_configured() -> bool:
    """True only when a usable encryption key is present."""

    return _fernet() is not None


def client_configured() -> bool:
    """Yahoo app credentials are set on the server (values never read here)."""

    return bool(os.environ.get("YAHOO_CLIENT_ID", "").strip() and os.environ.get("YAHOO_CLIENT_SECRET", "").strip())


def encrypt(credentials: YahooCredentials) -> dict[str, Any]:
    fernet = _fernet()
    if fernet is None:
        raise YahooCredentialError("not_configured", "Yahoo isn't available right now.")
    return {
        "refresh_token_enc": fernet.encrypt(credentials.refresh_token.encode("utf-8")).decode("ascii"),
        "access_token_enc": fernet.encrypt(credentials.access_token.encode("utf-8")).decode("ascii")
        if credentials.access_token
        else "",
        "access_expires_at": int(credentials.access_expires_at or 0),
        "yahoo_guid": credentials.yahoo_guid or "",
    }


def decrypt(row: dict[str, Any]) -> YahooCredentials | None:
    """Ciphertext row -> credentials, or None if it can't be read (wrong key, corrupt)."""

    fernet = _fernet()
    if fernet is None:
        return None
    try:
        refresh = fernet.decrypt(str(row.get("refresh_token_enc") or "").encode("ascii")).decode("utf-8")
        access_enc = str(row.get("access_token_enc") or "")
        access = fernet.decrypt(access_enc.encode("ascii")).decode("utf-8") if access_enc else ""
    except Exception:
        return None
    if not refresh:
        return None
    try:
        expires = float(row.get("access_expires_at") or 0)
    except (TypeError, ValueError):
        expires = 0.0
    return YahooCredentials(
        refresh_token=refresh, access_token=access, access_expires_at=expires, yahoo_guid=str(row.get("yahoo_guid") or "")
    )


# --- Supabase storage (per user; same shape as modules.espn_credentials) ------


def _user_query(user_id: str) -> str:
    return f"user_id=eq.{requests.utils.quote(str(user_id or '').strip(), safe='')}"


def _service_headers() -> dict[str, str] | None:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        return None
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _service_url(config: dict, query: str = "") -> str:
    return auth_supabase.rest_api_url(config, TABLE, query)


def load(config: dict, access_token: str, *, user_id: str) -> YahooCredentials | None:
    if not is_configured() or not user_id:
        return None
    headers = _service_headers()
    if headers is not None:
        try:
            response = requests.get(
                _service_url(config, f"{_user_query(user_id)}&limit=1"), headers=headers, timeout=15
            )
            rows = response.json() if response.status_code < 400 else []
        except Exception:
            return None
        return decrypt(rows[0]) if rows and isinstance(rows, list) else None
    rows, error = account_store.fetch_rows(
        config, access_token, TABLE, user_id=user_id, timing_label="supabase_yahoo_credentials_lookup"
    )
    if error or not rows:
        return None
    return decrypt(rows[0])


def has_saved(config: dict, access_token: str, *, user_id: str) -> bool:
    return load(config, access_token, user_id=user_id) is not None


def save(config: dict, access_token: str, *, user_id: str, credentials: YahooCredentials) -> None:
    payload = {"user_id": str(user_id), **encrypt(credentials)}
    headers = _service_headers()
    failure = "Couldn't save your Yahoo connection."
    if headers is not None:
        try:
            response = requests.post(
                _service_url(config, "on_conflict=user_id"),
                headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=payload,
                timeout=15,
            )
        except Exception:
            raise YahooCredentialError("storage_failed", failure) from None
        if response.status_code >= 400:
            raise YahooCredentialError("storage_failed", failure)
        return
    ok, error = account_store.upsert_row(config, access_token, TABLE, payload, on_conflict="user_id")
    if not ok:
        raise YahooCredentialError("storage_failed", failure)


def delete(config: dict, access_token: str, *, user_id: str) -> None:
    headers = _service_headers()
    failure = "Couldn't remove your Yahoo connection."
    if headers is not None:
        try:
            response = requests.delete(
                _service_url(config, _user_query(user_id)), headers={**headers, "Prefer": "return=minimal"}, timeout=8
            )
        except Exception:
            raise YahooCredentialError("storage_failed", failure) from None
        if response.status_code >= 400:
            raise YahooCredentialError("storage_failed", failure)
        return
    ok, _error = account_store.delete_rows(
        config, access_token, TABLE, query=_user_query(user_id), timing_label="supabase_yahoo_credentials_delete"
    )
    if not ok:
        raise YahooCredentialError("storage_failed", failure)
