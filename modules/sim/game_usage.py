"""Team-level usage conservation for the GM game's simulated NFL (``world_v`` 1+; see docs/audits/2026-11-sim-injuries-and-usage.md).

The player model draws every player's season independently, so nothing ties a depth player's breakout to his team's usage: a 2 ppg
backup running back could post 20 ppg next to an 18 ppg starter (a team RB group 60% above its baseline), a year after a year. Real
teams do not do that: a team has one ball. This module bounds, per NFL team, position group and week, how far the group's EXPECTED
points can exceed its public baseline (the same depth chart and roles at the preseason projections), and gives the excess back
pro rata: the breakout's gain is paid for by his teammates, never created.

* ``USAGE_CAP[pos]``: weekly cap on (hidden expected group points) / (baseline group points), fitted so the simulated season-level
  group-over-projection distribution has the real 2021-25 upper tail (``injury_usage_report`` prints both). RB 1.12, WR 1.18, TE 1.35.
* QB is exempt (a bench QB does not play at all under ``world_v``; the one who plays is the whole group), K and DEF too.
* It scales the week's role (own-mean scale and added points), so no new random draw is made and the stat-line streams are unchanged.
"""

from __future__ import annotations

from typing import Callable

from modules.sim import team_roles as tr

USAGE_CAP = {"RB": 1.12, "WR": 1.18, "TE": 1.35}
# Per-player upside by tier: without a vacancy (a starter ahead out: the role's added points) a RB/WR/TE's expected weekly points cannot pass
# ``TIER_A + TIER_B x (his preseason projection)``. Fitted to the real panel's upper tail by projection tier (2021-25, 8+ games: a
# 1.5-3 ppg player finishes at most 11 ppg, p99 8; a 3-4.5 ppg player at most 14, p99 11; the sim had 20 and 22): the model's solid-season,
# breakout and natural-promotion tails are calibrated season by season, not against the depth chart, so a scrub could "take" a job nobody left.
TIER_A = 6.0
TIER_B = 1.5


def _allowed(m0: float, scale: float, add: float) -> float:
    """The most a player's expected weekly points may be: the tier ceiling on his own side of the role, plus the points a vacancy hands him."""

    own = TIER_A + TIER_B * m0
    return own * max(scale, 0.0) + add


def group_factors(
    book: tr.RoleBook, snap_players, available: Callable[[str], bool],
    role_param: Callable[[str], tuple[float, float]], expected: Callable[[str, tuple[float, float]], float],
) -> dict[str, float]:
    """``{pid: factor <= 1}`` for the players of every capped group whose hidden expected total exceeds its cap this week.

    ``role_param(pid)``: the (scale, add) the engine would hand the model; ``expected(pid, (scale, add))``: the model's hidden expected
    points for that player this week with that role (healthy players only are asked)."""

    out: dict[str, float] = {}
    pre = lambda pid: float(snap_players[pid].mean or 0.0)  # noqa: E731 - the public preseason projection, frozen
    for key, ordered in book.groups.items():
        cap_k = USAGE_CAP.get(key[1])
        if cap_k is None:
            continue
        healthy = [m.pid for m in ordered if available(m.pid)]
        if len(healthy) < 2:
            continue
        base_roles = tr.resolve_group_additive(ordered, available, pre)
        base = 0.0
        for pid in healthy:
            r = base_roles[pid]
            base += tr.soft_ceiling(pre(pid) * r.mult + r.add, tr.PROJ_CEIL.get(key[1]))
        if base <= 0.0:
            continue
        raw = 0.0
        for pid in healthy:
            scale, add = role_param(pid)
            e = expected(pid, (scale, add))
            allowed = _allowed(pre(pid), scale, add)
            if e > allowed > 0.0:
                out[pid] = allowed / e
                e = allowed
            raw += e
        cap = base * cap_k
        if raw > cap > 0.0:
            f = cap / raw
            for pid in healthy:
                out[pid] = out.get(pid, 1.0) * f
    return out


__all__ = ["USAGE_CAP", "group_factors"]
