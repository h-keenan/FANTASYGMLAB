"""Basic automated push-notification trigger sweep.

Runs as a standalone Render Cron Job (scripts/run_push_trigger_sweep.py),
not inside the request-serving mobile API process — see render.yaml's
fantasygm-lab-push-trigger-sweep entry. Owns its own minimal service-role
Supabase access, mirroring modules/revenuecat_webhook.py's pattern: each
backend-only job gets its own config loader so a bug in one job can't
affect another's.

Scope ("basic", per explicit request): for every registered push token,
resolve the account's Sleeper leagues, build each league's real "Next Move"
briefing (modules.dashboard_engine — the exact same engine the mobile
Dashboard screen uses), and push only the two categories that already mean
"this needs your attention" (top_priority, watch). Dedup is a durable
Supabase table (docs/supabase_push_notification_log.sql) keyed on
(user_id, recommendation_id) so a recommendation is pushed once, not every
sweep.

Push safety (docs/notification-audit-2026-10.md): a global rolling-7-day
cap per user, quiet hours in the user's device timezone, one batched push per
sweep per user, fail-closed preference reads, and no league/team names in the
visible push text. Not covered: league_movement-category pushes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Mapping

import pandas as pd
import requests

from modules import alert_presentation, app_config, dashboard_engine, faab, gm_targets, league_calendar, league_recaps, league_value_settings, nfl_schedule, player_eligibility, push_tokens, rankings, sleeper, sleeper_leagues, team_stance


PLAYERS_DB_PATH = "data/players.db"
PUSH_TOKENS_TABLE = "push_tokens"
PROFILES_TABLE = "profiles"
NOTIFICATION_LOG_TABLE = "push_notification_log"
USER_SETTINGS_TABLE = "user_settings"
TRADE_OUTCOMES_TABLE = "trade_outcomes"
# Matches services/mobile_api_service.py's own copy of this constant — the
# mobile API and this cron script are separate processes, so it's a
# duplicated value rather than a shared import (see docs/supabase_trade_outcomes.sql).
TRADE_OUTCOME_FOLLOWUP_DELAY_HOURS = 20
# Every push category a user can individually toggle off — the Notification
# Settings screen (mobile) reads/writes exactly this key set.
TOGGLEABLE_PUSH_CATEGORIES = ("top_priority", "watch", "recap", "injury", "team_situation", "trade_followup", "lineup_lock", "waiver_reminder", "trade_deadline")
# push item category -> the preference key that gates it. Only the two
# one-off pushes differ from their category name.
PREFERENCE_KEY_BY_CATEGORY = {
    "gm_stance_reminder": "team_situation",
    "trade_followup": "trade_followup",
}
# Highest priority first. Used for ordering a batch and for deciding which
# items survive the weekly cap.
PUSH_PRIORITY_ORDER = (
    "injury",
    "lineup_lock",
    "trade_deadline",
    "top_priority",
    "watch",
    "waiver_reminder",
    "trade_followup",
    "recap",
    "gm_stance_reminder",
)
# Time-critical categories that may use the last weekly-cap slot.
# trade_deadline fires at most three times a season per league and is only
# useful before the window closes, so it may also use the last slot.
CAP_RESERVED_CATEGORIES = frozenset({"injury", "lineup_lock", "trade_deadline"})
# Sleeper exposes the deadline as a WEEK, not a date, so the countdown pushes
# are week-granular: two weeks out, one week out, and the deadline week
# itself ("last call"). The sweep never guesses a calendar date.
TRADE_DEADLINE_PUSH_WEEKS_LEFT = (2, 1, 0)
TRADE_DEADLINE_PUSH_COPY = {
    2: "Trade deadline is two weeks away. Review your trade ideas while there is time to deal.",
    1: "Trade deadline is next week. Check your trade ideas before the market closes.",
    0: "Last call: this is the trade deadline week. Make your final trades now.",
}
# Lineup-lock reminder fires when a flagged player's (or the next slate's)
# kickoff is inside this window; the sweep runs every 30 minutes.
LINEUP_LOCK_WINDOW = timedelta(hours=2)
# Waiver reminder: the evening before the league's waiver day, from this
# America/New_York hour on (see waiver_reminder_push_item).
WAIVER_REMINDER_START_HOUR_ET = 12
_ET = "America/New_York"
DEFAULT_WEEKLY_PUSH_CAP = 4
WEEKLY_CAP_WINDOW = timedelta(days=7)
QUIET_HOURS_START = 22  # local hour, inclusive
QUIET_HOURS_END = 8  # local hour, exclusive
DEFAULT_TIMEZONE = "America/New_York"
# No server-side privacy-mode flag exists (privacy mode is client-only display
# masking), so visible push text never carries league or team names. League
# context stays in the invisible `data` payload for tap routing.
INCLUDE_LEAGUE_NAMES_IN_PUSH_TEXT = False
PUSH_CATEGORIES = frozenset({"top_priority", "watch"})
PUSH_TITLE_BY_CATEGORY = {
    "top_priority": "Your Next Move",
    "watch": "Watch",
    "recap": "Recap Ready",
    "injury": "Injury Update",
    # Title text only — GM Stance / Team Situation merge (product decision,
    # 2026-09-26). The internal category key/recommendation_id prefix stays
    # "gm_stance_reminder" on purpose, so an already-sent dedup row for an
    # existing user still matches (see push_notification_log) rather than
    # firing the one-time nudge a second time after a rename.
    "gm_stance_reminder": "Set Your Team Situation",
    "trade_followup": "Did this trade happen?",
    "lineup_lock": "Lineup Lock",
    "waiver_reminder": "Waivers Process Soon",
    "trade_deadline": "Trade Deadline",
}
DEFAULT_LENS = league_value_settings.DEFAULT_VALUATION_LENS  # per-league lens: default_lens_for_league


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


@dataclass(frozen=True)
class PushTriggerConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_push_trigger_config(*, environ: dict | None = None, secrets: Any = None) -> PushTriggerConfig:
    return PushTriggerConfig(
        url=app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _headers(config: PushTriggerConfig, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def fetch_push_recipients(config: PushTriggerConfig) -> dict[str, list[str]]:
    """user_id -> list of that account's Expo push tokens (service-role, cross-user)."""

    if not config.configured:
        return {}
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{PUSH_TOKENS_TABLE}",
            headers=_headers(config),
            params={"select": "user_id,expo_push_token"},
            timeout=15,
        )
    except Exception:
        return {}
    if response.status_code >= 400:
        return {}
    try:
        rows = response.json()
    except Exception:
        return {}
    recipients: dict[str, list[str]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        token = _safe_text(row.get("expo_push_token"))
        if not user_id or not token:
            continue
        recipients.setdefault(user_id, []).append(token)
    return recipients


def fetch_sleeper_usernames(config: PushTriggerConfig, user_ids: list[str]) -> dict[str, str]:
    """user_id -> linked sleeper_username, for the given ids (service-role)."""

    ids = [uid for uid in (_safe_text(u) for u in user_ids) if uid]
    if not config.configured or not ids:
        return {}
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{PROFILES_TABLE}",
            headers=_headers(config),
            params={"select": "user_id,sleeper_username", "user_id": f"in.({','.join(ids)})"},
            timeout=15,
        )
    except Exception:
        return {}
    if response.status_code >= 400:
        return {}
    try:
        rows = response.json()
    except Exception:
        return {}
    usernames: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        username = _safe_text(row.get("sleeper_username"))
        if user_id and username:
            usernames[user_id] = username
    return usernames


