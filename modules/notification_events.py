"""notification_events: the audit / receipt / open-metric layer of the push
pipeline (docs/supabase_notifications.sql, docs/notifications.md).

One row per item in a delivered (or failed) push. ``push_notification_log``
remains the dedupe + weekly-cap source of truth (so behavior is identical
with or without this table); events add what the log cannot: delivery
receipts, failures, opens, and the exact text/deep link that was sent.

Everything here is optional and fails soft:
- Disabled unless ``NOTIFICATION_EVENTS`` is truthy (set once the SQL has been
  applied by hand), and
- auto-disables for the rest of the process the first time the table turns
  out to be missing, so an unapplied migration can never break a sweep.

``config`` is duck-typed (``.configured``, ``.url``, ``.service_role_key``) so
this module does not import modules.push_triggers (which imports it).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

import requests

from modules import app_config, push_tokens

EVENTS_TABLE = "notification_events"
RECEIPT_MIN_AGE = timedelta(minutes=15)
RECEIPT_MAX_AGE = timedelta(hours=23)  # Expo drops receipts after ~24h
RECEIPT_BATCH_LIMIT = 1000

_table_missing = False


def reset_for_tests() -> None:
    global _table_missing
    _table_missing = False


def events_enabled(*, environ: Mapping | None = None, secrets: Any = None) -> bool:
    if _table_missing:
        return False
    raw = app_config.config_value("NOTIFICATION_EVENTS", environ=environ, secrets=secrets)
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def new_batch_id() -> str:
    return str(uuid.uuid4())


def _headers(config: Any, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _note_response(response: Any) -> bool:
    """True when the write/read succeeded. Flags a missing table."""

    global _table_missing
    status = getattr(response, "status_code", 500)
    if status < 400:
        return True
    if status == 404:
        _table_missing = True
    else:
        try:
            text = str(response.text or "")
        except Exception:
            text = ""
        if "42P01" in text or "does not exist" in text or "PGRST205" in text:
            _table_missing = True
    return False


def record_batch(
    config: Any,
    *,
    user_id: str,
    batch_id: str,
    items: list[Mapping[str, Any]],
    title: str,
    body: str,
    state: str,
    tickets: list[Mapping[str, str]] | None = None,
    error: str = "",
    now: datetime | None = None,
) -> bool:
    """Insert one row per item of a push. ``state`` is 'sent' or 'failed'.
    Returns False (and never raises) on any problem."""

    if not config.configured or not user_id or not items or _table_missing:
        return False
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    rows = [
        {
            "user_id": user_id,
            "batch_id": batch_id,
            "league_id": str(item.get("league_id") or ""),
            "category": str(item.get("category") or ""),
            "dedupe_key": str(item.get("recommendation_id") or ""),
            "state": state,
            "title": title,
            "body": body,
            "deep_link": str(item.get("deep_link") or ""),
            "tickets": list(tickets or []),
            "error": error[:500],
            "sent_at": stamp if state == "sent" else None,
        }
        for item in items
    ]
    try:
        response = requests.post(
            f"{config.url}/rest/v1/{EVENTS_TABLE}",
            headers=_headers(config, prefer="return=minimal"),
            json=rows,
            timeout=15,
        )
    except Exception:
        return False
    return _note_response(response)


def poll_receipts(
    config: Any,
    *,
    delete_tokens: Callable[[list[str]], None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve Expo receipts for events sent 15 min-23 h ago.

    delivered -> state 'delivered'; error -> state 'failed' with the Expo error
    code; DeviceNotRegistered additionally prunes the token. Events whose
    receipt Expo no longer has are closed as 'delivered' only when ok, never
    guessed: an unknown receipt past the retention window is left as 'sent'
    (unconfirmed) and stops being polled. Never raises."""

    stats: dict[str, Any] = {"checked": 0, "delivered": 0, "failed": 0, "tokens_pruned": 0, "errors": []}
    if not config.configured or _table_missing:
        return stats
    current = now or datetime.now(timezone.utc)
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{EVENTS_TABLE}",
            headers=_headers(config),
            params={
                "select": "id,batch_id,tickets,sent_at",
                "state": "eq.sent",
                "receipt_checked_at": "is.null",
                "sent_at": f"lte.{(current - RECEIPT_MIN_AGE).isoformat()}",
                "order": "sent_at.asc",
                "limit": str(RECEIPT_BATCH_LIMIT),
            },
            timeout=20,
        )
    except Exception as exc:
        stats["errors"].append(f"events read failed ({exc})")
        return stats
    if not _note_response(response):
        stats["errors"].append("events read failed")
        return stats
    try:
        rows = response.json()
    except Exception:
        rows = []
    rows = [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []
    ticket_to_token: dict[str, str] = {}
    for row in rows:
        for ticket in row.get("tickets") or []:
            if isinstance(ticket, Mapping) and ticket.get("id"):
                ticket_to_token[str(ticket["id"])] = str(ticket.get("token") or "")
    if not ticket_to_token:
        # Nothing to ask Expo about (e.g. tickets lacked ids): close them so
        # they are not scanned forever.
        _patch_events(config, [str(r.get("id")) for r in rows], {"receipt_checked_at": current.isoformat()})
        return stats

    result = push_tokens.get_expo_receipts(list(ticket_to_token))
    if not result.get("ok") and not result.get("receipts"):
        stats["errors"].append(str(result.get("error") or "receipts unavailable"))
        return stats
    receipts: Mapping[str, Mapping[str, str]] = result.get("receipts") or {}
    dead_tokens: list[str] = []
    updates: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        row_tickets = [t for t in (row.get("tickets") or []) if isinstance(t, Mapping) and t.get("id")]
        statuses = [receipts.get(str(t["id"])) for t in row_tickets]
        sent_at = _parse(row.get("sent_at"))
        expired = sent_at is not None and current - sent_at > RECEIPT_MAX_AGE
        if any(s is None for s in statuses) and not expired:
            continue  # not ready yet; poll again next run
        stats["checked"] += 1
        errors = [s for s in statuses if s and s.get("status") == "error"]
        for ticket, status in zip(row_tickets, statuses):
            if status and status.get("error") == "DeviceNotRegistered" and ticket.get("token"):
                dead_tokens.append(str(ticket["token"]))
        if errors and len(errors) == len([s for s in statuses if s]) and statuses:
            state, error = "failed", str(errors[0].get("error") or "error")
            stats["failed"] += 1
        elif all(s is None for s in statuses):
            state, error = "sent", "receipt_expired"  # unconfirmed; stop polling
        else:
            state, error = "delivered", ""
            stats["delivered"] += 1
        updates.setdefault((state, error), []).append(str(row.get("id")))
    # One PATCH per (state, error) group, not one per row.
    for (state, error), ids in updates.items():
        for start in range(0, len(ids), 100):
            _patch_events(
                config,
                ids[start : start + 100],
                {"state": state, "error": error, "receipt_checked_at": current.isoformat()},
            )
    if dead_tokens and delete_tokens is not None:
        unique = list(dict.fromkeys(dead_tokens))
        delete_tokens(unique)
        stats["tokens_pruned"] = len(unique)
    return stats


def _parse(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _patch_events(config: Any, ids: list[str], values: Mapping[str, Any]) -> None:
    clean = [i for i in ids if i and "," not in i and ")" not in i]
    if not clean:
        return
    try:
        requests.patch(
            f"{config.url}/rest/v1/{EVENTS_TABLE}",
            headers=_headers(config, prefer="return=minimal"),
            params={"id": "in.(" + ",".join(clean) + ")"},
            json=dict(values),
            timeout=15,
        )
    except Exception:
        pass


def mark_opened(config: Mapping[str, Any], access_token: str, *, user_id: str, batch_id: str) -> bool:
    """Record that the user tapped a push (called by the app, as the user: RLS
    restricts the PATCH to their own rows). Idempotent: only the first open
    sets opened_at. Fails soft."""

    import re

    from modules import auth_supabase

    if not re.fullmatch(r"[0-9a-fA-F-]{32,40}", batch_id or "") or not user_id or _table_missing:
        return False
    if not auth_supabase.is_configured(dict(config)):
        return False
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        response = requests.patch(
            auth_supabase.rest_api_url(
                dict(config), EVENTS_TABLE, f"user_id=eq.{user_id}&batch_id=eq.{batch_id}&opened_at=is.null"
            ),
            headers={**auth_supabase.auth_headers(dict(config), access_token), "Prefer": "return=minimal"},
            json={"opened_at": stamp, "state": "opened"},
            timeout=10,
        )
    except Exception:
        return False
    return _note_response(response)
