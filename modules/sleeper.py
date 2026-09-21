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
# Was 60*60 — the entire "Nico Collins still shows as a starter after being
# ruled Out" class of bug traced back to this single number: the mobile
# API's stale-while-revalidate refresh (services/mobile_api_service.py's
# _maybe_schedule_players_refresh, via modules.startup_cold_path /
# modules.players_refresh_flight) only re-checks Sleeper this often, so an
# in-game status change could lag up to an hour. Lowered so a live gameday
# ruling reaches the app in minutes, not up to an hour — the existing
# single-flight + 45s failure-cooldown guard (players_refresh_flight.py)
# already prevents this from hammering Sleeper, so shortening the interval
# doesn't add stampede risk, just a few more cheap background refreshes/hour.
PLAYERS_CACHE_TTL_SECONDS = 5 * 60
PLAYER_STATS_CACHE_TEMPLATE = "data/sleeper_player_stats_{season}.json"
PLAYER_STATS_CACHE_TTL_SECONDS = 12 * 60 * 60
COMPLETED_PLAYER_STATS_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
# Completed prior seasons are effectively immutable — keep them warm for months.
PRIOR_PLAYER_STATS_CACHE_TTL_SECONDS = 180 * 24 * 60 * 60
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

# Compact per-week fields retained from the same fetch (no extra provider calls).
WEEKLY_RETAIN_SOURCE_FIELDS = (
    "gp",
    "rec_tgt",
    "rec",
    "rush_att",
    "pass_att",
    "off_snp",
    "tm_off_snp",
    "pts_ppr",
)
WEEKLY_RETAIN_FIELD_MAP = {
    "gp": "games_played",
    "rec_tgt": "targets",
    "rec": "receptions",
    "rush_att": "rush_attempts",
    "pass_att": "pass_attempts",
    "pts_ppr": "fantasy_points_ppr",
}


def default_player_stats_season(now: time.struct_time | None = None) -> int:
    """Canonical active NFL stats season (Sep+ → calendar year, else prior year)."""

    current = now or time.localtime()
    return int(current.tm_year if current.tm_mon >= 9 else current.tm_year - 1)


def prior_player_stats_season(now: time.struct_time | None = None) -> int:
    """Immediately previous NFL season relative to the canonical active season."""

    return int(default_player_stats_season(now) - 1)


def _player_stats_cache_ttl(season: int, now: time.struct_time | None = None) -> int:
    current = now or time.localtime()
    active = default_player_stats_season(current)
    season_i = int(season)
    if season_i < active:
        return PRIOR_PLAYER_STATS_CACHE_TTL_SECONDS
    # Active season: short TTL once the NFL regular season calendar starts.
    active_regular_season = season_i == int(current.tm_year) and current.tm_mon >= 9
    return PLAYER_STATS_CACHE_TTL_SECONDS if active_regular_season else COMPLETED_PLAYER_STATS_CACHE_TTL_SECONDS


def _extract_week_observation(week: int, raw_stats: Dict[str, Any]) -> Dict[str, Any] | None:
    """Compact week row from a Sleeper weekly payload. None when empty/unusable raw."""

    if not isinstance(raw_stats, dict):
        return None
    row: Dict[str, Any] = {"week": int(week)}
    saw_value = False
    for source_field in WEEKLY_RETAIN_SOURCE_FIELDS:
        if source_field not in raw_stats or raw_stats.get(source_field) is None:
            continue
        try:
            numeric = float(raw_stats.get(source_field))
        except (TypeError, ValueError):
            continue
        if not (numeric == numeric):  # NaN
            continue
        saw_value = True
        if source_field == "off_snp":
            row["_offensive_snaps"] = numeric
            continue
        if source_field == "tm_off_snp":
            row["_team_offensive_snaps"] = numeric
            continue
        target = WEEKLY_RETAIN_FIELD_MAP.get(source_field)
        if target:
            if target == "games_played":
                row[target] = int(round(numeric))
            else:
                row[target] = float(numeric) if target not in {"games_played"} else int(round(numeric))
                if target in {"targets", "receptions", "rush_attempts", "pass_attempts"}:
                    row[target] = int(round(numeric))
    if not saw_value:
        return None
    off_snp = float(row.pop("_offensive_snaps", 0.0) or 0.0)
    tm_off = float(row.pop("_team_offensive_snaps", 0.0) or 0.0)
    if off_snp >= 0 and tm_off > 0:
        row["snap_share"] = min(1.0, max(0.0, off_snp / tm_off))
    # Drop internal-only keys if snaps missing
    row.pop("_offensive_snaps", None)
    row.pop("_team_offensive_snaps", None)
    return row if len(row) > 1 else None


