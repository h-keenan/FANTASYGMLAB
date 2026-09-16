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
from typing import Any, Mapping

import pandas as pd
import requests

from modules import app_config, dashboard_engine, league_value_settings, player_eligibility, push_tokens, rankings, sleeper, sleeper_leagues


PLAYERS_DB_PATH = "data/players.db"
PUSH_TOKENS_TABLE = "push_tokens"
PROFILES_TABLE = "profiles"
NOTIFICATION_LOG_TABLE = "push_notification_log"
PUSH_CATEGORIES = frozenset({"top_priority", "watch"})
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


def already_notified(config: PushTriggerConfig, *, user_id: str, recommendation_id: str) -> bool:
    if not config.configured or not user_id or not recommendation_id:
        return False
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{NOTIFICATION_LOG_TABLE}",
            headers=_headers(config),
            params={
                "select": "recommendation_id",
                "user_id": f"eq.{user_id}",
                "recommendation_id": f"eq.{recommendation_id}",
                "limit": "1",
            },
            timeout=15,
        )
    except Exception:
        # Fail closed on the side of NOT re-notifying an unreachable log —
        # a missed push is much better than a spammy duplicate one.
        return True
    if response.status_code >= 400:
        return True
    try:
        rows = response.json()
    except Exception:
        return True
    return bool(rows)


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
    return [
        {
            "league_id": league_id,
            "league_name": _safe_text(league.get("name"), "Your league"),
            "category": item.category,
            "headline": item.headline,
            "recommendation_id": item.recommendation_id,
        }
        for item in briefing.items
        if item.category in PUSH_CATEGORIES and item.recommendation_id
    ]


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

            for push_item in push_items:
                recommendation_id = push_item["recommendation_id"]
                if already_notified(config, user_id=user_id, recommendation_id=recommendation_id):
                    continue
                title = "Your Next Move" if push_item["category"] == "top_priority" else "Watch"
                result = push_tokens.send_expo_push_notifications(
                    tokens,
                    title=f"{title} — {push_item['league_name']}",
                    body=push_item["headline"],
                    data={"league_id": league_id, "category": push_item["category"]},
                )
                record_notification(config, user_id=user_id, recommendation_id=recommendation_id, league_id=league_id)
                if result.get("ok"):
                    stats["pushes_sent"] += 1
                else:
                    stats["errors"].append(f"{user_id}/{league_id}: {result.get('error')}")

    return stats
