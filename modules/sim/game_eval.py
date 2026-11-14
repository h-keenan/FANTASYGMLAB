"""Read-only valuation over (snapshot, state): projections, lineups, worth.

Everything the AI managers and the UI need to answer "how good is this player
for this team right now?" lives here so the draft, waivers, trades and the API
share one definition. Nothing here mutates state or draws randomness.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

from modules.sim import aging
from modules.sim.game_scoring import team_roles_mode
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot, slot_positions
from modules.sim.picks import FUTURE_SLOT_FRAC, pick_label, pick_market_value
from modules.sim.lineup import Assignment, SlotPlan, carry_lineup, pick_lineup
from modules.sim.personas import PERSONAS, TeamParams
from modules.sim import team_roles as tr
from modules.sim.team_roles import Role, RoleBook
from modules.sim.types import GAME_POSITIONS, is_pick_id

PRIOR_GAMES = 5.0  # a projection counts as this many games of evidence
ROLE_HORIZON_WEEKS = 8  # a player's rest-of-season mean averages his role over his next playable weeks (known injuries only; 17 let a trade-spammer beat the anti-exploit margin)
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
        self.policy = snapshot.settings.policy
        self._ros: dict[str, float] = {}
        self._ros_key: object = -1
        self._seq = -1
        self._roles: dict[tuple, dict[str, Role]] = {}
        book = getattr(snapshot, "_role_book", None)
        if book is None:  # frozen snapshot: memoize on the instance (False = this game does not use team roles)
            mode = team_roles_mode(snapshot.scoring_model)
            book = RoleBook(snapshot.players) if mode else False
            object.__setattr__(snapshot, "_role_book", book)
            object.__setattr__(snapshot, "_role_mode", mode)
        self.book = book or None
        self.roles_on = self.book is not None
        # "additive" (player-model-4+): additive team roles and a robust, role-normalised player level.
        self.additive = getattr(snapshot, "_role_mode", "") == "additive"
        self._level: dict[str, float] = {}
        scale = getattr(snapshot, "_now_scale", None)
        if scale is None:  # frozen snapshot: memoize on the instance
            scale = self._compute_now_scale()
            object.__setattr__(snapshot, "_now_scale", scale)
        self.now_scale = scale

    def base_value(self, pid: str) -> float:
        """The long-run side of a player's worth: this season's settings-aware
        value in redraft (rules 2), the dynasty market value in dynasty/legacy."""

        p = self.snap.players[pid]
        if self.policy.dynasty:
            return aging.horizon_value(p.pos, p.age, p.market)
        return p.value if self.policy.season_valuation else p.market

    def _compute_now_scale(self) -> dict[str, float]:
        scale: dict[str, float] = {}
        base = (lambda p: p.value) if self.policy.season_valuation else (lambda p: p.market)
        for pos in GAME_POSITIONS:
            rows = sorted(
                (p for p in self.snap.players.values() if p.pos == pos and p.mean > 0),
                key=lambda p: (-base(p), p.pid),
            )[:24]
            if rows:
                mean_mean = sum(p.mean for p in rows) / len(rows)
                mean_market = sum(base(p) for p in rows) / len(rows)
                scale[pos] = mean_market / mean_mean if mean_mean > 0 else 4.0
            else:
                scale[pos] = 4.0
        return scale

    # ------------------------------------------------------------ projections

    def base_mean(self, pid: str) -> float:
        """The player's own rest-of-season weekly mean, role-free (``if he plays his usual role``): the frozen
        projection updated by what he has actually done this season (a Bayesian blend, so one big week moves
        it a little, not a lot)."""

        if self.additive:
            return self.level(pid)
        mean = self.snap.players[pid].mean
        games = self.state.games_played(pid) if self.state.status != "offseason" else []
        return (mean * PRIOR_GAMES + sum(games)) / (PRIOR_GAMES + len(games)) if games else mean

    def level(self, pid: str) -> float:
        """player-model-4: his own per-game level (what he scores in his usual role). A credibility-weighted
        average of the projection and what he has done, where each game is first stripped of the team role he had
        (``(points - role points) / role scale``), weighted by that role's share (a bench QB's 2 points say little), and
        winsorised (one game counts at most ``LEVEL_WIN_MULT x max(projection, 3)`` and never above the position's
        ceiling). One 70-point freak game, or a stretch as a fill-in, cannot make a depth player a star."""

        self._sync()
        cached = self._level.get(pid)
        if cached is not None:
            return cached
        p = self.snap.players[pid]
        mu = p.mean
        hist = self.state.points.get(pid) if self.state.status != "offseason" else None
        if not hist:
            self._level[pid] = mu
            return mu
        cap = min(tr.PROJ_CEIL.get(p.pos, 1e9), tr.LEVEL_WIN_MULT * max(mu, tr.LEVEL_WIN_FLOOR))
        roles = self.state.role_hist.get(pid, {})
        num, den = tr.LEVEL_PRIOR_GAMES * mu, tr.LEVEL_PRIOR_GAMES
        for i, pts in enumerate(hist):
            if pts is None:
                continue
            scale, add = roles.get(str(i + 1), (1.0, 0.0))
            w = max(float(scale), tr.MIN_ROLE_WEIGHT)
            x = min(cap, max(0.0, pts - float(add)) / w)
            num += w * x
            den += w
        value = num / den
        self._level[pid] = value
        return value

    def _sync(self) -> None:
        """Drop the caches when the game moved on (an event was applied: a week scored, an injury, a claim)."""

        seq = self.state.seq
        if seq == self._seq:
            return
        self._seq = seq
        # What the caches depend on: games played, the week, and who is out (rosters never matter: roles are NFL-level).
        key = (len(self.state.history), self.state.week, frozenset(self.state.out.items()))
        if self._ros_key != key:
            self._ros.clear()
            self._roles.clear()
            self._level.clear()
            self._ros_key = key

    def ros_mean(self, pid: str) -> float:
        """Rest-of-season weekly mean: ``base_mean`` times his expected team role over the coming weeks, so two
        backups of one injured starter are not both valued as the starter (team roles, player-model-3+; the
        same as ``base_mean`` for older saves)."""

        self._sync()
        cached = self._ros.get(pid)
        if cached is not None:
            return cached
        value = self._additive_ros(pid) if self.additive else self.base_mean(pid) * self.role_factor(pid)
        self._ros[pid] = value
        return value

    # ------------------------------------------------------------ team roles

    def role(self, pid: str, week: int) -> Role | None:
        """The role this player has in ``week`` given what is publicly known (current injuries and byes), or
        None when team roles are off or the position has none (K, DEF). One fill-in per vacated starter."""

        if self.book is None:
            return None
        key = self.book.key(pid)
        if key is None:
            return None
        self._sync()
        ck = (key, week)
        roles = self._roles.get(ck)
        if roles is None:
            roles = self.book.roles(key, lambda p: self.status(p, week) == "healthy", self.level if self.additive else None)
            self._roles[ck] = roles
        r = roles.get(pid)
        if r is not None and r.kind == "backup" and self.additive and self.snap.settings.world_v:
            return Role("backup", 0.0)  # world_v 1+: a backup quarterback does not play (he is the starter's insurance, nothing more)
        return r

    def role_mult(self, pid: str, week: int) -> float:
        r = self.role(pid, week)
        return r.mult if r is not None else 1.0

    def role_param(self, pid: str, week: int):
        """What the engine hands the scoring model for this week: a float multiplier (player-model-3) or a
        ``(scale, points)`` pair (player-model-4+)."""

        if not self.additive:
            return self.role_mult(pid, week)
        r = self.role(pid, week)
        return (r.mult, r.add) if r is not None else (1.0, 0.0)

    def _additive_ros(self, pid: str) -> float:
        start = 1 if self.state.status == "offseason" else max(self.state.week, 1)
        weeks = self._playable_weeks(pid, start, ROLE_HORIZON_WEEKS)
        if not weeks:
            return self.week_mean(pid, start)
        return sum(self.week_mean(pid, w) for w in weeks) / len(weeks)

    def _playable_weeks(self, pid: str, start: int, count: int) -> list[int]:
        last = self.snap.settings.regular_weeks
        return [w for w in range(start, min(last, start + count - 1) + 1) if self.status(pid, w) == "healthy"]

    def role_factor(self, pid: str) -> float:
        """Average role multiplier over his playable weeks in the next ROLE_HORIZON_WEEKS (1.0 without roles)."""

        if self.book is None or self.book.key(pid) is None:
            return 1.0
        start = 1 if self.state.status == "offseason" else max(self.state.week, 1)
        weeks = self._playable_weeks(pid, start, ROLE_HORIZON_WEEKS)
        if not weeks:
            return 1.0
        return sum(self.role_mult(pid, w) for w in weeks) / len(weeks)

    def week_mean(self, pid: str, week: int) -> float:
        """His mean for one specific week: ``base_mean`` times that week's role multiplier."""

        if self.additive:
            r = self.role(pid, week)
            scale, add = (r.mult, r.add) if r is not None else (1.0, 0.0)
            return tr.soft_ceiling(self.level(pid) * scale + add, tr.PROJ_CEIL.get(self.snap.players[pid].pos))
        return self.base_mean(pid) * self.role_mult(pid, week)

    def next_game(self, pid: str, week: int) -> int | None:
        """The first week from ``week`` on in which he can play (not out, not on a bye), or None."""

        for w in range(max(week, 1), self.snap.settings.regular_weeks + 1):
            if self.status(pid, w) == "healthy":
                return w
        return None

    def next_proj(self, pid: str, week: int) -> float:
        """Projection for the next game he plays (so an injured player shows what he will do when he is back)."""

        w = self.next_game(pid, week)
        return self.week_mean(pid, w) if w is not None else self.ros_mean(pid)

    def role_info(self, pid: str, week: int) -> dict | None:
        """What the UI shows beside a projection: the role in his next game, the starter he covers, and his
        'if he starts' number. None when team roles do not apply."""

        w = self.next_game(pid, week)
        r = self.role(pid, w if w is not None else week)
        if r is None:
            return None
        covering = self.snap.players[r.covering].name if r.covering else None
        label = {
            "fill_in": (f"Starting while {covering} is out" if self.snap.players[pid].pos == "QB" else f"Filling in for {covering}"),
            "backup": "Backup",
            "starter": None, "bench": None, "out": None,
        }.get(r.kind)
        return {
            "kind": r.kind, "label": label, "covering": r.covering or None, "covering_name": covering,
            "if_starts": round(self.base_mean(pid), 1), "week": w,
        }

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
        return 0.0 if self.status(pid, week) != "healthy" else self.week_mean(pid, week) if self.roles_on else self.ros_mean(pid)

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
            out.append((self.week_mean(pid, week) if self.roles_on else self.ros_mean(pid), pid, self.snap.players[pid].pos))
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
        week = 1 if self.state.status == "offseason" else self.state.week
        progress = min(1.0, max(0, week - 1) / max(1, regular))
        return self.policy.horizon(min(1.0, params.horizon + (1.0 - params.horizon) * 0.7 * progress))

    # ----------------------------------------------------------------- picks

    def pick_parts(self, pid: str) -> tuple[int, int, str]:
        _, season, rnd, orig = pid.split(":", 3)
        return int(season), int(rnd), orig

    def draft_year_now(self) -> int:
        """The calendar year of the next (or, in the offseason, the current) rookie draft."""

        return self.snap.settings.start_year + self.state.season_no

    def pick_slot_frac(self, orig: str) -> float:
        """0 = the first pick of a round, 1 = the last, for the next draft: exact
        once the draft order is set, else projected from record and roster strength
        (the weaker the team, the earlier its pick)."""

        off = self.state.offseason
        n = len(self.snap.teams)
        if off and off.get("slots") and orig in off["slots"]:
            return (off["slots"][orig] - 1) / max(1, n - 1)
        if not hasattr(self, "_slot_cache"):
            totals = {t: self.lineup_total(self.state.rosters[t]) for t in self.snap.tids}
            by_power = sorted(self.snap.tids, key=lambda t: (totals[t], t))  # weakest first
            power = {t: i / max(1, n - 1) for i, t in enumerate(by_power)}  # 0 = weakest
            played = sum(self.state.stand[t]["w"] + self.state.stand[t]["l"] + self.state.stand[t]["t"] for t in self.snap.tids) / max(1, n)
            w = min(1.0, played / max(1, self.snap.settings.regular_weeks))
            def pct(t):
                r = self.state.stand[t]
                g = r["w"] + r["l"] + r["t"]
                return (r["w"] + 0.5 * r["t"]) / g if g else 0.5
            score = {t: w * pct(t) + (1 - w) * power[t] for t in self.snap.tids}
            order = sorted(self.snap.tids, key=lambda t: (score[t], t))
            self._slot_cache = {t: i / max(1, n - 1) for i, t in enumerate(order)}
        return self._slot_cache.get(orig, FUTURE_SLOT_FRAC)

    def pick_value(self, pid: str) -> float:
        """The pick's market value on the 0-100 scale (what the rookie it becomes is worth)."""

        season, rnd, orig = self.pick_parts(pid)
        years_out = max(0, season - self.draft_year_now())
        frac = self.pick_slot_frac(orig) if years_out == 0 else FUTURE_SLOT_FRAC
        return pick_market_value(rnd, frac, years_out, len(self.snap.teams))

    def pick_worth(self, params: TeamParams, pid: str) -> float:
        """Picks are future value: rebuilders pay up, contenders discount, and the
        late-season shift toward win-now makes everyone sell a little."""

        h = self.horizon_now(params)
        return max(0.0, self.pick_value(pid) * (1.0 + self.policy.pick_slope * (0.55 - h)))

    def pick_name(self, pid: str) -> str:
        season, rnd, orig = self.pick_parts(pid)
        return f"{pick_label(season, rnd)} ({self.snap.team(orig).name})"

    def worth(self, params: TeamParams, pid: str) -> float:
        if is_pick_id(pid):
            return self.pick_worth(params, pid)
        p = self.snap.players[pid]
        h = self.horizon_now(params)
        now = min(100.0, self.now_scale[p.pos] * self.ros_mean(pid))
        now *= 1.0 - min(self.state.out.get(pid, 0), 6) / 10.0
        age_factor = (
            1.0 if (self.policy.season_valuation or self.policy.dynasty)
            else max(0.4, 1.0 - (1.0 - h) * params.age_penalty * max(0.0, p.age - 26.0))
        )
        value = h * now + (1.0 - h) * self.base_value(pid) * age_factor
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
