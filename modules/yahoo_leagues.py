"""Yahoo Fantasy leagues for the FastAPI service (web-next and mobile).

Follows the ESPN / Fleaflicker import pattern: a Yahoo league is the string key
``yahoo:{yahoo league_key}:{season}`` (e.g. ``yahoo:461.l.12345:2026``), loaded
into a Sleeper-shaped snapshot (``modules.external_league_common``) that the
valuation, roster, trade and matchup engines already understand.

Unlike every other imported platform, Yahoo leagues are always private: every
call carries the signed-in user's own OAuth access token
(``modules.yahoo_connect``), so snapshots are cached per (league, user) and a
league is served only to the user whose token loaded it.

API shape, re-checked against Yahoo's developer docs (2026-11; see
docs/yahoo-import.md). Base ``https://fantasysports.yahooapis.com/fantasy/v2``,
``?format=json``, ``Authorization: Bearer``:

* ``game/nfl``                                   current NFL game key + season
* ``users;use_login=1/games;game_keys={k}/leagues``  the user's leagues that season
* ``league/{key}/settings``                      roster slots, stat modifiers
* ``league/{key}/standings``                     teams, managers, record
* ``team/{team_key}/roster/players``             rostered players + lineup slot
* ``league/{key}/scoreboard``                    this week's pairings and scores

Yahoo's JSON is an automatic conversion of its XML: a resource is a *list* of
small dicts (``[{"team_key": ..}, {"name": ..}]``) and a collection is a dict
keyed ``"0"``, ``"1"`` ... plus ``"count"``. :func:`flatten` normalises both so
the parsers below read plain dicts and lists. NOTHING here has run against live
Yahoo from the repo's test environment; the fixtures follow that documented
shape.
"""

from __future__ import annotations

import contextvars
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
    build_snapshot,
    features_for,
    mapping_blocks_import,
    preview_payload as _preview_payload,
    safe_int,
    safe_text,
)
from modules.platforms.espn import normalize_espn_team

YAHOO_PLATFORM = "yahoo"
YAHOO_LABEL = "Yahoo"
YAHOO_LEAGUE_KEY_PREFIX = "yahoo:"
YAHOO_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_USER_AGENT = "FantasyDesk-LeagueImport/1.0 (+https://fantasydesk.app)"
REQUEST_TIMEOUT_SECONDS = 20
MIN_SEASON = 2010
MAX_SEASON = 2035

_KEY_PATTERN = re.compile(r"^yahoo:(\d{1,6}\.l\.\d{1,12}):(\d{4})$")
_YAHOO_KEY_PATTERN = re.compile(r"^(\d{1,6})\.l\.(\d{1,12})$")
_throttle = Throttle(0.25)
_cache = SnapshotCache()

ERROR_MESSAGES = {
    "invalid_input": "That Yahoo league couldn't be recognised. Pick one from your Yahoo league list.",
    "not_connected": "Connect your Yahoo account first.",
    "not_configured": "Connecting Yahoo isn't available right now.",
    "reconnect_needed": "Your Yahoo connection expired. Tap Connect Yahoo to sign in again.",
    "league_not_found": "We couldn't open that Yahoo league with your account. Check that you are in it, then try again.",
    "no_teams": "That Yahoo league loaded, but it has no teams or rosters yet.",
    "yahoo_unavailable": "Yahoo didn't respond. Please try again in a moment.",
    "yahoo_rate_limited": "Yahoo is limiting requests right now. Please try again in a minute.",
    "mapping_too_low": (
        "That Yahoo league loaded, but too few of its players matched FantasyDesk's player list "
        "to value the rosters accurately."
    ),
}
NOT_AVAILABLE_MESSAGE = f"Not available for {YAHOO_LABEL} leagues yet."
FEATURE_SUPPORT = features_for(YAHOO_LABEL, espn_leagues.ESPN_FEATURE_SUPPORT, espn_leagues.ESPN_NOT_AVAILABLE_MESSAGE)

# --- league key -----------------------------------------------------------------


