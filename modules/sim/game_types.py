"""Settings, frozen snapshot and constants for the interactive GM game.

Pure data: stdlib only (plus ``modules.sim.types``). A ``GameSnapshot`` is
everything a game needs, copied once at creation and never refreshed, so a save
replays identically after real values refresh.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from modules.sim.game_mode import DEFAULT_MODE, MODES, POLICIES, RULES_VERSION, ModePolicy, policy_for
from modules.sim.types import FLEX_SLOTS, GAME_POSITIONS, GAME_STRICT_SLOTS, POSITIONS, STRICT_SLOTS

GAME_ENGINE_VERSION = "game-1.1.0"
DIFFICULTIES = ("easy", "normal", "hard")
TEAM_COUNTS = (8, 10, 12, 14)  # even: every team plays every week
IMPORT_TEAM_COUNTS = (4, 6, 8, 10, 12, 14, 16)
TE_PREMIUMS = (0.0, 0.5, 1.0)
BENCH_RANGE = (4, 10)
TIEBREAKERS = ("points_for", "head_to_head")  # standings/seed tiebreak after win pct
DEFAULT_TIEBREAKER = "points_for"
LEGACY_TIEBREAKER = "head_to_head"  # saves from before the setting existed
DEFAULT_BENCH = 8
DEFAULT_TEAMS = 12
DEFAULT_SCORING = "half"
START_FRESH = "fresh"
START_LEAGUE = "league"
START_KINDS = (START_FRESH, START_LEAGUE)
SINGLETON_POSITIONS = ("K", "DEF")  # one per roster, drafted late, never traded
NON_TRADABLE = SINGLETON_POSITIONS
DRAFT_SPARE_SPOTS = 2  # roster spots the draft leaves open for the wire
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
POOL_CAPS = {"QB": 64, "RB": 160, "WR": 220, "TE": 90, "K": 36, "DEF": 32}

# Share of each flex slot a position is expected to fill (drives replacement
# level, hence value over replacement).
FLEX_SHARE: dict[str, dict[str, float]] = {
    "FLEX": {"RB": 0.40, "WR": 0.45, "TE": 0.15},
    "REC_FLEX": {"WR": 0.60, "TE": 0.40},
    "SUPER_FLEX": {"QB": 0.70, "RB": 0.10, "WR": 0.17, "TE": 0.03},
}


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


def derive_layout(
    *, superflex: bool, include_k: bool, include_def: bool, bench: int
) -> tuple[tuple[str, ...], int, int]:
    """(starting slots, roster limit, draft rounds) from the lineup toggles.
    The draft fills every roster but ``DRAFT_SPARE_SPOTS`` spots."""

    slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]
    if superflex:
        slots.append("SUPER_FLEX")
    if include_k:
        slots.append("K")
    if include_def:
        slots.append("DEF")
    limit = len(slots) + bench
    return tuple(slots), limit, limit - DRAFT_SPARE_SPOTS


def scoring_label(scoring_settings: Mapping[str, float]) -> str:
    """The nearest preset name for a full scoring blob (display only)."""

    rec = float(scoring_settings.get("rec", 0.0) or 0.0)
    return "ppr" if rec >= 0.75 else "half" if rec >= 0.25 else "std"


def _flag(raw: Mapping[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def headshot_id(pid: str) -> str | None:
    """The Sleeper player id a photo can be fetched with, or None.

    Real players carry their Sleeper id as the game id (all digits); a team
    defense (``DEF-<TEAM>``) and the synthetic fixture players have no photo,
    so the client shows its initials fallback instead of a broken image.
    """

    text = str(pid or "")
    return text if text.isdigit() else None


@dataclass(frozen=True)
class GameSettings:
    teams: int = DEFAULT_TEAMS
    scoring: str = DEFAULT_SCORING
    difficulty: str = "normal"
    user_slot: int = 1  # draft slot (1 = first pick of round 1)
    auto_lineup: bool = False
    slots: tuple[str, ...] = DEFAULT_SLOTS
    rounds: int = 14
    roster_limit: int = 16
    regular_weeks: int = 14
    playoff_teams: int = 6
    trade_deadline_week: int = 10
    # League shape (all saved with the game; none of it is a database column).
    mode: str = DEFAULT_MODE
    te_premium: float = 0.0  # extra points per TE reception
    superflex: bool = False
    include_k: bool = True
    include_def: bool = False
    bench: int = DEFAULT_BENCH
    start: str = START_FRESH  # "league": rosters imported from a real league
    # A real league's full scoring blob (imports only); overrides the preset.
    custom_scoring: Mapping[str, float] | None = None
    rules: int = RULES_VERSION
    tiebreaker: str = DEFAULT_TIEBREAKER

    @property
    def playoff_weeks(self) -> int:
        return playoff_rounds(self.playoff_teams)

    @property
    def total_weeks(self) -> int:
        return self.regular_weeks + self.playoff_weeks

    @property
    def policy(self) -> ModePolicy:
        return policy_for(self.mode, self.rules)

    @property
    def scoring_settings(self) -> dict[str, float]:
        if self.custom_scoring:
            return {str(k): float(v) for k, v in self.custom_scoring.items()}
        out = dict(SCORING_PRESETS[self.scoring])
        if self.te_premium:
            out["bonus_rec_te"] = float(self.te_premium)
        return out

    @property
    def pool_positions(self) -> tuple[str, ...]:
        """Positions that exist in this league's player pool."""

        return tuple(
            pos for pos in GAME_POSITIONS
            if (pos != "K" or self.include_k or "K" in self.slots) and (pos != "DEF" or self.include_def or "DEF" in self.slots)
        )

    @classmethod
    def parse(cls, raw: Mapping[str, Any] | None, *, user_slot_default: int = 1) -> "GameSettings":
        """Validate client options (everything optional). Raises ValueError with
        a client-safe message."""

        raw = dict(raw or {})
        mode = raw.get("mode", DEFAULT_MODE)
        if mode not in MODES:
            raise ValueError("mode must be one of: " + ", ".join(MODES))
        if not POLICIES[mode].available:
            raise ValueError(f"{mode} leagues are not available yet.")
        teams = raw.get("teams", DEFAULT_TEAMS)
        if isinstance(teams, bool) or not isinstance(teams, int) or teams not in TEAM_COUNTS:
            raise ValueError("teams must be one of: " + ", ".join(str(t) for t in TEAM_COUNTS))
        scoring = raw.get("scoring", DEFAULT_SCORING)
        if scoring not in SCORING_NAMES:
            raise ValueError("scoring must be one of: " + ", ".join(SCORING_NAMES))
        te_premium = raw.get("te_premium", 0.0)
        if isinstance(te_premium, bool) or not isinstance(te_premium, (int, float)) or float(te_premium) not in TE_PREMIUMS:
            raise ValueError("te_premium must be one of: " + ", ".join(str(t) for t in TE_PREMIUMS))
        difficulty = raw.get("difficulty", "normal")
        if difficulty not in DIFFICULTIES:
            raise ValueError("difficulty must be one of: " + ", ".join(DIFFICULTIES))
        superflex = _flag(raw, "superflex", False)
        include_k = _flag(raw, "include_k", True)
        include_def = _flag(raw, "include_def", False)
        bench = raw.get("bench", DEFAULT_BENCH)
        if isinstance(bench, bool) or not isinstance(bench, int) or not BENCH_RANGE[0] <= bench <= BENCH_RANGE[1]:
            raise ValueError(f"bench must be between {BENCH_RANGE[0]} and {BENCH_RANGE[1]}")
        slot = raw.get("user_slot")
        if slot is None:
            slot = user_slot_default
        if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot <= teams:
            raise ValueError(f"user_slot must be between 1 and {teams}")
        auto = _flag(raw, "auto_lineup", False)
        tiebreaker = raw.get("tiebreaker", DEFAULT_TIEBREAKER)
        if tiebreaker not in TIEBREAKERS:
            raise ValueError("tiebreaker must be one of: " + ", ".join(TIEBREAKERS))
        slots, limit, rounds = derive_layout(
            superflex=superflex, include_k=include_k, include_def=include_def, bench=bench
        )
        return cls(
            teams=teams, scoring=scoring, difficulty=difficulty, user_slot=slot, auto_lineup=auto,
            slots=slots, rounds=rounds, roster_limit=limit, playoff_teams=4 if teams <= 8 else 6,
            mode=mode, te_premium=float(te_premium), superflex=superflex, include_k=include_k,
            include_def=include_def, bench=bench, tiebreaker=tiebreaker,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "teams": self.teams, "scoring": self.scoring, "difficulty": self.difficulty,
            "user_slot": self.user_slot, "auto_lineup": self.auto_lineup, "slots": list(self.slots),
            "rounds": self.rounds, "roster_limit": self.roster_limit,
            "regular_weeks": self.regular_weeks, "playoff_teams": self.playoff_teams,
            "playoff_weeks": self.playoff_weeks, "trade_deadline_week": self.trade_deadline_week,
            "mode": self.mode, "te_premium": self.te_premium, "superflex": self.superflex,
            "include_k": self.include_k, "include_def": self.include_def, "bench": self.bench,
            "start": self.start, "rules": self.rules, "tiebreaker": self.tiebreaker,
        }
        if self.custom_scoring:
            out["custom_scoring"] = {str(k): float(v) for k, v in self.custom_scoring.items()}
        return out

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GameSettings":
        """Rebuild a saved game's settings. Saves from before league settings
        existed carry only the original keys; everything new is inferred from
        them (``rules`` 1 keeps their original valuation)."""

        slots = tuple(str(s) for s in raw["slots"])
        limit = int(raw["roster_limit"])
        custom = raw.get("custom_scoring")
        return cls(
            teams=int(raw["teams"]), scoring=str(raw["scoring"]), difficulty=str(raw["difficulty"]),
            user_slot=int(raw["user_slot"]), auto_lineup=bool(raw.get("auto_lineup")),
            slots=slots, rounds=int(raw["rounds"]),
            roster_limit=limit, regular_weeks=int(raw["regular_weeks"]),
            playoff_teams=int(raw["playoff_teams"]), trade_deadline_week=int(raw["trade_deadline_week"]),
            mode=str(raw.get("mode") or DEFAULT_MODE), te_premium=float(raw.get("te_premium") or 0.0),
            superflex=bool(raw.get("superflex", "SUPER_FLEX" in slots)),
            include_k=bool(raw.get("include_k", "K" in slots)),
            include_def=bool(raw.get("include_def", "DEF" in slots)),
            bench=int(raw.get("bench", limit - len(slots))), start=str(raw.get("start") or START_FRESH),
            custom_scoring={str(k): float(v) for k, v in custom.items()} if custom else None,
            rules=int(raw.get("rules", 1)),
            # Saves from before the setting ranked ties head-to-head first; keep that.
            tiebreaker=str(raw.get("tiebreaker") or LEGACY_TIEBREAKER),
        )


