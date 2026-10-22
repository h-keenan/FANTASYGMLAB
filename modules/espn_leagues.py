"""ESPN leagues for the FastAPI service (web-next and mobile).

ESPN import used to exist only in the legacy Streamlit app
(modules/platform_import_ui.py). This module is the API-side version, and it
is deliberately a narrow, honest slice rather than a second platform layer:

* An ESPN league is identified everywhere by one string key,
  ``espn:{league_id}:{season}`` (see ``build_espn_league_key``). That key is
  the ``saved_leagues.league_id`` value, so the platform marker lives in the
  existing column and no schema change is needed. It can never collide with
  a Sleeper league id, which is always purely numeric.
* ``load_league_snapshot`` loads the league from ESPN's public API once and
  translates it into the Sleeper-shaped league / rosters / users payloads the
  valuation, roster and trade engines already consume. ``modules.sleeper``'s
  league getters hand ESPN keys to this module, so those engines run
  unchanged on ESPN rosters.
* Only the features the snapshot can genuinely feed are open to ESPN keys
  (``ESPN_SUPPORTED_LEAGUE_ROUTES``). Everything else that needs Sleeper-only
  data (matchups, transactions, waivers, drafts, traded picks, news-to-roster
  alerts, ...) is refused by the API with ``ESPN_NOT_AVAILABLE_MESSAGE``
  rather than quietly running on empty data.

Private ESPN leagues are out of scope. Reading one needs the user's
``espn_s2`` and ``SWID`` cookies on every request, which means storing a live
ESPN session credential server side. There is no encrypted secret store for
user credentials in this service, so this module never accepts, logs or
persists those cookies. A private league comes back as ``private_league``.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

import pandas as pd

ESPN_PLATFORM = "espn"
ESPN_LEAGUE_KEY_PREFIX = "espn:"
ESPN_NOT_AVAILABLE_MESSAGE = "Not available for ESPN leagues yet."
ESPN_NOT_AVAILABLE_REASON = "espn_not_supported"

PLAYERS_DB_PATH = "data/players.db"
ESPN_SNAPSHOT_TTL_SECONDS = 5 * 60
ESPN_MIN_SEASON = 2018
ESPN_MAX_SEASON = 2035

# Same thresholds the Streamlit import uses (modules.platform_import_ui):
# below 60% of roster players mapped to FantasyDesk player ids, values and
# trade grades would describe a different roster than the user's real one.
ESPN_MAPPING_BLOCK_THRESHOLD = 0.60

_KEY_PATTERN = re.compile(r"^espn:(\d{1,12}):(\d{4})$")

# League-scoped routes (the part after /v1/leagues/{league_id}) that an ESPN
# league can actually serve. Every other /v1/leagues/{espn key}/... route is
# refused with ESPN_NOT_AVAILABLE_MESSAGE.
ESPN_SUPPORTED_LEAGUE_ROUTES: tuple[str, ...] = (
    "",
    "/users",
    "/rosters",
    "/team-profiles",
    "/team-rankings",
    "/my-roster",
    "/my-team",
    "/my-team-needs",
    "/rankings",
    "/trade-analyzer",
    # Answers with an empty list and reason espn_not_supported (ESPN exposes
    # no future-pick ownership), so Trade Analyzer runs players-only.
    "/draft-picks",
    # Removing a saved league must always work, whatever its platform.
    "/save",
)
_SUPPORTED_DYNAMIC_ROUTES = (re.compile(r"^/players/[^/]+/rank$"),)

# What the import step tells the user, before they save the league. Kept in
# one place so the API, web and mobile all show the same list.
ESPN_FEATURE_SUPPORT: tuple[dict[str, str], ...] = (
    {"feature": "My Team", "status": "available", "note": "Your roster, suggested lineup and team needs."},
    {"feature": "Trade Analyzer", "status": "available", "note": "Player-for-player trades. Draft picks aren't included."},
    {"feature": "Players", "status": "available", "note": "Player values for your league's scoring and lineup."},
    {
        "feature": "League Rankings",
        "status": "available",
        "note": (
            "Team power and roster rankings. Draft capital assumes each team holds its own future picks; "
            "playoff odds aren't included."
        ),
    },
    {"feature": "Dashboard", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "Matchup", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "Waivers", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "Trade Hub and Trade Finder", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "Alerts", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "GM Plan", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "Draft Center and Live Draft", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "League Recaps", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
    {"feature": "Portfolio", "status": "not_available", "note": ESPN_NOT_AVAILABLE_MESSAGE},
)

# ESPN lineup slot name -> the Sleeper roster_positions token that
# modules.league_value_settings.detect_league_value_settings_from_payload
# already understands. Slots with no fantasy value here (head coach, punter,
# the unused "TQB"/"ER" slots) are dropped.
_SLOT_TO_SLEEPER_POSITION = {
    "QB": "QB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "D/ST": "DEF",
    "RB/WR/TE": "FLEX",
    "RB/WR": "WRRB_FLEX",
    "WR/TE": "REC_FLEX",
    "OP": "SUPER_FLEX",
    "DT": "DL",
    "DE": "DL",
    "DL": "DL",
    "LB": "LB",
    "CB": "DB",
    "S": "DB",
    "DB": "DB",
    "DP": "IDP_FLEX",
    "BE": "BN",
    "IR": "IR",
}
_STARTER_SLOT_ORDER = (
    "QB", "RB", "WR", "TE", "RB/WR", "WR/TE", "RB/WR/TE", "OP", "K", "D/ST",
    "DT", "DE", "DL", "LB", "CB", "S", "DB", "DP",
)
_BENCH_LINEUP_SLOTS = {"BE", "IR"}

# ESPN scoring item abbreviation -> Sleeper scoring_settings key.
_SCORING_ABBR_TO_SLEEPER = {
    "REC": "rec",
    "PTD": "pass_td",
    "INTT": "pass_int",
    "FUML": "fum_lost",
    "PY": "pass_yd",
    "RY": "rush_yd",
    "REY": "rec_yd",
    "RTD": "rush_td",
    "RETD": "rec_td",
}
_ESPN_RECEPTION_STAT_ID = 53
_ESPN_TE_SLOT_ID = "6"


class ESPNLeagueError(RuntimeError):
    """A league could not be loaded. ``reason`` is a stable, client-facing code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