def build_league_key(yahoo_league_key: Any, season: Any) -> str:
    key, year = safe_text(yahoo_league_key), safe_int(season, 0)
    if not _YAHOO_KEY_PATTERN.match(key) or not MIN_SEASON <= year <= MAX_SEASON:
        return ""
    return f"{YAHOO_LEAGUE_KEY_PREFIX}{key}:{year}"


def parse_league_key(value: Any) -> tuple[str, int] | None:
    """``yahoo:461.l.12345:2026`` -> ``("461.l.12345", 2026)``."""

    match = _KEY_PATTERN.match(safe_text(value))
    if not match:
        return None
    season = safe_int(match.group(2), 0)
    return (match.group(1), season) if MIN_SEASON <= season <= MAX_SEASON else None


def is_league_key(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(YAHOO_LEAGUE_KEY_PREFIX)


# --- Yahoo JSON normalisation ----------------------------------------------------


def _is_index_key(key: Any) -> bool:
    return isinstance(key, str) and key.isdigit()


def flatten(value: Any) -> Any:
    """Undo Yahoo's XML-to-JSON quirks.

    * ``{"0": a, "1": b, "count": 2}`` becomes ``[a, b]``.
    * A dict that mixes index keys with named keys folds the indexed dicts into
      the named ones (a roster is ``{"coverage_type": .., "0": {"players": ..}}``).
    * A list of dicts/lists becomes one merged dict when no key repeats
      (``[{"team_key": ..}, {"name": ..}]``); with repeated keys
      (``[{"stat": ..}, {"stat": ..}]``) it stays a list.
    """

    if isinstance(value, dict):
        index_keys = sorted((k for k in value if _is_index_key(k)), key=int)
        # "count" is a collection's size marker only next to index keys; elsewhere it is data (roster slot count).
        named = {k: flatten(v) for k, v in value.items() if not _is_index_key(k) and not (index_keys and k == "count")}
        if index_keys and not named:
            return [flatten(value[k]) for k in index_keys]
        for key in index_keys:
            inner = flatten(value[key])
            if isinstance(inner, dict):
                for inner_key, inner_value in inner.items():
                    named.setdefault(inner_key, inner_value)
        return named
    if isinstance(value, list):
        items = [flatten(item) for item in value]
        parts = [item for item in items if item not in ([], {}, None)]
        if parts and all(isinstance(item, dict) for item in parts):
            keys = [key for item in parts for key in item]
            if len(keys) == len(set(keys)):
                merged: dict[str, Any] = {}
                for item in parts:
                    merged.update(item)
                return merged
        return items
    return value


def seq(container: Any, wrapper: str = "") -> list[Any]:
    """A flattened collection as a list; ``{"team": {...}}`` wrappers are removed."""

    if container is None or container == "":
        return []
    items = container if isinstance(container, list) else [container]
    out: list[Any] = []
    for item in items:
        if isinstance(item, dict) and wrapper and wrapper in item and len(item) == 1:
            out.append(item[wrapper])
        elif isinstance(item, list):
            out.extend(seq(item, wrapper))
        elif item not in ({}, None, ""):
            out.append(item)
    return out


def _content(payload: Any) -> dict[str, Any]:
    flat = flatten(payload.get("fantasy_content") if isinstance(payload, dict) and "fantasy_content" in payload else payload)
    return flat if isinstance(flat, dict) else {}


def _dig(obj: Any, *path: str) -> Any:
    for name in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(name)
    return obj


# --- network ----------------------------------------------------------------------


def _default_fetch(path: str, access_token: str) -> Any:
    _throttle.wait()
    try:
        response = requests.get(
            f"{YAHOO_API_BASE}/{path.lstrip('/')}",
            params={"format": "json"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": YAHOO_USER_AGENT,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise ExternalLeagueError("yahoo_unavailable", ERROR_MESSAGES["yahoo_unavailable"]) from None
    status = response.status_code
    if status == 401:
        raise ExternalLeagueError("reconnect_needed", ERROR_MESSAGES["reconnect_needed"])
    if status in (403, 404):
        raise ExternalLeagueError("league_not_found", ERROR_MESSAGES["league_not_found"])
    if status in (429, 999):  # Yahoo answers 999 when it throttles
        raise ExternalLeagueError("yahoo_rate_limited", ERROR_MESSAGES["yahoo_rate_limited"])
    if status != 200:
        raise ExternalLeagueError("yahoo_unavailable", ERROR_MESSAGES["yahoo_unavailable"])
    try:
        return response.json()
    except ValueError:
        raise ExternalLeagueError("yahoo_unavailable", ERROR_MESSAGES["yahoo_unavailable"]) from None


# Indirection points for tests (no network, no data/players.db).
fetch_provider: Callable[[str, str], Any] = _default_fetch


def _default_players_frame() -> pd.DataFrame:
    return espn_leagues.players_frame_provider()


def _default_sleeper_players() -> dict[str, Any]:
    return espn_leagues.sleeper_players_provider()


def _default_crosswalk() -> dict[str, str]:
    from modules import espn_player_crosswalk

    return espn_player_crosswalk.load_platform_crosswalk("yahoo_id")


players_frame_provider: Callable[[], pd.DataFrame] = _default_players_frame
sleeper_players_provider: Callable[[], dict[str, Any]] = _default_sleeper_players
crosswalk_provider: Callable[[], dict[str, str]] = _default_crosswalk


# --- the user's league list ---------------------------------------------------------


def current_game(access_token: str) -> tuple[str, int]:
    """``(game_key, season)`` of the current NFL game (e.g. ``("461", 2026)``)."""

    game = _dig(_content(fetch_provider("game/nfl", access_token)), "game") or {}
    game_key, season = safe_text(game.get("game_key")), safe_int(game.get("season"), 0)
    if not game_key or not season:
        raise ExternalLeagueError("yahoo_unavailable", ERROR_MESSAGES["yahoo_unavailable"])
    return game_key, season


def list_user_leagues(access_token: str) -> list[dict[str, Any]]:
    """The signed-in user's NFL leagues for the current game key, newest first."""

    game_key, season = current_game(access_token)
    content = _content(
        fetch_provider(f"users;use_login=1/games;game_keys={game_key}/leagues", access_token)
    )
    leagues: list[dict[str, Any]] = []
    for user in seq(content.get("users"), "user"):
        for game in seq(_dig(user, "games"), "game"):
            for league in seq(_dig(game, "leagues"), "league"):
                if not isinstance(league, dict):
                    continue
                yahoo_key = safe_text(league.get("league_key"))
                league_key = build_league_key(yahoo_key, league.get("season") or season)
                if not league_key:
                    continue
                leagues.append(
                    {
                        "league_key": league_key,
                        "yahoo_league_key": yahoo_key,
                        "name": safe_text(league.get("name")) or "Yahoo league",
                        "season": str(safe_int(league.get("season"), season)),
                        "team_count": safe_int(league.get("num_teams"), 0),
                        "scoring_type": safe_text(league.get("scoring_type")),
                        "is_finished": safe_text(league.get("is_finished")) == "1",
                    }
                )
    return leagues


# --- parsing --------------------------------------------------------------------------

_POSITION = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "DEF": "DEF",
    "DT": "DL", "DE": "DL", "DL": "DL", "LB": "LB", "CB": "DB", "S": "DB", "DB": "DB",
}
# Yahoo lineup slot -> Sleeper roster_positions token. Unlisted slots are dropped, never approximated.
_SLOT = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "DEF": "DEF",
    "W/R/T": "FLEX", "W/R": "WRRB_FLEX", "W/T": "REC_FLEX", "Q/W/R/T": "SUPER_FLEX",
    "DT": "DL", "DE": "DL", "DL": "DL", "LB": "LB", "CB": "DB", "S": "DB", "DB": "DB", "D": "IDP_FLEX",
    "BN": "BN", "IR": "IR", "IR+": "IR",
}
_BENCH_SLOTS = {"BN", "IR", "IR+"}
_RESERVE_SLOTS = {"IR", "IR+"}

# Yahoo NFL stat_id -> Sleeper scoring key. Only stats whose id is stable and
# that the valuation engines read; everything else is left to FantasyDesk's
# defaults rather than guessed.
_STAT_KEYS = {
    "4": "pass_yd", "5": "pass_td", "6": "pass_int",
    "9": "rush_yd", "10": "rush_td",
    "11": "rec", "12": "rec_yd", "13": "rec_td",
    "18": "fum_lost",
}


def roster_positions_from_settings(settings: Any) -> list[str]:
    starters: list[str] = []
    bench: list[str] = []
    for entry in seq(_dig(settings, "roster_positions"), "roster_position"):
        if not isinstance(entry, dict):
            continue
        token = _SLOT.get(safe_text(entry.get("position")))
        count = safe_int(entry.get("count"), 0)
        if token and count > 0:
            (bench if token in ("BN", "IR") else starters).extend([token] * count)
    return starters + bench


def scoring_from_settings(settings: Any) -> dict[str, float]:
    scoring: dict[str, float] = {}
    for entry in seq(_dig(settings, "stat_modifiers", "stats"), "stat"):
        if not isinstance(entry, dict):
            continue
        key = _STAT_KEYS.get(safe_text(entry.get("stat_id")))
        try:
            value = float(entry.get("value"))
        except (TypeError, ValueError):
            continue
        if key:
            scoring[key] = value
    return scoring


def _manager_name(team: dict[str, Any]) -> str:
    names = [
        safe_text(m.get("nickname"))
        for m in seq(team.get("managers"), "manager")
        if isinstance(m, dict) and safe_text(m.get("nickname")) and safe_text(m.get("nickname")) != "--hidden--"
    ]
    return ", ".join(names)


def _team_row(team: dict[str, Any]) -> dict[str, Any]:
    standings = team.get("team_standings") if isinstance(team.get("team_standings"), dict) else {}
    totals = standings.get("outcome_totals") if isinstance(standings.get("outcome_totals"), dict) else {}

    def points(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    return {
        "team_id": safe_text(team.get("team_id")),
        "team_key": safe_text(team.get("team_key")),
        "name": safe_text(team.get("name")),
        "owner": _manager_name(team),
        "wins": safe_int(totals.get("wins")),
        "losses": safe_int(totals.get("losses")),
        "ties": safe_int(totals.get("ties")),
        "points_for": points(standings.get("points_for")),
        "points_against": points(standings.get("points_against")),
    }


def parse_standings(payload: Any) -> list[dict[str, Any]]:
    league = _dig(_content(payload), "league") or {}
    teams = seq(_dig(league, "standings", "teams"), "team") or seq(_dig(league, "teams"), "team")
    return [_team_row(team) for team in teams if isinstance(team, dict) and safe_text(team.get("team_id"))]


def parse_roster(payload: Any) -> list[dict[str, Any]]:
    """Players of one ``team/{key}/roster/players`` response, with lineup slot."""

    team = _dig(_content(payload), "team") or {}
    out: list[dict[str, Any]] = []
    for player in seq(_dig(team, "roster", "players"), "player"):
        if not isinstance(player, dict):
            continue
        name = safe_text(_dig(player, "name", "full"))
        display = safe_text(player.get("display_position")).split(",")[0].strip().upper()
        position = _POSITION.get(display, "")
        slot = safe_text(_dig(player, "selected_position", "position")).upper() or "BN"
        out.append(
            {
                "platform_id": safe_text(player.get("player_id")),
                "name": name,
                "position": position,
                "team": normalize_espn_team(safe_text(player.get("editorial_team_abbr")).upper()),
                "yahoo_slot": slot,
            }
        )
    return out


def parse_scoreboard(payload: Any) -> dict[str, Any]:
    """``{"week": int, "games": [{a_id, b_id, a_points, b_points, status}]}``."""

    league = _dig(_content(payload), "league") or {}
    board = _dig(league, "scoreboard") or {}
    week = safe_int(board.get("week") if isinstance(board, dict) else 0, 0) or safe_int(league.get("current_week"), 0)
    games: list[dict[str, Any]] = []
    for matchup in seq(_dig(board, "matchups"), "matchup"):
        if not isinstance(matchup, dict):
            continue
        teams = [t for t in seq(matchup.get("teams"), "team") if isinstance(t, dict)]
        if len(teams) != 2:
            continue
        started = safe_text(matchup.get("status")) != "preevent"

        def total(team: dict[str, Any]) -> float | None:
            if not started:
                return None
            try:
                return float(_dig(team, "team_points", "total"))
            except (TypeError, ValueError):
                return None

        games.append(
            {
                "a_id": safe_text(teams[0].get("team_id")),
                "b_id": safe_text(teams[1].get("team_id")),
                "a_points": total(teams[0]),
                "b_points": total(teams[1]),
                "status": safe_text(matchup.get("status")),
            }
        )
    return {"week": week, "games": games}


# --- snapshot -----------------------------------------------------------------------


def _slot_token(raw_slot: str) -> str:
    return _SLOT.get(raw_slot, raw_slot)


def load_league_snapshot(league_key: str, access_token: str, *, owner_user_id: str = "") -> dict[str, Any]:
    parsed = parse_league_key(league_key)
    if not parsed:
        raise ExternalLeagueError("invalid_input", ERROR_MESSAGES["invalid_input"])
    yahoo_key, season = parsed
    settings_content = _content(fetch_provider(f"league/{yahoo_key}/settings", access_token))
    league_meta = _dig(settings_content, "league") or {}
    settings = league_meta.get("settings") if isinstance(league_meta.get("settings"), dict) else {}
    standings = parse_standings(fetch_provider(f"league/{yahoo_key}/standings", access_token))

    teams: list[NormalizedTeam] = []
    ignored = 0
    roster_rows: dict[str, list[dict[str, Any]]] = {}
    for row in standings:
        players_raw = parse_roster(fetch_provider(f"team/{row['team_key']}/roster/players", access_token))
        roster_rows[row["team_id"]] = players_raw
        players: list[NormalizedPlayer] = []
        for item in players_raw:
            if not item["position"] or not item["name"]:
                ignored += 1
                continue
            players.append(
                NormalizedPlayer(
                    platform_id=item["platform_id"],
                    name=item["name"],
                    position=item["position"],
                    team=item["team"],
                    slot="RESERVE" if item["yahoo_slot"] in _RESERVE_SLOTS else "ROSTER",
                )
            )
        teams.append(
            NormalizedTeam(
                team_id=row["team_id"],
                name=row["name"],
                owner=row["owner"],
                wins=row["wins"],
                losses=row["losses"],
                ties=row["ties"],
                points_for=row["points_for"],
                points_against=row["points_against"],
                players=players,
            )
        )
    if not teams:
        raise ExternalLeagueError("no_teams", ERROR_MESSAGES["no_teams"])

    league = NormalizedLeague(
        name=safe_text(league_meta.get("name")),
        season=season,
        teams=teams,
        roster_positions=roster_positions_from_settings(settings),
        scoring_settings=scoring_from_settings(settings),
        ignored_players=ignored,
    )
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
        YAHOO_PLATFORM,
        league,
        league_key=league_key,
        external_league_id=yahoo_key,
        default_name="Yahoo league",
        df_players=df_players,
        sleeper_players=sleeper_players,
        crosswalk=crosswalk,
        league_settings={"scoring_type": safe_text(league_meta.get("scoring_type"))},
    )
    snapshot["league"]["status"] = "complete" if safe_text(league_meta.get("is_finished")) == "1" else "in_season"

    # Lineups (from the same roster calls) and this week's pairings (1 more call).
    id_map = snapshot.get("id_map") or {}
    lineups: dict[str, dict[str, Any]] = {}
    for roster in snapshot["rosters"]:
        rid = str(roster["roster_id"])
        starters: list[str] = []
        slots: list[str] = []
        unmapped: list[dict[str, str]] = []
        for item in roster_rows.get(rid, []):
            if item["yahoo_slot"] in _BENCH_SLOTS:
                continue
            canonical = id_map.get(item["platform_id"])
            if canonical:
                starters.append(canonical)
                slots.append(_slot_token(item["yahoo_slot"]))
            elif item["name"]:
                unmapped.append(
                    {"name": item["name"], "position": item["position"], "team": item["team"], "slot": _slot_token(item["yahoo_slot"])}
                )
        roster["starters"] = [s for s in starters if s in roster["players"]]
        lineups[rid] = {"starters": starters, "slots": slots, "unmapped": unmapped}
    snapshot["lineups"] = lineups
    snapshot["week_state"] = _week_state(yahoo_key, access_token, league_meta)
    snapshot["owner_user_id"] = owner_user_id
    return snapshot


def _week_state(yahoo_key: str, access_token: str, league_meta: dict[str, Any]) -> dict[str, Any]:
    current_week = safe_int(league_meta.get("current_week"), 0)
    pairings: dict[str, dict[str, Any]] = {}
    try:
        board = parse_scoreboard(fetch_provider(f"league/{yahoo_key}/scoreboard", access_token))
    except ExternalLeagueError:
        return {"week": current_week, "pairings": pairings}  # lineups still work without pairings
    for game in board["games"]:
        pairings[game["a_id"]] = {"opponent": game["b_id"], "points": game["a_points"]}
        pairings[game["b_id"]] = {"opponent": game["a_id"], "points": game["b_points"]}
    return {"week": board["week"] or current_week, "pairings": pairings}


# --- per-request login + cache ----------------------------------------------------------


class RequestLogin:
    """The caller's Yahoo access, resolved lazily so requests that never touch
    Yahoo pay nothing. ``resolve`` returns ``(user_id, access_token)`` or None."""

    def __init__(self, resolver: Callable[[], tuple[str, str] | None]):
        self._resolver = resolver
        self._done = False
        self._value: tuple[str, str] | None = None

    def resolve(self) -> tuple[str, str] | None:
        if not self._done:
            try:
                self._value = self._resolver()
            except Exception:
                self._value = None
            self._done = True
        return self._value


_REQUEST_LOGIN: contextvars.ContextVar[RequestLogin | None] = contextvars.ContextVar("yahoo_request_login", default=None)


def bind_request_login(login: RequestLogin) -> contextvars.Token:
    return _REQUEST_LOGIN.set(login)


def bind_request_access(user_id: str, access_token: str) -> contextvars.Token:
    return _REQUEST_LOGIN.set(RequestLogin(lambda: (str(user_id), access_token)))


def reset_request_login(token: contextvars.Token) -> None:
    _REQUEST_LOGIN.reset(token)


def _user_key(league_key: str, user_id: str) -> str:
    return f"{league_key}\x00{user_id}"


def get_league_snapshot(league_key: str, *, refresh: bool = False) -> dict[str, Any] | None:
    """Cached snapshot for the *bound* user, or None (no login, not their
    league, Yahoo down). Never served across users."""

    if not parse_league_key(league_key):
        return None
    login = _REQUEST_LOGIN.get()
    resolved = login.resolve() if login else None
    if not resolved:
        return None
    user_id, access_token = resolved
    return _cache.get(
        _user_key(league_key, user_id),
        lambda _key: load_league_snapshot(league_key, access_token, owner_user_id=user_id),
        refresh=refresh,
    )


def store_snapshot(league_key: str, snapshot: dict[str, Any]) -> None:
    owner = safe_text(snapshot.get("owner_user_id"))
    if owner:
        _cache.store(_user_key(league_key, owner), snapshot)


def clear_snapshot_cache() -> None:
    _cache.clear()


def preview_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return _preview_payload(
        snapshot, label=YAHOO_LABEL, features=FEATURE_SUPPORT, mapping_message=ERROR_MESSAGES["mapping_too_low"]
    )


__all__ = [
    "ExternalLeagueError",
    "build_league_key",
    "parse_league_key",
    "is_league_key",
    "flatten",
    "list_user_leagues",
    "load_league_snapshot",
    "get_league_snapshot",
    "store_snapshot",
    "clear_snapshot_cache",
    "preview_payload",
    "mapping_blocks_import",
]
