"""Shared plumbing for non-Sleeper league imports (Fleaflicker, MyFantasyLeague).

ESPN (``modules.espn_leagues``) was the first platform imported into
FantasyDesk. Fleaflicker and MFL follow the same pattern, so the parts that are
not platform specific live here:

* ``NormalizedLeague``: what a platform module hands over after it fetched and
  parsed its public API (league facts, teams, and each team's players with the
  platform's own id, name, position and NFL team).
* ``build_snapshot``: maps those players to FantasyDesk (Sleeper) player ids and
  produces the same Sleeper-shaped ``league`` / ``rosters`` / ``users``
  payloads ``modules.espn_leagues`` produces, plus honest mapping diagnostics.
* a small TTL snapshot cache and the import preview payload.

Player mapping never guesses. In order: an exact platform-id -> Sleeper-id
crosswalk (DynastyProcess' public id table, columns ``mfl_id`` and
``fleaflicker_id``), then a name match that must be unique after narrowing by
position and NFL team (``modules.platforms.espn``' resolver, shared with ESPN).
Anything else is listed as unmapped (or ambiguous) and left off the roster.

No credentials are accepted, stored or logged: only public leagues are read.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from modules.player_identity import normalize_player_id
from modules.platforms.espn import ESPNPlatformAdapter

MAPPING_BLOCK_THRESHOLD = 0.60
SNAPSHOT_TTL_SECONDS = 5 * 60
MAX_UNMAPPED_LISTED = 60


class ExternalLeagueError(RuntimeError):
    """A league could not be loaded. ``reason`` is a stable, client-facing code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_list(value: Any) -> list[Any]:
    """MFL's XML-to-JSON turns a single child into an object; normalize."""

    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


@dataclass
class NormalizedPlayer:
    platform_id: str
    name: str
    position: str  # already in Sleeper vocabulary: QB RB WR TE K DEF DL LB DB
    team: str  # Sleeper NFL team abbreviation, "" when unknown/free agent
    slot: str = "ROSTER"  # ROSTER | RESERVE | TAXI


@dataclass
class NormalizedTeam:
    team_id: str
    name: str
    owner: str = ""
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    players: list[NormalizedPlayer] = field(default_factory=list)


@dataclass
class NormalizedLeague:
    name: str
    season: int
    teams: list[NormalizedTeam]
    roster_positions: list[str] = field(default_factory=list)
    scoring_settings: dict[str, float] = field(default_factory=dict)
    ignored_players: int = 0


class IdCrosswalkAdapter(ESPNPlatformAdapter):
    """ESPN's name resolver with a platform-specific id crosswalk.

    The base class also folds any ``espn_id`` column of the player table into
    its crosswalk. That would map another platform's ids through ESPN's, so it
    is replaced wholesale with this platform's own crosswalk."""

    def __init__(self, platform: str, crosswalk: dict[str, str], df_players, sleeper_players):
        super().__init__(df_players=df_players, sleeper_players=sleeper_players)
        self.platform = platform
        self.espn_crosswalk = {normalize_player_id(k): v for k, v in (crosswalk or {}).items() if k and v}


