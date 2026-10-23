"""Referral program: a unique per-user invite link, distinct-leaguemate
connection tracking, and a capped free-month GM Pro reward.

Referral code <-> owner: a bijective base62 encoding of the Supabase auth
``user_id`` (a UUID). Decoding the code recovers the referrer's user_id
directly, so no code -> owner lookup table is ever needed — the only
"pending" state the app needs before a brand-new visitor signs up is the one
short string this module caches in ``session_state``, nothing durable.

Everything that *is* durable is a key inside the already-established
per-user ``user_settings.settings`` JSONB blob — the exact same pattern
``modules.theme_mode`` / ``modules.user_preferences`` / ``modules.
trade_eval_usage`` already use. No new Supabase table.

Two settings keys, two different row owners:

- ``REFERRAL_ATTRIBUTION_KEY`` lives on the REFERRED user's own row: which
  referrer's code brought them in, written once (idempotency guard) so a
  later reconnect can never double-count the referrer.
- ``REFERRAL_PROGRAM_KEY`` lives on the REFERRER's own row: the distinct
  referred user_ids that have completed a Sleeper connection, plus the
  reward state computed from that count (``comp_months_granted``,
  ``comp_until``).

Writing the attribution flag is an ordinary own-row write with the referred
user's own access token (same shape as every other preference write in this
app). Crediting the REFERRER is a cross-row write with no access token
available for that other account at all — this app already has exactly that
shape in ``modules.stripe_webhook`` / ``modules.revenuecat_webhook``, which
update a *different* customer's ``profiles`` row from a backend process
holding only a Supabase service-role key, never that customer's own JWT.
``grant_referral_credit`` below reuses that identical service-role
GET-then-PATCH shape for the ``user_settings`` table. This is a best-effort,
low-contention counter (one Sleeper connection landing at a time in the
overwhelming common case), not a financial ledger — the same read-merge-
write trade-off this app already accepts for every other JSONB preference
(see ``modules.user_preferences.with_onboarding_dismissal`` and siblings).

Reward: once ``REFERRALS_PER_COMP_MONTH`` (3) distinct referred leaguemates
have each connected Sleeper, the referrer's ``comp_until`` extends by 30
days, stacking up to ``MAX_COMP_MONTHS`` (3) total free months (i.e. the
cap bites at the 9th distinct connection). Turning a live ``comp_until``
into an actual Pro grant is ``modules.premium.effective_entitlement``'s job
— see that module's docstring additions: a comp *only ever upgrades an
otherwise-Free resolved tier*, so an active paid Stripe subscription (which
already resolves Pro/Front Office) is never touched by this module.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, MutableMapping
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from modules import account_store
from modules import app_config
from modules import auth_supabase
from modules import user_preferences

REFERRAL_QUERY_PARAM = "ref"
REFERRAL_PROGRAM_KEY = "referral_program"
REFERRAL_ATTRIBUTION_KEY = "referral_attribution"

REFERRALS_PER_COMP_MONTH = 3
MAX_COMP_MONTHS = 3
COMP_MONTH_DAYS = 30

# session_state keys — session-only, never persisted directly.
PENDING_CODE_SESSION_KEY = "_pending_referral_code"
PENDING_REFERRER_SESSION_KEY = "_pending_referrer_user_id"

_BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_BASE62_INDEX = {char: index for index, char in enumerate(_BASE62_ALPHABET)}


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


# --------------------------------------------------------------------------
# Referral code <-> user_id (bijective, no lookup table required).


def _to_base62(number: int) -> str:
    if number <= 0:
        return _BASE62_ALPHABET[0]
    base = len(_BASE62_ALPHABET)
    digits: list[str] = []
    while number:
        number, remainder = divmod(number, base)
        digits.append(_BASE62_ALPHABET[remainder])
    return "".join(reversed(digits))


def _from_base62(text: str) -> int | None:
    base = len(_BASE62_ALPHABET)
    total = 0
    for char in text:
        digit = _BASE62_INDEX.get(char)
        if digit is None:
            return None
        total = total * base + digit
    return total


def referral_code_for_user(user_id: Any) -> str:
    """Stable, unique, reversible code for one Supabase auth ``user_id``.

    Bijective with the UUID: decoding the code *is* the owner lookup, so
    this never needs a durable code -> owner mapping of its own.
    """

    text = _safe_text(user_id)
    try:
        parsed = uuid.UUID(text)
    except (ValueError, AttributeError, TypeError):
        return ""
    return _to_base62(parsed.int)


def referrer_user_id_from_code(code: Any) -> str:
    """Inverse of ``referral_code_for_user``. "" for anything invalid."""

    text = _safe_text(code)
    if not text:
        return ""
    number = _from_base62(text)
    if number is None:
        return ""
    try:
        return str(uuid.UUID(int=number))
    except (ValueError, OverflowError):
        return ""


def referral_link(user_id: Any, *, base_url: str = "") -> str:
    """The full shareable invite URL for one signed-in user. "" if invalid."""

    code = referral_code_for_user(user_id)
    if not code:
        return ""
    clean_base = _safe_text(base_url).rstrip("/") or app_config.app_base_url()
    return f"{clean_base}/?{REFERRAL_QUERY_PARAM}={code}"


# --------------------------------------------------------------------------
# Arrival capture — session-only until the visitor authenticates.


def _first_query_value(raw: Any) -> str:
    if isinstance(raw, (list, tuple)):
        return _safe_text(raw[0]) if raw else ""
    return _safe_text(raw)


def capture_referral_code(raw_query_value: Any, session_state: MutableMapping[str, Any]) -> None:
    """Session-only capture of a visiting ``?ref=`` code.

    Pure with respect to ``session_state`` — callers read the ``?ref=`` query value
    themselves and pass it in, so this stays unit-testable with a plain dict. Never
    attributes a user to themselves, and silently ignores an invalid or
    missing code (never raises, never clears an already-pending code on a
    blank re-read).
    """

    code = _first_query_value(raw_query_value)
    if not code:
        return
    referrer_user_id = referrer_user_id_from_code(code)
    if not referrer_user_id:
        return
    auth_session = session_state.get("auth_session")
    auth_session = auth_session if _is_mapping(auth_session) else {}
    account_profile = session_state.get("account_profile")
    account_profile = account_profile if _is_mapping(account_profile) else {}
    current_user_id = _safe_text(auth_session.get("user_id") or account_profile.get("user_id"))
    if current_user_id and current_user_id == referrer_user_id:
        return
    session_state[PENDING_CODE_SESSION_KEY] = code
    session_state[PENDING_REFERRER_SESSION_KEY] = referrer_user_id


# --------------------------------------------------------------------------
# Referred user's own one-time attribution marker.


def attribution_record(user_settings: Mapping[str, Any] | None) -> dict:
    raw = user_preferences.preference_values(user_settings).get(REFERRAL_ATTRIBUTION_KEY)
    return dict(raw) if _is_mapping(raw) else {}


def with_attribution_recorded(
    user_settings: Mapping[str, Any] | None,
    *,
    referrer_user_id: str,
    code: str,
    now: datetime | None = None,
) -> dict:
    """Merge the referred user's own one-time attribution marker."""

    current_time = now or datetime.now(timezone.utc)
    merged = user_preferences.preference_values(user_settings)
    merged[REFERRAL_ATTRIBUTION_KEY] = {
        "referrer_user_id": _safe_text(referrer_user_id),
        "code": _safe_text(code),
        "connected_recorded": True,
        "attributed_at": current_time.isoformat(),
    }
    return {"settings": merged}


