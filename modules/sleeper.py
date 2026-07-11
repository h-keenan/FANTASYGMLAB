import json
import os
import time
from functools import lru_cache
from typing import Dict, Any, List, Optional
from urllib.parse import quote

import requests

from modules import performance

SLEEPER_BASE = "https://api.sleeper.app/v1"
PLAYERS_CACHE_PATH = "data/sleeper_players.json"
PLAYERS_CACHE_TTL_SECONDS = 60 * 60
PLAYER_STATS_CACHE_TEMPLATE = "data/sleeper_player_stats_{season}.json"
PLAYER_STATS_CACHE_TTL_SECONDS = 12 * 60 * 60
COMPLETED_PLAYER_STATS_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
SLEEPER_AVATAR_BASE = "https://sleepercdn.com/avatars"

PLAYER_STATS_SUM_FIELDS = {
    "gp": "games_played",
    "rec_tgt": "targets",
    "rec": "receptions",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds",
    "rush_att": "rush_attempts",
    "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds",
    "pass_att": "pass_attempts",
    "pass_yd": "passing_yards",
    "pass_td": "passing_tds",
    "pts_std": "fantasy_points",
    "pts_half_ppr": "fantasy_points_half_ppr",
    "pts_ppr": "fantasy_points_ppr",
    "off_snp": "_offensive_snaps",
    "tm_off_snp": "_team_offensive_snaps",
}


def default_player_stats_season(now: time.struct_time | None = None) -> int:
    current = now or time.localtime()
    return int(current.tm_year if current.tm_mon >= 9 else current.tm_year - 1)


def _player_stats_cache_ttl(season: int, now: time.struct_time | None = None) -> int:
    current = now or time.localtime()
    active_regular_season = int(season) == int(current.tm_year) and current.tm_mon >= 9
    return PLAYER_STATS_CACHE_TTL_SECONDS if active_regular_season else COMPLETED_PLAYER_STATS_CACHE_TTL_SECONDS


def _aggregate_player_week_stats(weekly_payloads: List[Dict[str, Any]], season: int) -> Dict[str, Dict[str, Any]]:
    aggregate: Dict[str, Dict[str, Any]] = {}
    observed_fields: Dict[str, set[str]] = {}

    for payload in weekly_payloads:
        if not isinstance(payload, dict):
            continue
        for player_id, raw_stats in payload.items():
            if not isinstance(raw_stats, dict):
                continue
            player_key = str(player_id)
            totals = aggregate.setdefault(player_key, {"stats_season": int(season)})
            seen = observed_fields.setdefault(player_key, set())
            for source_field, target_field in PLAYER_STATS_SUM_FIELDS.items():
                if source_field not in raw_stats or raw_stats.get(source_field) is None:
                    continue
                try:
                    numeric = float(raw_stats.get(source_field))
                except (TypeError, ValueError):
                    continue
                totals[target_field] = float(totals.get(target_field, 0.0)) + numeric
                seen.add(target_field)

    cleaned: Dict[str, Dict[str, Any]] = {}
    integer_fields = {
        "games_played",
        "targets",
        "receptions",
        "receiving_tds",
        "rush_attempts",
        "rushing_tds",
        "pass_attempts",
        "passing_tds",
    }
    for player_id, totals in aggregate.items():
        fields_seen = observed_fields.get(player_id, set())
        result: Dict[str, Any] = {"stats_season": int(season)}
        for field_name in fields_seen:
            value = totals.get(field_name)
            if field_name.startswith("_"):
                continue
            result[field_name] = int(round(value)) if field_name in integer_fields else float(value)

        offensive_snaps = float(totals.get("_offensive_snaps", 0.0))
        team_offensive_snaps = float(totals.get("_team_offensive_snaps", 0.0))
        if offensive_snaps >= 0 and team_offensive_snaps > 0:
            result["snap_share"] = min(1.0, max(0.0, offensive_snaps / team_offensive_snaps))

        games_played = result.get("games_played")
        fantasy_points_ppr = result.get("fantasy_points_ppr")
        if games_played and fantasy_points_ppr is not None:
            result["ppg"] = float(fantasy_points_ppr) / float(games_played)

        if len(result) > 1:
            cleaned[player_id] = result
    return cleaned


