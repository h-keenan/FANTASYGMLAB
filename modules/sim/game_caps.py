"""The one position limit of the Sim (``cap_v`` 1): how many players of a position a roster is worth holding.

Before it, three places each had their own number: the draft (``game_draft.POSITION_CAP``: QB 3, TE 3, RB / WR 9), the AI's waiver depth planner (``game_ai_depth._cap``: slots plus a share of
the flex slots plus backups) and nothing at all in auto-pick's roster building, so an auto-drafted team ended with three quarterbacks in a one-QB league while the waiver AI would refuse to
hold a third. ``position_cap`` is that one number, read by auto-pick, the draft hint, the AI draft and the AI waiver planner:

    cap(pos) = strict starting slots at pos (a SUPER_FLEX is one more QB)
             + the flex slots that take pos          (a flex slot is filled by the best of its positions: it is bench value, not a hole)
             + backups the position needs            (QB / TE: one, RB / WR: two: byes and injuries, the marginal lineup)
    K / DEF: one.

A league whose bench is larger than those caps add up to (a deep bench would otherwise leave the draft nowhere legal to put its last picks) gets the slack spread over RB, WR, TE.
"""

from __future__ import annotations

from modules.sim.game_types import SINGLETON_POSITIONS, GameSettings, slot_positions

BACKUPS = {"QB": 1, "TE": 1, "RB": 2, "WR": 2}


def _base(settings: GameSettings, pos: str) -> int:
    if pos in SINGLETON_POSITIONS:
        return 1
    strict = sum(1 for s in settings.slots if s == pos)
    flex = 0
    for s in settings.slots:
        positions = slot_positions(s)
        if len(positions) > 1 and pos in positions:
            flex += 1  # SUPER_FLEX is a QB start (nearly every superflex team fills it with one), any other flex is shared bench value
    return strict + flex + BACKUPS.get(pos, 2)


def position_cap(settings: GameSettings, pos: str) -> int:
    """The most players of ``pos`` worth holding in this league (see the module doc)."""

    cap = _base(settings, pos)
    if pos in SINGLETON_POSITIONS or pos not in BACKUPS:
        return cap
    room = settings.roster_limit - sum(_base(settings, p) for p in (*BACKUPS, *(q for q in SINGLETON_POSITIONS if q in settings.pool_positions)))
    if room > 0:  # more roster spots than the caps hold: the extra bench goes to RB, WR, TE in that order, never to a QB or a singleton
        order = [p for p in ("RB", "WR", "TE") if p in settings.pool_positions]
        if pos in order:
            cap += room // len(order) + (1 if order.index(pos) < room % len(order) else 0)
    return cap


__all__ = ["position_cap", "BACKUPS"]