def persist_attribution(
    *,
    config: dict,
    session_state: MutableMapping[str, Any],
    referrer_user_id: str,
    code: str,
) -> str:
    """Persist the referred user's own attribution marker. "" on success."""

    user_id = auth_supabase.current_user_id(session_state)
    access_token = auth_supabase.current_access_token(session_state)
    if not user_id or not access_token:
        return "Authentication is required."
    updated = with_attribution_recorded(
        session_state.get("account_user_settings"),
        referrer_user_id=referrer_user_id,
        code=code,
    )
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=updated["settings"])
    saved, error = account_store.upsert_user_settings(config, access_token, payload)
    if saved:
        session_state["account_user_settings"] = payload
        return ""
    return error


# --------------------------------------------------------------------------
# Referrer's own reward state — distinct connected count + comp window.


def program_state(user_settings: Mapping[str, Any] | None) -> dict:
    raw = user_preferences.preference_values(user_settings).get(REFERRAL_PROGRAM_KEY)
    return dict(raw) if _is_mapping(raw) else {}


def _parse_iso(value: Any) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def with_referral_connection_recorded(
    referrer_settings: Mapping[str, Any] | None,
    *,
    referred_user_id: str,
    now: datetime | None = None,
) -> dict:
    """Pure reward computation — the single source of truth for the 3-referral
    threshold and the 3-free-month cap. ``grant_referral_credit`` persists
    exactly what this returns; keep the two in lockstep.

    Idempotent: re-recording an already-counted ``referred_user_id`` is a
    no-op (``already_counted=True``) so a retried/duplicate credit call can
    never inflate the count or grant an extra month.
    """

    current_time = now or datetime.now(timezone.utc)
    merged = user_preferences.preference_values(referrer_settings)
    program = program_state(referrer_settings)
    referred_ids = [
        _safe_text(value) for value in (program.get("referred_user_ids") or []) if _safe_text(value)
    ]
    referred_clean = _safe_text(referred_user_id)
    if not referred_clean or referred_clean in referred_ids:
        return {"settings": merged, "already_counted": True, "program": program}

    referred_ids.append(referred_clean)
    connected_count = len(referred_ids)
    comp_months_granted = max(0, int(program.get("comp_months_granted") or 0))
    comp_until = _parse_iso(program.get("comp_until"))

    if connected_count % REFERRALS_PER_COMP_MONTH == 0 and comp_months_granted < MAX_COMP_MONTHS:
        comp_months_granted += 1
        base = comp_until if comp_until and comp_until > current_time else current_time
        comp_until = base + timedelta(days=COMP_MONTH_DAYS)

    new_program = {
        "referred_user_ids": referred_ids,
        "connected_count": connected_count,
        "comp_months_granted": comp_months_granted,
        "comp_until": comp_until.isoformat() if comp_until else None,
    }
    merged[REFERRAL_PROGRAM_KEY] = new_program
    return {"settings": merged, "already_counted": False, "program": new_program}


