"""League-scoped leaderboard for the "Guess the Player" mini-games' real,
persisted streaks (modules.guess_the_player; docs/supabase_guess_the_player.sql
and docs/supabase_guess_the_player_name_match.sql).

coridian_, 2026-10-19 ("do it all" on the feature-brainstorm list, confirmed
via Discord): both "Whose stats are these?" and "Who is who?" already
persist a durable, per-user current/best streak (guess_the_player_streaks /
guess_the_player_name_match_streaks — see services/mobile_api_service.py's
GET /v1/guess-the-player[/name-match]). A league-scoped leaderboard
comparing streaks among a user's actual leaguemates is pure assembly of
data that already exists — no new game/valuation logic lives here.

WHO COUNTS AS A "LEAGUEMATE" HERE
----------------------------------
Not every real Sleeper manager in the league — only the other FantasyDesk
accounts that have THIS SAME league_id saved (public.saved_leagues). Both
streak tables are keyed by this app's own Supabase auth user_id, which has
no stored relationship to a Sleeper user_id at all (see module docstring
of modules.guess_the_player and services/mobile_api_service.py's
_resolve_my_roster, which only ever resolves the CALLER's own linked
Sleeper user_id, never a roster of other accounts). Most real Sleeper
managers in a league have no FantasyDesk account, let alone one that
happens to have saved this specific league_id — this leaderboard is
scoped to the ones who do: "the people playing this game together", not
"every real manager in the Sleeper league". That is a genuine, documented
interpretation choice, not an oversight.

CROSS-USER READ — SAME PATTERN AS modules.community_trades
----------------------------------------------------------------
saved_leagues and both streak tables are RLS `auth.uid() = user_id` (see
docs/supabase_accounts.sql, docs/supabase_guess_the_player*.sql) — a
caller's own anon-key + JWT can only ever see their OWN rows, never a
leaguemate's. Exactly the same problem modules.community_trades' own
module docstring documents and solves: this module owns its OWN minimal
service-role Supabase access, isolated from every other job/feature (same
"a bug in one job's config handling can't reach another's" reasoning as
modules.community_trades.load_community_feed_config), used only to
(a) find every saved_leagues row for one league_id across all users and
(b) read those specific users' streak/profile rows — never a broader
scan, never a table dump.

Unlike modules.community_trades, this module does NOT anonymize display
identity: profiles.display_name / saved_leagues.sleeper_username are
already visible to real Sleeper leaguemates via Sleeper itself, so there
is no third-party consent problem the way a stranger's partner_team_name
is in the community feed. The one thing still withheld from the response
is the raw Supabase auth user_id itself — an internal implementation
detail with no reason to ever reach a client — replaced by an opaque,
per-league `member_id` (see `_member_id`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import requests

from modules import app_config

SAVED_LEAGUES_TABLE = "saved_leagues"
PROFILES_TABLE = "profiles"
STAT_LINE_STREAKS_TABLE = "guess_the_player_streaks"
NAME_MATCH_STREAKS_TABLE = "guess_the_player_name_match_streaks"

# Generous, not a pagination contract — real dynasty leagues are 8-16
# teams; this just guards against a pathological league_id.
LEADERBOARD_LIMIT = 100


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


@dataclass(frozen=True)
class LeaderboardConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_leaderboard_config(*, environ: dict | None = None, secrets: Any = None) -> LeaderboardConfig:
    """Own config loader — not modules.community_trades.load_community_feed_
    config — same isolation reasoning that module's own docstring gives,
    applied here even though both read the same two env vars today."""

    return LeaderboardConfig(
        url=app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _headers(config: LeaderboardConfig) -> dict[str, str]:
    return {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }


def _member_id(league_id: str, user_id: str) -> str:
    """Stable, opaque per-(league, user) identity for a leaderboard row —
    same "hash of real identity, never raw ids" convention as
    modules.guess_the_player.compute_pick_id. Lets a client key/diff rows
    without this module ever handing out a raw Supabase auth user_id."""

    raw = f"{_safe_text(league_id)}:{_safe_text(user_id)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def fetch_league_members(config: LeaderboardConfig, league_id: str) -> list[dict[str, Any]]:
    """Every saved_leagues row for this league_id, across ALL users —
    service-role, cross-user by necessity (see module docstring). Only
    user_id/sleeper_username/team_id are selected; user_id is used purely
    to join profiles/streaks and to flag the viewer's own row, never
    returned raw (see build_leaderboard)."""

    league_id_text = _safe_text(league_id)
    if not config.configured or not league_id_text:
        return []
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{SAVED_LEAGUES_TABLE}",
            headers=_headers(config),
            params={
                "select": "user_id,sleeper_username,team_id",
                "league_id": f"eq.{league_id_text}",
                "limit": str(LEADERBOARD_LIMIT),
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
    if not isinstance(rows, list):
        return []
    # One saved_leagues row per (user_id, league_id) by DB constraint
    # (docs/supabase_accounts.sql's unique(user_id, league_id)), but dedupe
    # defensively anyway so a leaderboard row can never be duplicated.
    seen: set[str] = set()
    members: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        members.append(dict(row))
    return members


def _fetch_rows_for_user_ids(
    config: LeaderboardConfig, table: str, user_ids: Iterable[str], *, select: str
) -> dict[str, dict[str, Any]]:
    """Shared helper: rows from `table` for the given user_ids, service-
    role, keyed by user_id. Used for both streak tables and profiles —
    same query shape, different table/select."""

    ids = sorted({_safe_text(user_id) for user_id in user_ids if _safe_text(user_id)})
    if not config.configured or not ids:
        return {}
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{table}",
            headers=_headers(config),
            params={
                "select": select,
                "user_id": "in.(" + ",".join(ids) + ")",
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
    if not isinstance(rows, list):
        return {}
    by_user: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        user_id = _safe_text(row.get("user_id"))
        if user_id:
            by_user[user_id] = dict(row)
    return by_user


def fetch_profiles(config: LeaderboardConfig, user_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """user_id -> {user_id, display_name}, service-role (profiles is RLS
    auth.uid()=user_id too)."""

    return _fetch_rows_for_user_ids(config, PROFILES_TABLE, user_ids, select="user_id,display_name")


def fetch_streaks(config: LeaderboardConfig, table: str, user_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """user_id -> {user_id, current_streak, best_streak} for either streak
    table (STAT_LINE_STREAKS_TABLE or NAME_MATCH_STREAKS_TABLE)."""

    return _fetch_rows_for_user_ids(config, table, user_ids, select="user_id,current_streak,best_streak")


def _streak_int(row: Mapping[str, Any] | None, key: str) -> int:
    if not row:
        return 0
    try:
        return int(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _display_name(member: Mapping[str, Any], profile: Mapping[str, Any] | None) -> str:
    """Fallback chain: profiles.display_name -> saved_leagues.team_id ->
    saved_leagues.sleeper_username -> a generic label. Mirrors the kind of
    fallback chain modules.sleeper.get_league_roster_profiles already uses
    for team identity elsewhere in this app."""

    if profile:
        display_name = _safe_text(profile.get("display_name"))
        if display_name:
            return display_name
    team_id = _safe_text(member.get("team_id"))
    if team_id:
        return team_id
    sleeper_username = _safe_text(member.get("sleeper_username"))
    if sleeper_username:
        return sleeper_username
    return "Manager"


def build_leaderboard(
    members: Iterable[Mapping[str, Any]],
    *,
    league_id: str,
    streaks_by_user: Mapping[str, Mapping[str, Any]],
    profiles_by_user: Mapping[str, Mapping[str, Any]] | None = None,
    viewer_user_id: str = "",
) -> list[dict[str, Any]]:
    """Ranked leaderboard rows — current_streak desc, then best_streak
    desc, then display_name for a stable tie-break. A member with no
    streak row at all (never played this particular game, or played the
    OTHER game) still appears, at 0/0 — never silently dropped. coridian_'s
    "do it all" scope explicitly calls out "a leaguemate with no streak
    history" as a case this must handle, not exclude.
    """

    profiles = profiles_by_user or {}
    viewer = _safe_text(viewer_user_id)
    entries: list[dict[str, Any]] = []
    for member in members:
        if not isinstance(member, Mapping):
            continue
        user_id = _safe_text(member.get("user_id"))
        if not user_id:
            continue
        streak_row = streaks_by_user.get(user_id)
        profile = profiles.get(user_id)
        entries.append(
            {
                "member_id": _member_id(league_id, user_id),
                "display_name": _display_name(member, profile),
                "current_streak": _streak_int(streak_row, "current_streak"),
                "best_streak": _streak_int(streak_row, "best_streak"),
                "is_viewer": bool(viewer) and user_id == viewer,
            }
        )

    entries.sort(
        key=lambda entry: (-entry["current_streak"], -entry["best_streak"], entry["display_name"].lower())
    )
    for index, entry in enumerate(entries):
        entry["rank"] = index + 1
    return entries
