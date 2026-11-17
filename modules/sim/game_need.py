"""The one positional-need source for the Sim: the per-team, per-position strength report behind every "Needs K" / "Strength QB" tag, and the same
report the trade AI reads (``TradeDesk.need_position`` under pos_v 1), so a tag and a valuation cannot disagree."""

from __future__ import annotations

import math
from typing import Any

from modules.sim.game_eval import Evaluator
from modules.sim.game_types import GameSettings, GameSnapshot
from modules.sim.types import FLEX_SLOTS


def effective(ev: Evaluator, pid: str) -> float:
    """Season-style worth of a player to a lineup: byes ignored, long injuries discounted."""

    return ev.ros_mean(pid) * (1.0 if ev.state.out.get(pid, 0) <= 2 else 0.3)


def position_report(snap: GameSnapshot, ev: Evaluator) -> dict[str, list[dict[str, Any]]]:
    """Per team, per position: starter-group strength ranked across the league. ``need_v`` 1: see ``position_report_v1``."""

    if snap.settings.need_v >= 1:
        return position_report_v1(snap, ev)
    S = snap.settings
    starters: dict[str, float] = {}
    for pos in S.pool_positions:
        weight = float(sum(1 for s in S.slots if s == pos))
        for slot in S.slots:
            if slot in FLEX_SLOTS and pos in FLEX_SLOTS[slot]:
                weight += 1.0 / len(FLEX_SLOTS[slot])
        if weight > 0:
            starters[pos] = weight
    raw: dict[str, dict[str, tuple[float, int]]] = {}
    for tid in snap.tids:
        by_pos: dict[str, list[float]] = {}
        for pid in ev.state.rosters[tid]:
            by_pos.setdefault(snap.players[pid].pos, []).append(effective(ev, pid))
        raw[tid] = {}
        for pos, weight in starters.items():
            vals = sorted(by_pos.get(pos, []), reverse=True)
            k = max(1, int(round(weight)))
            raw[tid][pos] = (sum(vals[:k]), max(0, len(vals) - k))
    n = len(snap.tids)
    report: dict[str, list[dict[str, Any]]] = {tid: [] for tid in snap.tids}
    for pos, weight in starters.items():
        order = sorted(snap.tids, key=lambda t: (-raw[t][pos][0], t))
        for tid in snap.tids:
            rank = order.index(tid) + 1
            strength, depth = raw[tid][pos]
            level = "strength" if rank <= max(1, math.ceil(n / 3)) else "need" if rank > n - max(1, math.ceil(n / 3)) else "ok"
            report[tid].append({
                "pos": pos, "rank": rank, "teams": n, "level": level, "depth": depth,
                "starters": max(1, int(round(weight))), "strength": round(strength, 1),
            })
    return report


# ---------------------------------------------------------------- need_v 1: tags from real holes

NEED_RATIO = 0.88      # a starter group this far under the league's median (after what the wire adds) is a need
STRENGTH_RATIO = 1.12  # and this far over it (and in the top third) a strength
USABLE_SHARE = 0.35    # a player below this share of the league's weakest-starter line is not a usable starter (a hole is "nobody usable")


def starter_slots(settings: GameSettings) -> dict[str, int]:
    """The strict starting slots per position, a superflex counted as one more quarterback and flex slots NOT counted: a flex slot is filled by
    whoever is best, so it is never a positional hole, and a team is not short at a position because a flex could use one more player."""

    out: dict[str, int] = {}
    for pos in settings.pool_positions:
        n = sum(1 for s in settings.slots if s == pos)
        if pos == "QB":
            n += sum(1 for s in settings.slots if s == "SUPER_FLEX")
        if n > 0:
            out[pos] = n
    return out


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def position_report_v1(snap: GameSnapshot, ev: Evaluator) -> dict[str, list[dict[str, Any]]]:
    """The Needs / Strength tags from real roster holes (``need_v 1``). For each position with starting slots:

    * strength = the best ``k`` players' season-style worth (``k`` = strict slots, see ``starter_slots``);
    * a team is short when that is under ``NEED_RATIO`` of the league's median, or when it cannot field ``k`` usable (healthy enough, not far below
      the league's weakest starter) players at all, and the best free agent cannot cure it: the wire's best player replaces the team's weakest starter
      first, so a position the wire alone fixes (most kickers) is not a need;
    * a strength is over ``STRENGTH_RATIO`` of the median and in the league's top third.

    Everything else is "ok", so the count of tagged teams follows the league's real spread (none, one or several) instead of a fixed bottom tercile."""

    n = len(snap.tids)
    owned = ev.state.owner_map()
    slots = starter_slots(snap.settings)
    free: dict[str, float] = {}
    for pid in snap.pids:
        if pid not in owned and ev.state.out.get(pid, 0) <= 1:
            pos = snap.players[pid].pos
            if pos in slots:
                free[pos] = max(free.get(pos, 0.0), effective(ev, pid))
    raw: dict[str, dict[str, list[float]]] = {tid: {} for tid in snap.tids}
    for tid in snap.tids:
        for pid in ev.state.rosters[tid]:
            pos = snap.players[pid].pos
            if pos in slots:
                raw[tid].setdefault(pos, []).append(effective(ev, pid))
    report: dict[str, list[dict[str, Any]]] = {tid: [] for tid in snap.tids}
    for pos, k in slots.items():
        tops = {tid: sorted(raw[tid].get(pos, []), reverse=True) for tid in snap.tids}
        strength = {tid: sum(v[:k]) for tid, v in tops.items()}
        median = _median(list(strength.values()))
        kth = sorted((v[k - 1] if len(v) >= k else 0.0 for v in tops.values()))
        floor = USABLE_SHARE * _median(kth)  # what a typical team's weakest starter is, scaled down: below it a player is not a usable starter
        order = sorted(snap.tids, key=lambda t: (-strength[t], t))
        for tid in snap.tids:
            vals = tops[tid]
            usable = sum(1 for v in vals if v > floor)
            hole = usable < k
            cured = strength[tid]
            if free.get(pos, 0.0) > (vals[k - 1] if len(vals) >= k else 0.0):  # the wire's best replaces the weakest starter (or fills an empty slot)
                cured = strength[tid] - (vals[k - 1] if len(vals) >= k else 0.0) + free[pos]
                hole = hole and (usable + 1 < k or free[pos] <= floor)
            ratio = cured / median if median > 0 else 1.0
            rank = order.index(tid) + 1
            if hole or ratio < NEED_RATIO:
                level = "need"
            elif rank <= max(1, math.ceil(n / 3)) and ratio >= STRENGTH_RATIO:
                level = "strength"
            else:
                level = "ok"
            report[tid].append({
                "pos": pos, "rank": rank, "teams": n, "level": level, "depth": max(0, len(vals) - k), "starters": k,
                "strength": round(strength[tid], 1), "ratio": round(ratio, 3), "hole": bool(hole),
            })
    return report


__all__ = ["position_report", "position_report_v1", "starter_slots", "effective"]
