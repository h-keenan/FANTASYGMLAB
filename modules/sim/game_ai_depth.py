"""AI managers that plan depth around byes and injuries (``ai_v`` 1 and later). Pure, deterministic, no randomness beyond the
existing per-(seed, week, team) waiver stream.

The original AI (ai_v 0) only reacted to a slot that was empty THIS week, made at most one claim, and could only drop players
outside a narrow "kept" rule. A kicker or tight end on bye, two injuries in one week, or no droppable bench player left a hole.
Here a manager values a roster by what its lineup scores over the next few weeks, with byes and known injuries applied
week by week, plus a small insurance term for the best backup at each position (an injury nobody has announced yet):

    value(roster) = sum_w weight_w * best_lineup_total(roster, week + w) + INSURANCE * sum_pos slots_pos * bench_best_pos

Everything else follows from that one number: claim the free agent whose addition raises it most, drop the player whose removal
costs it least (then his long-run worth), make several claims in one week when there are several holes, never hoard a position
past what its slots and byes need. Needs, surplus and horizon come from the team's own parameters exactly as before.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from modules.sim.game_eval import NEED_K, Evaluator, team_params
from modules.sim.game_types import SINGLETON_POSITIONS, GameSnapshot, slot_positions
from modules.sim.lineup import pick_lineup
from modules.sim.rng import WorldRng

HORIZON_WEIGHTS = (1.0, 0.6, 0.3)   # this week, next week, the week after
HOLE_LOOKAHEAD = 2                  # a hole this week or next is an emergency: the random gate and the bar are waived
INSURANCE = 0.15                    # weekly injury chance x a few weeks of exposure, as a share of the best backup's mean
MAX_CLAIMS_EMERGENCY = 3
MAX_CLAIMS_ROUTINE = 1
MAX_CLAIMS_GAP = 2
CORE = ("QB", "RB", "WR", "TE")


def _idx(snap: GameSnapshot, tid: str) -> int:
    return [t.tid for t in snap.teams].index(tid)


def horizon_weeks(ev: Evaluator, week: int) -> list[int]:
    S = ev.snap.settings
    last = S.regular_weeks + S.playoff_weeks
    return [w for w in range(week, week + len(HORIZON_WEIGHTS)) if w <= last]


def slot_need(ev: Evaluator) -> dict[str, int]:
    """Strict starting slots per position (a superflex counts as one more QB slot)."""

    need = {p: 0 for p in (*CORE, "K", "DEF")}
    for slot in ev.snap.settings.slots:
        pos = sorted(slot_positions(slot))
        if len(pos) == 1 and pos[0] in need:
            need[pos[0]] += 1
        elif slot == "SUPER_FLEX":
            need["QB"] += 1
    return need


def flex_slots(ev: Evaluator) -> int:
    return sum(1 for s in ev.snap.settings.slots if len(slot_positions(s)) > 1 and s != "SUPER_FLEX")


def insurance(ev: Evaluator, roster: Iterable[str], need: dict[str, int]) -> float:
    snap = ev.snap
    roster = list(roster)
    total = 0.0
    for pos in CORE:
        n = need.get(pos, 0)
        if n <= 0:
            continue
        pool = sorted((ev.ros_mean(p) for p in roster if snap.players[p].pos == pos and ev.state.out.get(p, 0) <= 1), reverse=True)
        total += n * (pool[n] if len(pool) > n else 0.0)
    return INSURANCE * total


def horizon_value(ev: Evaluator, roster: Sequence[str], week: int, need: dict[str, int] | None = None) -> float:
    weeks = horizon_weeks(ev, week)
    total = 0.0
    for wt, w in zip(HORIZON_WEIGHTS, weeks):
        total += wt * pick_lineup(ev.plan, ev.entries(roster, w))[1]
    return total + insurance(ev, roster, need or slot_need(ev))


def holes(ev: Evaluator, roster: Sequence[str], week: int) -> list[tuple[int, str]]:
    """(week, slot) pairs nobody on the roster can fill, this week and next (byes and known injuries applied)."""

    out = []
    for w in horizon_weeks(ev, week)[:HOLE_LOOKAHEAD]:
        assignment, _ = pick_lineup(ev.plan, ev.entries(roster, w))
        out.extend((w, slot) for slot, pid in assignment if pid is None)
    return out


def backup_gaps(ev: Evaluator, roster: Sequence[str], need: dict[str, int]) -> set[str]:
    """Core positions where nobody beyond the starters is healthy: one injury away from a hole."""

    snap = ev.snap
    out = set()
    for pos in CORE:
        n = need.get(pos, 0)
        if n and sum(1 for p in roster if snap.players[p].pos == pos and ev.state.out.get(p, 0) <= 1) <= n:
            out.add(pos)
    return out


def hole_positions(found: Iterable[tuple[int, str]]) -> set[str]:
    return {pos for _, slot in found for pos in slot_positions(slot)}


def _cap(ev: Evaluator, pos: str, need: dict[str, int]) -> int:
    """Most players of a position worth holding: its slots (plus flex share) plus the backups byes and injuries call for."""

    if pos in SINGLETON_POSITIONS:
        return 1
    flex = flex_slots(ev) if pos in ("RB", "WR", "TE") else 0
    extra = 1 if pos in ("QB", "TE") else 2
    return need.get(pos, 0) + flex + extra


def _why(ev: Evaluator, roster: Sequence[str], found: list[tuple[int, str]], add: str) -> str:
    pos = ev.snap.players[add].pos
    for w, slot in found:
        if pos in slot_positions(slot):
            if any(ev.on_bye(p, w) and ev.snap.players[p].pos == pos for p in roster):
                return "bye"
            return "injury"
    return "depth"


def ai_waiver_claims(
    ev: Evaluator, tid: str, week: int, seed: int, exclude: Iterable[str] = (), *, max_claims: int | None = None,
    emergency_only: bool = False,
) -> list[dict[str, Any]]:
    """The claims one AI team makes this week (usually none, up to three when several holes open at once)."""

    snap, state = ev.snap, ev.state
    params = team_params(snap, tid)
    r = WorldRng(seed).stream(week, "gwaiver", _idx(snap, tid))
    roll = r.random()
    limit = snap.settings.roster_limit
    need = slot_need(ev)
    roster = list(state.rosters[tid])
    owned = set(state.owner_map())
    taken = set(exclude)
    claims: list[dict[str, Any]] = []
    h = ev.horizon_now(params)
    cap_n = max_claims if max_claims is not None else MAX_CLAIMS_EMERGENCY
    for n in range(cap_n):
        found = holes(ev, roster, week)
        emergency = bool(found)
        gaps = backup_gaps(ev, roster, need) if len(roster) < limit and not emergency_only else set()  # a free spot and no backup: just fill it
        if emergency_only and not emergency:
            break
        if n >= 1 and not emergency and not gaps:
            break
        if n == 0 and not emergency and not gaps and (params.waiver_aggr <= 0 or roll > params.waiver_aggr):
            break
        if not emergency and not gaps and n >= MAX_CLAIMS_ROUTINE:
            break
        if not emergency and n >= MAX_CLAIMS_GAP:
            break
        base = horizon_value(ev, roster, week, need)
        weights = sum(HORIZON_WEIGHTS[: len(horizon_weeks(ev, week))]) or 1.0
        # free agents worth a look: the best by worth, plus the best at every position that has a hole or no backup
        free = [p for p in snap.pids if p not in owned and p not in taken and state.out.get(p, 0) == 0 and snap.players[p].pos in (*CORE, "K", "DEF")]
        want = hole_positions(found) | gaps
        by_worth = sorted(free, key=lambda p: (-ev.worth(params, p), p))[:5]
        by_need = []
        for pos in sorted((*CORE, "K", "DEF")):
            pool = [p for p in free if snap.players[p].pos == pos]
            if pos in want:
                hole_weeks = [w for w, slot in found if pos in slot_positions(slot)]
                pool = [p for p in pool if all(ev.status(p, w) == "healthy" for w in hole_weeks)] or pool
                by_need += sorted(pool, key=lambda p: (-ev.ros_mean(p), p))[:4]
            else:
                by_need += sorted(pool, key=lambda p: (-ev.ros_mean(p), p))[:2]
        cands = list(dict.fromkeys([*by_need, *by_worth]))
        counts: dict[str, int] = {}
        for p in roster:
            counts[snap.players[p].pos] = counts.get(snap.players[p].pos, 0) + 1
        if len(roster) < limit:
            drops: list[str | None] = [None]
        else:
            lineup_ids = {pid for _, pid in pick_lineup(ev.plan, ev.entries(roster, week))[0] if pid}  # this week's starters stay
            bench = [p for p in roster if p not in lineup_ids and not (snap.players[p].pos in SINGLETON_POSITIONS and counts[snap.players[p].pos] <= 1)]
            scored = []
            for p in bench:
                loss = base - horizon_value(ev, [q for q in roster if q != p], week, need)
                scored.append((loss * NEED_K / weights + ev.worth(params, p), p))
            scored.sort()
            drops = [p for _, p in scored[:3]]
            if not drops:
                break
        best: tuple[float, str, str | None] | None = None
        for add in cands:
            pos = snap.players[add].pos
            for drop in drops:
                after = counts.get(pos, 0) + 1 - (1 if drop and snap.players[drop].pos == pos else 0)
                if after > _cap(ev, pos, need) and pos not in want:
                    continue  # no hoarding: a position holds its slots plus the backups byes and injuries need
                new_roster = [p for p in roster if p != drop] + [add]
                gain_pts = (horizon_value(ev, new_roster, week, need) - base) / weights
                gain_worth = ev.worth(params, add) - (ev.worth(params, drop) if drop else 0.0)
                score = gain_pts * NEED_K * (0.4 + h) + 0.5 * gain_worth
                if gain_pts <= 0.0:
                    continue
                if best is None or (-score, add) < (-best[0], best[1]):
                    best = (score, add, drop)
        free_spot_fill = bool(gaps) and best is not None and best[2] is None and snap.players[best[1]].pos in gaps
        if best is None or (best[0] < 6.0 - 4.0 * params.waiver_aggr and not emergency and not free_spot_fill):
            break
        score, add, drop = best
        claims.append({"team": tid, "add": add, "drop": drop, "start_slot": None, "gain": round(score, 2),
                       "why": _why(ev, roster, found, add) if emergency else ("depth" if free_spot_fill else "upgrade")})
        roster = [p for p in roster if p != drop] + [add]
        taken.add(add)
    return claims


def cut_order(ev: Evaluator, tid: str, roster: Sequence[str], week: int) -> list[str]:
    """Bench players cheapest to lose first: what the next weeks' lineups and the backup insurance lose without him, then his
    long-run worth. Starters in the horizon are never offered."""

    snap = ev.snap
    params = team_params(snap, tid)
    need = slot_need(ev)
    base = horizon_value(ev, roster, week, need)
    weights = sum(HORIZON_WEIGHTS[: len(horizon_weeks(ev, week))]) or 1.0
    lineup_ids = {pid for _, pid in pick_lineup(ev.plan, ev.entries(roster, week))[0] if pid}
    counts: dict[str, int] = {}
    for p in roster:
        counts[snap.players[p].pos] = counts.get(snap.players[p].pos, 0) + 1
    scored = []
    for p in roster:
        if p in lineup_ids:
            continue
        if snap.players[p].pos in SINGLETON_POSITIONS and counts[snap.players[p].pos] <= 1:
            continue
        loss = base - horizon_value(ev, [q for q in roster if q != p], week, need)
        scored.append((loss * NEED_K / weights + ev.worth(params, p), p))
    scored.sort()
    return [p for _, p in scored]


def depth_adds(ev: Evaluator, tid: str, week: int, free: Iterable[str]) -> list[str]:
    """Offseason depth: free agents an AI team adds so every core position has a healthy backup (and no slot is empty)."""

    snap, state = ev.snap, ev.state
    need = slot_need(ev)
    roster = list(state.rosters[tid])
    pool = set(free)
    out: list[str] = []
    for _ in range(len(snap.settings.slots) + len(CORE)):
        if len(roster) >= snap.settings.roster_limit:
            break
        found = holes(ev, roster, week)
        want = hole_positions(found)
        for pos in CORE:
            n = need.get(pos, 0)
            if n and sum(1 for p in roster if snap.players[p].pos == pos and state.out.get(p, 0) <= 1) <= n:
                want.add(pos)
        cands = sorted((p for p in pool if snap.players[p].pos in want and state.out.get(p, 0) == 0), key=lambda p: (-ev.ros_mean(p), p))
        if not cands:
            break
        out.append(cands[0])
        roster.append(cands[0])
        pool.discard(cands[0])
    return out


__all__ = ["ai_waiver_claims", "cut_order", "depth_adds", "holes", "horizon_value", "slot_need"]
