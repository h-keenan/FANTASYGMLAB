from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from modules.player_identity import (
    canonicalize_player_id,
    ensure_identity_columns,
    normalize_player_id,
    normalize_player_name,
    resolve_identity_candidates,
)

# Sleeper's team defenses use the team abbreviation as the player id.
SLEEPER_DEF_IDS = frozenset(
    {
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
        "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE",
        "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
    }
)
# ESPN team abbreviations that differ from Sleeper's.
ESPN_TEAM_ALIASES = {"WSH": "WAS", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR", "LA": "LAR"}
_DST_POSITIONS = {"D/ST", "DST", "DEF"}


def normalize_espn_team(team: Any) -> str:
    text = str(team or "").strip().upper()
    return ESPN_TEAM_ALIASES.get(text, text)


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip().casefold()
    if text in {"1", "1.0", "true", "yes"}:
        return True
    if text in {"0", "0.0", "false", "no"}:
        return False
    return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


class ESPNAdapterUnavailable(RuntimeError):
    """Raised when the optional ESPN dependency is not installed."""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return number


def _read(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj.get(name)
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _call_or_value(value: Any) -> Any:
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value


def _position_from_player(player: Any) -> str:
    position = _read(player, "position", "pos", "defaultPosition", default="")
    if isinstance(position, dict):
        position = position.get("abbreviation") or position.get("name") or ""
    return str(position or "").upper()


def _team_from_player(player: Any) -> str:
    team = _read(player, "proTeam", "pro_team", "team", "proTeamAbbreviation", default="")
    if isinstance(team, dict):
        team = team.get("abbreviation") or team.get("location") or team.get("name") or ""
    return str(team or "").upper()


@dataclass
class ESPNMappingDiagnostics:
    total_players_seen: int = 0
    canonical_matched_count: int = 0
    unmatched_count: int = 0
    ambiguous_count: int = 0
    unmatched_examples: list[dict[str, str]] = field(default_factory=list)
    ambiguous_examples: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_espn_players_seen": self.total_players_seen,
            "canonical_matched_count": self.canonical_matched_count,
            "unmatched_count": self.unmatched_count,
            "ambiguous_count": self.ambiguous_count,
            "unmatched_examples": list(self.unmatched_examples[:10]),
            "ambiguous_examples": list(self.ambiguous_examples[:10]),
        }


class ESPNPlatformAdapter:
    platform = "espn"

    def __init__(
        self,
        identity_map: dict[str, dict[str, str]] | None = None,
        df_players: pd.DataFrame | None = None,
        league_factory: Callable[..., Any] | None = None,
        espn_crosswalk: dict[str, str] | None = None,
        sleeper_players: dict[str, Any] | None = None,
    ):
        self.identity_map = identity_map
        self.df_players = ensure_identity_columns(df_players)
        self.league_factory = league_factory
        # ESPN player id -> Sleeper (canonical) player id. A player table
        # that carries an espn_id column contributes to it too.
        self.espn_crosswalk = dict(espn_crosswalk or {})
        if "espn_id" in self.df_players.columns:
            for espn_id, canonical in zip(self.df_players["espn_id"], self.df_players["canonical_player_id"]):
                espn_key, canonical_key = normalize_player_id(espn_id), normalize_player_id(canonical)
                if espn_key and canonical_key:
                    self.espn_crosswalk.setdefault(espn_key, canonical_key)
        # Sleeper's full players/nfl dump: a superset of the valued player
        # table, used to sanity check crosswalk hits and as the last name
        # matching pool. A player missing from the valued table is still the
        # same Sleeper player, exactly as he would be on a Sleeper roster.
        self.sleeper_players = sleeper_players or {}
        self._table_name_index: dict[str, list[dict[str, Any]]] | None = None
        self._sleeper_name_index: dict[str, list[dict[str, Any]]] | None = None
        self.diagnostics = ESPNMappingDiagnostics()
        self.last_error = ""

    def mapping_diagnostics(self) -> dict[str, Any]:
        return self.diagnostics.as_dict()

    def _record_unmatched(self, raw_id: Any, name: Any, position: Any, team: Any, reason: str) -> None:
        self.diagnostics.unmatched_count += 1
        if len(self.diagnostics.unmatched_examples) < 10:
            self.diagnostics.unmatched_examples.append(
                {
                    "espn_id": normalize_player_id(raw_id),
                    "name": str(name or ""),
                    "position": str(position or ""),
                    "team": str(team or ""),
                    "reason": reason,
                }
            )

    def _record_ambiguous(self, raw_id: Any, name: Any, position: Any, team: Any) -> None:
        self.diagnostics.ambiguous_count += 1
        if len(self.diagnostics.ambiguous_examples) < 10:
            self.diagnostics.ambiguous_examples.append(
                {
                    "espn_id": normalize_player_id(raw_id),
                    "name": str(name or ""),
                    "position": str(position or ""),
                    "team": str(team or ""),
                    "reason": "Multiple possible canonical player matches.",
                }
            )

    def canonicalize_player_id(self, raw_id: Any) -> str | None:
        return canonicalize_player_id(self.platform, raw_id, self.identity_map)

    def _table_candidates(self, name_key: str) -> list[dict[str, Any]]:
        if self._table_name_index is None:
            index: dict[str, list[dict[str, Any]]] = {}
            df = self.df_players
            if not df.empty and "name" in df.columns:
                blank = pd.Series([None] * len(df), index=df.index)
                for name, canonical, position, team, active in zip(
                    df["name"],
                    df["canonical_player_id"],
                    df["position"] if "position" in df.columns else blank,
                    df["team"] if "team" in df.columns else blank,
                    df["active"] if "active" in df.columns else blank,
                ):
                    key = normalize_player_name(name)
                    if key:
                        index.setdefault(key, []).append(
                            {
                                "id": normalize_player_id(canonical),
                                "position": _clean_text(position).upper(),
                                "team": normalize_espn_team(_clean_text(team)),
                                "active": _optional_bool(active),
                            }
                        )
            self._table_name_index = index
        return self._table_name_index.get(name_key, [])

    def _sleeper_candidates(self, name_key: str) -> list[dict[str, Any]]:
        if self._sleeper_name_index is None:
            index: dict[str, list[dict[str, Any]]] = {}
            for sleeper_id, record in self.sleeper_players.items():
                if not isinstance(record, dict) or _clean_text(record.get("position")).upper() == "DEF":
                    continue
                full_name = record.get("full_name") or " ".join(
                    _clean_text(part) for part in (record.get("first_name"), record.get("last_name")) if part
                )
                key = normalize_player_name(full_name)
                if key:
                    index.setdefault(key, []).append(
                        {
                            "id": normalize_player_id(record.get("player_id") or sleeper_id),
                            "position": self._sleeper_positions(record),
                            "team": _clean_text(record.get("team")).upper(),
                            "active": _optional_bool(record.get("active")),
                        }
                    )
            self._sleeper_name_index = index
        return self._sleeper_name_index.get(name_key, [])

    @staticmethod
    def _sleeper_positions(record: dict[str, Any]) -> set[str]:
        positions = {_clean_text(record.get("position")).upper()}
        for item in record.get("fantasy_positions") or []:
            positions.add(_clean_text(item).upper())
        positions.discard("")
        return positions

    def _crosswalk_match(self, raw_id: Any, name: Any, position: str) -> str | None:
        canonical = self.espn_crosswalk.get(normalize_player_id(raw_id))
        if not canonical:
            return None
        record = self.sleeper_players.get(canonical)
        if not isinstance(record, dict):
            return canonical
        # Guard against a bad crosswalk row: the Sleeper record must agree
        # with ESPN on either position or name.
        if position and position in self._sleeper_positions(record):
            return canonical
        name_key = normalize_player_name(name)
        if name_key and name_key == normalize_player_name(record.get("full_name")):
            return canonical
        return None

    def _canonicalize_player(self, player: Any) -> tuple[str | None, str]:
        raw_id = _read(player, "playerId", "player_id", "id", default="")
        name = _read(player, "name", "fullName", "playerName", default="")
        position = _position_from_player(player)
        team = normalize_espn_team(_team_from_player(player))
        self.diagnostics.total_players_seen += 1

        canonical_id = self.canonicalize_player_id(raw_id)
        if canonical_id:
            self.diagnostics.canonical_matched_count += 1
            return canonical_id, "espn_id"

        # ESPN team defenses (negative ids, "Seahawks D/ST") are Sleeper's
        # DEF entries, whose player id is the team abbreviation.
        if position in _DST_POSITIONS:
            if team in SLEEPER_DEF_IDS:
                self.diagnostics.canonical_matched_count += 1
                return team, "dst_team"
            self._record_unmatched(raw_id, name, position, team, "Unknown NFL team for this team defense.")
            return None, "unmatched"

        # Exact ESPN id -> Sleeper id crosswalk first, names only after.
        canonical_id = self._crosswalk_match(raw_id, name, position)
        if canonical_id:
            self.diagnostics.canonical_matched_count += 1
            return canonical_id, "espn_id_crosswalk"

        if self.df_players.empty and not self.sleeper_players:
            self._record_unmatched(raw_id, name, position, team, "No player table was provided for canonical matching.")
            return None, "unmatched"
        name_key = normalize_player_name(name)
        if not name_key:
            self._record_unmatched(raw_id, name, position, team, "ESPN sent no player name.")
            return None, "unmatched"

        # The valued player table first, then Sleeper's full dump. Same-name
        # players are narrowed by position, then NFL team, then active status.
        ambiguous = False
        for method, candidates in (
            ("name_position_team", self._table_candidates(name_key)),
            ("sleeper_name_position_team", self._sleeper_candidates(name_key)),
        ):
            canonical_id, is_ambiguous = resolve_identity_candidates(candidates, position=position, team=team)
            if canonical_id:
                self.diagnostics.canonical_matched_count += 1
                return canonical_id, method
            ambiguous = ambiguous or is_ambiguous

        if ambiguous:
            self._record_ambiguous(raw_id, name, position, team)
            return None, "ambiguous"
        self._record_unmatched(raw_id, name, position, team, "No unique high-confidence player match.")
        return None, "unmatched"

    def _league(
        self,
        league_id: str,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> Any:
        if self.league_factory is None:
            try:
                from espn_api.football import League
            except Exception as exc:  # pragma: no cover - exercised through dependency-missing tests
                raise ESPNAdapterUnavailable(
                    "ESPN support requires the optional espn_api package. Install requirements.txt first."
                ) from exc
            self.league_factory = League
        year = _safe_int(season, 0)
        if year <= 0:
            raise ValueError("ESPN league import requires a season/year.")
        kwargs: dict[str, Any] = {"league_id": _safe_int(league_id), "year": year}
        if swid:
            kwargs["swid"] = swid
        if espn_s2:
            kwargs["espn_s2"] = espn_s2
        try:
            return self.league_factory(**kwargs)
        except Exception as exc:
            self.last_error = "ESPN league could not be loaded. Private leagues require valid SWID and ESPN_S2 cookies."
            raise RuntimeError(self.last_error) from exc

    def get_user_leagues(self, username: str) -> list[dict[str, Any]]:
        self.last_error = "ESPN does not support username-based league discovery in this MVP. Enter league ID and season."
        return []

    def get_league(
        self,
        league_id: str,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> dict[str, Any]:
        return self.normalize_league_settings(self._league(league_id, season, swid, espn_s2))

    def get_rosters(
        self,
        league_id: str,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> list[dict[str, Any]]:
        league = self._league(league_id, season, swid, espn_s2)
        return [self.normalize_roster(team) for team in (_read(league, "teams", default=[]) or [])]

    def get_users(
        self,
        league_id: str,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> list[dict[str, Any]]:
        league = self._league(league_id, season, swid, espn_s2)
        users = []
        for team in _read(league, "teams", default=[]) or []:
            team_id = str(_read(team, "team_id", "teamId", "id", default=""))
            owner = _read(team, "owner", "owners", default="")
            if isinstance(owner, list):
                owner = ", ".join(str(item) for item in owner if item)
            users.append(
                {
                    "platform": self.platform,
                    "user_id": team_id,
                    "display_name": str(owner or _read(team, "team_name", "teamName", default=f"Team {team_id}")),
                    "team_id": team_id,
                    "raw": team,
                }
            )
        return users

    def get_roster_player_ids(
        self,
        league_id: str,
        roster_id: int,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> list[str]:
        for roster in self.get_rosters(league_id, season, swid, espn_s2):
            if str(roster.get("roster_id")) == str(roster_id):
                return list(roster.get("players") or [])
        return []

    def get_transactions(
        self,
        league_id: str,
        round_num: int,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> list[dict[str, Any]]:
        league = self._league(league_id, season, swid, espn_s2)
        activity = _call_or_value(_read(league, "recent_activity", default=None))
        if not activity:
            return []
        return [
            {
                "platform": self.platform,
                "type": str(_read(item, "type", "msg_type", default="activity")),
                "raw": item,
            }
            for item in activity
        ]

    def get_traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        return []

    def get_league_drafts(
        self,
        league_id: str,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> list[dict[str, Any]]:
        league = self._league(league_id, season, swid, espn_s2)
        draft = _read(league, "draft", default=[]) or []
        if not draft:
            return []
        year = _safe_int(season, _safe_int(_read(league, "year", default=0)))
        return [
            {
                "platform": self.platform,
                "draft_id": f"espn:{league_id}:{year}:draft",
                "league_id": str(league_id),
                "season": str(year or ""),
                "status": "complete",
                "type": "draft",
                "raw": draft,
            }
        ]

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        return {"platform": self.platform, "draft_id": str(draft_id or ""), "status": "unknown"}

    def get_draft_picks(
        self,
        draft_id: str,
        league_id: str | None = None,
        season: int | str | None = None,
        swid: str | None = None,
        espn_s2: str | None = None,
    ) -> list[dict[str, Any]]:
        if not league_id:
            return []
        league = self._league(league_id, season, swid, espn_s2)
        return [self.normalize_draft_pick(pick) for pick in (_read(league, "draft", default=[]) or [])]

    def normalize_league_settings(self, raw_league: Any | None) -> dict[str, Any]:
        settings = _read(raw_league, "settings", default={}) or {}
        return {
            "platform": self.platform,
            "league_id": str(_read(raw_league, "league_id", "leagueId", default="")),
            "name": str(_read(settings, "name", default=_read(raw_league, "name", default="")) or ""),
            "season": _read(raw_league, "year", "season", default=None),
            "settings": {
                "team_count": _read(settings, "team_count", "teamCount", default=None),
                "reg_season_count": _read(settings, "reg_season_count", default=None),
            },
            "scoring_settings": _read(settings, "scoring_settings", "scoringSettings", default={}) or {},
            "roster_positions": _read(settings, "roster_positions", "rosterPositions", default=[]) or [],
            "raw": raw_league,
        }

    def normalize_roster(self, raw_roster: Any | None) -> dict[str, Any]:
        team_id = _safe_int(_read(raw_roster, "team_id", "teamId", "id", default=0), 0)
        roster = _read(raw_roster, "roster", "players", default=[]) or []
        platform_player_ids: list[str] = []
        canonical_players: list[str] = []
        mapping_methods: dict[str, str] = {}
        unmatched_players: list[dict[str, str]] = []
        for player in roster:
            raw_id = normalize_player_id(_read(player, "playerId", "player_id", "id", default=""))
            if raw_id:
                platform_player_ids.append(raw_id)
            canonical_id, method = self._canonicalize_player(player)
            if canonical_id:
                canonical_players.append(canonical_id)
                mapping_methods[raw_id or canonical_id] = method
            else:
                unmatched_players.append(
                    {
                        "espn_id": raw_id,
                        "name": str(_read(player, "name", "fullName", default="")),
                        "position": _position_from_player(player),
                        "team": _team_from_player(player),
                    }
                )
        return {
            "platform": self.platform,
            "roster_id": team_id,
            "owner_id": str(_read(raw_roster, "owner", "owners", default=team_id) or team_id),
            "team_name": str(_read(raw_roster, "team_name", "teamName", default=f"Team {team_id}") or f"Team {team_id}"),
            "players": list(dict.fromkeys(canonical_players)),
            "platform_player_ids": list(dict.fromkeys(platform_player_ids)),
            "platform_player_id_map": mapping_methods,
            "unmatched_players": unmatched_players,
            "raw": raw_roster,
        }

    def normalize_draft_pick(self, raw_pick: Any | None) -> dict[str, Any]:
        player = _read(raw_pick, "player", default=raw_pick)
        raw_id = _read(raw_pick, "playerId", "player_id", default=_read(player, "playerId", "player_id", "id", default=""))
        canonical_id, method = self._canonicalize_player(player)
        return {
            "platform": self.platform,
            "pick_no": _safe_int(_read(raw_pick, "pick", "pick_no", "overallPickNumber", default=0), 0),
            "round": _safe_int(_read(raw_pick, "round_num", "round", default=0), 0),
            "roster_id": _safe_int(_read(_read(raw_pick, "team", default=None), "team_id", "teamId", default=0), 0),
            "platform_player_id": normalize_player_id(raw_id),
            "player_id": canonical_id or "",
            "mapping_method": method,
            "metadata": {
                "first_name": "",
                "last_name": "",
                "full_name": str(_read(raw_pick, "playerName", default=_read(player, "name", "fullName", default="")) or ""),
                "position": _position_from_player(player),
                "team": _team_from_player(player),
            },
            "raw": raw_pick,
        }


def get_espn_adapter(
    identity_map: dict[str, dict[str, str]] | None = None,
    df_players: pd.DataFrame | None = None,
    league_factory: Callable[..., Any] | None = None,
    espn_crosswalk: dict[str, str] | None = None,
    sleeper_players: dict[str, Any] | None = None,
) -> ESPNPlatformAdapter:
    return ESPNPlatformAdapter(
        identity_map=identity_map,
        df_players=df_players,
        league_factory=league_factory,
        espn_crosswalk=espn_crosswalk,
        sleeper_players=sleeper_players,
    )