def _aggregate_player_week_stats(
    weekly_payloads: List[Any],
    season: int,
    *,
    retain_weekly: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Aggregate week payloads into season totals; optionally retain compact weekly rows.

    ``weekly_payloads`` may be a list of week dicts (legacy) or (week_number, dict) pairs.
    Weekly granularity is retained from the same fetch — no extra provider calls.
    """

    aggregate: Dict[str, Dict[str, Any]] = {}
    observed_fields: Dict[str, set[str]] = {}
    weekly_rows: Dict[str, List[Dict[str, Any]]] = {}

    for index, item in enumerate(weekly_payloads):
        if isinstance(item, tuple) and len(item) == 2:
            week_number, payload = int(item[0]), item[1]
        elif isinstance(item, dict):
            week_number, payload = index + 1, item
        else:
            continue
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

            if retain_weekly:
                week_row = _extract_week_observation(week_number, raw_stats)
                if week_row is not None:
                    weekly_rows.setdefault(player_key, []).append(week_row)

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

        if retain_weekly:
            weeks = weekly_rows.get(player_id) or []
            if weeks:
                # Stable week order; drop empty-only noise later in recency filter.
                result["weekly"] = sorted(weeks, key=lambda row: int(row.get("week") or 0))

        if len(result) > 1:
            cleaned[player_id] = result
    return cleaned


def season_stats_cache_has_weekly(season: int | None = None) -> bool:
    """True when the season aggregate cache retains at least one weekly series."""

    selected = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected)
    if not os.path.exists(cache_path):
        return False
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
        if not isinstance(cached, dict):
            return False
        for values in cached.values():
            if isinstance(values, dict) and isinstance(values.get("weekly"), list) and values.get("weekly"):
                return True
    except Exception:
        return False
    return False


def cached_season_player_weekly(player_id: str, season: int | None = None) -> List[Dict[str, Any]]:
    """Weekly rows already on disk for one player+season — never fetches.

    The read side of ``get_season_player_stats``'s ``retain_weekly`` output,
    for callers that must not block a render on an 18-week rebuild. Empty
    list whenever the cache is missing, unreadable, or was written without
    weekly retention (prior seasons are).
    """

    identifier = str(player_id or "").strip()
    if not identifier:
        return []
    selected = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected)
    if not os.path.exists(cache_path):
        return []
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except Exception:
        return []
    if not isinstance(cached, dict):
        return []
    record = cached.get(identifier)
    weekly = record.get("weekly") if isinstance(record, dict) else None
    if not isinstance(weekly, list):
        return []
    return [row for row in weekly if isinstance(row, dict)]


def get_season_player_stats(
    season: int | None = None,
    *,
    refresh: bool = False,
    max_week: int = 18,
    retain_weekly: bool | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Load cached Sleeper weekly production and aggregate it into season totals.

    When rebuilding from the network, weekly observations for the active season are
    retained on each player record under ``weekly`` (same provider calls as before).
    Prior-season rebuilds skip weekly retention to limit cache size.
    """
    _ensure_data_dir()
    selected_season = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected_season)
    keep_weekly = (
        bool(retain_weekly)
        if retain_weekly is not None
        else selected_season == default_player_stats_season()
    )

    if not refresh and os.path.exists(cache_path):
        try:
            cache_age = time.time() - os.path.getmtime(cache_path)
            if cache_age < _player_stats_cache_ttl(selected_season):
                with open(cache_path, "r", encoding="utf-8") as handle:
                    cached = json.load(handle)
                if isinstance(cached, dict):
                    has_weekly = any(
                        isinstance(values, dict)
                        and isinstance(values.get("weekly"), list)
                        and bool(values.get("weekly"))
                        for values in cached.values()
                    )
                    # Active season without weekly rows → rebuild once using the
                    # same week endpoints (no additional call volume vs a normal refresh).
                    if keep_weekly and not has_weekly:
                        pass
                    else:
                        return cached
        except Exception:
            pass

    weekly_payloads: List[Any] = []
    for week in range(1, max(1, int(max_week)) + 1):
        url = f"{SLEEPER_BASE}/stats/nfl/regular/{selected_season}/{week}"
        try:
            payload = _request_json("sleeper_player_stats_week", url, timeout=20)
            if isinstance(payload, dict):
                weekly_payloads.append((week, payload))
        except Exception:
            continue

    if weekly_payloads:
        aggregated = _aggregate_player_week_stats(
            weekly_payloads,
            selected_season,
            retain_weekly=keep_weekly,
        )
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


