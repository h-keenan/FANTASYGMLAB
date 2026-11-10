"""Frozen, JSON-round-trippable inputs and the user's strategy.

A ``LeagueSnapshot`` is everything the engine needs, copied once at world
creation. It never holds a live handle to real data, so a world replays
identically after real values refresh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

STRICT_SLOTS = ("QB", "RB", "WR", "TE", "K")
FLEX_SLOTS = {
    "REC_FLEX": frozenset({"WR", "TE"}),
    "FLEX": frozenset({"RB", "WR", "TE"}),
    "SUPER_FLEX": frozenset({"QB", "RB", "WR", "TE"}),
}
# Fill the most restrictive flex first so a super-flex never steals a player a
# narrower slot needs.
FLEX_ORDER = ("REC_FLEX", "FLEX", "SUPER_FLEX")
POSITIONS = ("QB", "RB", "WR", "TE", "K")
POSTURES = ("win_now", "balanced", "rebuild")


class SimInputsError(Exception):
    """The real data needed to build a snapshot is not available. ``code`` is a
    stable reason string the API passes through."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class SimPlayer:
    pid: str
    name: str
    pos: str
    nfl_team: str
    age: float
    market: float  # dynasty market value, normalized 0-100
    mean: float  # projected points per game in this league's scoring
    sd: float
    injury_weeks: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid, "name": self.name, "pos": self.pos, "nfl_team": self.nfl_team,
            "age": self.age, "market": self.market, "mean": self.mean, "sd": self.sd,
            "injury_weeks": self.injury_weeks,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SimPlayer":
        return cls(
            pid=str(raw["pid"]), name=str(raw.get("name") or raw["pid"]), pos=str(raw["pos"]),
            nfl_team=str(raw.get("nfl_team") or ""), age=float(raw.get("age") or 26.0),
            market=float(raw.get("market") or 0.0), mean=float(raw.get("mean") or 0.0),
            sd=float(raw.get("sd") or 0.0), injury_weeks=int(raw.get("injury_weeks") or 0),
        )


@dataclass(frozen=True)
class SimTeam:
    tid: str
    name: str
    owner: str
    is_user: bool
    roster: tuple[str, ...]
    wins: float = 0.0
    losses: float = 0.0
    ties: float = 0.0
    pf: float = 0.0
    pa: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tid": self.tid, "name": self.name, "owner": self.owner, "is_user": self.is_user,
            "roster": list(self.roster), "wins": self.wins, "losses": self.losses,
            "ties": self.ties, "pf": self.pf, "pa": self.pa,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SimTeam":
        return cls(
            tid=str(raw["tid"]), name=str(raw.get("name") or raw["tid"]),
            owner=str(raw.get("owner") or ""), is_user=bool(raw.get("is_user")),
            roster=tuple(str(p) for p in raw.get("roster") or ()),
            wins=float(raw.get("wins") or 0), losses=float(raw.get("losses") or 0),
            ties=float(raw.get("ties") or 0), pf=float(raw.get("pf") or 0),
            pa=float(raw.get("pa") or 0),
        )


@dataclass(frozen=True)
class LeagueSettings:
    slots: tuple[str, ...]  # starting lineup slots, e.g. QB RB RB WR WR TE FLEX
    start_week: int  # first week to simulate
    regular_season_end: int  # last regular-season week
    playoff_teams: int
    trade_deadline_week: int
    league_name: str = ""
    season: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slots": list(self.slots), "start_week": self.start_week,
            "regular_season_end": self.regular_season_end, "playoff_teams": self.playoff_teams,
            "trade_deadline_week": self.trade_deadline_week, "league_name": self.league_name,
            "season": self.season,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LeagueSettings":
        return cls(
            slots=tuple(str(s) for s in raw["slots"]), start_week=int(raw["start_week"]),
            regular_season_end=int(raw["regular_season_end"]),
            playoff_teams=int(raw["playoff_teams"]),
            trade_deadline_week=int(raw["trade_deadline_week"]),
            league_name=str(raw.get("league_name") or ""), season=str(raw.get("season") or ""),
        )


