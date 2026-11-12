"""Settings, frozen snapshot and constants for the interactive GM game.

Pure data: stdlib only (plus ``modules.sim.types``). A ``GameSnapshot`` is
everything a game needs, copied once at creation and never refreshed, so a save
replays identically after real values refresh.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from modules.sim.types import FLEX_SLOTS, POSITIONS, STRICT_SLOTS

GAME_ENGINE_VERSION = "game-1.0.0"
DIFFICULTIES = ("easy", "normal", "hard")
TEAM_COUNTS = (8, 10, 12)
SCORING_NAMES = ("ppr", "half", "std")
DEFAULT_SLOTS = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K")
PREVIEW_PAYWALL_WEEK = 4  # Free can play weeks 1-3; week 4 is paywalled
MAX_GAMES_PRO = 3
MAX_GAMES_FREE = 1

# Sleeper-style scoring_settings (what the projection estimator and the player
# model understand). Kickers: 3 pts through 39 yds, 4 for 40-49, 5 for 50+.
_BASE_SCORING = {
    "pass_yd": 0.04, "pass_td": 4.0, "pass_int": -1.0, "pass_2pt": 2.0,
    "rush_yd": 0.1, "rush_td": 6.0, "rush_2pt": 2.0,
    "rec_yd": 0.1, "rec_td": 6.0, "rec_2pt": 2.0,
    "fum_lost": -2.0,
    "xpm": 1.0, "fgm_0_19": 3.0, "fgm_20_29": 3.0, "fgm_30_39": 3.0,
    "fgm_40_49": 4.0, "fgm_50p": 5.0,
}
SCORING_PRESETS: dict[str, dict[str, float]] = {
    "ppr": {**_BASE_SCORING, "rec": 1.0},
    "half": {**_BASE_SCORING, "rec": 0.5},
    "std": {**_BASE_SCORING, "rec": 0.0},
}

# Fantasy-relevant pool size per position (top by market value). The whole NFL
# player pool for fantasy purposes, trimmed of players nobody would roster.
POOL_CAPS = {"QB": 64, "RB": 160, "WR": 220, "TE": 90, "K": 36}


class GameError(Exception):
    """A rule violation. ``code`` is a stable reason string the API passes
    through; ``detail`` carries extra context for the response body."""

    def __init__(self, code: str, message: str = "", **detail: Any) -> None:
        super().__init__(message or code)
        self.code = code
        self.detail = detail


def slot_positions(slot: str) -> frozenset[str]:
    return FLEX_SLOTS.get(slot) or frozenset({slot})


def playoff_rounds(playoff_teams: int) -> int:
    size = 1
    while size < max(2, playoff_teams):
        size *= 2
    return int(math.log2(size))


@dataclass(frozen=True)
class GameSettings:
    teams: int = 12
    scoring: str = "ppr"
    difficulty: str = "normal"
    user_slot: int = 1  # draft slot (1 = first pick of round 1)
    auto_lineup: bool = False
    slots: tuple[str, ...] = DEFAULT_SLOTS
    rounds: int = 14
    roster_limit: int = 16
    regular_weeks: int = 14
    playoff_teams: int = 6
    trade_deadline_week: int = 10

    @property
    def playoff_weeks(self) -> int:
        return playoff_rounds(self.playoff_teams)

    @property
    def total_weeks(self) -> int:
        return self.regular_weeks + self.playoff_weeks

    @property
    def scoring_settings(self) -> dict[str, float]:
        return dict(SCORING_PRESETS[self.scoring])

    @classmethod
    def parse(cls, raw: Mapping[str, Any] | None, *, user_slot_default: int = 1) -> "GameSettings":
        """Validate client options (everything optional). Raises ValueError with
        a client-safe message."""

        raw = dict(raw or {})
        teams = raw.get("teams", 12)
        if isinstance(teams, bool) or not isinstance(teams, int) or teams not in TEAM_COUNTS:
            raise ValueError("teams must be one of: " + ", ".join(str(t) for t in TEAM_COUNTS))
        scoring = raw.get("scoring", "ppr")
        if scoring not in SCORING_NAMES:
            raise ValueError("scoring must be one of: " + ", ".join(SCORING_NAMES))
        difficulty = raw.get("difficulty", "normal")
        if difficulty not in DIFFICULTIES:
            raise ValueError("difficulty must be one of: " + ", ".join(DIFFICULTIES))
        slot = raw.get("user_slot")
        if slot is None:
            slot = user_slot_default
        if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot <= teams:
            raise ValueError(f"user_slot must be between 1 and {teams}")
        auto = raw.get("auto_lineup", False)
        if not isinstance(auto, bool):
            raise ValueError("auto_lineup must be a boolean")
        return cls(
            teams=teams, scoring=scoring, difficulty=difficulty, user_slot=slot, auto_lineup=auto,
            playoff_teams=4 if teams <= 8 else 6,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "teams": self.teams, "scoring": self.scoring, "difficulty": self.difficulty,
            "user_slot": self.user_slot, "auto_lineup": self.auto_lineup, "slots": list(self.slots),
            "rounds": self.rounds, "roster_limit": self.roster_limit,
            "regular_weeks": self.regular_weeks, "playoff_teams": self.playoff_teams,
            "playoff_weeks": self.playoff_weeks, "trade_deadline_week": self.trade_deadline_week,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GameSettings":
        return cls(
            teams=int(raw["teams"]), scoring=str(raw["scoring"]), difficulty=str(raw["difficulty"]),
            user_slot=int(raw["user_slot"]), auto_lineup=bool(raw.get("auto_lineup")),
            slots=tuple(str(s) for s in raw["slots"]), rounds=int(raw["rounds"]),
            roster_limit=int(raw["roster_limit"]), regular_weeks=int(raw["regular_weeks"]),
            playoff_teams=int(raw["playoff_teams"]), trade_deadline_week=int(raw["trade_deadline_week"]),
        )


@dataclass(frozen=True)
class GamePlayer:
    pid: str
    name: str
    pos: str
    nfl_team: str
    age: float
    market: float  # 0-100 dynasty market value (drives AI trade valuation)
    mean: float  # projected points per game in this game's scoring
    sd: float
    adp: float  # draft rank 1..N from the frozen draft value
    value: float  # 0-100 one-season draft value (VORP blended with market)
    injury_weeks: int = 0  # weeks out at the start of the season
    # Extra numeric context handed to the player model (usage, last-season
    # production). Whatever the adapter could read; every key optional.
    extra: Mapping[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid, "name": self.name, "pos": self.pos, "nfl_team": self.nfl_team,
            "age": self.age, "market": self.market, "mean": self.mean, "sd": self.sd,
            "adp": self.adp, "value": self.value, "injury_weeks": self.injury_weeks,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GamePlayer":
        return cls(
            pid=str(raw["pid"]), name=str(raw.get("name") or raw["pid"]), pos=str(raw["pos"]),
            nfl_team=str(raw.get("nfl_team") or ""), age=float(raw.get("age") or 26.0),
            market=float(raw.get("market") or 0.0), mean=float(raw.get("mean") or 0.0),
            sd=float(raw.get("sd") or 0.0), adp=float(raw.get("adp") or 999.0),
            value=float(raw.get("value") or 0.0), injury_weeks=int(raw.get("injury_weeks") or 0),
            extra={str(k): float(v) for k, v in (raw.get("extra") or {}).items()},
        )

    def model_mapping(self) -> dict[str, Any]:
        """What the player model sees: identity, projection and context. Never
        anything about this game's other state."""

        return {
            "player_id": self.pid, "id": self.pid, "name": self.name, "position": self.pos,
            "pos": self.pos, "team": self.nfl_team, "age": self.age, "mean": self.mean,
            "sd": self.sd, "ppg": self.mean, "market": self.market, **dict(self.extra),
        }


