"""Startup snake draft: the AI pick model and the user's draft commands.

AI pick (per team, per pick):
    score = value x team-specific taste noise + positional need + persona bias
then **sample** from the top few with Gumbel noise seeded by ``(seed, pick)``,
under hard rules (no K before the last rounds, QB/TE caps, never leave a
starter slot unfillable). That yields realistic reaches and falls instead of
everyone taking exact ADP. The user's auto-pick is the same score with no noise
(best value for need), so "best available for my need" is one definition.

Events emitted: ``draft_pick`` {n, round, team, pid, auto}, ``draft_queue`` {pids}.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import draft_order, pick_round
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameError, GameSnapshot
from modules.sim.rng import WorldRng
from modules.sim.types import POSITIONS, STRICT_SLOTS

WINDOW = 40  # candidates considered per pick (by ADP)
POSITION_CAP = {"QB": 3, "TE": 3, "K": 1, "RB": 9, "WR": 9}
K_LAST_ROUNDS = 3  # kickers only in the final rounds
QUEUE_MAX = 30
_FLEX_POS = ("RB", "WR", "TE")

# persona -> (taste sigma, need weight, age preference, top-k, temperature)
# age preference > 0 favors young players, < 0 favors vets.
PERSONA_DRAFT: dict[str, tuple[float, float, float, int, float]] = {
    "contender": (0.10, 1.0, -0.8, 5, 3.0),
    "rebuilder": (0.12, 0.8, 0.7, 5, 3.0),
    "value_shark": (0.06, 0.5, 0.0, 4, 2.0),
    "youth_hoarder": (0.12, 0.8, 1.2, 5, 3.0),
    "specialist": (0.12, 0.9, 0.0, 5, 3.0),
    "passive": (0.05, 0.6, 0.0, 4, 1.5),
    "chaos": (0.30, 0.7, 0.0, 6, 5.0),
}
_DEFAULT_DRAFT = (0.10, 0.8, 0.0, 5, 3.0)


class DraftContext:
    def __init__(self, snapshot: GameSnapshot, state: GameState) -> None:
        self.snap = snapshot
        self.state = state
        self.order = getattr(snapshot, "_draft_order", None)
        if self.order is None:
            self.order = draft_order(snapshot)
            object.__setattr__(snapshot, "_draft_order", self.order)
        self.by_adp = getattr(snapshot, "_by_adp", None)
        if self.by_adp is None:
            self.by_adp = sorted(snapshot.players, key=lambda p: (snapshot.players[p].adp, p))
            object.__setattr__(snapshot, "_by_adp", self.by_adp)
        self.rng = WorldRng(0)
        self._noise: dict[str, np.ndarray] = {}
        self.ev = Evaluator(snapshot, state)

    # persistent per-team "taste": the same team always likes the same players
    def noise(self, tid: str, seed: int) -> np.ndarray:
        if tid not in self._noise:
            idx = [t.tid for t in self.snap.teams].index(tid)
            self._noise[tid] = WorldRng(seed).stream(0, "draft", 1000 + idx).standard_normal(len(self.snap.pids))
        return self._noise[tid]

    @property
    def total(self) -> int:
        return len(self.order)

    def on_clock(self) -> str | None:
        i = self.state.pick_index
        return self.order[i] if i < self.total else None

    def taken(self) -> set[str]:
        return {p["pid"] for p in self.state.picks}

    def counts(self, tid: str) -> dict[str, int]:
        c = {p: 0 for p in POSITIONS}
        for pid in self.state.rosters[tid]:
            c[self.snap.players[pid].pos] += 1
        return c


def starter_shortage(slots: tuple[str, ...], counts: Mapping[str, int]) -> dict[str, float]:
    """How many starters at each position the roster still lacks. Flex slots
    count against the RB/WR/TE surplus beyond the strict slots."""

    strict = {pos: sum(1 for s in slots if s == pos) for pos in STRICT_SLOTS}
    flex = sum(1 for s in slots if s not in STRICT_SLOTS)
    short = {pos: float(max(0, strict[pos] - counts.get(pos, 0))) for pos in POSITIONS}
    surplus = sum(max(0, counts.get(pos, 0) - strict[pos]) for pos in _FLEX_POS)
    flex_short = float(max(0, flex - surplus))
    short["FLEX"] = flex_short
    return short


def _forced_positions(slots, counts, picks_left) -> set[str] | None:
    short = starter_shortage(slots, counts)
    total = sum(v for k, v in short.items())
    if total <= 0 or picks_left > total:
        return None
    forced = {pos for pos in POSITIONS if short[pos] > 0}
    if short["FLEX"] > 0:
        forced |= set(_FLEX_POS)
    return forced


def _need_bonus(slots, counts, pos: str, rnd: int) -> float:
    strict = sum(1 for s in slots if s == pos)
    short = starter_shortage(slots, counts)
    if pos in _FLEX_POS and short["FLEX"] > 0 and counts.get(pos, 0) >= strict:
        frac = 0.5
    elif strict:
        frac = short[pos] / strict
    else:
        frac = 0.0
    if frac <= 0 and pos in ("RB", "WR") and counts.get(pos, 0) < strict + 2:
        frac = 0.15  # first couple of bench spots
    damp = 0.4 if rnd <= 4 else 1.0  # early rounds: best player available
    return 10.0 * frac * damp


def _candidates(ctx: DraftContext, tid: str, n: int) -> list[str]:
    snap, state = ctx.snap, ctx.state
    s = snap.settings
    rnd = pick_round(snap, n)
    counts = ctx.counts(tid)
    roster_n = len(state.rosters[tid])
    picks_left = s.rounds - roster_n
    forced = _forced_positions(s.slots, counts, picks_left)
    taken = ctx.taken()
    out = []
    for pid in ctx.by_adp:
        if pid in taken:
            continue
        pos = snap.players[pid].pos
        if forced is not None and pos not in forced:
            continue
        if pos == "K" and (rnd < s.rounds - K_LAST_ROUNDS + 1 or counts["K"] >= 1):
            continue
        if counts[pos] >= POSITION_CAP.get(pos, 99) and (forced is None or pos not in forced):
            continue
        out.append(pid)
        if len(out) >= WINDOW:
            break
    return out


def choose_pick(ctx: DraftContext, tid: str, n: int, seed: int, *, human: bool = False) -> str:
    """The pick ``tid`` makes at overall pick ``n`` (0-based). ``human=True`` is
    the user's auto-pick / hint: no taste noise, no sampling."""

    snap = ctx.snap
    team = snap.team(tid)
    sigma, need_w, age_pref, topk, temp = (
        (0.0, 1.0, 0.0, 1, 1.0) if human else PERSONA_DRAFT.get(team.persona_id, _DEFAULT_DRAFT)
    )
    cands = _candidates(ctx, tid, n)
    if not cands:  # nothing passed the rules (tiny pool): best remaining
        taken = ctx.taken()
        cands = [p for p in ctx.by_adp if p not in taken][:1]
        if not cands:
            raise GameError("pool_exhausted", "No players left to draft.")
    rnd = pick_round(snap, n)
    counts = ctx.counts(tid)
    noise = ctx.noise(tid, seed) if sigma > 0 else None
    scored = []
    for pid in cands:
        p = snap.players[pid]
        value = p.value * (math.exp(sigma * float(noise[snap.index[pid]])) if noise is not None else 1.0)
        need = need_w * _need_bonus(snap.settings.slots, counts, p.pos, rnd)
        persona = 28.0 * team.pos_bias.get(p.pos, 0.0) if not human else 0.0
        age = age_pref * 5.0 * max(-1.0, min(1.0, (26.0 - p.age) / 4.0)) if not human else 0.0
        scored.append((value + need + persona + age, pid))
    scored.sort(key=lambda t: (-t[0], t[1]))
    if topk <= 1:
        return scored[0][1]
    top = scored[:topk]
    g = WorldRng(seed).stream(0, "draft", n).gumbel(size=len(top))
    best = max(range(len(top)), key=lambda i: (top[i][0] / temp + float(g[i]), -i))
    return top[best][1]