def fetch_push_preferences(config: PushTriggerConfig, user_ids: list[str]) -> dict[str, dict[str, bool]] | None:
    """user_id -> {category: enabled}, defaulting every category to True.

    Returns None when the read FAILED (transport/HTTP/parse error): callers
    must fail closed and send nothing rather than ignore opt-outs. A user with
    no settings row is simply absent from the dict (default-open).

    Reuses modules.account_store's existing user_settings table (one JSONB
    `settings` blob per user, auth.uid()=user_id RLS — service-role bypasses
    that here same as it does for push_tokens/profiles above) rather than a
    new table: push category preferences are just another namespaced key
    under the same per-user settings blob the mobile app already has a
    working read/write path for (modules.account_store.fetch_user_settings /
    upsert_user_settings), under the "push_categories" key.
    """
    ids = [uid for uid in (_safe_text(u) for u in user_ids) if uid]
    if not config.configured or not ids:
        return {}
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{USER_SETTINGS_TABLE}",
            headers=_headers(config),
            params={"select": "user_id,settings", "user_id": f"in.({','.join(ids)})"},
            timeout=15,
        )
    except Exception:
        return None
    if response.status_code >= 400:
        return None
    try:
        rows = response.json()
    except Exception:
        return None
    if not isinstance(rows, list):
        return None
    preferences: dict[str, dict[str, bool]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        if not user_id:
            continue
        settings = row.get("settings") if isinstance(row.get("settings"), Mapping) else {}
        categories = settings.get("push_categories") if isinstance(settings.get("push_categories"), Mapping) else {}
        preferences[user_id] = {
            category: bool(categories.get(category, True)) for category in TOGGLEABLE_PUSH_CATEGORIES
        }
    return preferences


def push_item_allowed(preferences: dict[str, dict[str, bool]], *, user_id: str, category: str) -> bool:
    """Default-open: no settings row (or an unrecognized category) means enabled."""

    user_prefs = preferences.get(user_id)
    if user_prefs is None:
        return True
    return bool(user_prefs.get(PREFERENCE_KEY_BY_CATEGORY.get(category, category), True))


def fetch_gm_stance_leagues(config: PushTriggerConfig, user_ids: list[str]) -> dict[str, set[str]]:
    """user_id -> the set of league_ids that already have a declared Team
    Situation stored (see services/mobile_api_service.py's get_gm_stance,
    which now reads modules.team_stance — GM Stance's own separate
    "team_strategy_by_league" user_settings storage this used to read was
    retired in the GM Stance / Team Situation merge, 2026-09-26). Used only
    to decide whether the one-time "set your Team Situation" reminder is
    still owed for a league — never to read the stance value itself.
    """

    ids = [uid for uid in (_safe_text(u) for u in user_ids) if uid]
    if not config.configured or not ids:
        return {}
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{team_stance.STANCE_TABLE}",
            headers=_headers(config),
            params={"select": "user_id,league_id", "user_id": f"in.({','.join(ids)})"},
            timeout=15,
        )
    except Exception:
        return {}
    if response.status_code >= 400:
        return {}
    try:
        rows = response.json()
    except Exception:
        return {}
    result: dict[str, set[str]] = {uid: set() for uid in ids}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        league_id = _safe_text(row.get("league_id"))
        if not user_id or not league_id:
            continue
        result.setdefault(user_id, set()).add(league_id)
    return result


def fetch_gm_targets_untouchable_ids(
    config: PushTriggerConfig, user_ids: list[str]
) -> dict[str, dict[str, set[str]]]:
    """user_id -> league_id -> player_ids that user marked untouchable in
    GM Targets (modules.gm_targets.GmTarget.untouchable), read service-role/
    bulk since this sweep runs outside any one user's session — the push
    sweep's own equivalent of modules.gm_targets.cached_untouchable_ids.

    Recommendation-compliance audit finding: trade_hub_engine.
    generate_trade_idea_records' `untouchable_player_ids` contract ("hard-
    blocks those players from every outgoing package") only holds if every
    trade-idea caller actually fetches and threads it through. The
    Dashboard, mobile API, and Portfolio surfaces all do; this sweep
    previously didn't fetch GM Targets at all, so a push notification could
    recommend trading away a player the user had explicitly protected.
    """

    ids = [uid for uid in (_safe_text(u) for u in user_ids) if uid]
    if not config.configured or not ids:
        return {}
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{gm_targets.TARGETS_TABLE}",
            headers=_headers(config),
            params={
                "select": "user_id,league_id,player_id",
                "user_id": f"in.({','.join(ids)})",
                "untouchable": "eq.true",
            },
            timeout=15,
        )
    except Exception:
        return {}
    if response.status_code >= 400:
        return {}
    try:
        rows = response.json()
    except Exception:
        return {}
    result: dict[str, dict[str, set[str]]] = {uid: {} for uid in ids}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        league_id = _safe_text(row.get("league_id"))
        player_id = _safe_text(row.get("player_id"))
        if not user_id or not league_id or not player_id:
            continue
        result.setdefault(user_id, {}).setdefault(league_id, set()).add(player_id)
    return result


