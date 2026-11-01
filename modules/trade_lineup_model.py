"""Trade engine v2: expected lineup points, one principled trade score.

See ``docs/trade-engine-v2.md`` for the full description, calibration and
limitations. Summary of what this module does:

1. Gives every player an expected weekly point total in the LEAGUE's scoring
   (``PlayerPoints``), from the best source that exists, never invented:
   ``projection`` (the walk-forward baseline in ``modules.player_projections``,
   when a caller attaches ``proj_ppg``), else ``season_average`` (the player's
   real season PPG shrunk toward a value-derived prior by games played), else
   ``value_estimate`` (rank-matching the player's model value to the PPG
   distribution of his position's active players).
2. Solves the league's real lineup (QB/RB/WR/TE/K/FLEX/WR-RB/REC_FLEX/
   SUPER_FLEX, TE premium and PPR through the points themselves) for every
   remaining week, with byes, and with injuries as an availability
   probability (the repo's existing expected-weeks-missed estimate). Weeks
   with uncertain players are solved exactly by enumerating availability
   scenarios, so depth has real insurance value and the variance of the
   outcome is known, not guessed.
3. Lets the roster fill holes from the league's actual waiver pool
   (``waiver_df``) at a reliability discount; with no pool it falls back to
   the market replacement level.
4. Turns the points delta into value units (the app's own scale) with ONE
   calibrated rate ``k`` and combines it with the market value balance
   under the team's posture (contender vs rebuilder weights between this
   season and future capital). The result is ``trade_score``; the verdict,
   confidence, risk text and counter-offer search all read that number.

Pure: no network, no database. Everything it reads is in the frames and
settings passed in (schedule byes come from ``modules.nfl_schedule``'s
cached lookup; a failed lookup reads as "no bye", never a guess).
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date
from itertools import product
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from modules import nfl_schedule, player_projections
from modules.frame_records import frame_records
from modules.rankings import age_multiplier, injury_level, is_ruled_out
from modules.team_eval import _lineup_slots, normalize_team_strategy
from modules.trade_grade import (
    CURRENT_SEASON_VALUE_SHARE,
    STARTER_STRENGTH_WEIGHTS,
    FANTASY_SEASON_WEEKS,
    InjuryAbsence,
    SeasonWindow,
    estimate_injury_absence,
)

MODEL_VERSION = "trade-engine-v2.0"

MAX_CONFIDENCE = 0.99
SCORED_POSITIONS = ("QB", "RB", "WR", "TE", "K")
SKILL_POSITIONS = ("QB", "RB", "WR", "TE")

# (this-season weight, future weight). The market prices every point of
# value at 1.0. A posture's extra weight on REAL lineup points is the
# repo's existing starter-strength weight (contender 1.50 ... tank 1.00,
# trade_grade.STARTER_STRENGTH_WEIGHTS, "raw value treats bench and starting
# value the same"). Future capital stays at 1.0 for every posture because
# the asset scores arriving here are already posture-priced upstream (the
# strategy age curve and the strategy pick multiplier); weighting it again
# would double count. The relative weight between this season and the
# future is therefore w_now / w_future: contender 1.50, rebuild 1.05.
POSTURE_WEIGHTS: dict[str, tuple[float, float]] = {
    posture: (1.0 + starter_weight, 1.0) for posture, starter_weight in STARTER_STRENGTH_WEIGHTS.items()
}

# Documented static anchors (PPR PPG) used ONLY when the league-wide frame has
# too few players with real stats to calibrate from: (top, replacement),
# the p90 and p25 of games>=4 players in the 2026 players table.
STATIC_ANCHORS: dict[str, tuple[float, float]] = {
    "QB": (22.0, 12.0),
    "RB": (19.0, 4.5),
    "WR": (18.0, 5.0),
    "TE": (13.0, 3.5),
    "K": (10.0, 7.0),
}
STATIC_VALUE_TOP = 8000.0
# Value-per-point-over-replacement-week, measured on the 2026 players table
# (median of 0.40 * dynasty_score / (17 * (PPG - replacement PPG))). Used only
# when the frame given cannot calibrate its own.
STATIC_VALUE_PER_POINT = 22.0


@dataclass(frozen=True)
class ModelParams:
    """Every tunable of the model, in one place. Nothing else is special-cased."""

    horizon_end_week: int = FANTASY_SEASON_WEEKS
    # Waiver pickups are not guaranteed (other teams claim, one-week lag).
    fa_reliability: float = 0.90
    # Shrinkage of a player's season PPG toward the value-derived prior.
    prior_games: float = 3.0
    min_games_for_observed: int = 1
    # Value-derived estimates are rougher than projections: widen their spread.
    sd_inflation: dict[str, float] = field(
        default_factory=lambda: {"projection": 1.0, "season_average": 1.1, "value_estimate": 1.3}
    )
    # Share of a player's weekly spread that is a persistent baseline error
    # (does not average out across weeks).
    baseline_error_share: float = 0.25
    # At most this many uncertain (injury) players are enumerated exactly per
    # week; the rest are folded in as expected-value scaling.
    max_enumerated: int = 6
    # Future-years component (informational lineup + scored context).
    future_years: int = 2
    future_discount: float = 0.70
    future_sigma_share: float = 0.40
    # Market-value noise: disagreement between value sources on a package.
    market_noise_share: float = 0.04
    # Confidence labels from P(direction is right).
    confidence_high: float = 0.88
    confidence_moderate: float = 0.70
    league_size: int = 12


DEFAULT_PARAMS = ModelParams()


# --- small helpers -----------------------------------------------------------


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(out) or math.isinf(out):
        return default
    return out


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _flex_positions(slots: Mapping[str, int]) -> dict[str, int]:
    """How many flex-type slots each skill position can additionally fill."""

    out = {pos: 0 for pos in SKILL_POSITIONS}
    for name, eligible in _FLEX_ELIGIBLE.items():
        n = int(slots.get(name, 0) or 0)
        for pos in eligible:
            out[pos] += n
    return out


# Narrowest first: the nested structure that makes best-first greedy optimal.
_FLEX_ORDER = ("WR/RB", "REC_FLEX", "FLEX", "SUPER_FLEX")
_FLEX_ELIGIBLE: dict[str, tuple[str, ...]] = {
    "WR/RB": ("RB", "WR"),
    "REC_FLEX": ("WR", "TE"),
    "FLEX": ("RB", "WR", "TE"),
    "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
}


# --- scoring conversion ------------------------------------------------------


def scoring_profile(settings: Mapping[str, Any] | None) -> dict[str, float]:
    """Reception value and TE bonus per reception for this league."""

    settings = settings or {}
    detected = settings.get("_detected_scoring") if isinstance(settings.get("_detected_scoring"), Mapping) else {}
    rec = _num(detected.get("rec"))
    if rec is None:
        fmt = _text(settings.get("scoring_format")).lower()
        rec = 0.5 if "half" in fmt else 0.0 if fmt == "standard" else 1.0
    te_bonus = 0.0
    keys = detected.get("te_premium_keys") if isinstance(detected.get("te_premium_keys"), Mapping) else {}
    for key, value in keys.items():
        if "rec" in str(key):
            te_bonus = max(te_bonus, _num(value, 0.0) or 0.0)
    if settings.get("te_premium") and te_bonus <= 0:
        te_bonus = 0.5
    return {"rec": float(rec), "te_bonus": float(te_bonus)}


def _league_scored(ppg_ppr: float, row: Mapping[str, Any], position: str, scoring: Mapping[str, float]) -> float:
    """PPR points per game -> the league's scoring, using the player's real
    receptions per game. No receptions on file: the PPR number is kept as is."""

    games = _num(row.get("games_played"))
    recs = _num(row.get("receptions"))
    if not games or games <= 0 or recs is None or position not in {"RB", "WR", "TE"}:
        return ppg_ppr
    recs_pg = recs / games
    out = ppg_ppr - (1.0 - scoring["rec"]) * recs_pg
    if position == "TE":
        out += scoring["te_bonus"] * recs_pg
    return out


@dataclass(frozen=True)
class PlayerPoints:
    player_id: str
    name: str
    position: str
    team: str
    age: float | None
    ppg: float | None
    sd: float
    basis: str  # projection | season_average | value_estimate | none
    bye_week: int | None
    absence: InjuryAbsence | None
    out_all: bool
    free_agent: bool = False
    value: float = 0.0
    status_text: str = ""

    def availability(self, week: int, current_week: int) -> float:
        if self.bye_week is not None and week == self.bye_week:
            return 0.0
        if self.out_all:
            return 0.0
        if self.absence is None:
            return 1.0
        i = max(0, week - current_week)
        return 1.0 - min(1.0, max(0.0, float(self.absence.weeks) - i))


# --- context (calibration shared by every package for one league/roster) -----


@dataclass
class ModelContext:
    params: ModelParams
    settings: dict[str, Any]
    slots: dict[str, int]
    scoring: dict[str, float]
    score_column: str
    window: SeasonWindow
    season: int
    strategy: str
    curves: dict[str, list[tuple[float, float]]]  # pos -> [(value, ppg)] by value desc
    market_replacement: dict[str, float]
    value_per_point: float
    k_source: str
    waiver: list[PlayerPoints]
    waiver_provided: bool
    byes: dict[str, int | None]
    calibration: dict[str, Any]

    @property
    def weeks(self) -> list[int]:
        start = max(1, self.window.current_week)
        return list(range(start, self.params.horizon_end_week + 1))


def _active_rows(frame: pd.DataFrame, score_column: str, scoring: Mapping[str, float]) -> dict[str, list[tuple[float, float]]]:
    """pos -> [(value, league-scored PPG)] for players with real stats."""

    out: dict[str, list[tuple[float, float]]] = {pos: [] for pos in SCORED_POSITIONS}
    if frame is None or frame.empty or "ppg" not in frame.columns or score_column not in frame.columns:
        return out
    for row in frame_records(frame):
        pos = _text(row.get("position")).upper()
        if pos not in out:
            continue
        games = _num(row.get("games_played"), 0.0) or 0.0
        ppg = _num(row.get("ppg"))
        value = _num(row.get(score_column))
        if ppg is None or value is None or games < 3 or value <= 0:
            continue
        out[pos].append((value, _league_scored(ppg, row, pos, scoring)))
    for pos in out:
        out[pos].sort(key=lambda item: -item[0])
    return out


_CURVE_INDEX_CACHE: list[tuple[list, int, tuple[list[float], list[float]]]] = []
_CURVE_INDEX_CACHE_MAX = 16


def _curve_index(pairs: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """(ascending negated values, descending ppgs) for one position's curve.

    Built once per curve list instead of once per looked-up player. The list
    is held in the cache so its ``id`` cannot be reused while the entry
    lives (same pattern as ``get_context``)."""

    for cached_pairs, cached_len, index in _CURVE_INDEX_CACHE:
        if cached_pairs is pairs and cached_len == len(pairs):
            return index
    index = (sorted(-v for v, _ in pairs), sorted((p for _, p in pairs), reverse=True))
    _CURVE_INDEX_CACHE.append((pairs, len(pairs), index))
    del _CURVE_INDEX_CACHE[:-_CURVE_INDEX_CACHE_MAX]
    return index


def _value_curve_ppg(ctx_curves: Mapping[str, list[tuple[float, float]]], pos: str, value: float) -> tuple[float, bool]:
    """Rank-match a value to a PPG. Returns (ppg, from_data)."""

    pairs = ctx_curves.get(pos) or []
    if len(pairs) >= 6:
        neg_values, ppgs = _curve_index(pairs)
        rank = bisect_left(neg_values, -value)  # players that out-value him
        idx = min(rank, len(ppgs) - 1)
        return float(ppgs[idx]), True
    top, repl = STATIC_ANCHORS.get(pos, (15.0, 4.0))
    share = max(0.0, min(1.0, value / STATIC_VALUE_TOP))
    return repl + (top - repl) * share, False


def build_context(
    all_players_df: pd.DataFrame | None,
    lineup_settings: Mapping[str, Any] | None,
    score_column: str,
    *,
    window: SeasonWindow,
    strategy: str,
    waiver_df: pd.DataFrame | None = None,
    params: ModelParams = DEFAULT_PARAMS,
    season: int | None = None,
) -> ModelContext:
    settings = dict(lineup_settings or {})
    slots = _lineup_slots(settings)
    scoring = scoring_profile(settings)
    season = int(season or settings.get("season") or date.today().year)
    league_size = int(_num(settings.get("league_size"), params.league_size) or params.league_size)
    frame = all_players_df if all_players_df is not None else pd.DataFrame()

    curves = _active_rows(frame, score_column, scoring)
    flex = _flex_positions(slots)
    market_replacement: dict[str, float] = {}
    for pos in SCORED_POSITIONS:
        pairs = curves.get(pos) or []
        if len(pairs) >= 6:
            ppgs = sorted((p for _, p in pairs), reverse=True)
            # Standard replacement rank: every team's starters plus its share
            # of the flex slots, then the next player up.
            flex_share = flex.get(pos, 0) / max(1, len(_FLEX_ELIGIBLE["FLEX"]))
            rank = int(round(league_size * (int(slots.get(pos, 0) or 0) + flex_share))) + 1
            market_replacement[pos] = float(ppgs[min(rank, len(ppgs)) - 1])
        else:
            market_replacement[pos] = STATIC_ANCHORS.get(pos, (15.0, 4.0))[1]

    # One value-per-point rate for every position: the market's own
    # current-season share of a player's value divided by his points over
    # replacement across a full season, median over the league's starters.
    ratios: list[float] = []
    for pos in SKILL_POSITIONS:
        repl = market_replacement[pos]
        for value, ppg in curves.get(pos) or []:
            vorp = ppg - repl
            if vorp > 1.0:
                ratios.append(CURRENT_SEASON_VALUE_SHARE * value / (FANTASY_SEASON_WEEKS * vorp))
    if len(ratios) >= 8:
        ratios.sort()
        value_per_point = ratios[len(ratios) // 2]
        k_source = "calibrated"
    else:
        value_per_point = STATIC_VALUE_PER_POINT
        k_source = "static"

    byes: dict[str, int | None] = {}
    ctx = ModelContext(
        params=params,
        settings=settings,
        slots=slots,
        scoring=scoring,
        score_column=score_column,
        window=window,
        season=season,
        strategy=normalize_team_strategy(strategy),
        curves=curves,
        market_replacement=market_replacement,
        value_per_point=float(value_per_point),
        k_source=k_source,
        waiver=[],
        waiver_provided=waiver_df is not None,
        byes=byes,
        calibration={
            "active_players": {pos: len(curves.get(pos) or []) for pos in SCORED_POSITIONS},
            "market_replacement_ppg": {pos: round(v, 2) for pos, v in market_replacement.items()},
            "value_per_point": round(float(value_per_point), 2),
            "value_per_point_source": k_source,
            "league_size": league_size,
        },
    )
    if waiver_df is not None and not waiver_df.empty:
        profiles = profile_roster(waiver_df, ctx, free_agent=True)
        # Only the players who could actually crack a lineup: enough per
        # position to fill every slot that position can occupy.
        keep: list[PlayerPoints] = []
        for pos in SCORED_POSITIONS:
            room = int(slots.get(pos, 0) or 0) + flex.get(pos, 0)
            pool = [p for p in profiles if p.position == pos and p.ppg is not None and not p.out_all]
            pool.sort(key=lambda p: -(p.ppg or 0.0))
            keep.extend(pool[: max(1, room)])
        ctx.waiver = keep
    return ctx


_CONTEXT_CACHE: list[tuple[tuple, Any, Any, ModelContext]] = []
_CONTEXT_CACHE_MAX = 4


def get_context(
    all_players_df: pd.DataFrame | None,
    lineup_settings: Mapping[str, Any] | None,
    score_column: str,
    *,
    window: SeasonWindow,
    strategy: str,
    waiver_df: pd.DataFrame | None = None,
    params: ModelParams = DEFAULT_PARAMS,
) -> ModelContext:
    """``build_context`` memoized per (frame objects, settings, posture).

    A caller grading many packages for one roster (Trade Hub's gate, the
    counter-offer search) calibrates once. The frames are held so their
    ``id`` cannot be reused while the entry lives."""

    settings_key = repr(sorted((str(k), repr(v)) for k, v in (lineup_settings or {}).items()))
    key = (id(all_players_df), id(waiver_df), score_column, normalize_team_strategy(strategy),
           window.current_week, window.in_season, settings_key, params)
    for entry_key, _a, _w, ctx in _CONTEXT_CACHE:
        if entry_key == key:
            return ctx
    ctx = build_context(all_players_df, lineup_settings, score_column, window=window,
                        strategy=strategy, waiver_df=waiver_df, params=params)
    _CONTEXT_CACHE.append((key, all_players_df, waiver_df, ctx))
    del _CONTEXT_CACHE[:-_CONTEXT_CACHE_MAX]
    return ctx


def _bye_for(ctx: ModelContext, team: str) -> int | None:
    code = _text(team).upper()
    if not code:
        return None
    if code not in ctx.byes:
        try:
            ctx.byes[code] = nfl_schedule.team_bye_week(code, ctx.season)
        except Exception:
            ctx.byes[code] = None
    return ctx.byes[code]


def profile_roster(df: pd.DataFrame, ctx: ModelContext, *, free_agent: bool = False) -> list[PlayerPoints]:
    """One ``PlayerPoints`` per row of a roster/pool frame."""

    out: list[PlayerPoints] = []
    if df is None or df.empty:
        return out
    params = ctx.params
    seen: set[str] = set()
    for row in frame_records(df):
        pid = _text(row.get("player_id"))
        if not pid or pid in seen:
            continue
        seen.add(pid)
        pos = _text(row.get("position")).upper()
        status, injury = _text(row.get("status")), _text(row.get("injury_status"))
        absence = estimate_injury_absence(
            status,
            injury,
            body_part=row.get("injury_body_part"),
            notes=row.get("injury_notes"),
            window=ctx.window,
        )
        ruled_out = is_ruled_out(status, injury)
        out_all = bool(ruled_out and absence is None)
        value = _num(row.get(ctx.score_column), None)
        if value is None:
            value = _num(row.get("value_score"), _num(row.get("dynasty_score"), 0.0)) or 0.0
        ppg: float | None = None
        basis = "none"
        if pos in SCORED_POSITIONS:
            proj = _num(row.get("proj_ppg"))
            games = _num(row.get("games_played"), 0.0) or 0.0
            obs = _num(row.get("ppg"))
            prior, _from_data = _value_curve_ppg(ctx.curves, pos, max(0.0, float(value)))
            if proj is not None:
                ppg, basis = max(0.0, _league_scored(proj, row, pos, ctx.scoring)), "projection"
            elif obs is not None and games >= params.min_games_for_observed:
                obs = _league_scored(obs, row, pos, ctx.scoring)
                ppg = max(0.0, (games * obs + params.prior_games * prior) / (games + params.prior_games))
                basis = "season_average"
            elif value > 0:
                ppg, basis = max(0.0, prior), "value_estimate"
        sd = 0.0
        if ppg is not None:
            weekly = _num(row.get("proj_sd"))
            if weekly is None:
                low, high = player_projections._v2_range(max(0.0, ppg), pos, "low")
                weekly = max(0.5, (high - low) / 2.0)
            sd = float(weekly) * params.sd_inflation.get(basis, 1.3)
        age = _num(row.get("age"))
        if age is not None and age >= 99:
            age = None
        out.append(
            PlayerPoints(
                player_id=pid,
                name=_text(row.get("name")) or pid,
                position=pos,
                team=_text(row.get("team")),
                age=age,
                ppg=ppg,
                sd=sd,
                basis=basis,
                bye_week=_bye_for(ctx, _text(row.get("team"))) if ctx.window.in_season else None,
                absence=absence,
                out_all=out_all,
                free_agent=free_agent,
                value=float(value),
                status_text=injury or status,
            )
        )
    return out


# --- lineup solver -----------------------------------------------------------


def solve_lineup(
    candidates: Sequence[tuple[str, str, float]],
    slots: Mapping[str, int],
) -> tuple[float, list[tuple[str, str, float, str]], dict[str, int]]:
    """Best lineup for one week. ``candidates``: (player_id, position, points).

    Dedicated slots take the best at their position, then the flex slots from
    narrowest to widest take the best remaining eligible: optimal for this
    nested slot structure (an exchange argument), and what
    ``team_eval.suggest_optimal_lineup`` does. Returns (points, starters as
    (id, position, points, slot), open slot counts)."""

    order = sorted(candidates, key=lambda c: (-c[2], c[0]))
    used: set[str] = set()
    starters: list[tuple[str, str, float, str]] = []
    open_slots: dict[str, int] = {}

    def take(eligible: Iterable[str], slot_name: str, limit: int) -> None:
        eligible = tuple(eligible)
        got = 0
        for pid, pos, pts in order:
            if got >= limit:
                break
            if pid in used or pos not in eligible or pts <= 0:
                continue
            used.add(pid)
            starters.append((pid, pos, pts, slot_name))
            got += 1
        if got < limit:
            open_slots[slot_name] = open_slots.get(slot_name, 0) + (limit - got)

    for pos in SCORED_POSITIONS:
        take((pos,), pos, int(slots.get(pos, 0) or 0))
    for name in _FLEX_ORDER:
        take(_FLEX_ELIGIBLE[name], name, int(slots.get(name, 0) or 0))
    return sum(s[2] for s in starters), starters, open_slots


# --- weekly engine -----------------------------------------------------------


@dataclass
class SideResult:
    expected: float = 0.0
    weekly: list[float] = field(default_factory=list)
    by_position: dict[str, float] = field(default_factory=dict)
    open_slot_weeks: dict[str, float] = field(default_factory=dict)
    pickups: dict[str, float] = field(default_factory=dict)  # FA id -> expected weeks started


def _candidates(players: Sequence[PlayerPoints], week: int, current_week: int, fa_reliability: float):
    """Deterministic part: (id, pos, points, p_available, is_fa)."""

    out = []
    for p in players:
        if p.ppg is None:
            continue
        pts = p.ppg * (fa_reliability if p.free_agent else 1.0)
        out.append((p.player_id, p.position, pts, p.availability(week, current_week), p.free_agent))
    return out


def run_weeks(
    before: Sequence[PlayerPoints],
    after: Sequence[PlayerPoints],
    ctx: ModelContext,
    *,
    fill: str = "waiver",
    pool_override: Sequence[PlayerPoints] | None = None,
    weeks: Sequence[int] | None = None,
    ignore_availability: bool = False,
) -> tuple[SideResult, SideResult, dict[str, Any]]:
    """Expected lineup points for both rosters, week by week, sharing one
    availability scenario so the delta's variance accounts for their overlap."""

    params = ctx.params
    current_week = max(1, ctx.window.current_week)
    weeks = list(weeks) if weeks is not None else ctx.weeks
    # fill: "waiver" = the league's real free-agent pool; "market" = the
    # market replacement level at every position (also the fallback when no
    # pool was provided; flagged in the output); "none" = no pickups at all.
    use_pool = fill == "waiver" and ctx.waiver_provided
    pool = (list(pool_override) if pool_override is not None else list(ctx.waiver)) if use_pool else []
    phantom: list[PlayerPoints] = []
    if fill == "market" or (fill == "waiver" and not ctx.waiver_provided):
        for pos in SCORED_POSITIONS:
            room = int(ctx.slots.get(pos, 0) or 0) + _flex_positions(ctx.slots).get(pos, 0)
            for i in range(room):
                phantom.append(
                    PlayerPoints(
                        player_id=f"__repl_{pos}_{i}", name=f"Replacement {pos}", position=pos, team="",
                        age=None, ppg=ctx.market_replacement[pos], sd=0.0, basis="replacement",
                        bye_week=None, absence=None, out_all=False, free_agent=True,
                    )
                )
    extra = pool + phantom
    # Phantom replacement is a level, not a claim that can fail.
    fa_rel = {p.player_id: (1.0 if p.basis == "replacement" else params.fa_reliability) for p in extra}

    res_b, res_a = SideResult(), SideResult()
    var_delta = 0.0
    scen_weeks = 0
    symdiff_weeks: dict[str, int] = {}
    pos_delta_weeks: dict[str, list[float]] = {}

    def cands(players, week):
        rows = []
        for pid, pos, pts, p, is_fa in _candidates(players, week, current_week, 1.0):
            rows.append((pid, pos, pts, 1.0 if ignore_availability else p, is_fa))
        return rows

    for week in weeks:
        cb = cands(before, week)
        ca = cands(after, week)
        ce = []
        for p in extra:
            for pid, pos, pts, av, _ in _candidates([p], week, current_week, 1.0):
                ce.append((pid, pos, pts * fa_rel[pid], 1.0, True))
        # Uncertain = fractional availability among rostered players.
        uncertain: dict[str, float] = {}
        for pid, pos, pts, av, _ in cb + ca:
            if 0.0 < av < 1.0:
                uncertain[pid] = av
        ranked = sorted(uncertain, key=lambda i: -max([c[2] for c in cb + ca if c[0] == i] or [0.0]))
        enumerated = ranked[: params.max_enumerated]
        folded = {pid: uncertain[pid] for pid in ranked[params.max_enumerated:]}

        def points_for(rows, present: dict[str, bool]):
            lst = []
            for pid, pos, pts, av, _ in rows:
                if pid in present:
                    if present[pid]:
                        lst.append((pid, pos, pts))
                elif pid in folded:
                    lst.append((pid, pos, pts * folded[pid]))
                elif av >= 1.0:
                    lst.append((pid, pos, pts))
                # av == 0 -> not startable
            return lst

        wb = wa = 0.0
        e_delta = e_delta2 = 0.0
        bypos_b: dict[str, float] = {}
        bypos_a: dict[str, float] = {}
        open_b: dict[str, float] = {}
        open_a: dict[str, float] = {}
        pick_use: dict[str, float] = {}
        modal_b = modal_a = None
        best_prob = -1.0
        for combo in product((True, False), repeat=len(enumerated)):
            present = dict(zip(enumerated, combo))
            prob = 1.0
            for pid, here in present.items():
                prob *= uncertain[pid] if here else 1.0 - uncertain[pid]
            if prob <= 0.0:
                continue
            tb, sb, ob = solve_lineup(points_for(cb, present) + points_for(ce, {}), ctx.slots)
            ta, sa, oa = solve_lineup(points_for(ca, present) + points_for(ce, {}), ctx.slots)
            wb += prob * tb
            wa += prob * ta
            d = ta - tb
            e_delta += prob * d
            e_delta2 += prob * d * d
            for _id, pos, pts, _slot in sb:
                bypos_b[pos] = bypos_b.get(pos, 0.0) + prob * pts
            for _id, pos, pts, _slot in sa:
                bypos_a[pos] = bypos_a.get(pos, 0.0) + prob * pts
                if _id in fa_rel:
                    pick_use[_id] = pick_use.get(_id, 0.0) + prob
            for slot, n in ob.items():
                open_b[slot] = open_b.get(slot, 0.0) + prob * n
            for slot, n in oa.items():
                open_a[slot] = open_a.get(slot, 0.0) + prob * n
            if prob > best_prob:
                best_prob, modal_b, modal_a = prob, sb, sa
        res_b.weekly.append(wb)
        res_a.weekly.append(wa)
        res_b.expected += wb
        res_a.expected += wa
        var_delta += max(0.0, e_delta2 - e_delta * e_delta)
        if enumerated:
            scen_weeks += 1
        for pos, v in bypos_b.items():
            res_b.by_position[pos] = res_b.by_position.get(pos, 0.0) + v
        for pos, v in bypos_a.items():
            res_a.by_position[pos] = res_a.by_position.get(pos, 0.0) + v
        for pid, v in pick_use.items():
            res_a.pickups[pid] = res_a.pickups.get(pid, 0.0) + v
        for slot, v in open_b.items():
            res_b.open_slot_weeks[slot] = res_b.open_slot_weeks.get(slot, 0.0) + v
        for slot, v in open_a.items():
            res_a.open_slot_weeks[slot] = res_a.open_slot_weeks.get(slot, 0.0) + v
        for pos in SCORED_POSITIONS:
            pos_delta_weeks.setdefault(pos, []).append(bypos_a.get(pos, 0.0) - bypos_b.get(pos, 0.0))
        # Projection spread only for the players whose presence differs.
        if modal_b is not None and modal_a is not None:
            ids_b = {s[0] for s in modal_b}
            ids_a = {s[0] for s in modal_a}
            for pid in ids_a ^ ids_b:
                symdiff_weeks[pid] = symdiff_weeks.get(pid, 0) + 1
    sd_by_id = {p.player_id: p.sd for p in list(before) + list(after) + extra}
    # Projection spread, only for players whose presence differs between the
    # two lineups (shared starters cancel): independent game-to-game noise
    # adds per week; the persistent share of the baseline error does not
    # average out across the weeks he is in the difference.
    proj_var_weekly = sum((sd_by_id.get(pid, 0.0) ** 2) * n for pid, n in symdiff_weeks.items())
    proj_var_persistent = sum(
        (params.baseline_error_share * sd_by_id.get(pid, 0.0) * n) ** 2 for pid, n in symdiff_weeks.items()
    )
    meta = {
        "avail_variance": var_delta,
        "proj_var_weekly": proj_var_weekly,
        "proj_var_persistent": proj_var_persistent,
        "scenario_weeks": scen_weeks,
        "pos_delta_weeks": pos_delta_weeks,
    }
    return res_b, res_a, meta


