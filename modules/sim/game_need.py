"""The one positional-need source for the Sim: the per-team, per-position strength report behind every "Needs K" / "Strength QB" tag, and the same
report the trade AI reads (``TradeDesk.need_position`` under pos_v 1), so a tag and a valuation cannot disagree."""

from __future__ import annotations

import math
from typing import Any

from modules.sim.game_eval import Evaluator
from modules.sim.game_types import GameSnapshot
from modules.sim.types import FLEX_SLOTS


def effective(ev: Evaluator, pid: str) -> float:
    """Season-style worth of a player to a lineup: byes ignored, long injuries discounted."""

    return ev.ros_mean(pid) * (1.0 if ev.state.out.get(pid, 0) <= 2 else 0.3)


def position_report(snap: GameSnapshot, ev: Evaluator) -> dict[str, list[dict[str, Any]]]:
    """Per team, per position: starter-group strength ranked across the league."""

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


__all__ = ["position_report", "effective"]
