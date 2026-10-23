"""Fleaflicker leagues for the FastAPI service (web-next and mobile).

Follows the ESPN import pattern (``modules.espn_leagues``): a Fleaflicker
league is the string key ``fleaflicker:{league_id}:{season}``, loaded once into
a Sleeper-shaped snapshot (``modules.external_league_common``) that the
valuation, roster and trade engines already understand.

Source and terms (checked 2026-10-22, https://www.fleaflicker.com/api-docs):

* Official, documented JSON API: ``GET https://www.fleaflicker.com/api/{Endpoint}``.
  Used here: ``FetchLeagueRosters`` (teams + every rostered player),
  ``FetchLeagueStandings`` (owners, record, points) and ``FetchLeagueRules``
  (lineup slots), all with ``sport=NFL&league_id=..&season=..``. No
  authentication is needed for these; the API docs state no rate limit and no
  terms of use (contact: info@fleaflicker.com). We stay polite regardless:
  three calls per import, one in flight at a time with spacing between calls,
  an identifying User-Agent, a 5 minute snapshot cache, and no retries.
* A league id that does not exist is a 404 (``can't find league``).

Only what the API returns for a league id is read: no HTML pages, no cookies,
no user login. Scoring values are not part of the documented rules response in
a form we can trust, so ``scoring_settings`` is left empty and valuations use
FantasyDesk's defaults for it (never assumed PPR).
"""

from __future__ import annotations

import re
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
    safe_int,
    safe_text,
)
from modules.platforms.espn import normalize_espn_team

FLEAFLICKER_PLATFORM = "fleaflicker"
FLEAFLICKER_LABEL = "Fleaflicker"
FLEAFLICKER_LEAGUE_KEY_PREFIX = "fleaflicker:"
FLEAFLICKER_API_BASE = "https://www.fleaflicker.com/api"
FLEAFLICKER_USER_AGENT = "FantasyDesk-LeagueImport/1.0 (+https://fantasydesk.app)"
REQUEST_TIMEOUT_SECONDS = 15
MIN_SEASON = 2010
MAX_SEASON = 2035

_KEY_PATTERN = re.compile(r"^fleaflicker:(\d{1,12}):(\d{4})$")
_throttle = Throttle(0.5)
_cache = SnapshotCache()

ERROR_MESSAGES = {
    "invalid_input": "Enter a Fleaflicker league ID (numbers only) and a season.",
    "private_league": "This Fleaflicker league isn't viewable to the public, so FantasyDesk can't read it.",
    "league_not_found": "We couldn't find that Fleaflicker league for that season. Check the league ID and season.",
    "no_teams": "That Fleaflicker league loaded, but it has no teams or rosters yet.",
    "fleaflicker_unavailable": "Fleaflicker didn't respond. Please try again in a moment.",
    "mapping_too_low": (
        "That Fleaflicker league loaded, but too few of its players matched FantasyDesk's player list "
        "to value the rosters accurately."
    ),
}
FEATURE_SUPPORT = features_for(
    FLEAFLICKER_LABEL, espn_leagues.ESPN_FEATURE_SUPPORT, espn_leagues.ESPN_NOT_AVAILABLE_MESSAGE
)

# Fleaflicker position -> Sleeper position. Punters and anything unlisted
# are not valued players and are ignored (counted, never mapped).
_POSITION = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "D/ST": "DEF",
    "EDR": "DL", "DE": "DL", "DT": "DL", "IL": "DL", "DL": "DL", "EDR/IL": "DL",
    "LB": "LB", "CB": "DB", "S": "DB", "DB": "DB",
}
# Lineup slot label -> Sleeper roster_positions token. Slots we can't
# express (punter, odd IDP combinations) are dropped, never approximated.
_SLOT = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "D/ST": "DEF",
    "RB/WR/TE": "FLEX", "RB/WR": "WRRB_FLEX", "WR/TE": "REC_FLEX",
    "QB/RB/WR/TE": "SUPER_FLEX",
    "EDR": "DL", "DE": "DL", "DT": "DL", "IL": "DL", "DL": "DL", "EDR/IL": "DL",
    "LB": "LB", "CB": "DB", "S": "DB", "DB": "DB",
    "DB/EDR/IL/LB": "IDP_FLEX",
}
_STARTER_ORDER = ["QB", "RB", "WR", "TE", "WRRB_FLEX", "REC_FLEX", "FLEX", "SUPER_FLEX", "K", "DEF", "DL", "LB", "DB", "IDP_FLEX"]


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
    return f"{FLEAFLICKER_LEAGUE_KEY_PREFIX}{int(clean_id)}:{clean_season}"


def parse_league_key(value: Any) -> tuple[str, int] | None:
    match = _KEY_PATTERN.match(safe_text(value))
    if not match:
        return None
    season = normalize_season(match.group(2))
    return (str(int(match.group(1))), season) if season else None