# --- the public evaluation ---------------------------------------------------


_BEFORE_SIDE_CACHE: list[tuple[Any, Any, int, list[PlayerPoints], dict[int, list[PlayerPoints]]]] = []
_BEFORE_SIDE_CACHE_MAX = 4


def _before_side(before_df: pd.DataFrame, ctx: ModelContext) -> tuple[list[PlayerPoints], dict[int, list[PlayerPoints]]]:
    """``profile_roster(before_df, ctx)`` plus its per-year aged copies, memoized.

    Every candidate trade for one roster shares the same "before" frame, so its
    profile (and age-curved projection) is a per-roster cost, not a per-trade
    one. ``PlayerPoints`` is frozen, so sharing the objects is safe; the
    frame and context are held so their ``id`` cannot be reused."""

    for cached_df, cached_ctx, cached_len, profiles, aged in _BEFORE_SIDE_CACHE:
        if cached_df is before_df and cached_ctx is ctx and cached_len == len(before_df):
            return profiles, aged
    profiles = profile_roster(before_df, ctx)
    aged: dict[int, list[PlayerPoints]] = {}
    _BEFORE_SIDE_CACHE.append((before_df, ctx, len(before_df), profiles, aged))
    del _BEFORE_SIDE_CACHE[:-_BEFORE_SIDE_CACHE_MAX]
    return profiles, aged