def get_season_player_stats(
    season: int | None = None,
    *,
    refresh: bool = False,
    max_week: int = 18,
) -> Dict[str, Dict[str, Any]]:
    """Load cached Sleeper weekly production and aggregate it into season totals."""
    _ensure_data_dir()
    selected_season = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected_season)

    if not refresh and os.path.exists(cache_path):
        try:
            cache_age = time.time() - os.path.getmtime(cache_path)
            if cache_age < _player_stats_cache_ttl(selected_season):
                with open(cache_path, "r", encoding="utf-8") as handle:
                    cached = json.load(handle)
                if isinstance(cached, dict):
                    return cached
        except Exception:
            pass

    weekly_payloads: List[Dict[str, Any]] = []
    for week in range(1, max(1, int(max_week)) + 1):
        url = f"{SLEEPER_BASE}/stats/nfl/regular/{selected_season}/{week}"
        try:
            payload = _request_json("sleeper_player_stats_week", url, timeout=20)
            if isinstance(payload, dict):
                weekly_payloads.append(payload)
        except Exception:
            continue

    if weekly_payloads:
        aggregated = _aggregate_player_week_stats(weekly_payloads, selected_season)
        try:
            with open(cache_path, "w", encoding="utf-8") as handle:
                json.dump(aggregated, handle)
        except Exception:
            pass
        return aggregated

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as handle:
                cached = json.load(handle)
            if isinstance(cached, dict):
                return cached
        except Exception:
            pass
    return {}


def normalize_username(username: str) -> str:
    return (username or "").strip().casefold()


def _ensure_data_dir():
    if not os.path.exists("data"):
        os.makedirs("data")


def _request_json(label: str, url: str, *, timeout: int = 5):
    with performance.time_block(label, category="sleeper"):
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.json()


