"""Calibration layer for weekly projections and the probabilities built on them.

The usage empirical-Bayes estimator in ``modules.player_projections`` forecasts
PPR points. Everything user-facing (matchup totals, win probability, start/sit,
trade lineup model) is in a LEAGUE's own scoring. This module is the one place
that holds (a) the conversion from PPR to a league's scoring and (b) every
fitted calibration constant for the 2026-11 projection calibration pass, so a
future refit changes numbers here and nowhere else.

Every constant below was fitted/validated with
``scripts/projection_calibration_backtest.py`` (re-run it to refresh them; its
output table is the "how it was fit" record). The procedure for each: fit on
earlier data, score on later data the fit never saw, ship only if the held-out
metric improved. The measured before/after numbers are in the module constants'
comments and in ``docs/projection-calibration-2026-11.md``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional

# ---------------------------------------------------------------------------
# 1. League scoring conversion
# ---------------------------------------------------------------------------

# What Sleeper's ``pts_ppr`` is made of (recovered by least squares on 2026
# weekly stats, max abs error 0.009 pts over 3,525 player-games): the same
# stat keys a league's ``scoring_settings`` uses, so
#     league_points - ppr_points = sum over stats of (league_weight - ppr_weight) * stat
# is exact for every stat we retain on weekly rows.
PPR_BASE_WEIGHTS: Dict[str, float] = {
    "rec": 1.0,
    "rec_yd": 0.1,
    "rec_td": 6.0,
    "rush_yd": 0.1,
    "rush_td": 6.0,
    "pass_yd": 0.04,
    "pass_td": 4.0,
    "pass_int": -1.0,
    "fum_lost": -2.0,
}

# scoring-settings stat key -> weekly-row field (modules.sleeper's retained
# names). Sleeper omits zero stats, so an absent field is a real 0.
_STAT_FIELD: Dict[str, str] = {
    "rec": "receptions",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds",
    "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds",
    "pass_yd": "passing_yards",
    "pass_td": "passing_tds",
    "pass_int": "passing_interceptions",
    "fum_lost": "fumbles_lost",
    "pass_cmp": "passing_completions",
    "pass_att": "pass_attempts",
    "rush_att": "rush_attempts",
    "rec_tgt": "targets",
}
# Per-stat keys outside PPR_BASE_WEIGHTS that are linear in a retained stat.
_LINEAR_EXTRA = ("pass_cmp", "pass_att", "rush_att", "rec_tgt")
# Position-specific per-reception bonuses (TE premium and its RB/WR siblings).
_REC_BONUS_BY_POSITION = {"TE": "bonus_rec_te", "RB": "bonus_rec_rb", "WR": "bonus_rec_wr"}
# Yardage bonuses: (scoring key, stat field, threshold). Sleeper pays each
# threshold bonus when the game total reaches it.
_THRESHOLD_BONUSES = (
    ("bonus_pass_yd_300", "passing_yards", 300.0),
    ("bonus_pass_yd_400", "passing_yards", 400.0),
    ("bonus_rush_yd_100", "rushing_yards", 100.0),
    ("bonus_rush_yd_200", "rushing_yards", 200.0),
    ("bonus_rec_yd_100", "receiving_yards", 100.0),
    ("bonus_rec_yd_200", "receiving_yards", 200.0),
)
# Positions whose scoring we convert. K has no per-game kick detail retained
# (distance-based scoring), so a kicker's number is left in PPR (identical for
# the standard kicker scoring in nearly every league).
CONVERTIBLE_POSITIONS = ("QB", "RB", "WR", "TE")

# How the per-game league-minus-PPR difference is averaged over a player's
# games. Same recency half-life as the usage estimate (player_projections
# _V2_SHRINKAGE) so the conversion tracks the same role; ``DELTA_SHRINK_K``
# pulls the average toward the position's structural mean when few games are
# on file (n / (n + k) of the player's own difference is kept).
DELTA_HALF_LIFE_WEEKS = 6.0
DELTA_SHRINK_K = 0.0


def numeric_scoring_settings(raw: Mapping[str, Any] | None) -> Dict[str, float]:
    """A league's ``scoring_settings`` reduced to finite numbers (the rest of
    a Sleeper league payload is not scoring)."""

    out: Dict[str, float] = {}
    if not isinstance(raw, Mapping):
        return out
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = float(value)
        if math.isfinite(number):
            out[str(key)] = number
    return out


def _field(row: Mapping[str, Any], name: str) -> float:
    try:
        value = float(row.get(name) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return value if value == value else 0.0


def has_core_scoring(scoring: Mapping[str, float] | None) -> bool:
    """True when the dict is a real scoring blob (it names at least one core
    stat). An absent key inside a real blob means the league pays 0 for it
    (Sleeper omits unscored stats), but an empty/unparsed blob is "unknown",
    never "pays nothing", and is left in PPR."""

    return bool(scoring) and any(key in scoring for key in PPR_BASE_WEIGHTS)


def is_ppr_scoring(scoring: Mapping[str, float] | None) -> bool:
    """True when converting would change nothing (no scoring given, or it is
    exactly Sleeper PPR on every key we convert)."""

    if not has_core_scoring(scoring):
        return True
    for key, base in PPR_BASE_WEIGHTS.items():
        if abs(float(scoring.get(key, 0.0)) - base) > 1e-9:
            return False
    keys = set(_LINEAR_EXTRA) | {b for b in _REC_BONUS_BY_POSITION.values()} | {k for k, _f, _t in _THRESHOLD_BONUSES}
    return all(abs(float(scoring.get(key, 0.0))) <= 1e-9 for key in keys)


def game_scoring_delta(row: Mapping[str, Any], position: str, scoring: Mapping[str, float]) -> float:
    """League-scored minus PPR points for ONE game row (box-score fields as
    retained on ``sleeper`` weekly rows). Exact for every stat we have; stats
    not retained (first downs, long-play bonuses) contribute 0, which is the
    documented gap (``unsupported_scoring_keys``)."""

    position = str(position or "").upper()
    if position not in CONVERTIBLE_POSITIONS or not has_core_scoring(scoring):
        return 0.0
    delta = 0.0
    for key, base in PPR_BASE_WEIGHTS.items():
        weight = float(scoring.get(key, 0.0))
        if weight != base:
            delta += (weight - base) * _field(row, _STAT_FIELD[key])
    for key in _LINEAR_EXTRA:
        weight = float(scoring.get(key, 0.0))
        if weight:
            delta += weight * _field(row, _STAT_FIELD[key])
    pass_inc = float(scoring.get("pass_inc", 0.0))
    if pass_inc:
        delta += pass_inc * max(0.0, _field(row, "pass_attempts") - _field(row, "passing_completions"))
    bonus_key = _REC_BONUS_BY_POSITION.get(position)
    if bonus_key and scoring.get(bonus_key):
        delta += float(scoring[bonus_key]) * _field(row, "receptions")
    for key, field, threshold in _THRESHOLD_BONUSES:
        weight = float(scoring.get(key, 0.0))
        if weight and _field(row, field) >= threshold:
            delta += weight
    return delta


def unsupported_scoring_keys(scoring: Mapping[str, float] | None) -> List[str]:
    """Non-zero scoring keys that move offensive players' points but whose
    stat is not retained per game (so the conversion cannot see them)."""

    gaps = ("fd_rec", "fd_rush", "fd_pass", "rec_fd", "rush_fd", "pass_fd", "pass_2pt", "rush_2pt", "rec_2pt",
            "rec_0_4", "rec_5_9", "rec_10_19", "rec_20_29", "rec_30_39", "rec_40p",
            "rush_40p", "rec_40p", "pass_40p", "bonus_pass_cmp_25", "bonus_rec_yd_150")
    return [key for key in gaps if scoring and abs(float(scoring.get(key, 0.0))) > 1e-9]


def league_scoring_adjustment(
    played_rows: Iterable[Mapping[str, Any]],
    position: str,
    scoring: Mapping[str, float] | None,
    *,
    reference_week: int,
    half_life: float = DELTA_HALF_LIFE_WEEKS,
    shrink_k: float = DELTA_SHRINK_K,
) -> float:
    """Recency-weighted mean per-game (league - PPR) points over a player's
    played games, so ``league_estimate = ppr_estimate + adjustment``.

    ``played_rows`` carry ``week``; ``reference_week`` is the as-of week the
    estimator uses. 0.0 for no scoring given / PPR scoring / no games.
    """

    if is_ppr_scoring(scoring) or str(position or "").upper() not in CONVERTIBLE_POSITIONS:
        return 0.0
    total = weight_sum = 0.0
    games = 0
    for row in played_rows:
        week = row.get("week")
        if week is None:
            continue
        age = max(0, int(reference_week) - int(week))
        weight = 0.5 ** (age / half_life) if half_life else 1.0
        total += weight * game_scoring_delta(row, position, scoring or {})
        weight_sum += weight
        games += 1
    if not games or weight_sum <= 0:
        return 0.0
    mean = total / weight_sum
    return mean * games / (games + shrink_k) if shrink_k else mean


def apply_scoring_to_projection(
    estimate: float, low: float, high: float, adjustment: float
) -> tuple[float, float, float]:
    """Shift a PPR (estimate, low, high) by the scoring adjustment, floored at
    0 like the PPR output (a projection is never negative). The band keeps its
    width: the spread of a league-scored game is the PPR spread times a
    scoring-dependent factor close to 1, and re-deriving it would need
    component-level variances we do not model."""

    if not adjustment:
        return estimate, low, high
    return (
        max(0.0, estimate + adjustment),
        max(0.0, low + adjustment),
        max(0.0, high + adjustment),
    )


# ---------------------------------------------------------------------------
# 2. Win-probability spread
# ---------------------------------------------------------------------------

# The matchup win model sums independent per-starter variances (sd = band
# half-width). Realized outcomes are much noisier than that: shared game
# environment, lineup changes, who actually plays, and point estimates with
# limited skill (actual-vs-projected margin slope 0.80). Scaling the margin's
# SD by this constant fixes it. Fit by minimizing logloss on 7,012 decided
# head-to-heads (180 public Sleeper leagues, 2026 weeks 2-8, league-scored
# estimates): pooled c = 1.70; weeks 2-5 alone gave 1.90, tested on weeks 6-8;
# 5-fold CV by league. Held-out Brier / logloss:
#     league-CV:   0.2230 / 0.6433  ->  0.2154 / 0.6158
#     weeks 6-8:   0.2119 / 0.6111  ->  0.2080 / 0.5994 (c fit on weeks 2-5)
# Extra structure (a lineup-size term, a size exponent) fit to ~nothing
# (c_n: q=0.0; exponent -0.1) and was not shipped: the summed starter
# variances already scale with lineup size and composition. Refit with
# ``scripts/projection_calibration_backtest.py report --items 2``.
WIN_PROB_SPREAD_MULTIPLIER = 1.70


def calibrated_margin_stdev(variance: float) -> float:
    """Standard deviation of a matchup margin from the summed starter
    variances of both teams, widened to its empirical calibration."""

    return WIN_PROB_SPREAD_MULTIPLIER * math.sqrt(max(0.0, float(variance)))


def win_prob_per_point(team_variance: float | None, *, fallback_team_sd: float = 22.0) -> float:
    """d P(win) per lineup point against an evenly matched opponent:
    phi(0) / calibrated margin SD, where both teams carry the same weekly
    variance (``team_variance``, the sum of one lineup's starter variances).
    Falls back to a flat per-team SD when no lineup variance is known."""

    if team_variance is not None and team_variance > 0:
        margin_sd = calibrated_margin_stdev(2.0 * team_variance)
    else:
        margin_sd = math.sqrt(2.0) * fallback_team_sd
    return 0.3989422804014327 / margin_sd


# ---------------------------------------------------------------------------
# 3. Over-dispersion shrink (top tier, by position)
# ---------------------------------------------------------------------------

# Regressing actual on estimate gives slopes of 0.70-0.90 by position in all
# of 2021-26 (QB lowest at ~0.78): the estimator's top tier is too spread out.
# Shrinking the WHOLE range toward the position mean fixes the slope but worsens
# MAE on the all-players pool (low estimates get raised; scoring is right-skewed)
# in 5 of 5 seasons, so the shrink is one-sided: above ``anchor`` (the 70th
# percentile of the position's estimates), estimate -> anchor + slope * (estimate
# - anchor), identity at and below it (continuous, order-preserving within a
# position). Per position (anchor, slope) fitted by OLS of actual on estimate over
# estimates above the anchor, 2021-26 weekly panel (``report --items 3``).
#
# Walk-forward (fit on all earlier seasons, score the next; fold seasons 2022-26):
#   MAE >= 0.01 better in 5/5 seasons on BOTH pools:
#     relevant pool  5.995 5.929 5.988 5.956 6.029 -> 5.852 5.826 5.947 5.873 5.903
#     all played     4.093 3.948 3.961 3.924 4.013 -> 4.027 3.901 3.941 3.885 3.950
#   RMSE better in 4/5 seasons on both pools; QB calibration slope
#   0.78/0.79/0.85/0.78/0.70 -> 0.88/0.83/0.89/0.83/0.75; 68% interval coverage
#   (band recomputed from the shrunk estimate) 0.673-0.694 vs 0.672-0.696 before.
# Not shipped: a QB-specific shrinkage k / half-life (QB MAE 6.248 -> >= 6.237,
# slope unchanged at 0.78, inside noise) and a bigger QB feature set (the usage
# map already uses pass and rush attempts; richer yardage features would just
# re-fit the player's own points).
TOP_SHRINK: Dict[str, tuple] = {
    "QB": (17.58, 0.503),
    "RB": (10.18, 0.734),
    "WR": (9.17, 0.695),
    "TE": (5.12, 0.703),
}


def shrink_top_tier(estimate: float, position: str) -> float:
    """One-sided shrink of the over-dispersed top of a position's estimates
    (see ``TOP_SHRINK``). Identity for K/unknown positions and at/below the
    anchor."""

    params = TOP_SHRINK.get(str(position or "").upper())
    if params is None or estimate <= params[0]:
        return float(estimate)
    anchor, slope = params
    return anchor + slope * (float(estimate) - anchor)


# ---------------------------------------------------------------------------
# 4. Prior-season seeding
# ---------------------------------------------------------------------------

# Last season's games enter the same estimator as extra history, re-aged
# ``PRIOR_SEASON_WEEKS + PRIOR_SEASON_AGE_OFFSET_WEEKS`` weeks (a season plus an
# offseason discount, so they weigh less than any current game). Gives every
# returning player a week-1 projection (there was none) and tightens weeks 2-4.
# Offset chosen from {0, 6, 12, 24} by walk-forward MAE on seasons 2022-26.
# Same-player matched comparison vs current-season-only history, MAE:
#   weeks 2-4: 4.357 4.304 4.030 3.927 4.100 -> 4.272 4.157 3.933 3.911 3.980 (5/5 better)
#   weeks 5-8: neutral (4.076 3.753 4.086 3.948 4.004 -> 4.080 3.751 4.094 3.953 3.984; 3 of 5 worse by <= 0.008)
#   week 1 (new): MAE 4.35-4.77 vs Sleeper's 4.00-4.45; 68% band covers 61-70%
#              by season (65% pooled over 2022-26).
PRIOR_SEASON_WEEKS = 18
PRIOR_SEASON_AGE_OFFSET_WEEKS = 12


def seed_with_prior_season(
    current_rows: Iterable[Mapping[str, Any]] | None,
    prior_rows: Iterable[Mapping[str, Any]] | None,
) -> List[Dict[str, Any]]:
    """Current-season weekly rows preceded by last season's, week-shifted into
    the past (weeks <= 0). With no prior rows the current rows come back
    unchanged."""

    current = [dict(row) for row in (current_rows or []) if isinstance(row, Mapping)]
    shift = PRIOR_SEASON_WEEKS + PRIOR_SEASON_AGE_OFFSET_WEEKS
    seeded = []
    for row in prior_rows or []:
        if not isinstance(row, Mapping) or row.get("week") is None:
            continue
        shifted = dict(row)
        shifted["week"] = int(row["week"]) - shift
        seeded.append(shifted)
    return seeded + current


# ---------------------------------------------------------------------------
# 5. Playoff-odds win-model slope prior
# ---------------------------------------------------------------------------

# P(A beats B) = sigmoid(slope * (zA - zB)) in ``modules.playoff_simulator``. The
# shipped default (1.0) and the per-league MLE are both ~2x too steep against
# every strength proxy; the MLE is also unstable on a few weeks of games. The
# slope is now a MAP estimate with a Normal prior at ``PLAYOFF_SLOPE_PRIOR`` worth
# ``PLAYOFF_SLOPE_PRIOR_GAMES`` games of information (a hierarchical prior
# pooled across leagues). Held-out game Brier, 180 leagues, strength = season-to-
# date points-for z (fit on a league's games before the vantage week, scored on
# its later games; prior mean fit on the OTHER half of leagues):
#   vantage wk4: default 0.2553  MLE 0.2697  MAP(m=100) 0.2336  pooled const 0.2340
#   vantage wk5: default 0.2495  MLE 0.2518  MAP(m=100) 0.2299  pooled const 0.2308
#   vantage wk6: default 0.2447  MLE 0.2390  MAP(m=100) 0.2265  pooled const 0.2279
# Pooled slope on that proxy: 0.35-0.44. On the roster-value proxy the audit
# measured 0.54, so the prior sits between them. Caveat: Roster Power itself
# cannot be replayed historically; revisit after weeks 13-15 give real standings.
PLAYOFF_SLOPE_PRIOR = 0.45
PLAYOFF_SLOPE_PRIOR_GAMES = 100.0
# Average Fisher information per game of the slope at the prior (z-differential
# variance ~2 x p(1-p) ~0.2), turning "prior games" into a ridge strength.
PLAYOFF_SLOPE_FISHER_PER_GAME = 0.4
PLAYOFF_MAX_SLOPE = 1.5
