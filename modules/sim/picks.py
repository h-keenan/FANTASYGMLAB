"""Draft-pick valuation on the sim's own 0-100 market scale.

Pure and deterministic. A pick's value is the value of the rookie it is
expected to become, so it falls off geometrically through the draft, is
discounted for each year it is further out, and (for the next draft only)
follows the original team's projected record: the weaker the team, the earlier
the slot. Picks have no on-field effect inside a single simulated season; they
matter only as trade assets, so the season grade does not score them.
"""

from __future__ import annotations

TOP_PICK_VALUE = 70.0  # a 1.01 is worth about 70 of a 100-point franchise player
STEP_DECAY_12_TEAM = 0.945  # per-slot decay in a 12-team league (rescaled by size)
YEAR_DISCOUNT = 0.88  # per year further out than the next draft
FUTURE_SLOT_FRAC = 0.5  # beyond the next draft the slot is unknowable: mid-round


def pick_market_value(
    round_no: int, slot_frac: float, years_out: int, n_teams: int
) -> float:
    """``slot_frac`` 0.0 = earliest pick of the round, 1.0 = last. Returns 0-100."""

    n = max(2, int(n_teams))
    frac = min(1.0, max(0.0, slot_frac))
    index = (max(1, int(round_no)) - 1) * n + frac * (n - 1)
    decay = STEP_DECAY_12_TEAM ** (12.0 / n)
    value = TOP_PICK_VALUE * decay ** index * YEAR_DISCOUNT ** max(0, int(years_out))
    return max(0.0, min(100.0, value))


# econ_v 1: a pick is worth the rookie it becomes. Mean dynasty (horizon) value of the player taken at each overall slot, measured over 72 rookie
# drafts per league size (24 seeds x 3 drafts, 10 / 12 / 14 teams; the curve does not depend on the league size because a class is ranked, not
# split by team). The old curve was a pure geometric (70 at 1.01, x0.945 a slot): 25% under the rookie at the top, 45% over him in rounds 2-3.
ROOKIE_SLOT_KNOTS: tuple[tuple[int, float], ...] = (
    (1, 95.0), (2, 91.0), (3, 86.0), (4, 81.0), (5, 73.5), (6, 66.0), (8, 51.5), (10, 40.0), (12, 30.0), (14, 24.0), (16, 20.0),
    (20, 15.5), (24, 12.5), (30, 9.5), (36, 7.3), (48, 5.0),
)
ROOKIE_TAIL_DECAY = 0.975  # per slot beyond the last knot


def rookie_slot_value(slot: float) -> float:
    """Expected dynasty value of the rookie taken at overall slot ``slot`` (1 = first; fractional slots interpolate), 0-100."""

    import math

    s = max(1.0, float(slot))
    knots = ROOKIE_SLOT_KNOTS
    if s >= knots[-1][0]:
        return knots[-1][1] * ROOKIE_TAIL_DECAY ** (s - knots[-1][0])
    for (s0, v0), (s1, v1) in zip(knots, knots[1:]):
        if s <= s1:
            t = (s - s0) / (s1 - s0)
            return math.exp(math.log(v0) + t * (math.log(v1) - math.log(v0)))
    return knots[-1][1]


def pick_market_value_v2(round_no: int, slot_frac: float | None, years_out: int, n_teams: int) -> float:
    """econ_v 1: the expected value of the rookie the pick becomes. ``slot_frac`` None = the slot is unknown (a pick beyond the next draft): the
    average over the round, which beats the mid-round slot because the curve is convex. Further-out picks are discounted per year."""

    n = max(2, int(n_teams))
    r = max(1, int(round_no))
    if slot_frac is None:
        base = sum(rookie_slot_value((r - 1) * n + i) for i in range(1, n + 1)) / n
    else:
        frac = min(1.0, max(0.0, slot_frac))
        base = rookie_slot_value((r - 1) * n + 1 + frac * (n - 1))
    return max(0.0, min(100.0, base * YEAR_DISCOUNT ** max(0, int(years_out))))


def pick_label(season: int, round_no: int) -> str:
    return f"{season} round {round_no} pick"
