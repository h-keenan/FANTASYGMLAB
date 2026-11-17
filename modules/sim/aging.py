"""Age curves, progression and retirement for dynasty mode.

Pure and deterministic. The year-over-year multipliers below are calibrated on
the real-history panel the player model already uses
(``calibration/data/panel.json.gz``; reproduce with
``python -m modules.sim.calibration.age_curve``): the median ratio of a
player's next-season points per game to this season's, by position and age,
smoothed and extended past the ages the panel can support. Every draw is keyed
by ``(seed, season, player)`` through ``WorldRng``, so a resumed game and a
replayed one age the league identically.

Nothing here reads real data. The values it moves (``market``, ``mean``) were
frozen into the snapshot by the input door at creation.
"""

from __future__ import annotations

import math
import zlib

# (age, expected next-season PPG multiplier) knots; linear between, clamped to
# the end knots' trend outside. Rookies and 22-year-olds still grow; running
# backs fall off a cliff at 27; quarterbacks and kickers age slowly.
AGE_KNOTS: dict[str, tuple[tuple[float, float], ...]] = {
    "QB": ((21, 1.08), (23, 1.04), (25, 1.01), (28, 1.02), (30, 0.98), (33, 0.94), (36, 0.88), (40, 0.78)),
    "RB": ((21, 1.12), (22, 1.07), (23, 1.00), (24, 0.96), (26, 0.91), (27, 0.84), (28, 0.78), (30, 0.70), (33, 0.58)),
    "WR": ((21, 1.15), (22, 1.07), (23, 1.01), (24, 0.97), (26, 0.96), (28, 0.90), (30, 0.84), (32, 0.74), (35, 0.62)),
    "TE": ((21, 1.04), (22, 1.05), (24, 1.03), (25, 1.00), (26, 0.96), (28, 0.90), (29, 0.83), (31, 0.76), (34, 0.65)),  # slow starters: real TE rookies show no year-2 jump
    "K": ((21, 1.00), (30, 1.02), (35, 0.98), (38, 0.90), (42, 0.78)),
    "DEF": ((21, 1.0), (40, 1.0)),
}
# aging_v 1: kickers hold their level into the late 30s (real kickers and punters play into their 40s), quarterbacks decline slowly
# until the late 30s. Other positions keep the panel-fitted curves above.
AGE_KNOTS_V1: dict[str, tuple[tuple[float, float], ...]] = {
    **AGE_KNOTS,
    "QB": ((21, 1.08), (23, 1.04), (25, 1.02), (30, 1.00), (34, 0.985), (37, 0.95), (40, 0.89), (43, 0.80)),
    "K": ((21, 1.00), (38, 1.00), (40, 0.97), (43, 0.91), (46, 0.84)),
}
# stability_v 1 (aging knots v2): early-career growth. The v0/v1 knots reproduce the panel's median ratio of REALIZED next/this points per game,
# but the sim applies them to the hidden projection and every season then draws its own story around it, so the realized ratio the sim produced
# was 0.83 / 0.79 / 0.88 for a WR 22 / TE 23 / RB 22 against the panel's 1.05 / 1.14 / 1.07 (docs/audits/2026-11-sim-desk-logic-realism-audit.md P1-7).
# The v2 knots are the TRUE talent trajectory, shaped after the long-standing public dynasty aging curves and checked against the panel through the
# realized ratio the engine produces (``calibration/dynasty_distributions.py``, "realized ratio by age band"): running backs are youngest
# (rise to 22-23, flat to 25, a cliff from 26-27), wide receivers keep improving through 24-25 and plateau to 27, tight ends are slow starters that
# peak at 25-28 (the usual "year-3 breakout"), quarterbacks rise to their late 20s and hold into the mid 30s. The panel (TE n = 10 per age) only
# fixes the level of the realized ratios; the shape is the published one, not a fit to a 10-player cell.
AGE_KNOTS_V2: dict[str, tuple[tuple[float, float], ...]] = {
    "QB": ((21, 1.10), (23, 1.06), (25, 1.03), (28, 1.01), (31, 1.00), (34, 0.985), (37, 0.95), (40, 0.89), (43, 0.80)),
    "RB": ((21, 1.28), (22, 1.28), (23, 1.08), (24, 0.97), (25, 0.96), (26, 0.93), (27, 0.78), (28, 0.70), (30, 0.62), (33, 0.52)),
    "WR": ((21, 1.20), (22, 1.17), (23, 1.07), (24, 0.98), (25, 0.90), (26, 0.87), (27, 0.85), (28, 0.82), (30, 0.75), (32, 0.66), (35, 0.55)),
    "TE": ((21, 1.18), (22, 1.22), (23, 1.27), (24, 1.12), (25, 0.98), (26, 0.92), (27, 0.95), (28, 0.90), (29, 0.80), (31, 0.72), (34, 0.60)),
    "K": AGE_KNOTS_V1["K"],
    "DEF": ((21, 1.0), (40, 1.0)),
}
# stability_v 2 (aging knots v3): the v2 shapes were fitted on ages 21-24 only, and the sim's REALIZED next / this ratio for a top-24 player of 27 or more came out far
# below the panel's (RB 0.51-0.56 / WR 0.70-0.73 / TE 0.66-0.74 against 0.71 / 0.88 / 0.97, docs/audits/2026-11-realism-advice-audit-2.md), because the steep v2
# decline from 25 stacked on the REVERSION pull and a weak outcome carry. v3 is flatter from 25 on (a top-24 RB of 27 holds 0.83 of his projection a year instead of
# 0.78, a WR 0.94 instead of 0.85, a TE 1.01 instead of 0.95; QBs and kickers are unchanged). The stronger carry below (``OUTCOME_WEIGHT_V2``) also keeps a young
# player's breakout, so the early-career growth is trimmed a little (RB 22 1.28 -> 1.18, TE 23 1.27 -> 1.20) to keep the realized ratios of 22-year-olds on the panel's.
AGE_KNOTS_V3: dict[str, tuple[tuple[float, float], ...]] = {
    **AGE_KNOTS_V2,
    "RB": ((21, 1.20), (22, 1.18), (23, 1.04), (24, 0.96), (25, 0.97), (26, 0.94), (27, 0.83), (28, 0.75), (30, 0.66), (33, 0.54)),
    "WR": ((21, 1.20), (22, 1.17), (23, 1.07), (24, 1.00), (25, 0.97), (26, 0.95), (27, 0.94), (28, 0.92), (30, 0.85), (32, 0.74), (35, 0.60)),
    "TE": ((21, 1.14), (22, 1.16), (23, 1.20), (24, 1.08), (25, 1.00), (26, 0.98), (27, 1.01), (28, 0.98), (29, 0.92), (31, 0.82), (34, 0.65)),
}
# Age at which retirement starts to be likely, and how fast the hazard climbs.
RETIRE_AGE = {"QB": 38.0, "RB": 31.0, "WR": 34.0, "TE": 34.5, "K": 41.0, "DEF": 99.0}
RETIRE_SCALE = 1.7
MARKET_HALF_LIFE = 0.6  # how much of the PPG change carries into dynasty market value (exponent)
# stability_v 4: a market that follows production. A pool's price of a level of production is steeply convex (log market on log projection: 1.5-1.7 in the
# season-1 pool of RBs and WRs), but a veteran's market only took 0.6 of each year's change, so over 30 seasons the price flattened (WR 1.7 -> 1.3, TE 1.3 -> 0.9)
# and the top 30 markets fell 15 percent with production unchanged. Carrying the change at the pool's own elasticity keeps the price curve where it started.
MARKET_EXP_V4 = 1.5
# stability_v 1: how much of a season's result (realized / projected points per game, centered on the position's typical result) is carried into the
# next projection. A projection is a posterior: last year's production is evidence about talent, so a 22-year-old who broke out is projected higher
# next year, not pulled back to his old number. Weighted by OUTCOME_WEIGHT because one season is also mostly noise (roughly the weight real
# projection systems put on last season's per-game points against the prior, 0.3 to 0.6).
OUTCOME_WEIGHT = 0.5
REVERSION = 0.40  # share of the gap (log projection vs the position's typical starter) closed per year, see game_dynasty.season_outcomes
# stability_v 2: the carry and the pull per position, fitted to the panel's persistence (the correlation between a player's projection change and last season's
# result is 0.66-0.77 in the panel against 0.40-0.50 for stability_v 1) while the level of every position's top 12 and depth stays where the season-1 pool put it.
OUTCOME_WEIGHT_V2 = {"QB": 0.7, "RB": 1.0, "WR": 0.8, "TE": 0.7}
REVERSION_V2 = {"QB": 0.15, "RB": 0.10, "WR": 0.45, "TE": 0.35}
# stability_v 3: WR / TE persistence (docs/audits/2026-11-projections-backtest.md, Part B and Round 2). Against 11 real seasons the top-12 WR / TE next / this ppg tail was
# too fat (p10 0.51 / 0.52 against 0.61 / 0.58, share under 0.7 28% / 27% against 17% / 19%, WR median 0.84 against 0.875) with too many breakouts and busts. The cause is the
# pull toward the typical starter (``REVERSION_V2``): a receiver or tight end whose projection sits above a typical starter lost 45% / 35% of the gap every year ON TOP of his
# age curve, so a star's projection fell before his season did and the next year's ratio carried two drops. v3 keeps the carry (``OUTCOME_WEIGHT_V2``) and lowers the pull for
# WR / TE only (QB and RB are within the real interval already and keep the v2 values). A yearly projection redraw sd (0.10) and a stronger carry were tried and did nothing
# measurable, so they are not part of v3.
REVERSION_V3 = {**REVERSION_V2, "WR": 0.25, "TE": 0.30}
OUTCOME_CLIP = (-1.0, 0.6) # a 70-point season does not become next year's projection; a lost job (collapse) is remembered at most this hard
FUTURE_YEARS = 4
FUTURE_DISCOUNT = 0.9
MIN_FACTOR, MAX_FACTOR = 0.35, 1.3