def is_league_key(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(FLEAFLICKER_LEAGUE_KEY_PREFIX)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


def _default_fetch(endpoint: str, params: dict[str, Any]) -> Any:
    _throttle.wait()
    try:
        response = requests.get(
            f"{FLEAFLICKER_API_BASE}/{endpoint}",
            params=params,
            headers={"User-Agent": FLEAFLICKER_USER_AGENT, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise ExternalLeagueError("fleaflicker_unavailable", ERROR_MESSAGES["fleaflicker_unavailable"]) from None
    if response.status_code == 404:
        raise ExternalLeagueError("league_not_found", ERROR_MESSAGES["league_not_found"])
    if response.status_code in (401, 403):
        raise ExternalLeagueError("private_league", ERROR_MESSAGES["private_league"])
    if response.status_code != 200:
        # Includes 429: slow down rather than retry.
        raise ExternalLeagueError("fleaflicker_unavailable", ERROR_MESSAGES["fleaflicker_unavailable"])
    try:
        return response.json()
    except ValueError:
        raise ExternalLeagueError("fleaflicker_unavailable", ERROR_MESSAGES["fleaflicker_unavailable"]) from None


# Indirection points for tests (no network, no data/players.db).
fetch_provider: Callable[[str, dict[str, Any]], Any] = _default_fetch


def _default_players_frame() -> pd.DataFrame:
    return espn_leagues.players_frame_provider()


def _default_sleeper_players() -> dict[str, Any]:
    return espn_leagues.sleeper_players_provider()


def _default_crosswalk() -> dict[str, str]:
    from modules import espn_player_crosswalk

    return espn_player_crosswalk.load_platform_crosswalk("fleaflicker_id")


players_frame_provider: Callable[[], pd.DataFrame] = _default_players_frame
sleeper_players_provider: Callable[[], dict[str, Any]] = _default_sleeper_players
crosswalk_provider: Callable[[], dict[str, str]] = _default_crosswalk


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _get(obj: Any, *names: str) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
    return None


def _value(obj: Any) -> float:
    """Fleaflicker wraps numbers as {"value": 12.3, "formatted": "12.3"}."""

    if isinstance(obj, dict):
        obj = obj.get("value")
    try:
        return float(obj)
    except (TypeError, ValueError):
        return 0.0


def roster_positions_from_rules(rules: Any) -> list[str]:
    positions: list[str] = []
    counts: dict[str, int] = {}
    for entry in as_list(_get(rules, "rosterPositions")):
        if not isinstance(entry, dict) or entry.get("group") != "START":
            continue
        token = _SLOT.get(safe_text(entry.get("label")))
        count = safe_int(entry.get("start"), 0)
        if token and count > 0:
            counts[token] = counts.get(token, 0) + count
    for token in _STARTER_ORDER:
        positions.extend([token] * counts.get(token, 0))
    bench = safe_int(_get(rules, "numBench"), 0)
    positions.extend(["BN"] * max(0, bench))
    return positions


def _team_from_standings(standings: Any) -> dict[str, dict[str, Any]]:
    teams: dict[str, dict[str, Any]] = {}
    for division in as_list(_get(standings, "divisions")):
        for team in as_list(_get(division, "teams")):
            if isinstance(team, dict) and team.get("id") is not None:
                teams[str(team["id"])] = team
    return teams


def _owner_name(team: dict[str, Any]) -> str:
    names = [
        safe_text(owner.get("displayName"))
        for owner in as_list(team.get("owners"))
        if isinstance(owner, dict) and safe_text(owner.get("displayName"))
    ]
    return ", ".join(names)


def normalize_league(rosters_json: Any, standings_json: Any, rules_json: Any, season: int) -> NormalizedLeague:
    standings = _team_from_standings(standings_json)
    teams: list[NormalizedTeam] = []
    ignored = 0
    for entry in as_list(_get(rosters_json, "rosters")):
        team = _get(entry, "team") or {}
        team_id = safe_text(team.get("id"))
        if not team_id:
            continue
        record = _get(team, "recordOverall") or {}
        info = standings.get(team_id, {})
        players: list[NormalizedPlayer] = []
        for item in as_list(_get(entry, "players")):
            pro = _get(item, "proPlayer", "pro_player") or {}
            position = _POSITION.get(safe_text(pro.get("position")).upper(), "")
            name = safe_text(_get(pro, "nameFull", "name_full"))
            if not position or not name:
                ignored += 1
                continue
            raw_team = safe_text(_get(pro, "proTeamAbbreviation", "pro_team_abbreviation")).upper()
            players.append(
                NormalizedPlayer(
                    platform_id=safe_text(pro.get("id")),
                    name=name,
                    position=position,
                    team="" if raw_team in ("", "FA") else normalize_espn_team(raw_team),
                )
            )
        teams.append(
            NormalizedTeam(
                team_id=team_id,
                name=safe_text(team.get("name")),
                owner=_owner_name(info) or _owner_name(team),
                wins=safe_int(record.get("wins")),
                losses=safe_int(record.get("losses")),
                ties=safe_int(record.get("ties")),
                points_for=_value(team.get("pointsFor")),
                points_against=_value(team.get("pointsAgainst")),
                players=players,
            )
        )
    league_info = _get(standings_json, "league") or {}
    return NormalizedLeague(
        name=safe_text(league_info.get("name")) if isinstance(league_info, dict) else "",
        season=season,
        teams=teams,
        roster_positions=roster_positions_from_rules(rules_json),
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
    base = {"sport": "NFL", "league_id": league_id}
    rosters = fetch_provider("FetchLeagueRosters", {**base, "season": season})
    standings = fetch_provider("FetchLeagueStandings", {**base, "season": season})
    rules = fetch_provider("FetchLeagueRules", dict(base))
    league = normalize_league(rosters, standings, rules, season)
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
    snapshot = build_snapshot(
        FLEAFLICKER_PLATFORM,
        league,
        league_key=league_key,
        external_league_id=league_id,
        default_name="Fleaflicker league",
        df_players=df_players,
        sleeper_players=sleeper_players,
        crosswalk=crosswalk,
    )
    return snapshot


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
        snapshot, label=FLEAFLICKER_LABEL, features=FEATURE_SUPPORT, mapping_message=ERROR_MESSAGES["mapping_too_low"]
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