@dataclass(frozen=True)
class GameTeam:
    tid: str
    name: str
    owner: str
    is_user: bool
    persona_id: str  # "you" for the user's team
    draft_slot: int
    coin: int  # fixed tiebreak of last resort (lower wins)
    horizon: float = 0.55
    pos_bias: Mapping[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tid": self.tid, "name": self.name, "owner": self.owner, "is_user": self.is_user,
            "persona_id": self.persona_id, "draft_slot": self.draft_slot, "coin": self.coin,
            "horizon": self.horizon, "pos_bias": dict(self.pos_bias),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GameTeam":
        return cls(
            tid=str(raw["tid"]), name=str(raw["name"]), owner=str(raw.get("owner") or ""),
            is_user=bool(raw.get("is_user")), persona_id=str(raw["persona_id"]),
            draft_slot=int(raw["draft_slot"]), coin=int(raw["coin"]),
            horizon=float(raw.get("horizon", 0.55)),
            pos_bias={str(k): float(v) for k, v in (raw.get("pos_bias") or {}).items()},
        )


@dataclass(frozen=True)
class GameSnapshot:
    settings: GameSettings
    teams: tuple[GameTeam, ...]
    players: Mapping[str, GamePlayer]
    bye_weeks: Mapping[str, int]  # NFL team -> bye week (regular season)
    schedule: tuple[tuple[tuple[str, str], ...], ...]  # [week-1] -> ((home, away), ...)
    scoring_model: str = ""
    notes: tuple[str, ...] = ()
    pids: tuple[str, ...] = ()  # sorted ids; index = the player's stream key
    index: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pids:
            object.__setattr__(self, "pids", tuple(sorted(self.players)))
        object.__setattr__(self, "index", {p: i for i, p in enumerate(self.pids)})

    @property
    def user_team(self) -> GameTeam:
        return next(t for t in self.teams if t.is_user)

    def team(self, tid: str) -> GameTeam:
        for t in self.teams:
            if t.tid == tid:
                return t
        raise KeyError(tid)

    @property
    def tids(self) -> list[str]:
        return [t.tid for t in self.teams]

    def bye_of(self, pid: str) -> int:
        return int(self.bye_weeks.get(self.players[pid].nfl_team, 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings": self.settings.to_dict(), "teams": [t.to_dict() for t in self.teams],
            "players": [self.players[p].to_dict() for p in self.pids],
            "bye_weeks": {k: self.bye_weeks[k] for k in sorted(self.bye_weeks)},
            "schedule": [[list(pair) for pair in week] for week in self.schedule],
            "scoring_model": self.scoring_model, "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GameSnapshot":
        players = {str(p["pid"]): GamePlayer.from_dict(p) for p in raw["players"]}
        return cls(
            settings=GameSettings.from_dict(raw["settings"]),
            teams=tuple(GameTeam.from_dict(t) for t in raw["teams"]), players=players,
            bye_weeks={str(k): int(v) for k, v in (raw.get("bye_weeks") or {}).items()},
            schedule=tuple(tuple((str(a), str(b)) for a, b in week) for week in raw["schedule"]),
            scoring_model=str(raw.get("scoring_model") or ""), notes=tuple(raw.get("notes") or ()),
        )


__all__ = [
    "GAME_ENGINE_VERSION", "DIFFICULTIES", "TEAM_COUNTS", "SCORING_NAMES", "DEFAULT_SLOTS",
    "PREVIEW_PAYWALL_WEEK", "MAX_GAMES_PRO", "MAX_GAMES_FREE", "SCORING_PRESETS", "POOL_CAPS",
    "GameError", "GameSettings", "GamePlayer", "GameTeam", "GameSnapshot", "slot_positions",
    "playoff_rounds", "POSITIONS", "STRICT_SLOTS", "FLEX_SLOTS",
]
