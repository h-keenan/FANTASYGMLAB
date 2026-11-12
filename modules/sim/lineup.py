"""Pure lineup selection: strict slots first, then flex slots most-restrictive
first. Deterministic: ties break on player id."""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from modules.sim.types import FLEX_ORDER, FLEX_SLOTS, GAME_STRICT_SLOTS as STRICT_SLOTS

Entry = tuple[float, str, str]  # (score, pid, pos)
Assignment = list[tuple[str, "str | None"]]  # (slot, pid or None)


class SlotPlan:
    """The league's starting slots split into strict and flex groups."""

    def __init__(self, slots: Sequence[str]) -> None:
        self.strict = [s for s in slots if s in STRICT_SLOTS]
        self.flex = sorted((s for s in slots if s in FLEX_SLOTS), key=FLEX_ORDER.index)

    @property
    def size(self) -> int:
        return len(self.strict) + len(self.flex)


def _pools(entries: Iterable[Entry]) -> dict[str, list[Entry]]:
    pools: dict[str, list[Entry]] = {}
    for entry in entries:
        pools.setdefault(entry[2], []).append(entry)
    for pool in pools.values():
        pool.sort(key=lambda e: (-e[0], e[1]))
    return pools


def pick_lineup(plan: SlotPlan, entries: Iterable[Entry]) -> tuple[Assignment, float]:
    """Best lineup by score. Returns (assignment, total score)."""

    pools = _pools(entries)
    cursor = {pos: 0 for pos in pools}
    assignment: Assignment = []
    total = 0.0
    for slot in plan.strict:
        pool = pools.get(slot, [])
        at = cursor.get(slot, 0)
        if at < len(pool):
            cursor[slot] = at + 1
            assignment.append((slot, pool[at][1]))
            total += pool[at][0]
        else:
            assignment.append((slot, None))
    for slot in plan.flex:
        best: Entry | None = None
        for pos in FLEX_SLOTS[slot]:
            pool = pools.get(pos, [])
            at = cursor.get(pos, 0)
            if at < len(pool) and (best is None or (-pool[at][0], pool[at][1]) < (-best[0], best[1])):
                best = pool[at]
        if best is None:
            assignment.append((slot, None))
            continue
        cursor[best[2]] += 1
        assignment.append((slot, best[1]))
        total += best[0]
    return assignment, total


def lineup_total(plan: SlotPlan, entries: Iterable[Entry]) -> float:
    return pick_lineup(plan, entries)[1]


def carry_lineup(
    plan: SlotPlan,
    previous: Assignment | None,
    entries: Sequence[Entry],
) -> Assignment:
    """A "set and forget" lineup: keep last week's starter in each slot while he
    is still on the roster and available (present in ``entries``); fill every
    other slot with the best remaining eligible player."""

    by_pid = {e[1]: e for e in entries}
    if not previous:
        return pick_lineup(plan, entries)[0]
    kept: dict[int, str] = {}
    used: set[str] = set()
    for i, (slot, pid) in enumerate(previous):
        if pid is not None and pid in by_pid and pid not in used and _eligible(slot, by_pid[pid][2]):
            kept[i] = pid
            used.add(pid)
    free = [e for e in entries if e[1] not in used]
    pools = _pools(free)
    cursor = {pos: 0 for pos in pools}
    out: Assignment = []
    order = _fill_order(previous)
    result: dict[int, tuple[str, str | None]] = {}
    for i in order:
        slot = previous[i][0]
        if i in kept:
            result[i] = (slot, kept[i])
            continue
        best: Entry | None = None
        for pos in _eligible_positions(slot):
            pool = pools.get(pos, [])
            at = cursor.get(pos, 0)
            if at < len(pool) and (best is None or (-pool[at][0], pool[at][1]) < (-best[0], best[1])):
                best = pool[at]
        if best is None:
            result[i] = (slot, None)
        else:
            cursor[best[2]] += 1
            result[i] = (slot, best[1])
    for i in range(len(previous)):
        out.append(result[i])
    return out


def _eligible_positions(slot: str) -> frozenset[str]:
    return FLEX_SLOTS.get(slot) or frozenset({slot})


def _eligible(slot: str, pos: str) -> bool:
    return pos in _eligible_positions(slot)


def _fill_order(previous: Assignment) -> list[int]:
    strict = [i for i, (slot, _) in enumerate(previous) if slot in STRICT_SLOTS]
    flex = sorted(
        (i for i, (slot, _) in enumerate(previous) if slot in FLEX_SLOTS),
        key=lambda i: FLEX_ORDER.index(previous[i][0]),
    )
    return strict + flex


ScoreFn = Callable[[str], float]


def entries_for(pids: Iterable[str], pos_of: dict[str, str], score: ScoreFn) -> list[Entry]:
    return [(score(pid), pid, pos_of[pid]) for pid in pids]
