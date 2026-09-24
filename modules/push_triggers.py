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

Not covered here (left for a later pass, per the same "basic first"
request): per-user notification preferences/quiet hours, batching multiple
leagues into one push, and league_movement-category pushes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import pandas as pd
import requests

from modules import alert_presentation, app_config, dashboard_engine, league_recaps, league_value_settings, player_eligibility, push_tokens, rankings, sleeper, sleeper_leagues


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
TOGGLEABLE_PUSH_CATEGORIES = ("top_priority", "watch", "recap", "injury")
PUSH_CATEGORIES = frozenset({"top_priority", "watch"})
PUSH_TITLE_BY_CATEGORY = {
    "top_priority": "Your Next Move",
    "watch": "Watch",
    "recap": "Recap Ready",
    "injury": "Injury Update",
    "gm_stance_reminder": "Set Your GM Stance",
}
DEFAULT_LENS = "Dynasty"


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


def fetch_push_preferences(config: PushTriggerConfig, user_ids: list[str]) -> dict[str, dict[str, bool]]:
    """user_id -> {category: enabled}, defaulting every category to True.

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
        return {}
    if response.status_code >= 400:
        return {}
    try:
        rows = response.json()
    except Exception:
        return {}
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
    return bool(user_prefs.get(category, True))


def fetch_gm_stance_leagues(config: PushTriggerConfig, user_ids: list[str]) -> dict[str, set[str]]:
    """user_id -> the set of league_ids that already have an explicit GM
    stance stored (see services/mobile_api_service.py's get_gm_stance /
    "team_strategy_by_league" key in the same user_settings blob). Used
    only to decide whether the one-time "set your GM stance" reminder is
    still owed for a league — never to read the stance value itself.
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
        return {}
    if response.status_code >= 400:
        return {}
    try:
        rows = response.json()
    except Exception:
        return {}
    result: dict[str, set[str]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        if not user_id:
            continue
        settings = row.get("settings") if isinstance(row.get("settings"), Mapping) else {}
        by_league = settings.get("team_strategy_by_league")
        result[user_id] = set(by_league.keys()) if isinstance(by_league, Mapping) else set()
    return result


def gm_stance_reminder_push_item(
    *, league_id: str, league_name: str, leagues_with_stance: set[str]
) -> dict[str, Any] | None:
    """A one-time nudge to set a GM stance for this league — never re-fires
    once sent (dedup is the same durable push_notification_log every other
    category uses, keyed on this item's recommendation_id) regardless of
    whether the user ever actually sets one, matching the explicit "once,
    if never set" product decision (not a recurring reminder).
    """

    if league_id in leagues_with_stance:
        return None
    return {
        "league_id": league_id,
        "league_name": league_name,
        "category": "gm_stance_reminder",
        "headline": "Tell us if you're contending, rebuilding, or retooling — it shapes your trade suggestions.",
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
) -> list[dict[str, Any]]:
    """The subset of one league's "Next Move" briefing worth pushing about."""

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

    briefing = dashboard_engine.compose_next_move_briefing(
        league_id=league_id,
        roster_id=str(my_roster.get("roster_id") or ""),
        players_df=players_df,
        roster_player_ids=roster_player_ids,
        all_rostered_player_ids=all_rostered_player_ids,
        league_settings=league_settings,
        score_field=score_field,
        rosters=rosters,
    )
    league_name = _safe_text(league.get("name"), "Your league")
    items: list[dict[str, Any]] = []
    for item in briefing.items:
        if item.category not in PUSH_CATEGORIES or not item.recommendation_id:
            continue
        push_item: dict[str, Any] = {
            "league_id": league_id,
            "league_name": league_name,
            "category": item.category,
            "headline": item.headline,
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


def run_push_trigger_sweep(*, environ: dict | None = None, secrets: Any = None) -> dict[str, Any]:
    """One sweep: check every registered account's leagues, push what's new.

    Never raises — a bad league or account is logged into `errors` and
    skipped so one failure can't abort the whole sweep.
    """

    config = load_push_trigger_config(environ=environ, secrets=secrets)
    stats: dict[str, Any] = {
        "ok": True,
        "configured": config.configured,
        "accounts_checked": 0,
        "leagues_checked": 0,
        "pushes_sent": 0,
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
    gm_stance_leagues = fetch_gm_stance_leagues(config, list(recipients.keys()))
    players_cache: dict[str, tuple[pd.DataFrame, str]] = {}

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

        if DEFAULT_LENS not in players_cache:
            players_cache[DEFAULT_LENS] = load_valued_players(DEFAULT_LENS, None)
        players_df, score_field = players_cache[DEFAULT_LENS]
        if players_df.empty:
            continue

        try:
            leagues = sleeper_leagues.get_user_leagues(sleeper_username)
        except Exception as exc:
            stats["errors"].append(f"{user_id}: league lookup failed ({exc})")
            continue

        for league in leagues:
            league_id = _safe_text(league.get("league_id"))
            if not league_id:
                continue
            stats["leagues_checked"] += 1
            try:
                push_items = league_briefing_push_items(
                    league_id=league_id,
                    sleeper_user_id=sleeper_user_id,
                    players_df=players_df,
                    score_field=score_field,
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
            for push_item in push_items:
                recommendation_id = push_item["recommendation_id"]
                if recommendation_id in already_sent:
                    continue
                title = PUSH_TITLE_BY_CATEGORY.get(push_item["category"], "Watch")
                notification_data: dict[str, Any] = {
                    "league_id": league_id,
                    "league_name": push_item["league_name"],
                    "category": push_item["category"],
                }
                # Only top_priority/watch (route_player_id-sourced) and
                # injury items carry a player_id — recap and
                # gm_stance_reminder stay league-level routing on purpose.
                if push_item.get("player_id"):
                    notification_data["player_id"] = push_item["player_id"]
                    notification_data["player_name"] = push_item.get("player_name", "")
                result = push_tokens.send_expo_push_notifications(
                    tokens,
                    title=f"{title} — {push_item['league_name']}",
                    body=push_item["headline"],
                    data=notification_data,
                )
                record_notification(config, user_id=user_id, recommendation_id=recommendation_id, league_id=league_id)
                if result.get("ok"):
                    stats["pushes_sent"] += 1
                else:
                    stats["errors"].append(f"{user_id}/{league_id}: {result.get('error')}")

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
    stats: dict[str, Any] = {
        "ok": True,
        "configured": config.configured,
        "outcomes_checked": 0,
        "pushes_sent": 0,
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
        partner = _safe_text(row.get("partner_team_name")) or "your trade partner"
        try:
            result = push_tokens.send_expo_push_notifications(
                tokens,
                title="Did this trade happen?",
                body=f"You shared a trade with {partner} — let us know if it went through.",
                data={"type": "trade_outcome_followup", "outcome_id": outcome_id},
            )
        except Exception as exc:
            stats["errors"].append(f"{user_id}: trade outcome push failed ({exc})")
            mark_trade_outcome_followup_pushed(config, outcome_id=outcome_id)
            continue
        mark_trade_outcome_followup_pushed(config, outcome_id=outcome_id)
        if result.get("ok"):
            stats["pushes_sent"] += 1
        else:
            stats["errors"].append(f"{user_id}: {result.get('error')}")

    return stats