def stable_key(text: str) -> int:
    """A process-independent integer for an id (``hash()`` is salted per run)."""

    return zlib.crc32(str(text).encode("utf-8")) & 0x7FFFFFFF


def age_mult(pos: str, age: float, v: int = 0) -> float:
    """Expected multiplier on next season's PPG for a player of ``age`` now (``v`` = the game's aging_v)."""

    table = AGE_KNOTS_V3 if v >= 3 else AGE_KNOTS_V2 if v >= 2 else AGE_KNOTS_V1 if v >= 1 else AGE_KNOTS
    knots = table.get(pos) or table["WR"]
    if age <= knots[0][0]:
        return knots[0][1]
    for (a0, m0), (a1, m1) in zip(knots, knots[1:]):
        if age <= a1:
            return m0 + (m1 - m0) * (age - a0) / (a1 - a0)
    (a0, m0), (a1, m1) = knots[-2], knots[-1]
    slope = (m1 - m0) / (a1 - a0)
    return max(0.3, m1 + slope * (age - a1))


def future_factor(pos: str, age: float, years: int = FUTURE_YEARS) -> float:
    """Long-horizon value multiplier: the discounted average of the player's
    expected production over the next ``years`` seasons relative to holding
    his current level. About 1.0 for a prime-age player, well above for a
    young riser, well below for an aging running back."""

    level, total, weight = 1.0, 0.0, 0.0
    a = float(age)
    for t in range(years):
        level *= age_mult(pos, a)
        w = FUTURE_DISCOUNT ** t
        total += w * level
        weight += w
        a += 1.0
    return max(MIN_FACTOR, min(MAX_FACTOR, total / weight))


