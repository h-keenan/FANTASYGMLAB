"""Encrypted storage for a user's ESPN login cookies (espn_s2 and SWID).

A private ESPN league can only be read with the two cookies ESPN sets when the
league owner is signed in. ESPN has no sign-in for third parties, so the user
pastes them once. They are a live ESPN session, so:

* Both values are encrypted (Fernet) with ``ESPN_CREDENTIAL_KEY`` before they
  leave this process. Supabase only ever holds ciphertext; the key lives in the
  server environment, never in the database or the repo.
* The table (docs/supabase_espn_credentials.sql) is row-level secured to the
  owner, and this module never returns the values to any client: the API only
  reports *whether* credentials are saved.
* Nothing here logs a cookie value. Errors carry a stable reason code only.
* Without ``ESPN_CREDENTIAL_KEY`` the feature is simply off (``is_configured``
  is False); nothing is stored in the clear as a fallback.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import requests

from modules import account_store, auth_supabase

TABLE = "espn_credentials"
KEY_ENV = "ESPN_CREDENTIAL_KEY"

# ESPN's espn_s2 is a long URL-encoded token, SWID is a GUID in braces.
_SWID_PATTERN = re.compile(r"^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$")
_S2_MIN_LENGTH = 40
_S2_MAX_LENGTH = 4096
_S2_PATTERN = re.compile(r"^[A-Za-z0-9%+/=_\-.~]+$")


@dataclass(frozen=True)
class EspnCredentials:
    espn_s2: str
    swid: str

    def __repr__(self) -> str:  # never let a cookie land in a log line
        return "EspnCredentials(<redacted>)"


class EspnCredentialError(RuntimeError):
    """``reason`` is a stable code; the message never includes a cookie value."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _fernet():
    key = os.environ.get(KEY_ENV, "").strip()
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


def normalize(espn_s2: Any, swid: Any) -> EspnCredentials:
    """Trim, undo common paste mistakes, and validate the shape of both values."""

    s2 = str(espn_s2 or "").strip().strip("\"'")
    guid = str(swid or "").strip().strip("\"'")
    # Users often paste the value including its cookie name ("espn_s2=...").
    if s2.lower().startswith("espn_s2="):
        s2 = s2.split("=", 1)[1].strip()
    if guid.upper().startswith("SWID="):
        guid = guid.split("=", 1)[1].strip()
    # ESPN shows SWID with braces; a paste without them is easy to repair.
    if guid and not guid.startswith("{") and not guid.endswith("}"):
        guid = "{" + guid + "}"
    if not (_S2_MIN_LENGTH <= len(s2) <= _S2_MAX_LENGTH) or not _S2_PATTERN.match(s2):
        raise EspnCredentialError(
            "invalid_espn_s2",
            "That espn_s2 value doesn't look right. It is a long string of letters, numbers and % signs.",
        )
    if not _SWID_PATTERN.match(guid):
        raise EspnCredentialError(
            "invalid_swid",
            "That SWID value doesn't look right. It looks like {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}.",
        )
    return EspnCredentials(espn_s2=s2, swid=guid.upper())


def encrypt(credentials: EspnCredentials) -> dict[str, str]:
    fernet = _fernet()
    if fernet is None:
        raise EspnCredentialError("not_configured", "Private ESPN leagues aren't available right now.")
    return {
        "espn_s2_enc": fernet.encrypt(credentials.espn_s2.encode("utf-8")).decode("ascii"),
        "swid_enc": fernet.encrypt(credentials.swid.encode("utf-8")).decode("ascii"),
    }


def decrypt(row: dict[str, Any]) -> EspnCredentials | None:
    """Ciphertext row -> credentials, or None if it can't be read (wrong key, corrupt)."""

    fernet = _fernet()
    if fernet is None:
        return None
    try:
        s2 = fernet.decrypt(str(row.get("espn_s2_enc") or "").encode("ascii")).decode("utf-8")
        guid = fernet.decrypt(str(row.get("swid_enc") or "").encode("ascii")).decode("utf-8")
    except Exception:
        return None
    if not s2 or not guid:
        return None
    return EspnCredentials(espn_s2=s2, swid=guid)


# --- Supabase storage (per user, via the caller's own token + RLS) ------------


def _user_query(user_id: str) -> str:
    return f"user_id=eq.{requests.utils.quote(str(user_id or '').strip(), safe='')}"


def load(config: dict, access_token: str, *, user_id: str) -> EspnCredentials | None:
    if not is_configured() or not user_id:
        return None
    rows, error = account_store.fetch_rows(
        config, access_token, TABLE, user_id=user_id, timing_label="supabase_espn_credentials_lookup"
    )
    if error or not rows:
        return None
    return decrypt(rows[0])


def has_saved(config: dict, access_token: str, *, user_id: str) -> bool:
    """Whether a readable credential is saved. Never returns the values."""

    return load(config, access_token, user_id=user_id) is not None


def save(config: dict, access_token: str, *, user_id: str, credentials: EspnCredentials) -> None:
    payload = {"user_id": str(user_id), **encrypt(credentials)}
    ok, error = account_store.upsert_row(config, access_token, TABLE, payload, on_conflict="user_id")
    if not ok:
        raise EspnCredentialError("storage_failed", error or "Couldn't save your ESPN connection.")


def delete(config: dict, access_token: str, *, user_id: str) -> None:
    ok, error = account_store.delete_rows(
        config, access_token, TABLE, query=_user_query(user_id), timing_label="supabase_espn_credentials_delete"
    )
    if not ok:
        raise EspnCredentialError("storage_failed", error or "Couldn't remove your ESPN connection.")