def build_snapshot(
    platform: str,
    league: NormalizedLeague,
    *,
    league_key: str,
    external_league_id: str,
    default_name: str,
    df_players: pd.DataFrame | None,
    sleeper_players: dict[str, Any] | None,
    crosswalk: dict[str, str] | None,
    league_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adapter = IdCrosswalkAdapter(platform, crosswalk or {}, df_players, sleeper_players)
    rosters: list[dict[str, Any]] = []
    users: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    unmapped: list[dict[str, str]] = []
    id_map: dict[str, str] = {}
    total = matched = ambiguous = 0

    for team in league.teams:
        roster_id = safe_int(team.team_id, 0)
        owner_id = f"{platform}-team-{team.team_id}"
        team_name = team.name or f"Team {team.team_id}"
        owner_name = team.owner or team_name
        players: list[str] = []
        reserve: list[str] = []
        taxi: list[str] = []
        for player in team.players:
            total += 1
            canonical, method = adapter._canonicalize_player(
                {"playerId": player.platform_id, "name": player.name, "position": player.position, "proTeam": player.team}
            )
            if not canonical:
                if method == "ambiguous":
                    ambiguous += 1
                if len(unmapped) < MAX_UNMAPPED_LISTED:
                    unmapped.append(
                        {
                            "name": player.name,
                            "position": player.position,
                            "team": player.team,
                            "fantasy_team": team_name,
                            "reason": "ambiguous" if method == "ambiguous" else "no_unique_match",
                        }
                    )
                continue
            matched += 1
            if player.platform_id:
                id_map[str(player.platform_id)] = canonical
            if canonical in players:
                continue
            players.append(canonical)
            if player.slot == "RESERVE":
                reserve.append(canonical)
            elif player.slot == "TAXI":
                taxi.append(canonical)
        pf = team.points_for
        pa = team.points_against
        rosters.append(
            {
                "platform": platform,
                "roster_id": roster_id,
                "owner_id": owner_id,
                "players": players,
                "starters": [],
                "reserve": reserve,
                "taxi": taxi,
                "settings": {
                    "wins": team.wins,
                    "losses": team.losses,
                    "ties": team.ties,
                    "fpts": int(pf),
                    "fpts_decimal": int(round((pf % 1) * 100)),
                    "fpts_against": int(pa),
                    "fpts_against_decimal": int(round((pa % 1) * 100)),
                },
                "metadata": {"team_name": team_name},
            }
        )
        users.append(
            {
                "user_id": owner_id,
                "username": "",
                "display_name": owner_name,
                "avatar": "",
                "metadata": {"team_name": team_name},
            }
        )
        summaries.append(
            {
                "roster_id": str(roster_id),
                "team_name": team_name,
                "owner_name": owner_name,
                "player_count": len(team.players),
                "matched_player_count": len(players),
            }
        )

    num_teams = len(league.teams)
    settings = {"num_teams": num_teams}
    settings.update(league_settings or {})
    payload = {
        "platform": platform,
        "league_id": league_key,
        "external_league_id": external_league_id,
        "name": league.name or default_name,
        "season": str(league.season),
        "sport": "nfl",
        "status": "in_season",
        "total_rosters": num_teams,
        "settings": settings,
        "scoring_settings": dict(league.scoring_settings),
        "roster_positions": list(league.roster_positions),
    }
    return {
        "league_key": league_key,
        "league": payload,
        "rosters": rosters,
        "users": users,
        "teams": summaries,
        # platform player id -> FantasyDesk (Sleeper) id for every mapped player,
        # so a weekly lineup read later maps through the same, honest crosswalk.
        "id_map": id_map,
        "diagnostics": {
            "teams_found": num_teams,
            "total_players_seen": total,
            "canonical_matched_count": matched,
            "unmatched_count": total - matched,
            "ambiguous_count": ambiguous,
            "ignored_non_player_count": league.ignored_players,
            "matched_rate": round(matched / total, 4) if total else 0.0,
            "unmapped_players": unmapped,
        },
        "loaded_at": time.time(),
    }


def mapping_blocks_import(snapshot: dict[str, Any]) -> bool:
    diagnostics = snapshot.get("diagnostics") or {}
    return safe_float(diagnostics.get("matched_rate")) < MAPPING_BLOCK_THRESHOLD


def preview_payload(
    snapshot: dict[str, Any],
    *,
    label: str,
    features: tuple[dict[str, str], ...],
    mapping_message: str,
) -> dict[str, Any]:
    blocked = mapping_blocks_import(snapshot)
    league = snapshot["league"]
    return {
        "ok": not blocked,
        "reason": "mapping_too_low" if blocked else "",
        "message": mapping_message if blocked else "",
        "platform": league.get("platform") or "",
        "platform_label": label,
        "league": {
            "league_key": snapshot["league_key"],
            "external_league_id": league.get("external_league_id") or "",
            "season": league.get("season") or "",
            "name": league.get("name") or "",
            "team_count": league.get("total_rosters") or len(snapshot["rosters"]),
        },
        "teams": list(snapshot["teams"]),
        "diagnostics": dict(snapshot["diagnostics"]),
        "features": [dict(item) for item in features],
    }


def features_for(label: str, template: tuple[dict[str, str], ...], base_message: str) -> tuple[dict[str, str], ...]:
    """ESPN's feature list with the platform name swapped into the refusals."""

    message = f"Not available for {label} leagues yet."
    return tuple(
        {**item, "note": message if item.get("note") == base_message else item.get("note", "")} for item in template
    )


class SnapshotCache:
    """Single-flight TTL cache of loaded snapshots, one entry per league key."""

    def __init__(self, ttl: float = SNAPSHOT_TTL_SECONDS):
        self.ttl = ttl
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def get(self, key: str, loader: Callable[[str], dict[str, Any]], *, refresh: bool = False) -> dict[str, Any] | None:
        cached = self._cache.get(key)
        if cached and not refresh and time.time() - cached[0] < self.ttl:
            return cached[1]
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            cached = self._cache.get(key)
            if cached and not refresh and time.time() - cached[0] < self.ttl:
                return cached[1]
            try:
                snapshot = loader(key)
            except ExternalLeagueError:
                return None
            self._cache[key] = (time.time(), snapshot)
            return snapshot

    def store(self, key: str, snapshot: dict[str, Any]) -> None:
        self._cache[key] = (time.time(), snapshot)

    def clear(self) -> None:
        self._cache.clear()


class Throttle:
    """Minimum spacing between calls to one third-party API."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            delay = self._last + self.min_interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()