ERROR_MESSAGES = {
    "invalid_input": "Enter an ESPN league ID (numbers only) and a season.",
    "private_league": (
        "This ESPN league is private, or the league ID is wrong. FantasyDesk can only read ESPN "
        "leagues that are viewable to the public. Your league manager can turn that on in ESPN's "
        "league settings."
    ),
    "league_not_found": "We couldn't find that ESPN league for that season. Check the league ID and season.",
    "no_teams": "That ESPN league loaded, but it has no teams or rosters yet.",
    "espn_unavailable": "ESPN didn't respond. Please try again in a moment.",
    "mapping_too_low": (
        "That ESPN league loaded, but too few of its players matched FantasyDesk's player list "
        "to value the rosters accurately."
    ),
}


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_espn_league_id(value: Any) -> str:
    text = _safe_text(value)
    return text if text.isdigit() and len(text) <= 12 else ""


def normalize_espn_season(value: Any) -> int:
    season = _safe_int(value, 0)
    return season if ESPN_MIN_SEASON <= season <= ESPN_MAX_SEASON else 0


def build_espn_league_key(league_id: Any, season: Any) -> str:
    clean_id = normalize_espn_league_id(league_id)
    clean_season = normalize_espn_season(season)
    if not clean_id or not clean_season:
        return ""
    return f"{ESPN_LEAGUE_KEY_PREFIX}{int(clean_id)}:{clean_season}"


def parse_espn_league_key(value: Any) -> tuple[str, int] | None:
    match = _KEY_PATTERN.match(_safe_text(value))
    if not match:
        return None
    season = normalize_espn_season(match.group(2))
    if not season:
        return None
    return str(int(match.group(1))), season


def is_espn_league_key(value: Any) -> bool:
    """Cheap prefix check (no parsing) used on hot Sleeper code paths."""

    return isinstance(value, str) and value.startswith(ESPN_LEAGUE_KEY_PREFIX)


