"""Settings, frozen snapshot and constants for the interactive GM game.

Pure data: stdlib only (plus ``modules.sim.types``). A ``GameSnapshot`` is
everything a game needs, copied once at creation and never refreshed, so a save
replays identically after real values refresh.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from modules.sim.game_mode import (
    DEFAULT_MODE,
    DEFAULT_ROOKIE_ROUNDS,
    DEFAULT_SEASONS,
    DYNASTY_VERSION,
    MODES,
    PICK_YEARS,
    POLICIES,
    ROOKIE_ROUNDS,
    RULES_VERSION,
    SEASON_CHOICES,
    ModePolicy,
    policy_for,
)
from modules.sim.types import FLEX_SLOTS, GAME_POSITIONS, GAME_STRICT_SLOTS, POSITIONS, STRICT_SLOTS, SimPick

GAME_ENGINE_VERSION = "game-1.2.0"
DIFFICULTIES = ("easy", "normal", "hard")
TEAM_COUNTS = (8, 10, 12, 14)  # even: every team plays every week
IMPORT_TEAM_COUNTS = (4, 6, 8, 10, 12, 14, 16)
TE_PREMIUMS = (0.0, 0.5, 1.0)
BENCH_RANGE = (4, 10)
IR_SLOT_RANGE = (0, 4)
TAXI_SLOT_RANGE = (0, 8)
DEFAULT_IR_SLOTS = 2
DEFAULT_TAXI_YEARS = 2  # rookies and second-year players (years of experience below this), Sleeper's usual rule
DEFAULT_TAXI_SLOTS_DYNASTY = 4
RESERVE_VERSION = 1
AI_VERSION = 1  # 1: AI managers plan depth around byes and injuries, use the wire proactively (new games only)
VIEWS_KEPT = 2  # dynasty_v 3: season pools kept in memory behind the latest
KD_VERSION = 1  # 1 = kickers and defenses can be traded (user-initiated; 0 = a save from before: they never trade)
LIMIT_VERSION = 1  # 1 = a roster over the limit never blocks advancing, only acquiring players (0 = a save from before it: over the limit blocks Advance and Start season)
BLOCK_VERSION = 2  # 1 = the trade block: user block, AI blocks, block-aware offers (0 = a save from before it: nothing changes); 2 = an asset leaving the team leaves the block for good
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
# The flex slot's eligibility, picked at setup. "flex" (RB/WR/TE) is the default and is never serialized; "rb_wr" swaps the
# FLEX slot for WRRB_FLEX (RB/WR only). A save made before the option has no flex_type and replays exactly as it was.
FLEX_TYPES = ("flex", "rb_wr")
DEFAULT_FLEX_TYPE = "flex"
FLEX_SLOT_FOR_TYPE = {"flex": "FLEX", "rb_wr": "WRRB_FLEX"}
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
    "WRRB_FLEX": {"RB": 0.47, "WR": 0.53},
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
    *, superflex: bool, include_k: bool, include_def: bool, bench: int, flex_type: str = DEFAULT_FLEX_TYPE
) -> tuple[tuple[str, ...], int, int]:
    """(starting slots, roster limit, draft rounds) from the lineup toggles.
    The draft fills every roster but ``DRAFT_SPARE_SPOTS`` spots."""

    slots = ["QB", "RB", "RB", "WR", "WR", "TE", FLEX_SLOT_FOR_TYPE[flex_type]]
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
    flex_type: str = DEFAULT_FLEX_TYPE  # "flex" (RB/WR/TE) or "rb_wr" (RB/WR only); serialized only when not the default
    include_k: bool = True
    include_def: bool = False
    bench: int = DEFAULT_BENCH
    start: str = START_FRESH  # "league": rosters imported from a real league
    # A real league's full scoring blob (imports only); overrides the preset.
    custom_scoring: Mapping[str, float] | None = None
    rules: int = RULES_VERSION
    tiebreaker: str = DEFAULT_TIEBREAKER
    # Dynasty (all zero/absent on redraft and on every save made before it).
    seasons: int = 1  # seasons the game runs; > 1 means offseasons and rookie drafts
    start_year: int = 0  # the calendar label of season 1 (rookie drafts are start_year + 1 ...)
    pick_years: int = 0  # future rookie drafts' picks held at any time
    rookie_rounds: int = 0
    dynasty_v: int = 0  # dynasty save-format version
    # IR and taxi squads (reserve_v 0 = a save from before them: no reserve spots at all).
    reserve_v: int = 0
    kd_v: int = 0  # K/DEF trade version (0 on every save made before it: kickers and defenses are never traded)
    block_v: int = 0  # trade block version (0 on every save made before it)
    ir_slots: int = 0
    taxi_slots: int = 0
    taxi_years: int = 2  # years of NFL experience a player may have and still sit on the taxi squad
    # AI manager generation (0 = a save from before bye/injury-aware depth planning: its AI decisions replay exactly as they were).
    ai_v: int = 0
    # Roster limit rule generation (0 = a save from before it: being over the limit hard-stops Advance / Start season).
    limit_v: int = 0

    @property
    def soft_limit(self) -> bool:
        """limit_v 1+: a roster over the limit never blocks the game moving on; it only blocks acquiring players until back under."""
        return self.limit_v >= 1

    @property
    def non_tradable(self) -> tuple[str, ...]:
        """Positions that cannot be traded in this game: K and DEF on a save from before kd_v, none after."""
        return () if self.kd_v >= 1 else NON_TRADABLE

    @property
    def ai_depth(self) -> bool:
        """AI managers plan around byes and injuries (ai_v 1+). Older saves keep their original, reactive AI."""
        return self.ai_v >= 1

    @property
    def reserves(self) -> bool:
        return self.reserve_v >= 1

    @property
    def block(self) -> bool:
        """The trade block exists in this game (a save from before it keeps the engine exactly as it was)."""
        return self.block_v >= 1

    @property
    def dynasty(self) -> bool:
        return self.mode == "dynasty" and self.rules >= 2 and self.dynasty_v >= 1

    @property
    def rookie_curves(self) -> bool:
        """Generated rookies carry a scouting profile and a per-player development curve (dynasty_v 2+). Older dynasty saves keep the plain age curve."""
        return self.dynasty and self.dynasty_v >= 2

    @property
    def league_anchor(self) -> bool:
        """Rookie classes and their market values are scaled to the league's own season-1 talent level, not to the aged pool of the moment
        (dynasty_v 3+). Without it a long dynasty feeds back on itself: weaker veterans make weaker classes, which make weaker veterans."""
        return self.dynasty and self.dynasty_v >= 3

    @property
    def block_forgets(self) -> bool:
        """block_v 2+: an asset that leaves your team (cut, traded, dropped, retired, spent pick) is taken off the block in the state, so
        getting him back does not put him on the block again. block_v 1 saves keep the derived-only behaviour they replay with."""
        return self.block_v >= 2

    @property
    def multi_season(self) -> bool:
        return self.dynasty and self.seasons > 1

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
        seasons, rookie_rounds, start_year = 1, 0, 0
        if mode == "dynasty":
            seasons = raw.get("seasons", DEFAULT_SEASONS)
            if isinstance(seasons, bool) or not isinstance(seasons, int) or seasons not in SEASON_CHOICES:
                raise ValueError("seasons must be one of: " + ", ".join(str(t) for t in SEASON_CHOICES))
            rookie_rounds = raw.get("rookie_rounds", DEFAULT_ROOKIE_ROUNDS)
            if isinstance(rookie_rounds, bool) or not isinstance(rookie_rounds, int) or rookie_rounds not in ROOKIE_ROUNDS:
                raise ValueError("rookie_rounds must be one of: " + ", ".join(str(t) for t in ROOKIE_ROUNDS))
            start_year = raw.get("start_year", 0)
            if isinstance(start_year, bool) or not isinstance(start_year, int) or not (start_year == 0 or 2000 <= start_year <= 2100):
                raise ValueError("start_year must be a calendar year")
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
        flex_type = raw.get("flex_type", DEFAULT_FLEX_TYPE)
        if flex_type not in FLEX_TYPES:
            raise ValueError("flex_type must be one of: " + ", ".join(FLEX_TYPES))
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
        ir_slots = raw.get("ir_slots", DEFAULT_IR_SLOTS)
        if isinstance(ir_slots, bool) or not isinstance(ir_slots, int) or not IR_SLOT_RANGE[0] <= ir_slots <= IR_SLOT_RANGE[1]:
            raise ValueError(f"ir_slots must be between {IR_SLOT_RANGE[0]} and {IR_SLOT_RANGE[1]}")
        taxi_slots = raw.get("taxi_slots", DEFAULT_TAXI_SLOTS_DYNASTY if mode == "dynasty" else 0)
        if isinstance(taxi_slots, bool) or not isinstance(taxi_slots, int) or not TAXI_SLOT_RANGE[0] <= taxi_slots <= TAXI_SLOT_RANGE[1]:
            raise ValueError(f"taxi_slots must be between {TAXI_SLOT_RANGE[0]} and {TAXI_SLOT_RANGE[1]}")
        taxi_years = raw.get("taxi_years", DEFAULT_TAXI_YEARS)
        if isinstance(taxi_years, bool) or not isinstance(taxi_years, int) or taxi_years not in (1, 2, 3, 4):
            raise ValueError("taxi_years must be 1, 2, 3 or 4")
        slots, limit, rounds = derive_layout(
            superflex=superflex, include_k=include_k, include_def=include_def, bench=bench, flex_type=flex_type
        )
        return cls(
            teams=teams, scoring=scoring, difficulty=difficulty, user_slot=slot, auto_lineup=auto,
            slots=slots, rounds=rounds, roster_limit=limit, playoff_teams=4 if teams <= 8 else 6,
            mode=mode, te_premium=float(te_premium), superflex=superflex, flex_type=flex_type, include_k=include_k,
            include_def=include_def, bench=bench, tiebreaker=tiebreaker,
            reserve_v=RESERVE_VERSION, block_v=BLOCK_VERSION, kd_v=KD_VERSION, ir_slots=ir_slots, taxi_slots=taxi_slots, taxi_years=taxi_years, ai_v=AI_VERSION, limit_v=LIMIT_VERSION,
            seasons=seasons, start_year=start_year, rookie_rounds=rookie_rounds,
            pick_years=PICK_YEARS if mode == "dynasty" else 0, dynasty_v=DYNASTY_VERSION if mode == "dynasty" else 0,
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
        if self.reserve_v:
            out.update({"reserve_v": self.reserve_v, "ir_slots": self.ir_slots, "taxi_slots": self.taxi_slots,
                        "taxi_years": self.taxi_years})
        if self.flex_type != DEFAULT_FLEX_TYPE:  # the default flex never serializes, so every older save and digest is unchanged
            out["flex_type"] = self.flex_type
        if self.ai_v:  # saves from before the AI generation serialize exactly as before
            out["ai_v"] = self.ai_v
        if self.block_v:
            out["block_v"] = self.block_v
        if self.kd_v:
            out["kd_v"] = self.kd_v
        if self.limit_v:  # absent on every save made before the soft limit
            out["limit_v"] = self.limit_v
        if self.dynasty_v:  # only dynasty saves carry these: every other save serializes exactly as before
            out.update({
                "seasons": self.seasons, "start_year": self.start_year, "pick_years": self.pick_years,
                "rookie_rounds": self.rookie_rounds, "dynasty_v": self.dynasty_v,
            })
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
            flex_type=str(raw.get("flex_type") or DEFAULT_FLEX_TYPE),
            include_k=bool(raw.get("include_k", "K" in slots)),
            include_def=bool(raw.get("include_def", "DEF" in slots)),
            bench=int(raw.get("bench", limit - len(slots))), start=str(raw.get("start") or START_FRESH),
            custom_scoring={str(k): float(v) for k, v in custom.items()} if custom else None,
            rules=int(raw.get("rules", 1)),
            # Saves from before the setting ranked ties head-to-head first; keep that.
            tiebreaker=str(raw.get("tiebreaker") or LEGACY_TIEBREAKER),
            seasons=int(raw.get("seasons") or 1), start_year=int(raw.get("start_year") or 0),
            pick_years=int(raw.get("pick_years") or 0), rookie_rounds=int(raw.get("rookie_rounds") or 0),
            dynasty_v=int(raw.get("dynasty_v") or 0), reserve_v=int(raw.get("reserve_v") or 0), block_v=int(raw.get("block_v") or 0), kd_v=int(raw.get("kd_v") or 0),
            ir_slots=int(raw.get("ir_slots") or 0), taxi_slots=int(raw.get("taxi_slots") or 0),
            taxi_years=int(raw.get("taxi_years", 2)), ai_v=int(raw.get("ai_v") or 0),
            limit_v=int(raw.get("limit_v") or 0),
        )


@dataclass(frozen=True)
class ImportedTeam:
    """One team of a real league, as the adapter read it."""

    tid: str
    name: str
    owner: str
    is_user: bool
    roster: tuple[str, ...]  # game player ids (real ids; DEF mapped to ``DEF-<TEAM>``)
    ir: tuple[str, ...] = ()  # the real league's reserve (IR) squad, kept apart from ``roster``
    taxi: tuple[str, ...] = ()  # the real league's taxi squad


@dataclass(frozen=True)
class LeagueTeamChoice:
    """One team of a real league as the setup picker shows it. Identified by
    ``roster_id`` only; the name is display text, never a key."""

    roster_id: str
    team_name: str
    owner_name: str
    wins: int
    losses: int
    ties: int
    points_for: float
    rank: int  # 1 = best record (points for breaks ties)
    is_you: bool


@dataclass(frozen=True)
class LeagueTeams:
    league_id: str
    league_name: str
    season: str
    teams: tuple[LeagueTeamChoice, ...]
    you_roster_id: str  # "" when the account's team could not be identified


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
    # Dynasty import only: the league's real rookie-pick ownership for the next
    # drafts, the calendar label season 1 plays under, and its rookie draft length.
    picks: tuple[SimPick, ...] = ()
    start_year: int = 0
    rookie_rounds: int = 0
    ir_slots: int = 0
    taxi_slots: int = 0
    taxi_years: int = 2


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
    # Dynasty: the game's own seed (so a later season's pool is a pure function
    # of this snapshot) and every team's picks at the start (real ownership
    # for a league import).
    seed: int = 0
    start_picks: tuple[SimPick, ...] = ()
    start_ir: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    start_taxi: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pids:
            object.__setattr__(self, "pids", tuple(sorted(self.players)))
        object.__setattr__(self, "index", {p: i for i, p in enumerate(self.pids)})

    @property
    def root(self) -> "GameSnapshot":
        """The season-1 snapshot this one was derived from (itself for season 1)."""

        return getattr(self, "_root", self)

    def season_view(self, season: int) -> "GameSnapshot":
        """The snapshot for dynasty season ``season``: the same league with its
        players aged, retired and replaced by the incoming rookie classes. Season
        1 (and every non-dynasty game) is this snapshot itself."""

        root = self.root
        if season <= 1 or not root.settings.multi_season:
            return root
        from modules.sim.game_dynasty import season_snapshot  # lazy: game_dynasty imports this module

        views = getattr(root, "_views", None)
        if views is None:
            views = {}
            object.__setattr__(root, "_views", views)
        if season not in views:
            views[season] = season_snapshot(root, season)
            if root.settings.league_anchor:  # a 20-season game must not pin 20 pools: keep the latest few, rebuild older ones on demand
                for old in [k for k in views if k < season - VIEWS_KEPT]:
                    del views[old]
        return views[season]

    @property
    def user_team(self) -> GameTeam:
        team = getattr(self, "_user_team", None)
        if team is None:
            team = next(t for t in self.teams if t.is_user)
            object.__setattr__(self, "_user_team", team)
        return team

    def team(self, tid: str) -> GameTeam:
        index = getattr(self, "_team_index", None)
        if index is None:  # frozen snapshot: index once, on the instance (not a field, never serialized)
            index = {t.tid: t for t in self.teams}
            object.__setattr__(self, "_team_index", index)
        try:
            return index[tid]
        except KeyError:
            raise KeyError(tid) from None

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
            **({"start_ir": {t: list(p) for t, p in self.start_ir.items()},
                "start_taxi": {t: list(p) for t, p in self.start_taxi.items()}} if self.start_ir or self.start_taxi else {}),
            **({"seed": self.seed, "start_picks": [p.to_dict() for p in self.start_picks]}
               if self.settings.dynasty_v else {}),
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
            start_ir={str(t): tuple(str(p) for p in pids) for t, pids in (raw.get("start_ir") or {}).items()},
            start_taxi={str(t): tuple(str(p) for p in pids) for t, pids in (raw.get("start_taxi") or {}).items()},
            seed=int(raw.get("seed") or 0),
            start_picks=tuple(SimPick.from_dict(p) for p in (raw.get("start_picks") or ())),
        )


__all__ = [
    "GAME_ENGINE_VERSION", "DIFFICULTIES", "TEAM_COUNTS", "SCORING_NAMES", "DEFAULT_SLOTS",
    "PREVIEW_PAYWALL_WEEK", "MAX_GAMES_PRO", "MAX_GAMES_FREE", "SCORING_PRESETS", "POOL_CAPS",
    "TE_PREMIUMS", "BENCH_RANGE", "DEFAULT_BENCH", "DEFAULT_TEAMS", "DEFAULT_SCORING", "IMPORT_TEAM_COUNTS",
    "KD_VERSION", "FLEX_TYPES", "DEFAULT_FLEX_TYPE", "FLEX_SLOT_FOR_TYPE", "START_FRESH", "START_LEAGUE", "START_KINDS", "SINGLETON_POSITIONS", "NON_TRADABLE", "FLEX_SHARE",
    "DRAFT_SPARE_SPOTS", "derive_layout", "scoring_label", "GAME_POSITIONS", "GAME_STRICT_SLOTS",
    "ImportedTeam", "LeagueImport", "LeagueTeamChoice", "LeagueTeams", "GameError", "GameSettings", "GamePlayer", "GameTeam", "GameSnapshot", "slot_positions",
    "playoff_rounds", "POSITIONS", "STRICT_SLOTS", "FLEX_SLOTS",
]