def _aged(p: PlayerPoints, years: int) -> PlayerPoints:
    if p.ppg is None or p.age is None:
        return p
    now = age_multiplier(p.position, p.age)
    then = age_multiplier(p.position, p.age + years)
    factor = (then / now) if now > 0 else 1.0
    return PlayerPoints(**{**p.__dict__, "ppg": p.ppg * factor, "sd": p.sd * factor, "age": p.age + years,
                           "absence": None, "out_all": False, "bye_week": None})


def _name_list(items: Sequence[str], limit: int = 2) -> str:
    items = [i for i in items if i]
    return " or ".join(items[:limit])


def evaluate_trade(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    ctx: ModelContext,
    *,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    raw_value_delta: float,
    consolidation_adjustment: float = 0.0,
    healthy_restore: float = 0.0,
    asset_value=lambda a: float(a.get("score") or a.get("value_score") or 0),
) -> dict[str, Any]:
    """Expected lineup points before vs after, and the one combined score.

    Three lineup deltas, all expected points over the remaining weeks:

    ``dPts``   the real one: league slots, byes, injuries (availability
               probability), depth, and holes filled from the real waiver pool.
    ``dPts0``  the idealized one the market implicitly assumes: nobody is
               hurt, nobody is on bye, any hole is filled at the market's
               replacement level.
    ``F``      = dPts - dPts0, the roster-context "friction": what the market
               cannot see about THIS roster.

    ``trade_score`` (value units, same scale as ``raw_value_delta``)::

        raw_value_delta + healthy_restore + consolidation_adjustment
          + (w_now - 1) * k * dPts          # posture: extra weight on real points
          + (w_fut - 1) * d_value_future    # posture: weight on market future capital
          + k * F                           # friction at full weight

    which equals ``(w_now-1)*k*dPts0 + w_now*k*F`` for the lineup part. A
    surplus asset gets no credit beyond its market price (selling it IS the
    liquidation), a hole costs its full points.

    ``healthy_restore``: the market lists a short-term-injured player at a
    risk-discounted value; his absence is priced here in points, so the
    discount is added back (``asset_value`` must then return healthy values)."""

    params = ctx.params
    w_now, w_fut = POSTURE_WEIGHTS.get(ctx.strategy, POSTURE_WEIGHTS["retool"])
    weeks = ctx.weeks
    rem = len(weeks)
    k = ctx.value_per_point

    before, before_aged = _before_side(before_df, ctx)
    after = profile_roster(after_df, ctx)
    b, a, meta = run_weeks(before, after, ctx)
    b0, a0, _ = run_weeks(before, after, ctx, fill="market", ignore_availability=True)

    delta_pts = a.expected - b.expected
    ideal_pts = a0.expected - b0.expected
    friction_pts = delta_pts - ideal_pts

    # Market split of the assets' value into this-season and future shares.
    def now_share(asset):
        if asset.get("asset_type") != "player":
            return 0.0
        return asset_value(asset) * CURRENT_SEASON_VALUE_SHARE * rem / FANTASY_SEASON_WEEKS

    d_now_market = sum(now_share(x) for x in receive_assets) - sum(now_share(x) for x in send_assets)
    d_total = sum(asset_value(x) for x in receive_assets) - sum(asset_value(x) for x in send_assets)
    d_future = d_total - d_now_market

    posture_now = (w_now - 1.0) * k * delta_pts
    posture_future = (w_fut - 1.0) * d_future
    friction_adj = k * friction_pts

    # Next seasons (informational lineup effect, age-curved, healthy, market
    # replacement as fill-in). Not added to the score: future value is the
    # market's own (already age-curved and posture-priced upstream).
    fut_delta_pts = 0.0
    for y in range(1, params.future_years + 1):
        if y not in before_aged:
            before_aged[y] = [_aged(p, y) for p in before]
        fb = before_aged[y]
        fa = [_aged(p, y) for p in after]
        yb, ya, _ = run_weeks(fb, fa, ctx, fill="market", weeks=[1], ignore_availability=True)
        fut_delta_pts += (params.future_discount ** y) * FANTASY_SEASON_WEEKS * (ya.expected - yb.expected)

    trade_score = (
        raw_value_delta + healthy_restore + consolidation_adjustment + posture_now + posture_future + friction_adj
    )

    # Uncertainty (value units). Two different questions. The OUTCOME range
    # (what the lineup points could actually be) includes game-to-game noise.
    # CONFIDENCE in the verdict is about the evaluation, so it uses only what
    # could make the expected points wrong: injury timing and the persistent
    # error in each player's baseline (game-to-game luck averages out of an
    # expectation).
    avail_var = meta["avail_variance"]
    proj_var_total = meta["proj_var_weekly"] + meta["proj_var_persistent"]
    sigma_pts = math.sqrt(max(0.0, avail_var + proj_var_total))
    sigma_est_pts = math.sqrt(max(0.0, avail_var + meta["proj_var_persistent"]))
    sigma_now = max(w_now, 1.0) * k * sigma_est_pts
    sigma_future = abs(w_fut) * k * params.future_sigma_share * abs(fut_delta_pts)
    gross = sum(asset_value(x) for x in list(send_assets) + list(receive_assets))
    sigma_market = params.market_noise_share * gross
    sigma = math.sqrt(sigma_now ** 2 + sigma_future ** 2 + sigma_market ** 2) or 1.0
    z = trade_score / sigma
    # Never claim certainty: the inputs are projections and estimates.
    p_right = min(_phi(abs(z)), MAX_CONFIDENCE)
    confidence_label = (
        "High confidence" if p_right >= params.confidence_high
        else "Moderate confidence" if p_right >= params.confidence_moderate
        else "Close call"
    )

    # Per-position story.
    positions: dict[str, dict[str, Any]] = {}
    for pos in SCORED_POSITIONS:
        pb, pa = b.by_position.get(pos, 0.0), a.by_position.get(pos, 0.0)
        wk = meta["pos_delta_weeks"].get(pos, [])
        positions[pos] = {
            "ros_points_before": round(pb, 1),
            "ros_points_after": round(pa, 1),
            "ros_delta": round(pa - pb, 1),
            "per_week_delta": round((pa - pb) / rem, 2) if rem else 0.0,
            "weeks_worse": sum(1 for d in wk if d < -0.5),
        }
    worst_pos = min(SCORED_POSITIONS, key=lambda p: positions[p]["ros_delta"])
    worst = positions[worst_pos]

    pickup = None
    if worst["ros_delta"] < -1.0 and ctx.waiver:
        pool = [p for p in ctx.waiver if p.position == worst_pos]
        pool.sort(key=lambda p: (-(p.ppg or 0.0), p.player_id))
        if pool:
            best = pool[0]
            _, a_one, _ = run_weeks(before, after, ctx, pool_override=[best])
            _, a_none, _ = run_weeks(before, after, ctx, fill="none")
            pickup = {
                "player_id": best.player_id,
                "name": best.name,
                "position": best.position,
                "expected_ppg": round((best.ppg or 0.0) * params.fa_reliability, 1),
                "points_recovered_ros": round(a_one.expected - a_none.expected, 1),
            }

    this_week = round(a.weekly[0] - b.weekly[0], 2) if a.weekly else 0.0
    basis_counts: dict[str, int] = {}
    for p in after:
        if p.ppg is not None:
            basis_counts[p.basis] = basis_counts.get(p.basis, 0) + 1
    open_after = {s: v for s, v in a.open_slot_weeks.items() if v > 0.01}
    new_open = {
        s: round(v - b.open_slot_weeks.get(s, 0.0), 2)
        for s, v in open_after.items()
        if v - b.open_slot_weeks.get(s, 0.0) > 0.01
    }

    result = {
        "available": True,
        "model_version": MODEL_VERSION,
        "posture": ctx.strategy,
        "weights": {"now": w_now, "future": w_fut},
        "weeks": {"first": weeks[0] if weeks else 0, "last": weeks[-1] if weeks else 0, "count": rem},
        "value_per_point": round(k, 2),
        "points": {
            "ros_before": round(b.expected, 1),
            "ros_after": round(a.expected, 1),
            "ros_delta": round(delta_pts, 1),
            "per_week_delta": round(delta_pts / rem, 2) if rem else 0.0,
            "this_week_delta": this_week,
            "ideal_delta": round(ideal_pts, 1),
            "friction_delta": round(friction_pts, 1),
            "future_delta": round(fut_delta_pts, 1),
        },
        "positions": positions,
        "worst_position": worst_pos if worst["ros_delta"] < -1.0 else None,
        "pickup": pickup,
        "new_open_slot_weeks": new_open,
        "waiver_pool_used": bool(ctx.waiver_provided),
        "components": {
            "raw_value_delta": round(raw_value_delta),
            "consolidation": round(consolidation_adjustment),
            "injury_value_restore": round(healthy_restore),
            "posture_now": round(posture_now),
            "posture_future": round(posture_future),
            "roster_friction": round(friction_adj),
        },
        "win_now_delta": round(w_now * k * delta_pts),
        "future_delta": round(w_fut * d_future),
        "trade_score": round(trade_score),
        "uncertainty": {
            "sigma": round(sigma),
            "sigma_points": round(sigma_pts, 1),
            "estimate_sigma_points": round(sigma_est_pts, 1),
            "availability_variance": round(avail_var, 2),
            "projection_variance": round(proj_var_total, 2),
            "z": round(z, 2),
        },
        "confidence_pct": round(p_right * 100, 1),
        "confidence_label": confidence_label,
        "basis_counts": basis_counts,
        "calibration": ctx.calibration,
    }
    result["explanation"] = explain(result, ctx)
    return result