def get_prior_season_player_stats(
    *,
    refresh: bool = False,
    max_week: int = 18,
) -> Dict[str, Dict[str, Any]]:
    """Load the prior NFL season aggregate via the same Sleeper week→cache path.

    Fail-neutral: returns {} when the prior season cannot be loaded. Never invents
    player rows. Uses the longer prior-season TTL once cached.
    """

    try:
        return get_season_player_stats(
            season=prior_player_stats_season(),
            refresh=refresh,
            max_week=max_week,
            retain_weekly=False,
        )
    except Exception:
        return {}


def prior_season_stats_cache_available(now: time.struct_time | None = None) -> bool:
    """True when a non-empty prior-season aggregate file is already on disk."""

    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=prior_player_stats_season(now))
    if not os.path.exists(cache_path):
        return False
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
        return isinstance(cached, dict) and bool(cached)
    except Exception:
        return False


def normalize_username(username: str) -> str:
    return (username or "").strip().casefold()


def _ensure_data_dir():
    if not os.path.exists("data"):
        os.makedirs("data")


def _provider_category(label: str) -> str:
    text = str(label or "").casefold()
    if "user_lookup" in text or text.endswith("_user"):
        return "provider_user_lookup"
    if "league_users" in text or text.endswith("_users"):
        return "provider_users"
    if "rosters" in text:
        return "provider_rosters"
    if "transactions" in text:
        return "provider_transactions"
    if "players" in text:
        return "provider_players"
    if "league" in text or "draft" in text or "matchup" in text or "traded" in text:
        return "provider_leagues"
    return "provider_other"


def _note_provider_timing(
    label: str,
    duration_ms: float,
    *,
    cache_status: str = "miss",
    timeout: bool = False,
) -> None:
    """Best-effort provider timing into the active Streamlit session (no PII)."""

    try:
        import streamlit as st

        from modules import tail_latency_diagnostics

        tail_latency_diagnostics.note_provider_call(
            st.session_state,
            category=_provider_category(label),
            duration_ms=duration_ms,
            cache_status=cache_status,
            timeout=timeout,
            endpoint=_safe_provider_endpoint(label),
        )
        try:
            from modules import dashboard_waterfall as _waterfall

            _waterfall.note_provider(
                provider="sleeper",
                endpoint=_safe_provider_endpoint(label),
                duration_ms=duration_ms,
                cache_status=cache_status,
                session_state=st.session_state,
            )
        except Exception:
            pass
    except Exception:
        pass


def _safe_provider_endpoint(label: str) -> str:
    """Stable non-PII endpoint label for duplicate-call diagnosis."""

    text = str(label or "").strip().casefold()
    cleaned = "".join(ch if ch.isalnum() or ch in "._:-" else "_" for ch in text)
    return cleaned[:48]


def _request_json(label: str, url: str, *, timeout: int = 5):
    started = time.perf_counter()
    timed_out = False
    try:
        with performance.time_block(label, category="sleeper"):
            response = requests.get(url, timeout=timeout)
            if response.status_code != 200:
                return None
            return response.json()
    except requests.Timeout:
        timed_out = True
        raise
    finally:
        _note_provider_timing(
            label,
            (time.perf_counter() - started) * 1000.0,
            cache_status="timeout" if timed_out else "miss",
            timeout=timed_out,
        )


