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
# Age at which retirement starts to be likely, and how fast the hazard climbs.
RETIRE_AGE = {"QB": 38.0, "RB": 31.0, "WR": 34.0, "TE": 34.5, "K": 41.0, "DEF": 99.0}
RETIRE_SCALE = 1.7
MARKET_HALF_LIFE = 0.6  # how much of the PPG change carries into dynasty market value (exponent)
FUTURE_YEARS = 4
FUTURE_DISCOUNT = 0.9
MIN_FACTOR, MAX_FACTOR = 0.35, 1.3


def stable_key(text: str) -> int:
    """A process-independent integer for an id (``hash()`` is salted per run)."""

    return zlib.crc32(str(text).encode("utf-8")) & 0x7FFFFFFF


def age_mult(pos: str, age: float, v: int = 0) -> float:
    """Expected multiplier on next season's PPG for a player of ``age`` now (``v`` = the game's aging_v)."""

    table = AGE_KNOTS_V1 if v >= 1 else AGE_KNOTS
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
HAZ_MID = {"QB": 36.0, "RB": 30.2, "WR": 33.9, "TE": 36.3, "K": 37.7, "DEF": 99.0}
HAZ_SCALE = {"QB": 2.5, "RB": 1.7, "WR": 1.9, "TE": 1.9, "K": 1.5, "DEF": 1.0}
ROLE_YEARS = {"QB": 2.0, "RB": 2.5, "WR": 2.5, "TE": 2.5, "K": 1.5}
DECLINE_YEARS = {"K": 1.0}  # years earlier per 20% production drop (capped at 2 x); default 3.0
STAR_YEARS = 1.0
INJURY_FLOOR = {"QB": 0.008, "RB": 0.022, "WR": 0.012, "TE": 0.014, "K": 0.004, "DEF": 0.0}  # career-ending injury, per offseason


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
    flat_k: bool = False, aging_v: int = 0, role: float = 0.5,
) -> tuple[float, float, float, float, bool]:
    """One offseason for one player. ``z`` is a standard normal and ``u_ret`` a
    uniform from the player's own stream. ``mult`` replaces the plain age curve for a
    player with his own development curve (a generated rookie, see ``scouting``).
    Returns ``(age, mean, sd, market, retired)`` for next season."""

    if mult is None:
        mult = age_mult(pos, age, aging_v)
        if flat_k and pos == "K":  # dynasty_v 3: kickers hold their level until their late decline (the plain curve compounds +2% a year)
            mult = min(mult, 1.0)
    spread = 0.10 if pos != "K" else 0.06
    noise = math.exp(spread * z - 0.5 * spread * spread)
    new_mean = max(0.5, mean * mult * noise) if pos != "DEF" else mean
    ratio = new_mean / mean if mean > 0 else 1.0
    new_age = age + 1.0
    # Dynasty market value follows the production change and the new age.
    shift = (future_factor(pos, new_age) / future_factor(pos, age)) ** 0.5  # the market's own age belief is the original curve in every version
    new_market = max(0.0, min(100.0, market * (ratio ** MARKET_HALF_LIFE) * shift))
    quality = max(0.0, min(1.0, market / 100.0))
    if aging_v >= 1:
        retired = u_ret < retire_prob_v1(pos, new_age, role, quality, ratio)
    else:
        retired = u_ret < retire_prob(pos, new_age, quality)
    return new_age, new_mean, max(1.5, sd * ratio), new_market, retired


__all__ = [
    "age_mult", "retire_prob_v1", "AGE_KNOTS_V1", "future_factor", "horizon_value", "retire_prob", "progress", "stable_key", "AGE_KNOTS",
]
