"""Free-tier weekly Trade Evaluator usage counter.

Scout (Free) gets 3 trade evaluations per week, resetting Monday 00:00 in
the *user's own* timezone — not UTC, not server time. GM Pro and Front
Office are unlimited.

Persistence follows the exact pattern already established by
modules.theme_mode / modules.user_preferences: a reserved key inside the
account's `user_settings.settings` JSONB blob (Supabase `user_settings`
table), read via `account_store.fetch_user_settings` and written via
`account_store.upsert_user_settings`. No new storage layer, no new table.

There is currently no app-wide "user's timezone" source anywhere in this
codebase (checked modules/nfl_schedule.py's ZoneInfo use — that is a fixed
stadium timezone, not a per-user one; grepped the rest of modules/ and
app.py for any existing timezone preference — none exists). Every function
below therefore takes an explicit IANA `tz_name` (e.g. "America/New_York"),
defaulting to UTC when the caller has nothing better yet. Whoever wires the
actual browser/device timezone into the app should pass it through here
rather than this module inventing a second source of truth for it.

Pure helpers (`week_start_utc`, `evals_used_this_week`, ...) take the
current usage state directly and are what the Monday-reset boundary tests
exercise. The `user_id`-shaped public API
(`trade_evals_remaining_this_week` / `record_trade_eval_used`) matches the
names the product spec asked for; because this module has no direct
Supabase session of its own, they accept the already-fetched
`user_settings` mapping (or `session_state`/`config` for the write path)
as keyword arguments — `user_id` itself is accepted for interface
stability and future direct-fetch use, but is not required to compute the
answer when the caller already has the settings in hand (as every existing
per-user-preference caller in this app already does).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from modules import premium
from modules import user_preferences

TRADE_EVAL_USAGE_SETTINGS_KEY = "trade_eval_usage"
FREE_WEEKLY_TRADE_EVAL_LIMIT = 3
DEFAULT_TIMEZONE = "UTC"


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_zone(tz_name: Any) -> ZoneInfo:
    try:
        return ZoneInfo(_safe_text(tz_name) or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def week_start_utc(now: datetime, tz_name: Any = DEFAULT_TIMEZONE) -> datetime:
    """The most recent Monday 00:00 in `tz_name`, as a UTC-aware datetime.

    This is the reset boundary: any usage recorded before this instant is
    from a prior week and must not count against the current week's limit.
    """

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    zone = _safe_zone(tz_name)
    local_now = now.astimezone(zone)
    local_monday_date = local_now.date() - timedelta(days=local_now.weekday())
    local_monday_midnight = datetime(
        local_monday_date.year,
        local_monday_date.month,
        local_monday_date.day,
        tzinfo=zone,
    )
    return local_monday_midnight.astimezone(timezone.utc)


def usage_record(user_settings: Mapping[str, Any] | None) -> dict:
    """Defensive copy of the persisted usage record, or {} if none yet."""

    raw = user_preferences.preference_values(user_settings).get(TRADE_EVAL_USAGE_SETTINGS_KEY)
    return dict(raw) if isinstance(raw, Mapping) else {}


def evals_used_this_week(
    user_settings: Mapping[str, Any] | None,
    *,
    tz_name: Any = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> int:
    """Count of evaluations already used in the week containing `now`.

    A stored record from a prior week (its `week_start` does not match the
    current week's boundary) resets to 0 — this is the entire reset
    mechanism; no scheduled job is needed.
    """

    current_time = now if now is not None else datetime.now(timezone.utc)
    record = usage_record(user_settings)
    boundary = week_start_utc(current_time, tz_name).isoformat()
    if _safe_text(record.get("week_start")) != boundary:
        return 0
    try:
        return max(0, int(record.get("count", 0)))
    except (TypeError, ValueError):
        return 0


def trade_evals_remaining_this_week(
    user_id: Any,
    entitlement: Any,
    *,
    user_settings: Mapping[str, Any] | None = None,
    tz_name: Any = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> int | None:
    """Remaining evaluations this week. None = unlimited (Pro/Front Office).

    `user_id` is accepted for interface stability (a future direct-fetch
    implementation would use it) but the current implementation reads the
    count from `user_settings`, exactly like every other per-user
    preference in this app — pass the caller's already-loaded
    `account_user_settings` session value.
    """

    if premium.is_at_least(entitlement, premium.PRO):
        return None
    used = evals_used_this_week(user_settings, tz_name=tz_name, now=now)
    return max(0, FREE_WEEKLY_TRADE_EVAL_LIMIT - used)


def with_trade_eval_recorded(
    user_settings: Mapping[str, Any] | None,
    *,
    tz_name: Any = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> dict:
    """Merge one more recorded evaluation into the settings blob.

    Same "merge without replacing unrelated settings" shape as
    user_preferences.with_onboarding_dismissal / theme_mode.with_theme_mode.
    """

    current_time = now if now is not None else datetime.now(timezone.utc)
    boundary = week_start_utc(current_time, tz_name).isoformat()
    used = evals_used_this_week(user_settings, tz_name=tz_name, now=current_time)
    merged = user_preferences.preference_values(user_settings)
    merged[TRADE_EVAL_USAGE_SETTINGS_KEY] = {"week_start": boundary, "count": used + 1}
    return {"settings": merged}


def persist_trade_eval_used(
    *,
    config: dict,
    session_state: dict,
    tz_name: Any = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> str:
    """Persist one more used evaluation for the signed-in account.

    Empty string on success, else a customer-safe error — same contract as
    user_preferences.persist_authenticated_onboarding.
    """

    from modules import account_store
    from modules import auth_supabase

    user_id = auth_supabase.current_user_id(session_state)
    access_token = auth_supabase.current_access_token(session_state)
    if not user_id or not access_token:
        return "Authentication is required."
    updated = with_trade_eval_recorded(
        session_state.get("account_user_settings"),
        tz_name=tz_name,
        now=now,
    )
    payload = account_store.build_user_settings_payload(
        user_id=user_id,
        settings=updated["settings"],
    )
    saved, error = account_store.upsert_user_settings(config, access_token, payload)
    if saved:
        session_state["account_user_settings"] = payload
        return ""
    return error


def record_trade_eval_used(
    user_id: Any,
    *,
    config: dict | None = None,
    session_state: dict | None = None,
    tz_name: Any = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> str:
    """Record one used evaluation. Empty string on success.

    `user_id` is accepted for interface stability; the actual write goes
    through `session_state`/`config` (the already-authenticated caller),
    matching every other persisted preference in this app. Callers that
    have not yet wired session_state/config through get a clear
    "Authentication is required." rather than a silent no-op.
    """

    if session_state is not None and config is not None:
        return persist_trade_eval_used(
            config=config,
            session_state=session_state,
            tz_name=tz_name,
            now=now,
        )
    return "Authentication is required."