def comp_is_active(user_settings: Mapping[str, Any] | None, *, now: datetime | None = None) -> bool:
    """True when this account currently holds a live referral comp window."""

    current_time = now or datetime.now(timezone.utc)
    comp_until = _parse_iso(program_state(user_settings).get("comp_until"))
    return bool(comp_until and comp_until > current_time)


def comp_months_remaining_capacity(user_settings: Mapping[str, Any] | None) -> int:
    """How many more comp months this account could still earn (0..MAX)."""

    granted = max(0, int(program_state(user_settings).get("comp_months_granted") or 0))
    return max(0, MAX_COMP_MONTHS - granted)


# --------------------------------------------------------------------------
# Cross-row referrer credit via Supabase service role. Same shape as
# modules.stripe_webhook.update_profile_entitlement / modules.
# revenuecat_webhook writing a *different* account's row from a backend
# process holding no access token for that account.


def _service_role_config(*, environ: dict | None = None, secrets: Any = None) -> dict:
    return {
        "url": app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        "service_role_key": app_config.config_value(
            "SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets
        ),
    }


def _service_role_headers(config: Mapping[str, Any]) -> dict:
    key = _safe_text(config.get("service_role_key"))
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def grant_referral_credit(
    *,
    config: Mapping[str, Any],
    referrer_user_id: str,
    referred_user_id: str,
    request_session: Any = requests,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Best-effort cross-row credit to the referrer. Never raises.

    Fail-soft by design, the same posture every other growth/analytics
    counter in this app takes: the caller (``handle_sleeper_connected``)
    always lets the referred user's own Sleeper connection succeed
    regardless of what this returns.
    """

    url = _safe_text(config.get("url"))
    service_role_key = _safe_text(config.get("service_role_key"))
    referrer_clean = _safe_text(referrer_user_id)
    referred_clean = _safe_text(referred_user_id)
    if not url or not service_role_key:
        return False, "Referral credit is not configured."
    if not referrer_clean or not referred_clean or referrer_clean == referred_clean:
        return False, "Invalid referral pair."

    base = auth_supabase.normalize_supabase_project_url(url)
    headers = _service_role_headers(config)
    rows_url = (
        f"{base}/rest/v1/user_settings?user_id=eq.{referrer_clean}&select=user_id,settings&limit=1"
    )
    try:
        get_response = request_session.get(rows_url, headers=headers, timeout=15)
    except Exception:
        return False, "Could not reach Supabase table storage."
    if get_response.status_code >= 400:
        return False, f"HTTP {get_response.status_code}"
    try:
        rows = get_response.json()
    except Exception:
        rows = []
    current_settings: dict = {}
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping):
        settings_value = rows[0].get("settings")
        if _is_mapping(settings_value):
            current_settings = {"settings": settings_value}

    updated = with_referral_connection_recorded(current_settings, referred_user_id=referred_clean, now=now)
    if updated.get("already_counted"):
        return True, ""

    upsert_url = f"{base}/rest/v1/user_settings?on_conflict=user_id"
    payload = {"user_id": referrer_clean, "settings": updated["settings"]}
    try:
        write_response = request_session.post(
            upsert_url,
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=payload,
            timeout=15,
        )
    except Exception:
        return False, "Could not reach Supabase table storage."
    if write_response.status_code >= 400:
        return False, f"HTTP {write_response.status_code}"
    return True, ""


# --------------------------------------------------------------------------
# Wiring: call right after the existing `sleeper_connected` analytics event.


def handle_sleeper_connected(
    *,
    config: dict,
    session_state: MutableMapping[str, Any],
    service_config: Mapping[str, Any] | None = None,
) -> str:
    """Attribute + credit a pending referral once Sleeper connects.

    Call this right after the existing ``sleeper_connected`` analytics
    event fires (``app.load_leagues_for_username``). Idempotent and
    fail-soft: every branch either does nothing or persists a one-time
    marker, so a repeated call (the same session re-submitting the same
    username, or a later session reconnecting) can never double-count the
    referrer. Returns "" on success or benign no-op; a non-empty string is
    a customer-safe error that never blocks the caller's own Sleeper
    connection — it is purely informational.
    """

    pending_code = _safe_text(session_state.get(PENDING_CODE_SESSION_KEY))
    pending_referrer = _safe_text(session_state.get(PENDING_REFERRER_SESSION_KEY)) or (
        referrer_user_id_from_code(pending_code)
    )
    if not pending_code or not pending_referrer:
        return ""

    referred_user_id = auth_supabase.current_user_id(session_state)
    access_token = auth_supabase.current_access_token(session_state)
    if not referred_user_id or not access_token:
        # Not authenticated yet (guest Sleeper lookup) — keep the pending
        # marker for the rerun right after sign-up/sign-in completes.
        return ""
    if referred_user_id == pending_referrer:
        session_state.pop(PENDING_CODE_SESSION_KEY, None)
        session_state.pop(PENDING_REFERRER_SESSION_KEY, None)
        return ""

    if attribution_record(session_state.get("account_user_settings")).get("connected_recorded"):
        session_state.pop(PENDING_CODE_SESSION_KEY, None)
        session_state.pop(PENDING_REFERRER_SESSION_KEY, None)
        return ""

    attribution_error = persist_attribution(
        config=config,
        session_state=session_state,
        referrer_user_id=pending_referrer,
        code=pending_code,
    )
    if attribution_error:
        return attribution_error

    credit_config = service_config if service_config is not None else _service_role_config()
    granted, credit_error = grant_referral_credit(
        config=credit_config,
        referrer_user_id=pending_referrer,
        referred_user_id=referred_user_id,
    )

    session_state.pop(PENDING_CODE_SESSION_KEY, None)
    session_state.pop(PENDING_REFERRER_SESSION_KEY, None)

    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "referral_connected",
            props=launch_analytics.build_context_props(
                session_state, source_surface="sleeper_connect"
            ),
            once_key=f"referral_connected:{referred_user_id}",
            state=session_state,
        )
    except Exception:
        pass

    return "" if granted else credit_error