def league_platform(value: Any) -> str:
    return ESPN_PLATFORM if is_espn_league_key(value) else "sleeper"


def is_supported_league_route(suffix: str) -> bool:
    """`suffix` is the path after /v1/leagues/{league_id}, e.g. "/my-team"."""

    clean = suffix.rstrip("/") if suffix not in ("", "/") else ""
    if clean in ESPN_SUPPORTED_LEAGUE_ROUTES:
        return True
    return any(pattern.match(clean) for pattern in _SUPPORTED_DYNAMIC_ROUTES)


_LEAGUE_PATH_PATTERN = re.compile(r"^/v1/(?:leagues|portfolio/leagues)/(espn:[^/]*)(/.*)?$")


def gated_league_path(path: str) -> bool:
    """True when `path` asks an ESPN league for a feature it can't serve.

    Covers every /v1/leagues/{espn key}/... route outside
    ESPN_SUPPORTED_LEAGUE_ROUTES. Portfolio's per-league row is answered by
    the Portfolio code itself (a failed row with a reason), not here.
    """

    match = _LEAGUE_PATH_PATTERN.match(path or "")
    if not match or path.startswith("/v1/portfolio/"):
        return False
    return not is_supported_league_route(match.group(2) or "")


def not_available_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "error": ESPN_NOT_AVAILABLE_MESSAGE,
        "detail": ESPN_NOT_AVAILABLE_MESSAGE,
        "reason": ESPN_NOT_AVAILABLE_REASON,
        "platform": ESPN_PLATFORM,
    }


# ---------------------------------------------------------------------------
# Translation from espn_api objects to Sleeper-shaped payloads
# ---------------------------------------------------------------------------


def _owner_display_name(team: Any) -> str:
    owners = getattr(team, "owners", None) or []
    names: list[str] = []
    for owner in owners if isinstance(owners, list) else [owners]:
        if isinstance(owner, dict):
            name = _safe_text(owner.get("displayName")) or " ".join(
                part for part in (_safe_text(owner.get("firstName")), _safe_text(owner.get("lastName"))) if part
            )
        else:
            name = _safe_text(owner)
        if name:
            names.append(name)
    return ", ".join(names)


def _roster_positions(slot_counts: dict[str, Any]) -> list[str]:
    positions: list[str] = []
    for slot in _STARTER_SLOT_ORDER:
        token = _SLOT_TO_SLEEPER_POSITION.get(slot)
        positions.extend([token] * max(0, _safe_int(slot_counts.get(slot), 0)))
    positions.extend(["BN"] * max(0, _safe_int(slot_counts.get("BE"), 0)))
    positions.extend(["IR"] * max(0, _safe_int(slot_counts.get("IR"), 0)))
    return positions


def _scoring_settings(settings: Any) -> dict[str, float]:
    scoring: dict[str, float] = {}
    base_reception = None
    for item in getattr(settings, "scoring_format", None) or []:
        if not isinstance(item, dict):
            continue
        key = _SCORING_ABBR_TO_SLEEPER.get(_safe_text(item.get("abbr")).upper())
        if key:
            scoring[key] = _safe_float(item.get("points"))
            if key == "rec":
                base_reception = scoring[key]
    raw = getattr(settings, "_raw_scoring_settings", None)
    raw_items = raw.get("scoringItems") if isinstance(raw, dict) else None
    for item in raw_items or []:
        if not isinstance(item, dict) or _safe_int(item.get("statId"), -1) != _ESPN_RECEPTION_STAT_ID:
            continue
        overrides = item.get("pointsOverrides") if isinstance(item.get("pointsOverrides"), dict) else {}
        te_points = overrides.get(_ESPN_TE_SLOT_ID, overrides.get(int(_ESPN_TE_SLOT_ID)))
        if te_points is not None:
            bonus = _safe_float(te_points) - _safe_float(base_reception if base_reception is not None else item.get("points"))
            if bonus > 0:
                scoring["bonus_rec_te"] = round(bonus, 3)
    return scoring