def gm_stance_reminder_push_item(
    *, league_id: str, league_name: str, leagues_with_stance: set[str]
) -> dict[str, Any] | None:
    """A one-time nudge to declare a Team Situation for this league — never
    re-fires once sent (dedup is the same durable push_notification_log
    every other category uses, keyed on this item's recommendation_id)
    regardless of whether the user ever actually sets one, matching the
    explicit "once, if never set" product decision (not a recurring
    reminder). Internal category/id are still "gm_stance_reminder" — see
    PUSH_TITLE_BY_CATEGORY's comment for why.
    """

    if league_id in leagues_with_stance:
        return None
    return {
        "league_id": league_id,
        "league_name": league_name,
        "category": "gm_stance_reminder",
        "headline": "Tell us if you're rebuilding, competing, or balanced — it shapes your trade suggestions.",
        "recommendation_id": f"gm_stance_reminder:{league_id}",
    }


def already_notified_batch(config: PushTriggerConfig, *, user_id: str, recommendation_ids: list[str]) -> set[str]:
    """Which of these recommendation_ids have already been pushed to this user.

    One Supabase round trip per league's worth of push_items rather than one
    per item — at sweep scale (many users × many leagues), that per-item
    dedup lookup is the dominant cost. Fails closed: treats every id as
    already-notified (skip, don't push) on any transport/parse failure, so a
    missed push beats a duplicate one.
    """
    ids = [rid for rid in dict.fromkeys(recommendation_ids) if rid]
    if not config.configured or not user_id or not ids:
        return set()
    # PostgREST's `in.(...)` filter has no escaping for a literal "," or ")"
    # inside a value; every recommendation_id this codebase generates is a
    # sha256 hex digest or a colon-joined id/int string, so this can't
    # actually happen — but fail closed (skip pushing) rather than corrupt
    # the filter if it ever does.
    safe_ids = [rid for rid in ids if "," not in rid and ")" not in rid]
    if len(safe_ids) != len(ids):
        return set(ids)
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{NOTIFICATION_LOG_TABLE}",
            headers=_headers(config),
            params={
                "select": "recommendation_id",
                "user_id": f"eq.{user_id}",
                "recommendation_id": "in.(" + ",".join(safe_ids) + ")",
            },
            timeout=15,
        )
    except Exception:
        return set(ids)
    if response.status_code >= 400:
        return set(ids)
    try:
        rows = response.json()
    except Exception:
        return set(ids)
    if not isinstance(rows, list):
        return set(ids)
    return {str(row.get("recommendation_id")) for row in rows if isinstance(row, dict) and row.get("recommendation_id")}


def delete_invalid_push_tokens(config: PushTriggerConfig, tokens: list[str]) -> None:
    """Remove tokens Expo reported as DeviceNotRegistered (service-role)."""

    clean = [t for t in (_safe_text(tok) for tok in tokens) if push_tokens.is_expo_push_token(t)]
    if not config.configured or not clean:
        return
    # Token format is ExponentPushToken[...]; delete one at a time with an
    # exact eq filter so no value ever needs in.(...) escaping.
    for token in clean:
        try:
            requests.delete(
                f"{config.url}/rest/v1/{PUSH_TOKENS_TABLE}",
                headers=_headers(config, prefer="return=minimal"),
                params={"expo_push_token": f"eq.{token}"},
                timeout=15,
            )
        except Exception:
            pass


def record_notification(config: PushTriggerConfig, *, user_id: str, recommendation_id: str, league_id: str) -> None:
    if not config.configured or not user_id or not recommendation_id:
        return
    try:
        requests.post(
            f"{config.url}/rest/v1/{NOTIFICATION_LOG_TABLE}",
            headers=_headers(config, prefer="return=minimal,resolution=ignore-duplicates"),
            json={"user_id": user_id, "recommendation_id": recommendation_id, "league_id": _safe_text(league_id)},
            timeout=15,
        )
    except Exception:
        pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_weekly_push_cap(*, environ: dict | None = None, secrets: Any = None) -> int:
    """Per-user pushes allowed in a rolling 7 days (PUSH_WEEKLY_CAP, default 4)."""

    raw = app_config.config_value("PUSH_WEEKLY_CAP", environ=environ, secrets=secrets)
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_WEEKLY_PUSH_CAP
    return value if 1 <= value <= 50 else DEFAULT_WEEKLY_PUSH_CAP


def fetch_push_timezones(config: PushTriggerConfig) -> dict[str, str]:
    """user_id -> IANA timezone of that account's most recently registered
    device. Needs push_tokens.timezone (docs/supabase_push_safety.sql); when
    the column is not there yet the read errors and this returns {} so every
    user falls back to DEFAULT_TIMEZONE.
    """

    if not config.configured:
        return {}
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{PUSH_TOKENS_TABLE}",
            headers=_headers(config),
            params={"select": "user_id,timezone,updated_at", "order": "updated_at.asc"},
            timeout=15,
        )
    except Exception:
        return {}
    if response.status_code >= 400:
        return {}
    try:
        rows = response.json()
    except Exception:
        return {}
    zones: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        zone = push_tokens.normalize_timezone(row.get("timezone"))
        if user_id and zone:
            zones[user_id] = zone  # ascending updated_at: newest device wins
    return zones


def _resolve_tzinfo(tz_name: str) -> tzinfo:
    from zoneinfo import ZoneInfo

    for name in (tz_name, DEFAULT_TIMEZONE):
        try:
            if name:
                return ZoneInfo(name)
        except Exception:
            continue
    return timezone(timedelta(hours=-5))


def is_quiet_hours(tz_name: str, now: datetime | None = None) -> bool:
    """True from QUIET_HOURS_START to QUIET_HOURS_END (22:00-08:00) local."""

    current = (now or _utcnow()).astimezone(_resolve_tzinfo(tz_name))
    return current.hour >= QUIET_HOURS_START or current.hour < QUIET_HOURS_END


def count_recent_pushes(config: PushTriggerConfig, user_id: str, now: datetime | None = None) -> int | None:
    """Pushes sent to this user in the last 7 days, from push_notification_log.

    A batched push writes all its rows in ONE insert, so they share a
    sent_at (the DB's now()); distinct sent_at values == distinct pushes.
    Returns None on any read failure so the caller fails closed.
    """

    if not config.configured or not user_id:
        return None
    cutoff = ((now or _utcnow()) - WEEKLY_CAP_WINDOW).isoformat()
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{NOTIFICATION_LOG_TABLE}",
            headers=_headers(config),
            params={"select": "sent_at", "user_id": f"eq.{user_id}", "sent_at": f"gte.{cutoff}"},
            timeout=15,
        )
    except Exception:
        return None
    if response.status_code >= 400:
        return None
    try:
        rows = response.json()
    except Exception:
        return None
    if not isinstance(rows, list):
        return None
    return len({str(row.get("sent_at")) for row in rows if isinstance(row, Mapping) and row.get("sent_at")})