# --------------------------------------------------------------- commands


def _emit_pick(ctx: DraftContext, em: Emitter, tid: str, pid: str, auto: bool) -> dict[str, Any]:
    n = ctx.state.pick_index
    ev = em.emit(0, "user" if tid == ctx.snap.user_team.tid else tid, "draft_pick",
                 n=n, round=pick_round(ctx.snap, n), team=tid, pid=pid, auto=auto)
    return ev["payload"]


def run_ai_picks(ctx: DraftContext, em: Emitter, seed: int) -> list[dict[str, Any]]:
    """Resolve AI picks until the user is on the clock (or the draft ends)."""

    made = []
    user = ctx.snap.user_team.tid
    while ctx.state.pick_index < ctx.total:
        tid = ctx.order[ctx.state.pick_index]
        if tid == user:
            break
        pid = choose_pick(ctx, tid, ctx.state.pick_index, seed)
        made.append(_emit_pick(ctx, em, tid, pid, False))
    return made


def user_pick(ctx: DraftContext, em: Emitter, pid: str, seed: int, *, auto: bool = False) -> list[dict[str, Any]]:
    state = ctx.state
    if state.status != "drafting" or state.pick_index >= ctx.total:
        raise GameError("wrong_phase", "The draft is not in progress.", phase=state.status)
    user = ctx.snap.user_team.tid
    if ctx.order[state.pick_index] != user:
        raise GameError("not_your_turn", "An AI team is on the clock.")
    if pid not in ctx.snap.players:
        raise ValueError("Unknown player.")
    if pid in ctx.taken():
        raise GameError("player_taken", "That player has already been drafted.")
    made = [_emit_pick(ctx, em, user, pid, auto)]
    made.extend(run_ai_picks(ctx, em, seed))
    return made