def _league_type(settings: Any, roster_size: int) -> int:
    """Sleeper's settings.type (0 redraft, 1 keeper, 2 dynasty).

    ESPN has no dynasty flag. A league that keeps (nearly) the whole roster
    is a dynasty league in practice; any other keeper count is a keeper
    league; zero keepers is redraft."""

    keepers = _safe_int(getattr(settings, "keeper_count", 0), 0)
    if keepers <= 0:
        return 0
    if roster_size and keepers >= max(1, roster_size - 2):
        return 2
    return 1


def build_snapshot(
    raw_league: Any,
    *,
    league_key: str,
    df_players: pd.DataFrame | None,
    adapter_factory: Callable[..., Any] | None = None,
    sleeper_players: dict[str, Any] | None = None,
    espn_crosswalk: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Translate a loaded espn_api League into the payloads the API serves.

    ``espn_crosswalk`` (ESPN id -> Sleeper id) and ``sleeper_players``
    (Sleeper's players/nfl dump) let the adapter map players by exact id and
    match names against every Sleeper player, not only the valued table."""

    from modules.platforms.espn import get_espn_adapter

    adapter = (adapter_factory or get_espn_adapter)(
        df_players=df_players,
        sleeper_players=sleeper_players,
        espn_crosswalk=espn_crosswalk,
    )
    settings = getattr(raw_league, "settings", None)
    slot_counts = getattr(settings, "position_slot_counts", None) or {}
    roster_positions = _roster_positions(slot_counts if isinstance(slot_counts, dict) else {})
    teams = list(getattr(raw_league, "teams", None) or [])
    parsed = parse_espn_league_key(league_key) or ("", 0)

    rosters: list[dict[str, Any]] = []
    users: list[dict[str, Any]] = []
    team_summaries: list[dict[str, Any]] = []
    for team in teams:
        roster_id = _safe_int(getattr(team, "team_id", 0), 0)
        owner_id = f"espn-team-{roster_id}"
        team_name = _safe_text(getattr(team, "team_name", "")) or f"Team {roster_id}"
        owner_name = _owner_display_name(team) or team_name
        roster_players = list(getattr(team, "roster", None) or [])
        players: list[str] = []
        starters: list[str] = []
        reserve: list[str] = []
        for player in roster_players:
            canonical, _method = adapter._canonicalize_player(player)
            if not canonical or canonical in players:
                continue
            players.append(canonical)
            slot = _safe_text(getattr(player, "lineupSlot", "")).upper()
            if slot == "IR":
                reserve.append(canonical)
            elif slot and slot not in _BENCH_LINEUP_SLOTS:
                starters.append(canonical)
        rosters.append(
            {
                "platform": ESPN_PLATFORM,
                "roster_id": roster_id,
                "owner_id": owner_id,
                "players": players,
                "starters": starters,
                "reserve": reserve,
                "taxi": [],
                "settings": {
                    "wins": _safe_int(getattr(team, "wins", 0)),
                    "losses": _safe_int(getattr(team, "losses", 0)),
                    "ties": _safe_int(getattr(team, "ties", 0)),
                    "fpts": int(_safe_float(getattr(team, "points_for", 0.0))),
                    "fpts_decimal": int(round((_safe_float(getattr(team, "points_for", 0.0)) % 1) * 100)),
                    "fpts_against": int(_safe_float(getattr(team, "points_against", 0.0))),
                    "fpts_against_decimal": int(
                        round((_safe_float(getattr(team, "points_against", 0.0)) % 1) * 100)
                    ),
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
        team_summaries.append(
            {
                "roster_id": str(roster_id),
                "team_name": team_name,
                "owner_name": owner_name,
                "player_count": len(roster_players),
                "matched_player_count": len(players),
            }
        )

    diagnostics = adapter.mapping_diagnostics()
    total = _safe_int(diagnostics.get("total_espn_players_seen"), 0)
    matched = _safe_int(diagnostics.get("canonical_matched_count"), 0)
    team_count = _safe_int(getattr(settings, "team_count", 0), 0) or len(teams)
    roster_size = sum(1 for pos in roster_positions if pos != "IR")
    league = {
        "platform": ESPN_PLATFORM,
        "league_id": league_key,
        "espn_league_id": parsed[0],
        "name": _safe_text(getattr(settings, "name", "")) or "ESPN league",
        "season": str(parsed[1] or _safe_text(getattr(raw_league, "year", ""))),
        "sport": "nfl",
        # Not "complete": FantasyDesk's Sleeper rollover check keys off that
        # status, and ESPN league ids do not change between seasons.
        "status": "in_season",
        "total_rosters": team_count,
        "settings": {
            "type": _league_type(settings, roster_size),
            "num_teams": team_count,
            "playoff_teams": _safe_int(getattr(settings, "playoff_team_count", 0), 0),
            "reserve_slots": _safe_int(slot_counts.get("IR"), 0) if isinstance(slot_counts, dict) else 0,
            "leg": _safe_int(getattr(raw_league, "current_week", 0), 0),
        },
        "scoring_settings": _scoring_settings(settings),
        "roster_positions": roster_positions,
    }
    unmatched_examples = [
        {key: _safe_text(item.get(key)) for key in ("name", "position", "team")}
        for item in (diagnostics.get("unmatched_examples") or [])
        if isinstance(item, dict)
    ]
    return {
        "league_key": league_key,
        "league": league,
        "rosters": rosters,
        "users": users,
        "teams": team_summaries,
        "diagnostics": {
            "teams_found": len(teams),
            "total_espn_players_seen": total,
            "canonical_matched_count": matched,
            "unmatched_count": _safe_int(diagnostics.get("unmatched_count"), 0),
            "ambiguous_count": _safe_int(diagnostics.get("ambiguous_count"), 0),
            "matched_rate": round(matched / total, 4) if total else 0.0,
            "unmatched_examples": unmatched_examples,
        },
        "loaded_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Loading (network) and the in-process snapshot cache
# ---------------------------------------------------------------------------


def _default_league_factory() -> Callable[..., Any]:
    from espn_api.football import League

    return League


def _default_players_frame() -> pd.DataFrame:
    from modules import rankings

    return rankings.load_players(PLAYERS_DB_PATH)


def _default_sleeper_players() -> dict[str, Any]:
    from modules import sleeper

    players = sleeper.get_players()
    return players if isinstance(players, dict) else {}


def _default_espn_crosswalk(sleeper_players: dict[str, Any]) -> dict[str, str]:
    from modules import espn_player_crosswalk

    return espn_player_crosswalk.load_espn_crosswalk(sleeper_players)


# Indirection points for tests: the real factory hits ESPN's API, the real
# frame reads data/players.db, the Sleeper dump reads data/sleeper_players.json
# and the crosswalk fetches DynastyProcess's public player id table.
league_factory_provider: Callable[[], Callable[..., Any]] = _default_league_factory
players_frame_provider: Callable[[], pd.DataFrame] = _default_players_frame
sleeper_players_provider: Callable[[], dict[str, Any]] = _default_sleeper_players
espn_crosswalk_provider: Callable[[dict[str, Any]], dict[str, str]] = _default_espn_crosswalk


def _classify_load_error(exc: Exception) -> ESPNLeagueError:
    name = type(exc).__name__
    if name == "ESPNAccessDenied":
        return ESPNLeagueError("private_league", ERROR_MESSAGES["private_league"])
    if name == "ESPNInvalidLeague":
        return ESPNLeagueError("league_not_found", ERROR_MESSAGES["league_not_found"])
    return ESPNLeagueError("espn_unavailable", ERROR_MESSAGES["espn_unavailable"])


def load_league_snapshot(league_key: str) -> dict[str, Any]:
    """Load a public ESPN league live and translate it. Raises ESPNLeagueError."""

    parsed = parse_espn_league_key(league_key)
    if not parsed:
        raise ESPNLeagueError("invalid_input", ERROR_MESSAGES["invalid_input"])
    espn_league_id, season = parsed
    try:
        factory = league_factory_provider()
        # Public leagues only: no espn_s2/swid is ever passed (see module
        # docstring for why private leagues are out of scope).
        raw_league = factory(league_id=int(espn_league_id), year=season)
    except Exception as exc:
        raise _classify_load_error(exc) from None
    try:
        df_players = players_frame_provider()
    except Exception:
        df_players = pd.DataFrame()
    try:
        sleeper_players = sleeper_players_provider() or {}
    except Exception:
        sleeper_players = {}
    try:
        espn_crosswalk = espn_crosswalk_provider(sleeper_players) or {}
    except Exception:
        espn_crosswalk = {}
    snapshot = build_snapshot(
        raw_league,
        league_key=league_key,
        df_players=df_players,
        sleeper_players=sleeper_players,
        espn_crosswalk=espn_crosswalk,
    )
    if not snapshot["rosters"]:
        raise ESPNLeagueError("no_teams", ERROR_MESSAGES["no_teams"])
    return snapshot


_SNAPSHOT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SNAPSHOT_LOCKS: dict[str, threading.Lock] = {}
_SNAPSHOT_GUARD = threading.Lock()


def get_league_snapshot(league_key: str, *, refresh: bool = False) -> dict[str, Any] | None:
    """Cached snapshot, or None when the league can't be loaded.

    One load per key per ESPN_SNAPSHOT_TTL_SECONDS per process, single-flight
    so a page firing several league requests at once pays one ESPN call."""

    if not parse_espn_league_key(league_key):
        return None
    now = time.time()
    cached = _SNAPSHOT_CACHE.get(league_key)
    if cached and not refresh and now - cached[0] < ESPN_SNAPSHOT_TTL_SECONDS:
        return cached[1]
    with _SNAPSHOT_GUARD:
        lock = _SNAPSHOT_LOCKS.setdefault(league_key, threading.Lock())
    with lock:
        cached = _SNAPSHOT_CACHE.get(league_key)
        if cached and not refresh and time.time() - cached[0] < ESPN_SNAPSHOT_TTL_SECONDS:
            return cached[1]
        try:
            snapshot = load_league_snapshot(league_key)
        except ESPNLeagueError:
            return None
        _SNAPSHOT_CACHE[league_key] = (time.time(), snapshot)
        return snapshot


def store_snapshot(league_key: str, snapshot: dict[str, Any]) -> None:
    """Seed the cache with a snapshot the caller just loaded (preview/save)."""

    _SNAPSHOT_CACHE[league_key] = (time.time(), snapshot)


def clear_snapshot_cache() -> None:
    _SNAPSHOT_CACHE.clear()


def league_payload(league_key: str) -> dict[str, Any]:
    snapshot = get_league_snapshot(league_key)
    return dict(snapshot["league"]) if snapshot else {}


def rosters_payload(league_key: str) -> list[dict[str, Any]]:
    snapshot = get_league_snapshot(league_key)
    return [dict(roster) for roster in snapshot["rosters"]] if snapshot else []


def users_payload(league_key: str) -> list[dict[str, Any]]:
    snapshot = get_league_snapshot(league_key)
    return [dict(user) for user in snapshot["users"]] if snapshot else []


def mapping_blocks_import(snapshot: dict[str, Any]) -> bool:
    diagnostics = snapshot.get("diagnostics") or {}
    return _safe_float(diagnostics.get("matched_rate")) < ESPN_MAPPING_BLOCK_THRESHOLD


def preview_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    league = snapshot["league"]
    blocked = mapping_blocks_import(snapshot)
    return {
        "ok": not blocked,
        "reason": "mapping_too_low" if blocked else "",
        "message": ERROR_MESSAGES["mapping_too_low"] if blocked else "",
        "league": {
            "league_key": snapshot["league_key"],
            "espn_league_id": league.get("espn_league_id") or "",
            "season": league.get("season") or "",
            "name": league.get("name") or "",
            "team_count": league.get("total_rosters") or len(snapshot["rosters"]),
        },
        "teams": list(snapshot["teams"]),
        "diagnostics": dict(snapshot["diagnostics"]),
        "features": [dict(item) for item in ESPN_FEATURE_SUPPORT],
    }
