"""MyFantasyLeague (MFL) leagues for the FastAPI service (web-next and mobile).

Follows the ESPN import pattern (``modules.espn_leagues``): an MFL league is the
string key ``mfl:{league_id}:{season}``, loaded once into a Sleeper-shaped
snapshot (``modules.external_league_common``).

Source and terms (checked 2026-10-22, https://api.myfantasyleague.com/2025/api_info):

* Official export API: ``GET https://api.myfantasyleague.com/{season}/export?TYPE=..&L={league}&JSON=1``.
  MFL redirects a league request to the league's own host, which ``requests``
  follows. Used: ``TYPE=league`` (name, franchises, lineup limits),
  ``TYPE=rosters``, ``TYPE=leagueStandings`` and, once per 12 hours for the
  whole process, ``TYPE=players`` (the global player list, no league needed).
* Authentication: a user ``APIKEY`` is only needed for private leagues or
  franchise-only data. This module never accepts, stores or logs one: like
  ESPN, only leagues readable without credentials are imported, and a league
  that wants a login answers ``private_league``.
* Rate limits: unregistered clients are limited per IP; throttled requests get
  HTTP 429. MFL asks clients to space calls (about one per second), cache, and
  not retry. We space every call at least 1.1s apart, make four calls per
  import (the players list is cached), cache each snapshot for 5 minutes and
  never retry a 429.
* Terms: free to use; harvesting league or user data, circumventing rules,
  overloading the service, and calling the API from browser JavaScript on other
  domains are prohibited. All calls here are server side, one league at a time,
  on the user's request. Registered clients must send their registered
  User-Agent; we send an identifying one until FantasyDesk is registered as an
  MFL client (see docs/platform-import-status.md).
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

import pandas as pd
import requests

from modules import espn_leagues
from modules.external_league_common import (
    ExternalLeagueError,
    NormalizedLeague,
    NormalizedPlayer,
    NormalizedTeam,
    SnapshotCache,
    Throttle,
    as_list,
    build_snapshot,
    features_for,
    mapping_blocks_import,
    preview_payload as _preview_payload,
    safe_float,
    safe_int,
    safe_text,
)
from modules.platforms.espn import normalize_espn_team

MFL_PLATFORM = "mfl"
MFL_LABEL = "MFL"
MFL_LEAGUE_KEY_PREFIX = "mfl:"
MFL_API_BASE = "https://api.myfantasyleague.com"
MFL_USER_AGENT = "FantasyDesk-LeagueImport/1.0 (+https://fantasydesk.app)"
REQUEST_TIMEOUT_SECONDS = 20
MIN_SEASON = 2010
MAX_SEASON = 2035
PLAYERS_TTL_SECONDS = 12 * 60 * 60

_KEY_PATTERN = re.compile(r"^mfl:(\d{1,12}):(\d{4})$")
_throttle = Throttle(1.1)
_cache = SnapshotCache()

ERROR_MESSAGES = {
    "invalid_input": "Enter an MFL league ID (numbers only) and a season.",
    "private_league": (
        "This MFL league needs a login to read, so FantasyDesk can't import it. Public MFL leagues work."
    ),
    "league_not_found": "We couldn't find that MFL league for that season. Check the league ID and season.",
    "no_teams": "That MFL league loaded, but it has no teams or rosters yet.",
    "mfl_unavailable": "MyFantasyLeague didn't respond. Please try again in a moment.",
    "mfl_rate_limited": "MyFantasyLeague is limiting requests right now. Please try again in a minute.",
    "mapping_too_low": (
        "That MFL league loaded, but too few of its players matched FantasyDesk's player list "
        "to value the rosters accurately."
    ),
}
FEATURE_SUPPORT = features_for(MFL_LABEL, espn_leagues.ESPN_FEATURE_SUPPORT, espn_leagues.ESPN_NOT_AVAILABLE_MESSAGE)

# MFL team abbreviations that differ from Sleeper's (ESPN's aliases cover JAC, OAK, ...).
_MFL_TEAM_ALIASES = {"GBP": "GB", "KCC": "KC", "NEP": "NE", "NOS": "NO", "SFO": "SF", "TBB": "TB", "LVR": "LV", "SDC": "LAC", "STL": "LAR"}
_FREE_AGENT_TEAMS = {"", "FA", "FA*", "FREE"}
_POSITION = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "PK": "K", "DEF": "DEF",
    "DT": "DL", "DE": "DL", "DL": "DL", "LB": "LB", "CB": "DB", "S": "DB", "DB": "DB",
}
_SLOT = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "PK": "K", "DEF": "DEF",
    "RB+WR+TE": "FLEX", "RB+WR": "WRRB_FLEX", "WR+TE": "REC_FLEX", "QB+RB+WR+TE": "SUPER_FLEX",
    "DT": "DL", "DE": "DL", "DL": "DL", "DT+DE": "DL", "LB": "LB", "CB": "DB", "S": "DB", "DB": "DB", "CB+S": "DB",
    "DT+DE+LB+CB+S": "IDP_FLEX",
}
_OFFENSE_FLEX_ONLY = {"RB", "WR", "TE", "RB+WR", "WR+TE", "RB+WR+TE"}
_STARTER_ORDER = ["QB", "RB", "WR", "TE", "WRRB_FLEX", "REC_FLEX", "FLEX", "SUPER_FLEX", "K", "DEF", "DL", "LB", "DB", "IDP_FLEX"]
_NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
_STATUS_SLOT = {"INJURED_RESERVE": "RESERVE", "TAXI_SQUAD": "TAXI"}


def normalize_league_id(value: Any) -> str:
    text = safe_text(value)
    return text if text.isdigit() and len(text) <= 12 else ""


def normalize_season(value: Any) -> int:
    season = safe_int(value, 0)
    return season if MIN_SEASON <= season <= MAX_SEASON else 0


def build_league_key(league_id: Any, season: Any) -> str:
    clean_id, clean_season = normalize_league_id(league_id), normalize_season(season)
    if not clean_id or not clean_season:
        return ""
    return f"{MFL_LEAGUE_KEY_PREFIX}{int(clean_id)}:{clean_season}"


def parse_league_key(value: Any) -> tuple[str, int] | None:
    match = _KEY_PATTERN.match(safe_text(value))
    if not match:
        return None
    season = normalize_season(match.group(2))
    return (str(int(match.group(1))), season) if season else None


def is_league_key(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(MFL_LEAGUE_KEY_PREFIX)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

_PRIVATE_HINTS = ("login", "logged", "authoriz", "permission", "private", "not allowed", "password", "apikey")


def _raise_for_error(payload: Any) -> None:
    error = payload.get("error") if isinstance(payload, dict) else None
    if not error:
        return
    text = safe_text(error.get("$t") if isinstance(error, dict) else error)
    lowered = text.casefold()
    if "invalid league" in lowered:
        raise ExternalLeagueError("league_not_found", ERROR_MESSAGES["league_not_found"])
    if any(hint in lowered for hint in _PRIVATE_HINTS):
        raise ExternalLeagueError("private_league", ERROR_MESSAGES["private_league"])
    raise ExternalLeagueError("mfl_unavailable", ERROR_MESSAGES["mfl_unavailable"])


def _default_fetch(season: int, params: dict[str, Any]) -> Any:
    _throttle.wait()
    try:
        response = requests.get(
            f"{MFL_API_BASE}/{season}/export",
            params={**params, "JSON": 1},
            headers={"User-Agent": MFL_USER_AGENT, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise ExternalLeagueError("mfl_unavailable", ERROR_MESSAGES["mfl_unavailable"]) from None
    if response.status_code == 429:
        raise ExternalLeagueError("mfl_rate_limited", ERROR_MESSAGES["mfl_rate_limited"])
    if response.status_code in (401, 403):
        raise ExternalLeagueError("private_league", ERROR_MESSAGES["private_league"])
    if response.status_code != 200:
        raise ExternalLeagueError("mfl_unavailable", ERROR_MESSAGES["mfl_unavailable"])
    try:
        payload = response.json()
    except ValueError:
        raise ExternalLeagueError("mfl_unavailable", ERROR_MESSAGES["mfl_unavailable"]) from None
    _raise_for_error(payload)
    return payload


# Indirection points for tests (no network, no data/players.db).
fetch_provider: Callable[[int, dict[str, Any]], Any] = _default_fetch
players_frame_provider: Callable[[], pd.DataFrame] = lambda: espn_leagues.players_frame_provider()
sleeper_players_provider: Callable[[], dict[str, Any]] = lambda: espn_leagues.sleeper_players_provider()


def _default_crosswalk() -> dict[str, str]:
    from modules import espn_player_crosswalk

    return espn_player_crosswalk.load_platform_crosswalk("mfl_id")


crosswalk_provider: Callable[[], dict[str, str]] = _default_crosswalk

_players_lock = threading.Lock()
_players_cache: dict[int, tuple[float, dict[str, dict[str, Any]]]] = {}


def _players_by_id(season: int) -> dict[str, dict[str, Any]]:
    with _players_lock:
        cached = _players_cache.get(season)
        if cached and time.time() - cached[0] < PLAYERS_TTL_SECONDS:
            return cached[1]
        payload = fetch_provider(season, {"TYPE": "players"})
        rows = (payload.get("players") or {}) if isinstance(payload, dict) else {}
        players = {
            safe_text(row.get("id")): row
            for row in as_list(rows.get("player") if isinstance(rows, dict) else None)
            if isinstance(row, dict) and row.get("id") is not None
        }
        if players:
            _players_cache[season] = (time.time(), players)
        return players


def clear_players_cache() -> None:
    _players_cache.clear()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def display_name(raw: Any) -> str:
    """MFL names are "Last, First [Suffix]"; return "First Last [Suffix]"."""

    text = safe_text(raw)
    if "," not in text:
        return text
    last, first = (part.strip() for part in text.split(",", 1))
    tokens = first.split()
    suffix = []
    while tokens and tokens[-1].casefold() in _NAME_SUFFIXES:
        suffix.insert(0, tokens.pop())
    return " ".join([*tokens, last, *suffix]).strip()


def normalize_team_abbreviation(raw: Any) -> str:
    text = safe_text(raw).upper()
    if text in _FREE_AGENT_TEAMS:
        return ""
    return normalize_espn_team(_MFL_TEAM_ALIASES.get(text, text))


def roster_positions_from_league(league: dict[str, Any]) -> list[str]:
    """Lineup slots from MFL's per-position ``limit`` ("min" or "min-max").

    Only the guaranteed minimum of each position is a fixed slot. Starters MFL
    counts beyond those minimums can be filled by any ranged position; when
    every ranged position is a skill position (RB/WR/TE), the remainder is a
    FLEX slot, otherwise it is left out rather than guessed."""

    starters = league.get("starters") if isinstance(league.get("starters"), dict) else {}
    counts: dict[str, int] = {}
    minimum_total = 0
    ranged: list[str] = []
    for entry in as_list(starters.get("position")):
        if not isinstance(entry, dict):
            continue
        name = safe_text(entry.get("name")).upper()
        limit = safe_text(entry.get("limit"))
        low_text, _, high_text = limit.partition("-")
        low = safe_int(low_text, 0)
        high = safe_int(high_text, low) if high_text else low
        minimum_total += low
        if high > low:
            ranged.append(name)
        token = _SLOT.get(name)
        if token and low > 0:
            counts[token] = counts.get(token, 0) + low
    leftover = safe_int(starters.get("count"), 0) - minimum_total
    if leftover > 0 and ranged and all(name in _OFFENSE_FLEX_ONLY for name in ranged):
        counts["FLEX"] = counts.get("FLEX", 0) + leftover
    positions: list[str] = []
    for token in _STARTER_ORDER:
        positions.extend([token] * counts.get(token, 0))
    roster_size = safe_int(league.get("rosterSize"), 0)
    if roster_size:
        positions.extend(["BN"] * max(0, roster_size - len(positions)))
    positions.extend(["IR"] * max(0, safe_int(league.get("injuredReserve"), 0)))
    return positions


def normalize_league(
    league_json: Any,
    rosters_json: Any,
    standings_json: Any,
    players: dict[str, dict[str, Any]],
    season: int,
) -> NormalizedLeague:
    league = (league_json.get("league") if isinstance(league_json, dict) else None) or {}
    franchises = {
        safe_text(item.get("id")): item
        for item in as_list((league.get("franchises") or {}).get("franchise") if isinstance(league.get("franchises"), dict) else None)
        if isinstance(item, dict)
    }
    standing_rows = {
        safe_text(item.get("id")): item
        for item in as_list(((standings_json or {}).get("leagueStandings") or {}).get("franchise"))
        if isinstance(item, dict)
    }
    roster_rows = as_list(((rosters_json or {}).get("rosters") or {}).get("franchise"))
    teams: list[NormalizedTeam] = []
    ignored = 0
    for row in roster_rows:
        if not isinstance(row, dict):
            continue
        fid = safe_text(row.get("id"))
        if not fid:
            continue
        franchise = franchises.get(fid, {})
        standing = standing_rows.get(fid, {})
        roster_players: list[NormalizedPlayer] = []
        for item in as_list(row.get("player")):
            if not isinstance(item, dict):
                continue
            info = players.get(safe_text(item.get("id")))
            position = _POSITION.get(safe_text((info or {}).get("position")).upper(), "")
            name = display_name((info or {}).get("name"))
            if not info or not position or not name:
                # Coaches, team units, retired ids: not valued players.
                ignored += 1
                continue
            roster_players.append(
                NormalizedPlayer(
                    platform_id=safe_text(item.get("id")),
                    name=name,
                    position=position,
                    team=normalize_team_abbreviation(info.get("team")),
                    slot=_STATUS_SLOT.get(safe_text(item.get("status")).upper(), "ROSTER"),
                )
            )
        teams.append(
            NormalizedTeam(
                team_id=fid,
                name=safe_text(franchise.get("name")),
                owner=safe_text(franchise.get("owner_name")),
                wins=safe_int(standing.get("h2hw")),
                losses=safe_int(standing.get("h2hl")),
                ties=safe_int(standing.get("h2ht")),
                points_for=safe_float(safe_text(standing.get("pf")).replace(",", "")),
                points_against=safe_float(safe_text(standing.get("pa")).replace(",", "")),
                players=roster_players,
            )
        )
    return NormalizedLeague(
        name=safe_text(league.get("name")),
        season=season,
        teams=teams,
        roster_positions=roster_positions_from_league(league),
        ignored_players=ignored,
    )


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def load_league_snapshot(league_key: str) -> dict[str, Any]:
    parsed = parse_league_key(league_key)
    if not parsed:
        raise ExternalLeagueError("invalid_input", ERROR_MESSAGES["invalid_input"])
    league_id, season = parsed
    league_json = fetch_provider(season, {"TYPE": "league", "L": league_id})
    rosters_json = fetch_provider(season, {"TYPE": "rosters", "L": league_id})
    standings_json = fetch_provider(season, {"TYPE": "leagueStandings", "L": league_id})
    players = _players_by_id(season)
    league = normalize_league(league_json, rosters_json, standings_json, players, season)
    if not league.teams:
        raise ExternalLeagueError("no_teams", ERROR_MESSAGES["no_teams"])
    try:
        df_players = players_frame_provider()
    except Exception:
        df_players = pd.DataFrame()
    try:
        sleeper_players = sleeper_players_provider() or {}
    except Exception:
        sleeper_players = {}
    try:
        crosswalk = crosswalk_provider() or {}
    except Exception:
        crosswalk = {}
    return build_snapshot(
        MFL_PLATFORM,
        league,
        league_key=league_key,
        external_league_id=league_id,
        default_name="MFL league",
        df_players=df_players,
        sleeper_players=sleeper_players,
        crosswalk=crosswalk,
    )


def get_league_snapshot(league_key: str, *, refresh: bool = False) -> dict[str, Any] | None:
    if not parse_league_key(league_key):
        return None
    return _cache.get(league_key, load_league_snapshot, refresh=refresh)


def store_snapshot(league_key: str, snapshot: dict[str, Any]) -> None:
    _cache.store(league_key, snapshot)


def clear_snapshot_cache() -> None:
    _cache.clear()


def preview_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return _preview_payload(
        snapshot, label=MFL_LABEL, features=FEATURE_SUPPORT, mapping_message=ERROR_MESSAGES["mapping_too_low"]
    )


__all__ = [
    "ExternalLeagueError",
    "build_league_key",
    "parse_league_key",
    "is_league_key",
    "load_league_snapshot",
    "get_league_snapshot",
    "store_snapshot",
    "clear_snapshot_cache",
    "preview_payload",
    "mapping_blocks_import",
]
