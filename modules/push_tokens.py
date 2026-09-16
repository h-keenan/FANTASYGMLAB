"""Mobile push notification token registry + Expo push delivery.

Registration is a thin RLS-scoped table (docs/supabase_push_tokens.sql),
mirroring modules/gm_targets.py's separation: this module never decides
*when* to notify a user, it only records device tokens and can hand a
message to Expo's push API. Callers (e.g. a future alerts-driven trigger)
own the "what to send and when" decision.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import requests

from modules import account_store, auth_supabase


TOKENS_TABLE = "push_tokens"
VALID_PLATFORMS = ("ios", "android")
EXPO_PUSH_API_URL = "https://exp.host/--/api/v2/push/send"
EXPO_PUSH_CHUNK_SIZE = 100


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_platform(value: object) -> str:
    text = _safe_text(value).lower()
    return text if text in VALID_PLATFORMS else ""


def is_expo_push_token(value: object) -> bool:
    text = _safe_text(value)
    return text.startswith("ExponentPushToken[") or text.startswith("ExpoPushToken[")


def register_token(
    config: Mapping[str, Any],
    access_token: str,
    *,
    user_id: str,
    expo_push_token: str,
    platform: str = "",
    device_name: str = "",
) -> tuple[bool, str]:
    """Upsert a device token for the caller. Primary key is the token itself,
    so re-registering the same device under a different account reassigns
    the row instead of erroring or duplicating.
    """

    token = _safe_text(expo_push_token)
    uid = _safe_text(user_id)
    if not token or not uid:
        return False, "A push token and user are required."
    if not is_expo_push_token(token):
        return False, "That doesn't look like an Expo push token."

    return account_store.upsert_row(
        dict(config),
        access_token,
        TOKENS_TABLE,
        {
            "expo_push_token": token,
            "user_id": uid,
            "platform": normalize_platform(platform),
            "device_name": _safe_text(device_name)[:120],
        },
        on_conflict="expo_push_token",
    )


def unregister_token(
    config: Mapping[str, Any],
    access_token: str,
    *,
    user_id: str,
    expo_push_token: str,
) -> tuple[bool, str]:
    """Delete one of the caller's own tokens (e.g. called on sign-out)."""

    token = _safe_text(expo_push_token)
    uid = _safe_text(user_id)
    if not token or not uid:
        return False, "A push token and user are required."

    return account_store.delete_rows(
        dict(config),
        access_token,
        TOKENS_TABLE,
        query=f"user_id=eq.{uid}&expo_push_token=eq.{token}",
    )


def fetch_tokens_for_user(
    config: Mapping[str, Any],
    access_token: str,
    *,
    user_id: str,
) -> tuple[list[str], str]:
    rows, error = account_store.fetch_rows(
        dict(config),
        access_token,
        TOKENS_TABLE,
        user_id=user_id,
        extra_query="select=expo_push_token",
    )
    if error:
        return [], error
    tokens = [
        _safe_text(row.get("expo_push_token"))
        for row in rows
        if isinstance(row, Mapping) and _safe_text(row.get("expo_push_token"))
    ]
    return tokens, ""


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def send_expo_push_notifications(
    tokens: Iterable[str],
    *,
    title: str,
    body: str,
    data: Mapping[str, Any] | None = None,
    timeout: float = 15,
) -> dict[str, Any]:
    """POST one or more messages to Expo's push API.

    Pure I/O wrapper — the caller decides who gets notified and with what
    copy. Chunks at Expo's documented 100-message-per-request limit and
    fails soft (never raises) so a delivery hiccup can't take down a
    request handler.
    """

    valid_tokens = [t for t in (_safe_text(tok) for tok in tokens) if is_expo_push_token(t)]
    if not valid_tokens:
        return {"ok": False, "sent": 0, "error": "No valid push tokens."}

    sent = 0
    tickets: list[Any] = []
    for chunk in _chunked(valid_tokens, EXPO_PUSH_CHUNK_SIZE):
        messages = [
            {"to": token, "title": title, "body": body, "data": dict(data or {})}
            for token in chunk
        ]
        try:
            response = requests.post(
                EXPO_PUSH_API_URL,
                json=messages,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=timeout,
            )
        except Exception as exc:
            return {"ok": sent > 0, "sent": sent, "error": f"Could not reach Expo push API: {exc}"}
        if response.status_code >= 400:
            return {"ok": sent > 0, "sent": sent, "error": f"Expo push API returned {response.status_code}."}
        try:
            payload = response.json()
        except Exception:
            payload = {}
        chunk_tickets = payload.get("data") if isinstance(payload, Mapping) else None
        if isinstance(chunk_tickets, list):
            tickets.extend(chunk_tickets)
        sent += len(chunk)

    return {"ok": True, "sent": sent, "tickets": tickets, "error": ""}
