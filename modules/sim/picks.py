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


def pick_label(season: int, round_no: int) -> str:
    return f"{season} round {round_no} pick"