@dataclass(frozen=True)
class LeagueSnapshot:
    league_id: str
    settings: LeagueSettings
    teams: tuple[SimTeam, ...]
    players: Mapping[str, SimPlayer]
    free_agents: tuple[str, ...]
    # schedule[i] is week (start_week + i): tuple of (tid, tid) pairs.
    schedule: tuple[tuple[tuple[str, str], ...], ...]
    mode: str = "remaining"
    # Honest caveats about how this snapshot approximates the real league.
    notes: tuple[str, ...] = ()

    @property
    def user_team(self) -> SimTeam:
        for team in self.teams:
            if team.is_user:
                return team
        raise ValueError("snapshot has no user team")

    def to_dict(self) -> dict[str, Any]:
        return {
            "league_id": self.league_id, "mode": self.mode,
            "settings": self.settings.to_dict(),
            "teams": [t.to_dict() for t in self.teams],
            "players": [self.players[k].to_dict() for k in sorted(self.players)],
            "free_agents": list(self.free_agents),
            "schedule": [[list(pair) for pair in week] for week in self.schedule],
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LeagueSnapshot":
        players = {str(p["pid"]): SimPlayer.from_dict(p) for p in raw["players"]}
        snapshot = cls(
            league_id=str(raw["league_id"]), mode=str(raw.get("mode") or "remaining"),
            settings=LeagueSettings.from_dict(raw["settings"]),
            teams=tuple(SimTeam.from_dict(t) for t in raw["teams"]), players=players,
            free_agents=tuple(str(p) for p in raw.get("free_agents") or ()),
            schedule=tuple(tuple((str(a), str(b)) for a, b in week) for week in raw["schedule"]),
            notes=tuple(str(n) for n in raw.get("notes") or ()),
        )
        snapshot.validate()
        return snapshot

    def validate(self) -> None:
        if len(self.teams) < 2:
            raise ValueError("a league needs at least two teams")
        if sum(1 for t in self.teams if t.is_user) != 1:
            raise ValueError("exactly one team must be the user's")
        tids = {t.tid for t in self.teams}
        for week in self.schedule:
            for a, b in week:
                if a not in tids or b not in tids:
                    raise ValueError("schedule references an unknown team")
        for team in self.teams:
            for pid in team.roster:
                if pid not in self.players:
                    raise ValueError(f"roster player {pid} missing from snapshot")
        for pid in self.free_agents:
            if pid not in self.players:
                raise ValueError(f"free agent {pid} missing from snapshot")


@dataclass(frozen=True)
class Strategy:
    posture: str = "balanced"
    trade_aggressiveness: float = 0.5
    waiver_aggressiveness: float = 0.5
    lineup_auto_set: bool = True
    protected_player_ids: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "Strategy":
        raw = dict(raw or {})
        posture = str(raw.get("posture", "balanced"))
        if posture not in POSTURES:
            raise ValueError("posture must be one of: " + ", ".join(POSTURES))

        def unit(key: str, default: float) -> float:
            value = raw.get(key, default)
            if isinstance(value, bool):
                raise ValueError(f"{key} must be a number between 0 and 1")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be a number between 0 and 1") from None
            if not 0.0 <= number <= 1.0:
                raise ValueError(f"{key} must be between 0 and 1")
            return number

        auto = raw.get("lineup_auto_set", True)
        if not isinstance(auto, bool):
            raise ValueError("lineup_auto_set must be a boolean")
        protected = raw.get("protected_player_ids") or ()
        if not isinstance(protected, (list, tuple)) or len(protected) > 50:
            raise ValueError("protected_player_ids must be a list of at most 50 ids")
        return cls(
            posture=posture,
            trade_aggressiveness=unit("trade_aggressiveness", 0.5),
            waiver_aggressiveness=unit("waiver_aggressiveness", 0.5),
            lineup_auto_set=auto,
            protected_player_ids=tuple(sorted({str(p) for p in protected})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "posture": self.posture, "trade_aggressiveness": self.trade_aggressiveness,
            "waiver_aggressiveness": self.waiver_aggressiveness,
            "lineup_auto_set": self.lineup_auto_set,
            "protected_player_ids": list(self.protected_player_ids),
        }