def _priority(item: Mapping[str, Any]) -> int:
    category = item.get("category")
    return PUSH_PRIORITY_ORDER.index(category) if category in PUSH_PRIORITY_ORDER else len(PUSH_PRIORITY_ORDER)


def apply_weekly_cap(items: list[dict[str, Any]], *, sent_this_week: int, cap: int) -> list[dict[str, Any]]:
    """Items allowed to push given the user's rolling-7-day count.

    One slot is reserved for time-critical categories (injury, lineup_lock):
    other items stop at cap-1 sent, reserved ones at cap.
    """

    if sent_this_week >= cap:
        return []
    if sent_this_week >= cap - 1:
        return [item for item in items if item.get("category") in CAP_RESERVED_CATEGORIES]
    return list(items)


def build_batched_message(items: list[dict[str, Any]]) -> tuple[str, str, dict[str, Any]]:
    """One push for all of a user's pending items: highest priority leads, the
    rest are summarised ("+N more"). No league or team names in visible text
    (see INCLUDE_LEAGUE_NAMES_IN_PUSH_TEXT); league context rides in `data`.
    """

    ordered = sorted(items, key=_priority)
    lead = ordered[0]
    title = PUSH_TITLE_BY_CATEGORY.get(lead["category"], "Watch")
    if INCLUDE_LEAGUE_NAMES_IN_PUSH_TEXT and lead.get("league_name"):
        title = f"{title} — {lead['league_name']}"
    body = lead["headline"]
    if len(ordered) > 1:
        body = f"{body} (+{len(ordered) - 1} more update{'s' if len(ordered) > 2 else ''})"
    data: dict[str, Any] = {
        "league_id": lead.get("league_id", ""),
        "league_name": lead.get("league_name", ""),
        "category": lead["category"],
    }
    if lead.get("player_id"):
        data["player_id"] = lead["player_id"]
        data["player_name"] = lead.get("player_name", "")
    if len(ordered) > 1:
        data["count"] = len(ordered)
    return title, body, data


def record_notifications(config: PushTriggerConfig, *, user_id: str, entries: list[tuple[str, str]]) -> None:
    """Log (recommendation_id, league_id) pairs in ONE insert so they share
    sent_at and count as a single push toward the weekly cap."""

    rows = [
        {"user_id": user_id, "recommendation_id": rid, "league_id": _safe_text(lid)}
        for rid, lid in entries
        if rid
    ]
    if not config.configured or not user_id or not rows:
        return
    try:
        requests.post(
            f"{config.url}/rest/v1/{NOTIFICATION_LOG_TABLE}",
            headers=_headers(config, prefer="return=minimal,resolution=ignore-duplicates"),
            json=rows,
            timeout=15,
        )
    except Exception:
        pass


def resolve_roster_for_sleeper_user(rosters: list[dict], sleeper_user_id: str) -> dict | None:
    """Faithful port of services/mobile_api_service.py's _resolve_my_roster
    matching step (owner_id == sleeper_user_id) — see module docstring."""

    for roster in rosters or ():
        if _safe_text(roster.get("owner_id")) == sleeper_user_id:
            return roster
    return None


def load_valued_players(lens: str, league_settings: Mapping[str, Any] | None) -> tuple[pd.DataFrame, str]:
    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(players_df, surface="push_trigger_sweep")
    if players_df.empty:
        return players_df, ""
    valued = league_value_settings.apply_valuation_lens(players_df, lens, league_settings)
    score_field = league_value_settings.valuation_score_field(lens)
    return valued, score_field