def horizon_value(pos: str, age: float, market: float) -> float:
    """The dynasty (long-horizon) side of a player's worth: the market value
    (already a dynasty number from the input door) bent by his age curve.
    Dampened, because the market value already embeds some of the age."""

    return max(0.0, min(100.0, market * future_factor(pos, age) ** 0.6))


def retire_prob(pos: str, age: float, quality: float) -> float:
    """Chance a player retires this offseason. ``quality`` is 0 (replacement) to
    1 (star): stars play longer."""

    start = RETIRE_AGE.get(pos, 34.0) + 2.0 * max(0.0, min(1.0, quality))
    return 1.0 / (1.0 + math.exp(-(float(age) - start) / RETIRE_SCALE))


# --- aging_v 1 retirement: a position age hazard x role x recent production, plus a small career-ending injury floor ----------------
# Logistic hazard per offseason, centred at HAZ_MID[pos] (years) with width HAZ_SCALE[pos]; a starter's centre sits ROLE_YEARS above
# and a deep reserve's ROLE_YEARS below the neutral one, a falling production level (this offseason's PPG ratio) pulls it earlier,
# stars (market) play a little longer. No hard age cutoff: every age has a nonzero chance, no age a certainty.
HAZ_MID = {"QB": 36.0, "RB": 30.2, "WR": 33.9, "TE": 36.3, "K": 37.5, "DEF": 99.0}
HAZ_SCALE = {"QB": 2.5, "RB": 1.7, "WR": 1.9, "TE": 1.9, "K": 1.3, "DEF": 1.0}
ROLE_YEARS = {"QB": 2.0, "RB": 2.5, "WR": 2.5, "TE": 2.5, "K": 1.2}
DECLINE_YEARS = {"K": 1.0}  # years earlier per 20% production drop (capped at 2 x); default 3.0
STAR_YEARS = 1.0
INJURY_FLOOR = {"QB": 0.008, "RB": 0.022, "WR": 0.012, "TE": 0.014, "K": 0.002, "DEF": 0.0}  # career-ending injury, per offseason