def explain(result: Mapping[str, Any], ctx: ModelContext) -> str:
    pts = result["points"]
    weeks = result["weeks"]
    span = f"Weeks {weeks['first']}-{weeks['last']}"
    pos = result.get("worst_position")
    parts: list[str] = []
    # A position can lose points simply because a flex slot moved to a better
    # player elsewhere; that is only worth saying when the lineup as a whole
    # loses points or a slot is left open.
    if pos and pts["ros_delta"] >= 0 and not result.get("new_open_slot_weeks"):
        pos = None
    if pos:
        row = result["positions"][pos]
        n = row["weeks_worse"]
        parts.append(
            f"You lose ~{abs(row['per_week_delta']):.1f} pts/week at {pos}"
            + (f" for {n} week{'s' if n != 1 else ''}" if n else "")
        )
        pickup = result.get("pickup")
        if pickup and pickup["points_recovered_ros"] > 0.5:
            loss = abs(row["ros_delta"])
            recovered = pickup["points_recovered_ros"]
            if recovered >= 0.5 * loss:
                parts[-1] += (
                    f" unless you pick up {pickup['name']} (~{pickup['expected_ppg']:.1f} ppg, "
                    f"worth ~{recovered:.0f} pts)"
                )
            else:
                parts[-1] += (
                    f" (the best free agent, {pickup['name']}, ~{pickup['expected_ppg']:.1f} ppg, "
                    f"only recovers ~{recovered:.0f} pts)"
                )
        elif not ctx.waiver_provided:
            parts[-1] += " (no waiver data, replacement level assumed)"
        parts[-1] += "; "
    sign = "+" if pts["ros_delta"] >= 0 else "-"
    parts.append(f"net {sign}{abs(pts['ros_delta']):.0f} lineup pts over {span}")
    if pts["this_week_delta"]:
        tw = pts["this_week_delta"]
        parts.append(f" ({'+' if tw >= 0 else '-'}{abs(tw):.1f} this week)")
    parts.append(
        f". Posture {result['posture'].replace('_', ' ')} weights real lineup points x{result['weights']['now']:.2f}."
    )
    return "".join(parts)


def future_note() -> str:
    return "Future seasons use age-curved projections, not a forecast of your roster."