@dataclass(frozen=True)
class ImportedTeam:
    """One team of a real league, as the adapter read it."""

    tid: str
    name: str
    owner: str
    is_user: bool
    roster: tuple[str, ...]  # game player ids (real ids; DEF mapped to ``DEF-<TEAM>``)


@dataclass(frozen=True)
class LeagueImport:
    """A real league's settings and current rosters, frozen. Everything the
    "start from one of my leagues" mode needs and nothing else; the game never
    holds a handle back to the real league."""

    league_id: str
    league_name: str
    season: str
    teams: tuple[ImportedTeam, ...]
    slots: tuple[str, ...]  # starting slots the game models (QB/RB/WR/TE/K/DEF + flex)
    bench: int
    scoring_settings: Mapping[str, float]
    playoff_teams: int
    notes: tuple[str, ...] = ()


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
    # Starting rosters of a game imported from a real league ({tid: [pid]}).
    start_rosters: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
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
            "start_rosters": {t: list(p) for t, p in self.start_rosters.items()},
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
            start_rosters={str(t): tuple(str(p) for p in pids) for t, pids in (raw.get("start_rosters") or {}).items()},
        )


__all__ = [
    "GAME_ENGINE_VERSION", "DIFFICULTIES", "TEAM_COUNTS", "SCORING_NAMES", "DEFAULT_SLOTS",
    "PREVIEW_PAYWALL_WEEK", "MAX_GAMES_PRO", "MAX_GAMES_FREE", "SCORING_PRESETS", "POOL_CAPS",
    "TE_PREMIUMS", "BENCH_RANGE", "DEFAULT_BENCH", "DEFAULT_TEAMS", "DEFAULT_SCORING", "IMPORT_TEAM_COUNTS",
    "START_FRESH", "START_LEAGUE", "START_KINDS", "SINGLETON_POSITIONS", "NON_TRADABLE", "FLEX_SHARE",
    "DRAFT_SPARE_SPOTS", "derive_layout", "scoring_label", "GAME_POSITIONS", "GAME_STRICT_SLOTS",
    "ImportedTeam", "LeagueImport", "GameError", "GameSettings", "GamePlayer", "GameTeam", "GameSnapshot", "slot_positions",
    "playoff_rounds", "POSITIONS", "STRICT_SLOTS", "FLEX_SLOTS",
]