def retire_prob_v1(pos: str, age: float, role: float, quality: float, ratio: float = 1.0) -> float:
    """aging_v 1: chance a player retires this offseason. ``role`` 0 (deep reserve) to 1 (starter), ``quality`` 0..1 (market),
    ``ratio`` the player's new / old PPG (a collapsing player is on his way out)."""

    if pos == "DEF":
        return 0.0
    mid = HAZ_MID.get(pos, 32.0) + ROLE_YEARS.get(pos, 2.5) * (2.0 * max(0.0, min(1.0, role)) - 1.0) + STAR_YEARS * max(0.0, min(1.0, quality))
    mid -= DECLINE_YEARS.get(pos, 3.0) * min(2.0, max(0.0, (1.0 - ratio) / 0.2))
    z = (float(age) - mid) / HAZ_SCALE.get(pos, 1.9)
    age_p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
    inj = INJURY_FLOOR.get(pos, 0.01) if age >= 23 else 0.0
    return 1.0 - (1.0 - age_p) * (1.0 - inj)


def progress(
    pos: str, age: float, mean: float, sd: float, market: float, z: float, u_ret: float, mult: float | None = None,
    flat_k: bool = False, aging_v: int = 0, role: float = 0.5, knots_v: int | None = None, outcome: float = 0.0, ceiling: float | None = None, market_exp: float | None = None,
) -> tuple[float, float, float, float, bool]:
    """One offseason for one player. ``z`` is a standard normal and ``u_ret`` a
    uniform from the player's own stream. ``mult`` replaces the plain age curve for a
    player with his own development curve (a generated rookie, see ``scouting``). ``knots_v`` picks the age-knot
    generation (default: ``aging_v``); ``ceiling`` (stability_v 1) is the position's best projection in the league's first season, which growth cannot run past; ``outcome`` is the stability_v 1 feedback: the log of how the season just played
    went against his projection (centered on the position), already weighted by ``OUTCOME_WEIGHT``, so a breakout carries into next year's projection and a bust does too.
    Returns ``(age, mean, sd, market, retired)`` for next season."""

    if mult is None:
        mult = age_mult(pos, age, aging_v if knots_v is None else knots_v)
        if flat_k and pos == "K":  # dynasty_v 3: kickers hold their level until their late decline (the plain curve compounds +2% a year)
            mult = min(mult, 1.0)
    if ceiling and mult > 1.0:  # stability_v 1: growth has diminishing returns as a projection nears the best the league has ever had
        mult = 1.0 + (mult - 1.0) * max(0.0, 1.0 - (mean / ceiling) ** 2)
    spread = 0.10 if pos != "K" else 0.06
    noise = math.exp(spread * z - 0.5 * spread * spread)
    new_mean = max(0.5, mean * mult * noise * math.exp(outcome)) if pos != "DEF" else mean
    ratio = new_mean / mean if mean > 0 else 1.0
    new_age = age + 1.0
    # Dynasty market value follows the production change and the new age.
    shift = (future_factor(pos, new_age) / future_factor(pos, age)) ** 0.5  # the market's own age belief is the original curve in every version
    new_market = max(0.0, min(100.0, market * (ratio ** (MARKET_HALF_LIFE if market_exp is None else market_exp)) * shift))
    quality = max(0.0, min(1.0, market / 100.0))
    if aging_v >= 1:
        retired = u_ret < retire_prob_v1(pos, new_age, role, quality, ratio)
    else:
        retired = u_ret < retire_prob(pos, new_age, quality)
    return new_age, new_mean, max(1.5, sd * ratio), new_market, retired


__all__ = [
    "age_mult", "retire_prob_v1", "AGE_KNOTS_V1", "future_factor", "horizon_value", "retire_prob", "progress", "stable_key", "AGE_KNOTS",
]
