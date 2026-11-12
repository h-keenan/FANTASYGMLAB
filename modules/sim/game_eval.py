"""Read-only valuation over (snapshot, state): projections, lineups, worth.

Everything the AI managers and the UI need to answer "how good is this player
for this team right now?" lives here so the draft, waivers, trades and the API
share one definition. Nothing here mutates state or draws randomness.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot, slot_positions
from modules.sim.lineup import Assignment, SlotPlan, carry_lineup, pick_lineup
from modules.sim.personas import PERSONAS, TeamParams
from modules.sim.types import POSITIONS

PRIOR_GAMES = 5.0  # a projection counts as this many games of evidence
NEED_K = 8.0  # value units per projected weekly lineup point
USER_PARAMS = TeamParams(
    horizon=0.55, accept_threshold=0.0, propose_min=0.0, activity=0.0, noise_sd=0.0, waiver_aggr=0.0,
)


def convex(worth: float) -> float:
    """Value is convex: one 90 is worth more than two 45s (consolidation).
    Same shape as the season engine's trade valuation."""

    return (max(worth, 0.0) / 100.0) ** 1.4 * 100.0


def to_slot_order(slots: Sequence[str], assignment: Assignment) -> list[list]:
    """``pick_lineup`` returns strict slots then flex; the game stores lineups
    in the league's own slot order."""

    pool: dict[str, list] = {}
    for slot, pid in assignment:
        pool.setdefault(slot, []).append(pid)
    return [[slot, (pool[slot].pop(0) if pool.get(slot) else None)] for slot in slots]


def slot_assignment(lineup: Sequence[Sequence]) -> Assignment:
    return [(row[0], row[1]) for row in lineup]