def load_cached_players_disk(
    path: str | None = None,
) -> tuple[Dict[str, Any], int]:
    """Read ``sleeper_players.json`` only. Never fetches.

    Returns ``(players_by_id, mtime_ns)``. Missing or unreadable cache yields
    ``({}, 0)``. Used by structured football freshness so startup can patch
    status/injury/depth without calling ``get_players(refresh=...)``.
    """

    cache_path = path or PLAYERS_CACHE_PATH
    if not os.path.exists(cache_path):
        return {}, 0
    try:
        stat = os.stat(cache_path)
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        with open(cache_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            _note_provider_timing("sleeper_players_disk_only", 0.0, cache_status="hit")
            return data, mtime_ns
    except Exception:
        return {}, 0
    return {}, 0


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
                _note_provider_timing("sleeper_players_disk", 0.0, cache_status="hit")
                return data
        except Exception:
            pass

    url = f"{SLEEPER_BASE}/players/nfl"
    started = time.perf_counter()
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
        _note_provider_timing(
            "sleeper_players_fetch",
            (time.perf_counter() - started) * 1000.0,
            cache_status="miss",
        )
        return players
    except Exception:
        _note_provider_timing(
            "sleeper_players_fetch",
            (time.perf_counter() - started) * 1000.0,
            cache_status="error",
        )
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


# These three live endpoints change constantly (rosters via trades/waivers/
# drops, users/league settings less often but still live) — a bare
# lru_cache here would cache them for the rest of the process's life,
# refreshed only by clear_live_league_endpoint_caches() below. The web app
# calls that on its own Game Plan TTL/manual-refresh, but services/
# mobile_api_service.py (a separate long-running process) never does —
# without this, a mobile Render instance would serve one stale roster
# snapshot per league for its entire uptime between deploys. The time
# bucket in the cache key makes every entry expire on its own after
# LIVE_LEAGUE_ENDPOINT_TTL_SECONDS regardless of whether anything ever
# calls clear_live_league_endpoint_caches() for this process.
LIVE_LEAGUE_ENDPOINT_TTL_SECONDS = 30


def _live_league_cache_bucket() -> int:
    return int(time.time() // LIVE_LEAGUE_ENDPOINT_TTL_SECONDS)


@lru_cache(maxsize=128)
def _get_users_cached(league_id: str, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/users"
    try:
        users = _request_json("sleeper_league_users", url, timeout=5)
        return users if isinstance(users, list) else []
    except Exception:
        return []


def get_users(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all users in a league.[web:4]
    """
    return _get_users_cached(league_id, _live_league_cache_bucket())


@lru_cache(maxsize=128)
def _get_rosters_cached(league_id: str, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/rosters"
    try:
        rosters = _request_json("sleeper_league_rosters", url, timeout=5)
        return rosters if isinstance(rosters, list) else []
    except Exception:
        return []


def get_rosters(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all rosters in a league.[web:4]
    """
    return _get_rosters_cached(league_id, _live_league_cache_bucket())


@lru_cache(maxsize=128)
def _get_league_cached(league_id: str, _bucket: int) -> Dict[str, Any]:
    if not league_id:
        return {}
    url = f"{SLEEPER_BASE}/league/{league_id}"
    try:
        league = _request_json("sleeper_league", url, timeout=5)
        return league if isinstance(league, dict) else {}
    except Exception:
        return {}


def get_league(league_id: str) -> Dict[str, Any]:
    """
    Get league metadata/settings from Sleeper.
    """
    return _get_league_cached(league_id, _live_league_cache_bucket())


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
def _get_traded_picks_cached(league_id: str, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/traded_picks"
    try:
        picks = _request_json("sleeper_traded_picks", url, timeout=5)
        return picks if isinstance(picks, list) else []
    except Exception:
        return []


def get_traded_picks(league_id: str) -> List[Dict[str, Any]]:
    """
    Get traded draft picks for a league. Untraded picks are not returned by
    Sleeper, so callers should assume original ownership unless listed here.

    Time-bucketed like get_league/get_rosters/get_users above — a trade
    changes pick ownership immediately, and services/mobile_api_service.py's
    long-lived process has no other invalidation hook for it.
    """
    return _get_traded_picks_cached(league_id, _live_league_cache_bucket())


@lru_cache(maxsize=512)
def _get_transactions_cached(league_id: str, round_num: int, _bucket: int) -> List[Dict[str, Any]]:
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


def get_transactions(league_id: str, round_num: int) -> List[Dict[str, Any]]:
    """
    Get league transactions for a specific round/week from Sleeper.

    Time-bucketed — waiver claims and adds/drops land on this endpoint in
    real time, and mobile's long-lived process has no other way to see them.
    """
    return _get_transactions_cached(league_id, round_num, _live_league_cache_bucket())


def clear_live_league_endpoint_caches() -> None:
    """Drop in-process LRU for live Sleeper league endpoints.

    Username lookup and the static players dump stay cached. Call on
    recommendation refresh, Game Plan TTL expiry, and tests — never from
    anonymous presentation-only reruns.
    """

    _get_users_cached.cache_clear()
    _get_rosters_cached.cache_clear()
    _get_league_cached.cache_clear()
    get_league_drafts.cache_clear()
    get_draft.cache_clear()
    get_draft_picks.cache_clear()
    _get_traded_picks_cached.cache_clear()
    _get_transactions_cached.cache_clear()
    _get_matchups_cached.cache_clear()


@lru_cache(maxsize=512)
def _get_matchups_cached(league_id: str, round_num: int, _bucket: int) -> List[Dict[str, Any]]:
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


def get_matchups(league_id: str, round_num: int) -> List[Dict[str, Any]]:
    """
    Get league matchups for a specific round/week from Sleeper.

    Time-bucketed — scores update live during games, and mobile's long-lived
    process has no other invalidation hook for this endpoint.
    """
    return _get_matchups_cached(league_id, round_num, _live_league_cache_bucket())


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