def get_players(refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch all NFL players from Sleeper, with basic local caching.
    Returns dict keyed by player_id -> player_object.[web:4]
    """
    _ensure_data_dir()

    cache_ok = False
    if not refresh and os.path.exists(PLAYERS_CACHE_PATH):
        try:
            age = time.time() - os.path.getmtime(PLAYERS_CACHE_PATH)
            if age < PLAYERS_CACHE_TTL_SECONDS:
                cache_ok = True
        except Exception:
            cache_ok = False

    if cache_ok:
        try:
            with open(PLAYERS_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    url = f"{SLEEPER_BASE}/players/nfl"
    try:
        with performance.time_block("sleeper_players_fetch", category="sleeper"):
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            players = resp.json()
        if not isinstance(players, dict):
            players = {}
        try:
            with open(PLAYERS_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(players, f)
        except Exception:
            pass
        return players
    except Exception:
        if os.path.exists(PLAYERS_CACHE_PATH):
            try:
                with open(PLAYERS_CACHE_PATH, "r", encoding="utf-8") as f:
                    players = json.load(f)
                if isinstance(players, dict):
                    return players
            except Exception:
                pass
        return {}


@lru_cache(maxsize=256)
def get_user_id(username: str) -> Optional[str]:
    """
    Look up a Sleeper user_id from username.[web:4]
    """
    username = (username or "").strip()
    if not username:
        return None

    candidates = []
    for candidate in [username, username.lower(), username.casefold()]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        url = f"{SLEEPER_BASE}/user/{quote(candidate, safe='')}"
        try:
            data = _request_json("sleeper_user_lookup", url, timeout=5)
            if isinstance(data, dict) and data.get("user_id"):
                return data.get("user_id")
        except Exception:
            continue
    return None


@lru_cache(maxsize=128)
def get_users(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all users in a league.[web:4]
    """
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/users"
    try:
        users = _request_json("sleeper_league_users", url, timeout=5)
        return users if isinstance(users, list) else []
    except Exception:
        return []


@lru_cache(maxsize=128)
def get_rosters(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all rosters in a league.[web:4]
    """
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/rosters"
    try:
        rosters = _request_json("sleeper_league_rosters", url, timeout=5)
        return rosters if isinstance(rosters, list) else []
    except Exception:
        return []


@lru_cache(maxsize=128)
def get_league(league_id: str) -> Dict[str, Any]:
    """
    Get league metadata/settings from Sleeper.
    """
    if not league_id:
        return {}
    url = f"{SLEEPER_BASE}/league/{league_id}"
    try:
        league = _request_json("sleeper_league", url, timeout=5)
        return league if isinstance(league, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=128)
def get_league_drafts(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all draft objects attached to a league.
    """
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/drafts"
    try:
        drafts = _request_json("sleeper_league_drafts", url, timeout=5)
        return drafts if isinstance(drafts, list) else []
    except Exception:
        return []


@lru_cache(maxsize=256)
def get_draft(draft_id: str) -> Dict[str, Any]:
    """
    Get metadata for a Sleeper draft.
    """
    if not draft_id:
        return {}
    url = f"{SLEEPER_BASE}/draft/{draft_id}"
    try:
        draft = _request_json("sleeper_draft", url, timeout=5)
        return draft if isinstance(draft, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=256)
def get_draft_picks(draft_id: str) -> List[Dict[str, Any]]:
    """
    Get all picks made in a Sleeper draft.
    """
    if not draft_id:
        return []
    url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
    try:
        picks = _request_json("sleeper_draft_picks", url, timeout=10)
        return picks if isinstance(picks, list) else []
    except Exception:
        return []


@lru_cache(maxsize=128)
def get_traded_picks(league_id: str) -> List[Dict[str, Any]]:
    """
    Get traded draft picks for a league. Untraded picks are not returned by
    Sleeper, so callers should assume original ownership unless listed here.
    """
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/traded_picks"
    try:
        picks = _request_json("sleeper_traded_picks", url, timeout=5)
        return picks if isinstance(picks, list) else []
    except Exception:
        return []


@lru_cache(maxsize=512)
def get_transactions(league_id: str, round_num: int) -> List[Dict[str, Any]]:
    """
    Get league transactions for a specific round/week from Sleeper.
    """
    if not league_id or round_num is None:
        return []
    try:
        round_num = int(round_num)
    except Exception:
        return []
    if round_num <= 0:
        return []

    url = f"{SLEEPER_BASE}/league/{league_id}/transactions/{round_num}"
    try:
        transactions = _request_json("sleeper_transactions", url, timeout=5)
        return transactions if isinstance(transactions, list) else []
    except Exception:
        return []


@lru_cache(maxsize=512)
def get_matchups(league_id: str, round_num: int) -> List[Dict[str, Any]]:
    """
    Get league matchups for a specific round/week from Sleeper.
    """
    if not league_id or round_num is None:
        return []
    try:
        round_num = int(round_num)
    except Exception:
        return []
    if round_num <= 0:
        return []

    url = f"{SLEEPER_BASE}/league/{league_id}/matchups/{round_num}"
    try:
        matchups = _request_json("sleeper_matchups", url, timeout=5)
        return matchups if isinstance(matchups, list) else []
    except Exception:
        return []


def get_user_roster_id(league_id: str, username: str) -> Optional[int]:
    """
    Returns the roster_id for this username in a league, or None if not found.[web:4]
    """
    normalized_username = normalize_username(username)
    if not league_id or not normalized_username:
        return None

    users = get_users(league_id)
    user_id = None
    for u in users or []:
        sleeper_username = normalize_username(u.get("username"))
        display_name = normalize_username(u.get("display_name"))
        if (
            sleeper_username == normalized_username
            or display_name == normalized_username
        ):
            user_id = u.get("user_id")
            break

    if not user_id:
        return None

    rosters = get_rosters(league_id)
    for r in rosters or []:
        if str(r.get("owner_id")) == str(user_id):
            return r.get("roster_id")

    return None


def get_roster_player_ids(league_id: str, roster_id: int) -> List[str]:
    """
    Returns a list of Sleeper player_ids on this roster.
    Never returns None; returns [] on any failure.[web:4]
    """
    if not league_id or roster_id is None:
        return []

    rosters = get_rosters(league_id)
    for r in rosters or []:
        if str(r.get("roster_id")) == str(roster_id):
            players = r.get("players") or []
            if not isinstance(players, list):
                return []
            return [str(pid) for pid in players if pid is not None]

    return []


def get_sleeper_avatar_url(avatar_id: str, thumb: bool = False) -> str:
    avatar_id = (avatar_id or "").strip()
    if not avatar_id:
        return ""
    if avatar_id.startswith("http://") or avatar_id.startswith("https://"):
        return avatar_id
    avatar_path = f"thumbs/{avatar_id}" if thumb else avatar_id
    return f"{SLEEPER_AVATAR_BASE}/{avatar_path}"


def get_league_roster_profiles(league_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Build roster/team identity details once per league.
    """
    if not league_id:
        return {}

    rosters = get_rosters(league_id)
    users = get_users(league_id)
    users_by_id = {
        str(user.get("user_id") or ""): user
        for user in users or []
    }

    profiles: Dict[str, Dict[str, Any]] = {}
    for roster in rosters or []:
        roster_id = str(roster.get("roster_id") or "")
        owner_id = str(roster.get("owner_id") or "")
        user = users_by_id.get(owner_id, {})
        roster_meta = roster.get("metadata") if isinstance(roster.get("metadata"), dict) else {}
        user_meta = user.get("metadata") if isinstance(user.get("metadata"), dict) else {}

        team_name = (
            roster_meta.get("team_name")
            or user_meta.get("team_name")
            or user.get("display_name")
            or user.get("username")
            or f"Team {roster_id}"
        )
        avatar_id = (
            roster_meta.get("avatar")
            or roster_meta.get("team_avatar")
            or user_meta.get("avatar")
            or user.get("avatar")
            or ""
        )
        profiles[roster_id] = {
            "team_name": team_name,
            "owner_name": user.get("display_name") or user.get("username") or "Unknown",
            "username": user.get("username") or "",
            "avatar_id": avatar_id,
            "avatar_url": get_sleeper_avatar_url(avatar_id),
            "roster_id": roster.get("roster_id"),
            "owner_id": owner_id,
        }

    return profiles


def get_roster_profile(league_id: str, roster_id: int) -> Dict[str, Any]:
    """
    Return team identity details for a roster from Sleeper users/rosters data.
    """
    if not league_id or roster_id is None:
        return {}

    profiles = get_league_roster_profiles(league_id)
    return profiles.get(str(roster_id), {})