class Evaluator:
    def __init__(self, snapshot: GameSnapshot, state: GameState) -> None:
        self.snap = snapshot
        self.state = state
        self.plan = SlotPlan(snapshot.settings.slots)
        self._ros: dict[str, float] = {}
        self._ros_key = -1
        scale = getattr(snapshot, "_now_scale", None)
        if scale is None:  # frozen snapshot: memoize on the instance
            scale = self._compute_now_scale()
            object.__setattr__(snapshot, "_now_scale", scale)
        self.now_scale = scale

    def _compute_now_scale(self) -> dict[str, float]:
        scale: dict[str, float] = {}
        for pos in POSITIONS:
            rows = sorted(
                (p for p in self.snap.players.values() if p.pos == pos and p.mean > 0),
                key=lambda p: (-p.market, p.pid),
            )[:24]
            if rows:
                mean_mean = sum(p.mean for p in rows) / len(rows)
                mean_market = sum(p.market for p in rows) / len(rows)
                scale[pos] = mean_market / mean_mean if mean_mean > 0 else 4.0
            else:
                scale[pos] = 4.0
        return scale

    # ------------------------------------------------------------ projections

    def ros_mean(self, pid: str) -> float:
        """Rest-of-season weekly mean: the frozen projection updated by what the
        player has actually done this season (a Bayesian blend, so one big week
        moves it a little, not a lot)."""

        if self._ros_key != len(self.state.history):
            self._ros.clear()
            self._ros_key = len(self.state.history)
        cached = self._ros.get(pid)
        if cached is not None:
            return cached
        mean = self.snap.players[pid].mean
        games = self.state.games_played(pid)
        value = (mean * PRIOR_GAMES + sum(games)) / (PRIOR_GAMES + len(games)) if games else mean
        self._ros[pid] = value
        return value

    def out_in(self, pid: str, week: int) -> bool:
        """Is the player injured (out) in ``week``? Only meaningful for weeks
        from the current one on."""

        weeks = self.state.out.get(pid, 0)
        return weeks > 0 and 0 <= week - max(self.state.week, 1) < weeks

    def on_bye(self, pid: str, week: int) -> bool:
        return self.snap.bye_of(pid) == week

    def status(self, pid: str, week: int) -> str:
        if self.out_in(pid, week):
            return "out"
        if self.on_bye(pid, week):
            return "bye"
        return "healthy"

    def proj(self, pid: str, week: int) -> float:
        return 0.0 if self.status(pid, week) != "healthy" else self.ros_mean(pid)

    def band(self, pid: str) -> tuple[float, float]:
        p = self.snap.players[pid]
        mean = self.ros_mean(pid)
        return max(0.0, mean - 0.8 * p.sd), mean + 0.8 * p.sd

    # ---------------------------------------------------------------- lineups

    def entries(self, roster: Iterable[str], week: int, *, bye: bool = True) -> list[tuple[float, str, str]]:
        """Lineup candidates for ``week``: healthy players (and, with
        ``bye=True``, not on bye)."""

        out = []
        for pid in roster:
            if self.out_in(pid, week) or (bye and self.on_bye(pid, week)):
                continue
            out.append((self.ros_mean(pid), pid, self.snap.players[pid].pos))
        return out

    def best_lineup(self, roster: Iterable[str], week: int) -> tuple[list[list], float]:
        assignment, total = pick_lineup(self.plan, self.entries(roster, week))
        return to_slot_order(self.snap.settings.slots, assignment), total

    def sticky_lineup(self, roster: Iterable[str], week: int, previous: Sequence[Sequence]) -> list[list]:
        """Last week's lineup, with only the forced changes (injury/bye/gone)."""

        entries = self.entries(roster, week)
        order = [(row[0], row[1]) for row in previous]
        assignment = carry_lineup(SlotPlan(self.snap.settings.slots), _plan_order(self.plan, order), entries)
        return to_slot_order(self.snap.settings.slots, assignment)

    def lineup_total(self, roster: Iterable[str], week: int | None = None) -> float:
        """Season-style lineup strength: byes ignored, long-term injuries out."""

        entries = [
            (self.ros_mean(p) * (1.0 if self.state.out.get(p, 0) <= 2 else 0.3), p, self.snap.players[p].pos)
            for p in roster
        ]
        return pick_lineup(self.plan, entries)[1]

    def lineup_projection(self, lineup: Sequence[Sequence], week: int) -> float:
        return sum(self.proj(row[1], week) for row in lineup if row[1])

    # ---------------------------------------------------------------- worth

    def horizon_now(self, params: TeamParams) -> float:
        """Late in a one-season game everyone cares more about now-value."""

        regular = self.snap.settings.regular_weeks
        progress = min(1.0, max(0, self.state.week - 1) / max(1, regular))
        return min(1.0, params.horizon + (1.0 - params.horizon) * 0.7 * progress)

    def worth(self, params: TeamParams, pid: str) -> float:
        p = self.snap.players[pid]
        h = self.horizon_now(params)
        now = min(100.0, self.now_scale[p.pos] * self.ros_mean(pid))
        now *= 1.0 - min(self.state.out.get(pid, 0), 6) / 10.0
        age_factor = max(0.4, 1.0 - (1.0 - h) * params.age_penalty * max(0.0, p.age - 26.0))
        value = h * now + (1.0 - h) * p.market * age_factor
        return value * (1.0 + params.pos_bias.get(p.pos, 0.0))


def _plan_order(plan: SlotPlan, order: Assignment) -> Assignment:
    """Re-order a slot-ordered assignment into the strict-then-flex order the
    carry helper expects."""

    pool: dict[str, list] = {}
    for slot, pid in order:
        pool.setdefault(slot, []).append(pid)
    out: Assignment = []
    for slot in [*plan.strict, *plan.flex]:
        out.append((slot, pool[slot].pop(0) if pool.get(slot) else None))
    return out


def team_params(snapshot: GameSnapshot, tid: str) -> TeamParams:
    """The AI manager's parameters: persona base, this team's own horizon and
    position bias, then the game's difficulty (never hidden dice on the user)."""

    team = snapshot.team(tid)
    persona = PERSONAS.get(team.persona_id)
    if persona is None:  # the user's team
        return USER_PARAMS
    params = replace(persona.params, horizon=team.horizon, pos_bias=dict(team.pos_bias))
    diff = snapshot.settings.difficulty
    if diff == "easy":
        params = replace(
            params, accept_threshold=params.accept_threshold - 3.0,
            noise_sd=params.noise_sd * 1.4, waiver_aggr=params.waiver_aggr * 0.7,
        )
    elif diff == "hard":
        params = replace(
            params, accept_threshold=params.accept_threshold * 1.3 + 2.0,
            noise_sd=params.noise_sd * 0.8, waiver_aggr=min(0.95, params.waiver_aggr * 1.3),
        )
    return params


__all__ = [
    "Evaluator", "convex", "to_slot_order", "slot_assignment", "team_params", "USER_PARAMS",
    "NEED_K", "slot_positions",
]
