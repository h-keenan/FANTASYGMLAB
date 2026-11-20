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

from modules import account_store, app_config, auth_supabase, experimental_graduation


TOKENS_TABLE = "push_tokens"
VALID_PLATFORMS = ("ios", "android")
EXPO_PUSH_API_URL = "https://exp.host/--/api/v2/push/send"
EXPO_PUSH_CHUNK_SIZE = 100
EXPO_RECEIPTS_API_URL = "https://exp.host/--/api/v2/push/getReceipts"
EXPO_RECEIPTS_CHUNK_SIZE = 300
# Kill switch (owner Zach, infra). ON: registering a token re-owns it to the
# caller server-side (service-role upsert; the user-JWT path cannot, RLS hides
# another account's row) and senders drop a token whose owner is ambiguous.
# OFF restores the previous user-JWT-only behaviour exactly.
HANDOFF_FLAG = "DYNASTYGM_PUSH_TOKEN_HANDOFF_V1"


def handoff_enabled() -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(HANDOFF_FLAG, default=True)


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_platform(value: object) -> str:
    text = _safe_text(value).lower()
    return text if text in VALID_PLATFORMS else ""


def normalize_timezone(value: object) -> str:
    """Return a valid IANA timezone name or "" (unknown)."""

    text = _safe_text(value)
    if not text or len(text) > 64:
        return ""
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(text)
    except Exception:
        return ""
    return text


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
    timezone: str = "",
) -> tuple[bool, str]:
    """Upsert a device token for the caller. Primary key is the token itself,
    so one token has exactly one owner. Under the user's JWT, RLS hides a
    row owned by another account, so the conflict update is rejected and the
    old owner would keep the device. With the handoff flag on, the upsert runs
    with the service role instead (``user_id`` is the verified caller): one
    atomic statement that moves the token to the caller. Falls back to the
    JWT path when the service key is not configured or the flag is off.
    """

    token = _safe_text(expo_push_token)
    uid = _safe_text(user_id)
    if not token or not uid:
        return False, "A push token and user are required."
    if not is_expo_push_token(token):
        return False, "That doesn't look like an Expo push token."

    payload: dict[str, Any] = {
        "expo_push_token": token,
        "user_id": uid,
        "platform": normalize_platform(platform),
        "device_name": _safe_text(device_name)[:120],
    }
    if handoff_enabled():
        ok, error, attempted = _service_reown(config, payload, normalize_timezone(timezone))
        if attempted:
            return ok, error
    tz_name = normalize_timezone(timezone)
    if tz_name:
        # `timezone` needs docs/supabase_push_safety.sql. Until that is
        # applied the upsert with the extra column errors, so retry without
        # it: registration itself must never break on an unapplied migration.
        ok, error = account_store.upsert_row(
            dict(config), access_token, TOKENS_TABLE, {**payload, "timezone": tz_name}, on_conflict="expo_push_token"
        )
        if ok:
            return ok, error
    return account_store.upsert_row(
        dict(config), access_token, TOKENS_TABLE, payload, on_conflict="expo_push_token"
    )


def _service_reown(config: Mapping[str, Any], payload: dict[str, Any], tz_name: str) -> tuple[bool, str, bool]:
    """Service-role upsert on the token primary key. Returns (ok, error, attempted)."""

    key = app_config.config_value("SUPABASE_SERVICE_ROLE_KEY")
    if not key or not auth_supabase.is_configured(dict(config)):
        return False, "", False
    from datetime import datetime, timezone as _tz

    body = {**payload, "updated_at": datetime.now(_tz.utc).isoformat()}
    attempts = ([{"timezone": tz_name}] if tz_name else []) + [{}]
    for extra in attempts:
        try:
            response = requests.post(
                auth_supabase.rest_api_url(dict(config), TOKENS_TABLE, "on_conflict=expo_push_token"),
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                json={**body, **extra},
                timeout=15,
            )
        except Exception:
            return False, "Could not reach Supabase table storage.", True
        if response.status_code < 400:
            return True, "", True
        # `timezone` column may be unapplied: the next attempt omits it.
    return False, "push token upsert failed", True