def league_briefing_push_items(
    *,
    league_id: str,
    sleeper_user_id: str,
    players_df: pd.DataFrame,
    score_field: str,
    untouchable_player_ids: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """The subset of one league's "Next Move" briefing worth pushing about.

    `untouchable_player_ids` is the caller's GM Targets untouchable list for
    this exact (user, league) — see fetch_gm_targets_untouchable_ids. This
    sweep never precomputes its own `trade_idea_records` (no live request
    context to share one with), so it relies on
    dashboard_engine.compose_next_move_briefing's own fallback trade-idea
    generation — threading the list through to that fallback is what makes
    this sweep's trade tile honor the same "never send this player away"
    guarantee the Dashboard/mobile API/Portfolio surfaces already do for the
    identical recommendation.
    """

    league = sleeper.get_league(league_id)
    if not league:
        return []
    league_settings = league_value_settings.detect_league_value_settings_from_payload(league)
    rosters = sleeper.get_rosters(league_id)
    my_roster = resolve_roster_for_sleeper_user(rosters, sleeper_user_id)
    if my_roster is None:
        return []
    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return []
    all_rostered_player_ids: set[str] = set()
    for roster in rosters:
        all_rostered_player_ids.update(str(pid) for pid in (roster.get("players") or []))

    # Trade-idea alerts are graded and ranked under the team's posture too
    # (modules.trade_posture): the auto classification from the shared cached
    # rankings row. The sweep has no per-user Team Situation read, so a
    # declared stance is not applied here (the Dashboard/Trade Hub apply it).
    from modules import trade_hub_engine

    try:
        team_strategy = trade_hub_engine.roster_posture(
            league_id=league_id,
            roster=my_roster,
            lens=league_value_settings.default_lens_for_league(league),
            players_db_path=PLAYERS_DB_PATH,
        )["key"]
    except Exception:
        team_strategy = "retool"
    briefing = dashboard_engine.compose_next_move_briefing(
        league_id=league_id,
        roster_id=str(my_roster.get("roster_id") or ""),
        players_df=players_df,
        roster_player_ids=roster_player_ids,
        all_rostered_player_ids=all_rostered_player_ids,
        league_settings=league_settings,
        score_field=score_field,
        rosters=rosters,
        untouchable_player_ids=untouchable_player_ids,
        team_strategy=team_strategy,
    )
    league_name = _safe_text(league.get("name"), "Your league")
    # Push-safety (#1493): no league/team/manager names in push text. A trade
    # headline must never name the partner; scrub any known team name.
    private_names: set[str] = set()
    for roster in rosters:
        meta = roster.get("metadata") if isinstance(roster.get("metadata"), Mapping) else {}
        private_names.add(_safe_text(meta.get("team_name")))
    if league_name != "Your league":
        private_names.add(league_name)
    items: list[dict[str, Any]] = []
    for item in briefing.items:
        if item.category not in PUSH_CATEGORIES or not item.recommendation_id:
            continue
        item_names = set(private_names)
        presentation = getattr(item, "presentation", None)
        if isinstance(presentation, Mapping):
            item_names.add(_safe_text(presentation.get("partner_team_name")))
        item_names.discard("")
        item_names.discard("Trade partner")
        headline_text = item.headline
        if any(name.casefold() in headline_text.casefold() for name in item_names):
            headline_text = "A trade idea is ready to review"
        push_item: dict[str, Any] = {
            "league_id": league_id,
            "league_name": league_name,
            "category": item.category,
            "headline": headline_text,
            "recommendation_id": item.recommendation_id,
        }
        # route_player_id/_name already exist on DailyBriefingItem for the
        # Dashboard's own player-tap-through (modules/daily_gm_briefing.py,
        # built for the Dashboard injury-tap-through feature) — carry them
        # into the push payload so a tap can deep-link straight to that
        # player instead of always landing on the league hub.
        if item.route_player_id:
            push_item["player_id"] = item.route_player_id
            push_item["player_name"] = item.route_player_name
        items.append(push_item)
    return items


def recap_push_item(league_id: str, league: Mapping[str, Any]) -> dict[str, Any] | None:
    """A "Week N recap is ready" push item — same completed-week detection
    the mobile Recap screen already uses (modules.league_recaps), so a push
    only fires once the exact same data that screen would show is ready."""

    _, _, max_history_week = league_recaps.league_history_window(league)
    matchup_rows = league_recaps.build_matchup_history_rows(
        league_id, max_history_week, fetch_matchups=sleeper.get_matchups
    )
    week = league_recaps.completed_recap_week(league, matchup_rows)
    if week <= 0:
        return None
    return {
        "league_id": league_id,
        "league_name": _safe_text(league.get("name"), "Your league"),
        "category": "recap",
        "headline": f"Week {week} recap is ready",
        "recommendation_id": f"recap:{league_id}:{week}",
    }


def injury_status_push_items(
    *,
    league_id: str,
    league_name: str,
    roster_player_ids: set[str],
    players_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Push items for roster players carrying a real availability-risk status.

    Reuses the exact same Out/Doubtful/IR/etc. classification the Alerts
    feed uses (modules.alert_presentation.UNAVAILABLE_INJURY_STATUSES) —
    "Questionable" is deliberately excluded (too common to be push-worthy;
    it stays visible in-app via Alerts, same as today). No history is
    stored: recommendation_id is keyed on (player, status), so the durable
    push_notification_log dedup already used everywhere else in this sweep
    naturally re-fires only when the status text actually changes, and
    naturally never re-fires for an unchanged status. The first sweep after
    this ships will push once for anyone already carrying a risk status —
    a one-time, bounded backfill, not a recurring spam source.
    """

    if not roster_player_ids or players_df is None or players_df.empty:
        return []
    if "injury_status" not in players_df.columns or "player_id" not in players_df.columns:
        return []

    rows = players_df[players_df["player_id"].astype(str).isin(roster_player_ids)]
    items: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        status_raw = _safe_text(row.get("injury_status"))
        status_norm = status_raw.strip().casefold()
        if status_norm not in alert_presentation.UNAVAILABLE_INJURY_STATUSES:
            continue
        player_id = _safe_text(row.get("player_id"))
        name = _safe_text(row.get("name"), "A player on your roster")
        if not player_id:
            continue
        items.append(
            {
                "league_id": league_id,
                "league_name": league_name,
                "category": "injury",
                "headline": f"{name} is now {status_raw}",
                "recommendation_id": f"injury:{player_id}:{status_norm}",
                # player_id/name are already in scope for this row — carry
                # them along so a tap can deep-link to this exact player
                # instead of only the league hub.
                "player_id": player_id,
                "player_name": name,
            }
        )
    return items


_EMPTY_SLOT_IDS = frozenset({"", "0", "none", "null"})


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def lineup_lock_push_items(
    *,
    league_id: str,
    league_name: str,
    league: Mapping[str, Any],
    my_roster: Mapping[str, Any],
    players_df: pd.DataFrame,
    games: pd.DataFrame | None,
    now: datetime,
) -> list[dict[str, Any]]:
    """Lineup-lock reminders for one league, from real data only.

    Flags (a) a starter carrying an unavailable status (Out/IR/...) whose own
    game kicks off inside LINEUP_LOCK_WINDOW and has not started, and (b) an
    empty slot, a starter no longer on the roster, or a starter on bye, when
    the next NFL kickoff of the week is inside the window. Returns [] (never
    a guess) for off-season / best-ball leagues, a missing starters list, or
    a missing schedule.
    """

    if games is None or not league_calendar.is_in_season(league) or league_calendar.is_best_ball(league):
        return []
    week = league_calendar.current_league_week(league)
    try:
        season = int(league.get("season"))
    except (TypeError, ValueError):
        return []
    starters = my_roster.get("starters")
    if not week or not isinstance(starters, list) or not starters:
        return []
    roster_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    horizon = now + LINEUP_LOCK_WINDOW

    def in_window(kickoff: datetime | None) -> bool:
        return kickoff is not None and now < kickoff <= horizon

    players_by_id: dict[str, Any] = {}
    if players_df is not None and not players_df.empty and "player_id" in players_df.columns:
        wanted = {str(pid) for pid in starters if pid is not None}
        for _, row in players_df[players_df["player_id"].astype(str).isin(wanted)].iterrows():
            players_by_id[str(row.get("player_id"))] = row

    items: list[dict[str, Any]] = []
    bad_slots = 0
    for raw in starters:
        pid = _safe_text(raw)
        if pid.casefold() in _EMPTY_SLOT_IDS or (roster_ids and pid not in roster_ids):
            bad_slots += 1
            continue
        row = players_by_id.get(pid)
        if row is None:
            continue
        team = _safe_text(row.get("team"))
        if not team:
            continue
        game = nfl_schedule.team_matchup_for_week(team, week, season, games=games)
        if game is None:
            if nfl_schedule.team_bye_week(team, season, games=games) == week:
                bad_slots += 1  # a bye-week starter scores zero
            continue
        status_raw = _safe_text(row.get("injury_status"))
        status_norm = status_raw.casefold()
        if status_norm in alert_presentation.UNAVAILABLE_INJURY_STATUSES and in_window(
            _parse_dt(game.get("kickoff_at"))
        ):
            name = _safe_text(row.get("name"), "A starter")
            items.append(
                {
                    "league_id": league_id,
                    "league_name": league_name,
                    "category": "lineup_lock",
                    "headline": f"{name} is {status_raw} and still in your lineup. Kickoff is soon.",
                    "recommendation_id": f"lineup_lock:{league_id}:{week}:out:{pid}:{status_norm}",
                }
            )
    if bad_slots:
        upcoming = [k for k in nfl_schedule.week_kickoffs(season, week, games=games) if k > now]
        next_kickoff = upcoming[0] if upcoming else None
        if in_window(next_kickoff):
            day = next_kickoff.astimezone(_resolve_tzinfo(_ET)).date().isoformat()
            plural = "s" if bad_slots > 1 else ""
            items.append(
                {
                    "league_id": league_id,
                    "league_name": league_name,
                    "category": "lineup_lock",
                    "headline": f"You have {bad_slots} empty or invalid starter slot{plural}. Kickoff is soon.",
                    "recommendation_id": f"lineup_lock:{league_id}:{week}:slots:{day}",
                }
            )
    return items


def waiver_reminder_push_item(
    *,
    league_id: str,
    league_name: str,
    league: Mapping[str, Any],
    my_roster: Mapping[str, Any],
    rosters: list[Mapping[str, Any]],
    players_df: pd.DataFrame,
    score_field: str,
    now: datetime,
) -> dict[str, Any] | None:
    """A waiver reminder only when both signals are real; otherwise None.

    1. Timing: the league has a known waiver system, is in season, is not
       daily-waiver, and tomorrow (America/New_York) is its
       settings.waiver_day_of_week (assumed Monday=0, matching Sleeper's
       Wednesday default of 2; UNVERIFIED: docs.sleeper.com does not document
       this field, checked 2026-10-24. Keep the mapping in one place here
       and re-check against a real league's UI day if it is ever in doubt). Sleeper does not expose the processing
       time of day, so the reminder goes out from midday the day BEFORE,
       never claiming an exact deadline. FAAB leagues with no budget left
       are skipped.
    2. Need: the same need-fit check the Dashboard waiver tile uses
       (select_top_waiver_opportunity flags priority_need_fit /
       injury_replacement_fit), recomputed only on the one eligible day.
    """

    if not league_calendar.is_in_season(league):
        return None
    settings = league.get("settings") if isinstance(league.get("settings"), Mapping) else {}
    mode = faab.sleeper_waiver_mode(league)
    if mode == faab.WAIVER_MODE_UNKNOWN or settings.get("daily_waivers"):
        return None
    try:
        waiver_day = int(settings.get("waiver_day_of_week"))
    except (TypeError, ValueError):
        return None
    if not 0 <= waiver_day <= 6:
        return None
    local = now.astimezone(_resolve_tzinfo(_ET))
    if local.weekday() != (waiver_day - 1) % 7 or local.hour < WAIVER_REMINDER_START_HOUR_ET:
        return None
    if mode == faab.WAIVER_MODE_FAAB:
        try:
            total = int(settings.get("waiver_budget"))
            used = int((my_roster.get("settings") or {}).get("waiver_budget_used"))
        except (TypeError, ValueError):
            return None
        if total - used <= 0:
            return None
    roster_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_ids or players_df is None or players_df.empty:
        return None
    all_rostered: set[str] = set()
    for roster in rosters or ():
        all_rostered.update(str(pid) for pid in (roster.get("players") or []))
    league_settings = league_value_settings.detect_league_value_settings_from_payload(league)
    roster_df = players_df[players_df["player_id"].astype(str).isin(roster_ids)].copy()
    lineup_df = dashboard_engine.suggest_optimal_lineup(roster_df, league_settings, score_field=score_field)
    assessment = dashboard_engine.build_team_needs_assessment(
        roster_df, None, league_settings, lineup_df=lineup_df, score_field=score_field
    )
    needed = dashboard_engine.get_needed_positions(
        roster_df, None, league_settings, assessment=assessment, lineup_df=lineup_df
    )
    if not needed:
        return None
    free_agents = players_df[~players_df["player_id"].astype(str).isin(all_rostered)]
    top = dashboard_engine.select_top_waiver_opportunity(
        free_agents, roster_df, league_settings, score_field, needed_positions=needed
    )
    if top is None or getattr(top, "empty", True):
        return None
    if not (bool(top.get("priority_need_fit")) or bool(top.get("injury_replacement_fit"))):
        return None
    position = _safe_text(top.get("position"))
    where = f" at {position}" if position else ""
    return {
        "league_id": league_id,
        "league_name": league_name,
        "category": "waiver_reminder",
        "headline": f"Waivers process soon and you have a clear need{where}. Check the best available add.",
        "recommendation_id": f"waiver_reminder:{league_id}:{(local.date() + timedelta(days=1)).isoformat()}",
    }


def trade_deadline_push_item(
    *,
    league_id: str,
    league_name: str,
    league: Mapping[str, Any],
) -> dict[str, Any] | None:
    """A trade-deadline countdown push, only from the league's real deadline week.

    Fires when the in-season league is 2 / 1 / 0 weeks from its Sleeper
    ``trade_deadline`` week (modules.league_calendar.weeks_to_deadline). No
    deadline, offseason, or a passed deadline yields None, so nothing is sent
    once trades are closed. The recommendation_id carries the tier, so each
    tier dedups against push_notification_log and sends once per league.
    """

    weeks_left = league_calendar.weeks_to_deadline(league)
    deadline = league_calendar.trade_deadline_week(league)
    if deadline is None or weeks_left not in TRADE_DEADLINE_PUSH_WEEKS_LEFT:
        return None
    return {
        "league_id": league_id,
        "league_name": league_name,
        "category": "trade_deadline",
        "headline": TRADE_DEADLINE_PUSH_COPY[weeks_left],
        "recommendation_id": f"trade_deadline:{league_id}:{deadline}:{weeks_left}",
    }


def run_push_trigger_sweep(*, environ: dict | None = None, secrets: Any = None) -> dict[str, Any]:
    """One sweep: check every registered account's leagues, push what's new.

    Never raises — a bad league or account is logged into `errors` and
    skipped so one failure can't abort the whole sweep.
    """

    config = load_push_trigger_config(environ=environ, secrets=secrets)
    weekly_cap = load_weekly_push_cap(environ=environ, secrets=secrets)
    stats: dict[str, Any] = {
        "ok": True,
        "configured": config.configured,
        "accounts_checked": 0,
        "leagues_checked": 0,
        "pushes_sent": 0,
        "held_quiet_hours": 0,
        "capped": 0,
        "errors": [],
    }
    if not config.configured:
        stats["ok"] = False
        stats["errors"].append("Supabase service-role is not configured.")
        return stats

    recipients = fetch_push_recipients(config)
    if not recipients:
        return stats

    usernames = fetch_sleeper_usernames(config, list(recipients.keys()))
    preferences = fetch_push_preferences(config, list(recipients.keys()))
    if preferences is None:
        # Fail closed: without readable opt-outs, send nothing this run.
        stats["ok"] = False
        stats["errors"].append("Push preferences could not be read; sent nothing this run.")
        return stats
    timezones = fetch_push_timezones(config)
    gm_stance_leagues = fetch_gm_stance_leagues(config, list(recipients.keys()))
    gm_untouchable_ids = fetch_gm_targets_untouchable_ids(config, list(recipients.keys()))
    players_cache: dict[str, tuple[pd.DataFrame, str]] = {}
    games_holder: dict[str, pd.DataFrame | None] = {}

    for user_id, tokens in recipients.items():
        stats["accounts_checked"] += 1
        sleeper_username = usernames.get(user_id, "")
        if not sleeper_username:
            continue
        try:
            sleeper_user_id = sleeper_leagues.resolve_sleeper_user_id(sleeper_username)
        except Exception as exc:
            stats["errors"].append(f"{user_id}: sleeper lookup failed ({exc})")
            continue
        if not sleeper_user_id:
            continue

        try:
            leagues = sleeper_leagues.get_user_leagues(sleeper_username)
        except Exception as exc:
            stats["errors"].append(f"{user_id}: league lookup failed ({exc})")
            continue

        candidates: list[dict[str, Any]] = []
        for league in leagues:
            league_id = _safe_text(league.get("league_id"))
            if not league_id:
                continue
            # Each league is valued on ITS lens (redraft -> Non-Dynasty), the
            # same one server-side decision the app and web open on.
            league_lens = league_value_settings.default_lens_for_league(league)
            if league_lens not in players_cache:
                players_cache[league_lens] = load_valued_players(league_lens, None)
            players_df, score_field = players_cache[league_lens]
            if players_df.empty:
                continue
            stats["leagues_checked"] += 1
            try:
                push_items = league_briefing_push_items(
                    league_id=league_id,
                    sleeper_user_id=sleeper_user_id,
                    players_df=players_df,
                    score_field=score_field,
                    untouchable_player_ids=tuple(
                        sorted(gm_untouchable_ids.get(user_id, {}).get(league_id, ()))
                    ),
                )
            except Exception as exc:
                stats["errors"].append(f"{user_id}/{league_id}: briefing failed ({exc})")
                continue

            league_payload: dict[str, Any] = {}
            try:
                league_payload = sleeper.get_league(league_id) or {}
                if league_payload:
                    recap_item = recap_push_item(league_id, league_payload)
                    if recap_item:
                        push_items.append(recap_item)
            except Exception as exc:
                stats["errors"].append(f"{user_id}/{league_id}: recap check failed ({exc})")

            try:
                rosters = sleeper.get_rosters(league_id)
                my_roster = resolve_roster_for_sleeper_user(rosters, sleeper_user_id)
                if my_roster is not None:
                    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
                    push_items.extend(
                        injury_status_push_items(
                            league_id=league_id,
                            league_name=_safe_text(league_payload.get("name"), "Your league"),
                            roster_player_ids=roster_player_ids,
                            players_df=players_df,
                        )
                    )
            except Exception as exc:
                stats["errors"].append(f"{user_id}/{league_id}: injury status check failed ({exc})")

            try:
                rosters_for_reminders = sleeper.get_rosters(league_id)
                reminder_roster = resolve_roster_for_sleeper_user(rosters_for_reminders, sleeper_user_id)
                if reminder_roster is not None and league_payload:
                    reminder_league_name = _safe_text(league_payload.get("name"), "Your league")
                    now = _utcnow()
                    if league_calendar.is_in_season(league_payload) and push_item_allowed(
                        preferences, user_id=user_id, category="lineup_lock"
                    ):
                        if "games" not in games_holder:
                            try:
                                games_holder["games"] = nfl_schedule.load_games()
                            except Exception:
                                games_holder["games"] = None
                        push_items.extend(
                            lineup_lock_push_items(
                                league_id=league_id,
                                league_name=reminder_league_name,
                                league=league_payload,
                                my_roster=reminder_roster,
                                players_df=players_df,
                                games=games_holder["games"],
                                now=now,
                            )
                        )
                    if push_item_allowed(preferences, user_id=user_id, category="waiver_reminder"):
                        waiver_item = waiver_reminder_push_item(
                            league_id=league_id,
                            league_name=reminder_league_name,
                            league=league_payload,
                            my_roster=reminder_roster,
                            rosters=rosters_for_reminders,
                            players_df=players_df,
                            score_field=score_field,
                            now=now,
                        )
                        if waiver_item:
                            push_items.append(waiver_item)
            except Exception as exc:
                stats["errors"].append(f"{user_id}/{league_id}: lineup/waiver reminder check failed ({exc})")

            if league_payload:
                deadline_item = trade_deadline_push_item(
                    league_id=league_id,
                    league_name=_safe_text(league_payload.get("name"), "Your league"),
                    league=league_payload,
                )
                if deadline_item:
                    push_items.append(deadline_item)

            try:
                stance_item = gm_stance_reminder_push_item(
                    league_id=league_id,
                    league_name=_safe_text(league_payload.get("name"), "Your league"),
                    leagues_with_stance=gm_stance_leagues.get(user_id, set()),
                )
                if stance_item:
                    push_items.append(stance_item)
            except Exception as exc:
                stats["errors"].append(f"{user_id}/{league_id}: gm stance reminder check failed ({exc})")

            push_items = [
                item for item in push_items if push_item_allowed(preferences, user_id=user_id, category=item["category"])
            ]

            already_sent = already_notified_batch(
                config,
                user_id=user_id,
                recommendation_ids=[item["recommendation_id"] for item in push_items],
            )
            candidates.extend(
                item for item in push_items if item["recommendation_id"] not in already_sent
            )

        if not candidates:
            continue
        if is_quiet_hours(timezones.get(user_id, DEFAULT_TIMEZONE)):
            # Held, not dropped: nothing is logged, so the next sweep after
            # quiet hours re-derives these items and sends what is still live.
            stats["held_quiet_hours"] += 1
            continue
        sent_this_week = count_recent_pushes(config, user_id)
        if sent_this_week is None:
            stats["errors"].append(f"{user_id}: weekly push count unavailable; held")
            continue
        allowed = apply_weekly_cap(candidates, sent_this_week=sent_this_week, cap=weekly_cap)
        if not allowed:
            stats["capped"] += 1
            continue
        title, body, notification_data = build_batched_message(allowed)
        result = push_tokens.send_expo_push_notifications(
            tokens, title=title, body=body, data=notification_data
        )
        if result.get("invalid_tokens"):
            delete_invalid_push_tokens(config, list(result["invalid_tokens"]))
        if result.get("ok"):
            # Only dedup-log a delivered push: a transient Expo outage must
            # not permanently swallow these notifications.
            record_notifications(
                config,
                user_id=user_id,
                entries=[(item["recommendation_id"], item["league_id"]) for item in allowed],
            )
            stats["pushes_sent"] += 1
        else:
            stats["errors"].append(f"{user_id}: {result.get('error')}")

    return stats


def fetch_pending_trade_outcome_followups(config: PushTriggerConfig) -> list[dict[str, Any]]:
    """trade_outcomes rows old enough to ask about and not yet pushed
    (service-role, cross-user — see docs/supabase_trade_outcomes.sql).
    """

    if not config.configured:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=TRADE_OUTCOME_FOLLOWUP_DELAY_HOURS)).isoformat()
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{TRADE_OUTCOMES_TABLE}",
            headers=_headers(config),
            params={
                "select": "id,user_id,league_id,partner_team_name",
                "outcome": "eq.pending",
                "followup_pushed_at": "is.null",
                "shared_at": f"lte.{cutoff}",
            },
            timeout=15,
        )
    except Exception:
        return []
    if response.status_code >= 400:
        return []
    try:
        rows = response.json()
    except Exception:
        return []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def mark_trade_outcome_followup_pushed(config: PushTriggerConfig, *, outcome_id: str) -> None:
    """Stop asking again next sweep — set regardless of whether a push was
    actually delivered (e.g. no registered device): the in-app "pending"
    prompt (GET /v1/trade-outcomes/pending) never reads this column, so a
    user without a push token still gets asked next time they open the app.
    """

    if not config.configured or not outcome_id:
        return
    try:
        requests.patch(
            f"{config.url}/rest/v1/{TRADE_OUTCOMES_TABLE}",
            headers=_headers(config, prefer="return=minimal"),
            params={"id": f"eq.{outcome_id}"},
            json={"followup_pushed_at": datetime.now(timezone.utc).isoformat()},
            timeout=15,
        )
    except Exception:
        pass


def run_trade_outcome_followup_sweep(*, environ: dict | None = None, secrets: Any = None) -> dict[str, Any]:
    """One sweep of the "did this trade happen?" push follow-up.

    Independent of run_push_trigger_sweep's per-league briefing loop —
    trade_outcomes rows carry everything needed (user_id, partner name)
    without resolving Sleeper leagues/rosters at all. Never raises; a bad
    row is logged into `errors` and skipped.
    """

    config = load_push_trigger_config(environ=environ, secrets=secrets)
    weekly_cap = load_weekly_push_cap(environ=environ, secrets=secrets)
    stats: dict[str, Any] = {
        "ok": True,
        "configured": config.configured,
        "outcomes_checked": 0,
        "pushes_sent": 0,
        "held": 0,
        "errors": [],
    }
    if not config.configured:
        stats["ok"] = False
        stats["errors"].append("Supabase service-role is not configured.")
        return stats

    pending = fetch_pending_trade_outcome_followups(config)
    if not pending:
        return stats

    recipients = fetch_push_recipients(config)
    preferences = fetch_push_preferences(config, [_safe_text(r.get("user_id")) for r in pending])
    if preferences is None:
        # Fail closed: nothing is sent or marked, the next run retries.
        stats["ok"] = False
        stats["errors"].append("Push preferences could not be read; sent nothing this run.")
        return stats
    timezones = fetch_push_timezones(config)
    sent_counts: dict[str, int | None] = {}
    for row in pending:
        stats["outcomes_checked"] += 1
        outcome_id = _safe_text(row.get("id"))
        user_id = _safe_text(row.get("user_id"))
        if not outcome_id or not user_id:
            continue
        tokens = recipients.get(user_id) or []
        if not tokens:
            mark_trade_outcome_followup_pushed(config, outcome_id=outcome_id)
            continue
        if not push_item_allowed(preferences, user_id=user_id, category="trade_followup"):
            # Opted out: stop asking. The in-app pending prompt still covers it.
            mark_trade_outcome_followup_pushed(config, outcome_id=outcome_id)
            continue
        if is_quiet_hours(timezones.get(user_id, DEFAULT_TIMEZONE)):
            stats["held"] += 1  # not marked: retried at the next sweep
            continue
        if user_id not in sent_counts:
            sent_counts[user_id] = count_recent_pushes(config, user_id)
        sent_this_week = sent_counts[user_id]
        if sent_this_week is None:
            stats["held"] += 1
            continue
        item = {"category": "trade_followup"}
        if not apply_weekly_cap([item], sent_this_week=sent_this_week, cap=weekly_cap):
            stats["held"] += 1
            continue
        league_id = _safe_text(row.get("league_id"))
        # Generic copy: the partner team name is not put in push text (no
        # server-side privacy flag exists; see INCLUDE_LEAGUE_NAMES_IN_PUSH_TEXT).
        try:
            result = push_tokens.send_expo_push_notifications(
                tokens,
                title=PUSH_TITLE_BY_CATEGORY["trade_followup"],
                body="You shared a trade recently \u2014 let us know if it went through.",
                data={
                    "type": "trade_outcome_followup",
                    "category": "trade_followup",
                    "outcome_id": outcome_id,
                    "league_id": league_id,
                },
            )
        except Exception as exc:
            stats["errors"].append(f"{user_id}: trade outcome push failed ({exc})")
            mark_trade_outcome_followup_pushed(config, outcome_id=outcome_id)
            continue
        mark_trade_outcome_followup_pushed(config, outcome_id=outcome_id)
        if result.get("ok"):
            stats["pushes_sent"] += 1
            sent_counts[user_id] = sent_this_week + 1
            record_notifications(
                config, user_id=user_id, entries=[(f"trade_followup:{outcome_id}", league_id)]
            )
        else:
            stats["errors"].append(f"{user_id}: {result.get('error')}")

    return stats