def best_for_user(ctx: DraftContext, seed: int) -> str:
    """Queue first, else best value for need."""

    taken = ctx.taken()
    for pid in ctx.state.queue:
        if pid in ctx.snap.players and pid not in taken:
            return pid
    user = ctx.snap.user_team.tid
    return choose_pick(ctx, user, ctx.state.pick_index, seed, human=True)


def auto_for_user(ctx: DraftContext, em: Emitter, seed: int) -> list[dict[str, Any]]:
    """Auto-pick for the user until the draft ends."""

    if ctx.state.status != "drafting" or ctx.state.pick_index >= ctx.total:
        raise GameError("wrong_phase", "The draft is not in progress.", phase=ctx.state.status)
    made: list[dict[str, Any]] = []
    made.extend(run_ai_picks(ctx, em, seed))
    while ctx.state.pick_index < ctx.total:
        made.extend(user_pick(ctx, em, best_for_user(ctx, seed), seed, auto=True))
    return made


def set_queue(ctx: DraftContext, em: Emitter, pids: list[str]) -> None:
    if len(pids) > QUEUE_MAX:
        raise ValueError(f"queue holds at most {QUEUE_MAX} players")
    seen: list[str] = []
    for pid in pids:
        pid = str(pid)
        if pid not in ctx.snap.players:
            raise ValueError("Unknown player in queue.")
        if pid not in seen:
            seen.append(pid)
    em.emit(0, "user", "draft_queue", pids=seen)


# ----------------------------------------------------------------- recap

_LETTERS = ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F")


def _letter(rank: int, n: int) -> str:
    frac = rank / max(1, n - 1)
    return _LETTERS[min(len(_LETTERS) - 1, int(frac * (len(_LETTERS) - 1) + 0.5))]


def draft_recap(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    picks = []
    for p in state.picks:
        player = snap.players[p["pid"]]
        picks.append({
            "pick_no": p["n"] + 1, "round": p["round"], "team_id": p["team"], "player_id": p["pid"],
            "name": player.name, "pos": player.pos, "adp": player.adp,
            "value_over_adp": round((p["n"] + 1) - player.adp, 1), "auto": p["auto"],
        })
    totals = {t.tid: ev.lineup_total(state.rosters[t.tid]) for t in snap.teams}
    depth = {t.tid: sum(snap.players[p].value for p in state.rosters[t.tid]) for t in snap.teams}
    ranked = sorted(snap.tids, key=lambda t: (-(totals[t] + 0.02 * depth[t]), t))
    teams = []
    for rank, tid in enumerate(ranked):
        mine = [p for p in picks if p["team_id"] == tid]
        teams.append({
            "team_id": tid, "name": snap.team(tid).name, "is_you": snap.team(tid).is_user,
            "grade": _letter(rank, len(ranked)), "rank": rank + 1,
            "starter_projection": round(totals[tid], 1),
            "best_pick": max(mine, key=lambda x: (x["value_over_adp"], -x["pick_no"]), default=None),
            "worst_pick": min(mine, key=lambda x: (x["value_over_adp"], x["pick_no"]), default=None),
        })
    you = snap.user_team.tid
    return {
        "picks_value": picks, "teams": teams,
        "your_team": next(t for t in teams if t["team_id"] == you),
    }


__all__ = [
    "DraftContext", "choose_pick", "run_ai_picks", "user_pick", "auto_for_user", "best_for_user",
    "set_queue", "draft_recap", "starter_shortage",
]