def owned_recipients(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    """user_id -> tokens, each token under exactly one user.

    The primary key already guarantees one owner per token; if a legacy or
    hand-edited table ever shows the same token under two users, only the most
    recently updated owner keeps it, so a handed-off device never receives the
    previous account's notifications. With the flag off, rows pass through.
    """

    clean = [r for r in rows if isinstance(r, Mapping)]
    newest: dict[str, tuple[str, str]] = {}
    if handoff_enabled():
        for row in clean:
            token = _safe_text(row.get("expo_push_token"))
            stamp = _safe_text(row.get("updated_at"))
            if token and (token not in newest or stamp >= newest[token][0]):
                newest[token] = (stamp, _safe_text(row.get("user_id")))
    out: dict[str, list[str]] = {}
    for row in clean:
        uid = _safe_text(row.get("user_id"))
        token = _safe_text(row.get("expo_push_token"))
        if not uid or not token:
            continue
        if newest and newest[token][1] != uid:
            continue
        if token not in out.setdefault(uid, []):
            out[uid].append(token)
    return out


def unregister_token(
    config: Mapping[str, Any],
    access_token: str,
    *,
    user_id: str,
    expo_push_token: str,
) -> tuple[bool, str]:
    """Delete one of the caller's own tokens (e.g. called on sign-out). The
    ``user_id`` filter plus the table's delete RLS policy mean a caller can
    never remove another account's token (a foreign token deletes 0 rows)."""

    token = _safe_text(expo_push_token)
    uid = _safe_text(user_id)
    if not token or not uid:
        return False, "A push token and user are required."

    return account_store.delete_rows(
        dict(config),
        access_token,
        TOKENS_TABLE,
        query=f"user_id=eq.{uid}&expo_push_token=eq.{account_store.pg_eq(token, safe="[]")}",
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
    invalid_tokens: list[str] = []
    ticket_ids: list[dict[str, str]] = []  # [{token, id}] for receipt polling
    ticket_errors: list[dict[str, str]] = []  # [{token, error}] immediate rejections
    accepted = 0
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
            # Tickets come back in request order. DeviceNotRegistered means
            # the app was uninstalled / token revoked -- the caller should
            # delete it so it stops being retried every sweep.
            for token, ticket in zip(chunk, chunk_tickets):
                if _ticket_is_device_not_registered(ticket):
                    invalid_tokens.append(token)
                if isinstance(ticket, Mapping) and ticket.get("status") == "ok" and ticket.get("id"):
                    ticket_ids.append({"token": token, "id": str(ticket["id"])})
                    accepted += 1
                elif isinstance(ticket, Mapping) and ticket.get("status") == "error":
                    details = ticket.get("details") if isinstance(ticket.get("details"), Mapping) else {}
                    ticket_errors.append({"token": token, "error": str(details.get("error") or ticket.get("message") or "error")})
                else:
                    accepted += 1
        sent += len(chunk)

    return {
        "ok": True,
        "sent": sent,
        "tickets": tickets,
        "invalid_tokens": invalid_tokens,
        "ticket_ids": ticket_ids,
        "ticket_errors": ticket_errors,
        "error": "",
    }


def get_expo_receipts(ticket_ids: Iterable[str], *, timeout: float = 20) -> dict[str, Any]:
    """Fetch delivery receipts for earlier tickets.

    Returns {"ok": bool, "receipts": {ticket_id: {"status", "error"?}}}. Never
    raises. Expo only retains receipts ~24h, and a missing id simply means
    "not ready / expired" (the caller leaves it for the next poll)."""

    ids = [i for i in (_safe_text(t) for t in ticket_ids) if i]
    receipts: dict[str, Any] = {}
    for start in range(0, len(ids), EXPO_RECEIPTS_CHUNK_SIZE):
        chunk = ids[start : start + EXPO_RECEIPTS_CHUNK_SIZE]
        try:
            response = requests.post(
                EXPO_RECEIPTS_API_URL,
                json={"ids": chunk},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=timeout,
            )
            if response.status_code >= 400:
                return {"ok": bool(receipts), "receipts": receipts, "error": f"Expo receipts API returned {response.status_code}."}
            payload = response.json()
        except Exception as exc:
            return {"ok": bool(receipts), "receipts": receipts, "error": f"Could not reach Expo receipts API: {exc}"}
        data = payload.get("data") if isinstance(payload, Mapping) else None
        if isinstance(data, Mapping):
            for key, value in data.items():
                if isinstance(value, Mapping):
                    details = value.get("details") if isinstance(value.get("details"), Mapping) else {}
                    receipts[str(key)] = {
                        "status": str(value.get("status") or ""),
                        "error": str(details.get("error") or value.get("message") or ""),
                    }
    return {"ok": True, "receipts": receipts, "error": ""}


def _ticket_is_device_not_registered(ticket: Any) -> bool:
    if not isinstance(ticket, Mapping) or ticket.get("status") != "error":
        return False
    details = ticket.get("details")
    return isinstance(details, Mapping) and details.get("error") == "DeviceNotRegistered"
