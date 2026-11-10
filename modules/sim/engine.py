"""The season engine: weekly loop, AI managers, trades, waivers, playoffs.

Pure: stdlib + numpy + modules.sim only. Takes a frozen ``LeagueSnapshot``, a
``Strategy`` and a seed; returns a plain-dict outcome. Same inputs, same
outcome, byte for byte (tests/test_sim_engine.py::test_deterministic_replay).

Per week: injury/form roll -> waivers -> trades -> lineups -> scores ->
standings. Then a single-elimination playoff. All randomness comes from
``WorldRng`` streams keyed by (week, subsystem, team) so results never depend
on call order, and a counterfactual replay shares every unaffected draw.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from modules.sim.lineup import Assignment, SlotPlan, carry_lineup, pick_lineup
from modules.sim.personas import (
    PERSONAS,
    Persona,
    TeamParams,
    assign_personas,
    user_params,
)
from modules.sim.rng import WorldRng
from modules.sim.types import POSITIONS, LeagueSnapshot, Strategy
from modules.sim.version import ENGINE_VERSION

NEED_K = 8.0  # value units per projected weekly lineup point
MAX_TRADES_PER_WEEK = 3  # league-wide anti-spam / anti-farm cap
PARTNERS_PER_SEARCH = 3
CANDIDATES_PER_SIDE = 4
TEAM_CORRELATION = 0.15  # shared NFL-team factor in player score draws
INJURY_RATE = {"QB": 0.02, "RB": 0.06, "WR": 0.045, "TE": 0.04, "K": 0.005}
FORM_STEP = 0.03


def _convex(worth: float) -> float:
    """Value is convex: one 90 is worth more than two 45s (consolidation)."""

    return (max(worth, 0.0) / 100.0) ** 1.4 * 100.0


def decision_key_trade(week: int, give: Iterable[str], get: Iterable[str]) -> str:
    return f"trade:w{week}:give={'+'.join(sorted(give))}:get={'+'.join(sorted(get))}"


def decision_key_waiver(week: int, add: str, drop: str | None) -> str:
    return f"waiver:w{week}:add={add}:drop={drop or ''}"


@dataclass
class _Stand:
    wins: float = 0.0
    losses: float = 0.0
    ties: float = 0.0
    pf: float = 0.0
    pa: float = 0.0

    @property
    def win_pct_points(self) -> float:
        return self.wins + 0.5 * self.ties


@dataclass
class SeasonOutcome:
    engine_version: str
    seed: int
    mode: str
    start_week: int
    standings: list[dict[str, Any]]
    weekly: list[dict[str, Any]]
    playoffs: list[dict[str, Any]]
    champion: str
    events: list[dict[str, Any]]
    personas: list[dict[str, Any]]
    user: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": self.engine_version, "seed": self.seed, "mode": self.mode,
            "start_week": self.start_week, "standings": self.standings, "weekly": self.weekly,
            "playoffs": self.playoffs, "champion": self.champion, "events": self.events,
            "personas": self.personas, "user": self.user,
        }


class _World:
    def __init__(self, snapshot: LeagueSnapshot, strategy: Strategy, seed: int, veto: frozenset[str]):
        self.snap = snapshot
        self.strategy = strategy
        self.veto = veto
        self.rng = WorldRng(seed)
        self.seed = seed
        settings = snapshot.settings
        self.plan = SlotPlan(settings.slots)
        self.teams = list(snapshot.teams)
        self.tids = [t.tid for t in self.teams]
        self.team_index = {tid: i for i, tid in enumerate(self.tids)}
        self.user_tid = snapshot.user_team.tid

        self.pids = sorted(snapshot.players)
        self.idx = {pid: i for i, pid in enumerate(self.pids)}
        players = [snapshot.players[p] for p in self.pids]
        self.pos = {p.pid: p.pos for p in players}
        self.name = {p.pid: p.name for p in players}
        self.age = [p.age for p in players]
        self.market = [p.market for p in players]
        self.mean0 = [p.mean for p in players]
        self.sd = np.array([p.sd for p in players], dtype=float)
        nfl = sorted({p.nfl_team for p in players})
        self.nfl_count = max(1, len(nfl))
        nfl_index = {t: i for i, t in enumerate(nfl)}
        self.nfl_of = np.array([nfl_index[p.nfl_team] for p in players], dtype=int)
        self.form = [1.0] * len(players)
        self.out = [p.injury_weeks for p in players]
        self.mean_arr = np.array(self.mean0, dtype=float)

        self.rosters: dict[str, list[str]] = {t.tid: list(t.roster) for t in self.teams}
        self.cap = {tid: len(r) for tid, r in self.rosters.items()}
        self.fa: set[str] = set(snapshot.free_agents)
        self.stand = {
            t.tid: _Stand(t.wins, t.losses, t.ties, t.pf, t.pa) for t in self.teams
        }
        self.trades_made = {tid: 0 for tid in self.tids}
        self.events: list[dict[str, Any]] = []
        self.user_assign: Assignment | None = None
        self.now_scale = self._now_scale()
        self.weekly_points: dict[tuple[int, str], float] = {}

        self.personas, self.params = self._setup_managers()
        self.protected = set(strategy.protected_player_ids)

        # user metrics
        self.user_pts_started = 0.0
        self.user_pts_optimal = 0.0
        self.all_play_expected = 0.0
        self.user_games = 0
        self._noise_cache: dict[tuple[int, str], float] = {}

    # ------------------------------------------------------------------ setup

    def _now_scale(self) -> dict[str, float]:
        scale: dict[str, float] = {}
        for pos in POSITIONS:
            rows = sorted(
                (i for i, p in enumerate(self.pids) if self.pos[p] == pos and self.mean0[i] > 0),
                key=lambda i: (-self.market[i], i),
            )[:24]
            if rows:
                mean_mean = sum(self.mean0[i] for i in rows) / len(rows)
                mean_market = sum(self.market[i] for i in rows) / len(rows)
                scale[pos] = mean_market / mean_mean if mean_mean > 0 else 4.0
            else:
                scale[pos] = 4.0
        return scale

    def _setup_managers(self) -> tuple[dict[str, Persona], dict[str, TeamParams]]:
        totals = {tid: self._lineup_total(self.rosters[tid]) for tid in self.tids}
        ranked = sorted(self.tids, key=lambda t: (totals[t], t))
        pct = {tid: (i / max(1, len(ranked) - 1)) for i, tid in enumerate(ranked)}
        avg_age = {
            tid: (sum(self.age[self.idx[p]] for p in r) / len(r) if r else 26.0)
            for tid, r in self.rosters.items()
        }
        ai = [t for t in self.tids if t != self.user_tid]
        personas = assign_personas(self.rng.stream(0, "persona", 0), ai, pct, avg_age)
        params = {tid: persona.params for tid, persona in personas.items()}
        params[self.user_tid] = user_params(self.strategy)
        self.power_pct = pct
        self.avg_age = avg_age
        return personas, params

    # ---------------------------------------------------------------- helpers

    def proj(self, pid: str) -> float:
        """Projected points this week: mean x form; discounted when injured."""

        i = self.idx[pid]
        value = self.mean0[i] * self.form[i]
        out = self.out[i]
        if out > 2:
            return value * 0.3
        return value

    def _healthy_score(self, pid: str) -> float:
        i = self.idx[pid]
        return self.mean0[i] * self.form[i] if self.out[i] == 0 else -1.0

    def _lineup_entries(self, roster: Iterable[str]) -> list[tuple[float, str, str]]:
        return [(self.proj(p), p, self.pos[p]) for p in roster if self.out[self.idx[p]] <= 2]

    def _lineup_total(self, roster: Iterable[str]) -> float:
        return pick_lineup(self.plan, self._lineup_entries(roster))[1]

    def worth(self, params: TeamParams, pid: str) -> float:
        i = self.idx[pid]
        pos = self.pos[pid]
        horizon = params.horizon
        now = min(100.0, self.now_scale[pos] * self.mean0[i] * self.form[i])
        now *= 1.0 - min(self.out[i], 6) / 10.0
        age_factor = max(0.4, 1.0 - (1.0 - horizon) * params.age_penalty * max(0.0, self.age[i] - 26.0))
        value = horizon * now + (1.0 - horizon) * self.market[i] * age_factor
        return value * (1.0 + params.pos_bias.get(pos, 0.0))

    # ----------------------------------------------------------- weekly state

    def _roll_injuries_and_form(self, week: int) -> None:
        n = len(self.pids)
        u = self.rng.stream(week, "injury", 0).random(n)
        d = self.rng.stream(week, "injury", 1).random(n)
        z = self.rng.stream(week, "form", 0).standard_normal(n)
        for i in range(n):
            if self.out[i] > 0:
                self.out[i] -= 1
            elif u[i] < INJURY_RATE.get(self.pos[self.pids[i]], 0.03):
                self.out[i] = 1 + int(d[i] * 5)
            self.form[i] = min(1.2, max(0.8, self.form[i] + FORM_STEP * float(z[i])))

    # --------------------------------------------------------------- waivers

    def _waiver_phase(self, week: int) -> None:
        order = sorted(
            self.tids,
            key=lambda t: (self.stand[t].win_pct_points, self.stand[t].pf, t),
        )  # worst record picks first
        for tid in order:
            params = self.params[tid]
            r = self.rng.stream(week, "waiver", self.team_index[tid])
            if params.waiver_aggr <= 0 or r.random() > params.waiver_aggr:
                continue
            roster = self.rosters[tid]
            base_total = self._lineup_total(roster)
            starters = {pid for _, pid in pick_lineup(self.plan, self._lineup_entries(roster))[0] if pid}
            droppable = sorted(
                (p for p in roster if p not in starters and p not in self.protected_for(tid)),
                key=lambda p: (self.worth(params, p), p),
            )[:3]
            room = len(roster) < self.cap[tid]
            drops: list[str | None] = [None] if room else list(droppable)
            if not drops:
                continue
            fas = sorted(
                (p for p in self.fa if self.out[self.idx[p]] == 0),
                key=lambda p: (-self.worth(params, p), p),
            )[:8]
            best: tuple[float, str, str | None] | None = None
            for add in fas:
                for drop in drops:
                    new_roster = [p for p in roster if p != drop] + [add]
                    gain_pts = self._lineup_total(new_roster) - base_total
                    gain_worth = self.worth(params, add) - (self.worth(params, drop) if drop else 0.0)
                    score = gain_pts * NEED_K * (0.4 + params.horizon) + 0.5 * gain_worth
                    candidate = (score, add, drop)
                    if best is None or (-candidate[0], candidate[1]) < (-best[0], best[1]):
                        best = candidate
            if best is None or best[0] < 6.0 - 4.0 * params.waiver_aggr:
                continue
            _, add, drop = best
            if tid == self.user_tid and decision_key_waiver(week, add, drop) in self.veto:
                continue
            self.fa.discard(add)
            if drop:
                roster.remove(drop)
                self.fa.add(drop)
            roster.append(add)
            self._event(
                week, "waiver", team=tid, involves_user=tid == self.user_tid,
                add=self._asset(add), drop=self._asset(drop) if drop else None,
                key=decision_key_waiver(week, add, drop), gain=round(best[0], 2),
            )

    def protected_for(self, tid: str) -> set[str]:
        return self.protected if tid == self.user_tid else set()

    # ---------------------------------------------------------------- trades

    def _accept_noise(self, week: int, tid: str) -> float:
        key = (week, tid)
        if key not in self._noise_cache:
            sd = self.params[tid].noise_sd
            z = self.rng.stream(week, "trade", 100 + self.team_index[tid]).standard_normal()
            self._noise_cache[key] = sd * float(z)
        return self._noise_cache[key]

    def _utility(
        self, tid: str, base_total: float, give: tuple[str, ...], get: tuple[str, ...]
    ) -> float:
        params = self.params[tid]
        give_set = set(give)
        new_roster = [p for p in self.rosters[tid] if p not in give_set] + list(get)
        dval = sum(_convex(self.worth(params, p)) for p in get) - sum(
            _convex(self.worth(params, p)) for p in give
        )
        need = (self._lineup_total(new_roster) - base_total) * NEED_K * (0.4 + params.horizon)
        return dval + need

    def _trade_phase(self, week: int) -> None:
        if week > self.snap.settings.trade_deadline_week:
            return
        n = len(self.tids)
        order = self.rng.stream(week, "trade", 0).permutation(n)
        done: set[str] = set()
        count = 0
        for ti in order:
            if count >= MAX_TRADES_PER_WEEK:
                break
            tid = self.tids[int(ti)]
            params = self.params[tid]
            if tid in done or params.activity <= 0 or self.trades_made[tid] >= params.max_trades:
                continue
            r = self.rng.stream(week, "trade", 1 + int(ti))
            if r.random() > params.activity:
                continue
            partners = [
                self.tids[int(j)]
                for j in r.permutation(n)
                if int(j) != int(ti) and self.tids[int(j)] not in done
            ][:PARTNERS_PER_SEARCH]
            found = self._best_deal(week, tid, partners)
            if found is None:
                continue
            partner, give, get, ui, uj = found
            involves_user = self.user_tid in (tid, partner)
            key = decision_key_trade(
                week,
                give if tid == self.user_tid else get,
                get if tid == self.user_tid else give,
            ) if involves_user else ""
            done.update((tid, partner))
            if involves_user and key in self.veto:
                continue
            self._apply_trade(week, tid, partner, give, get, key, ui, uj)
            count += 1

    def _best_deal(self, week: int, tid: str, partners: list[str]):
        params = self.params[tid]
        base = self._lineup_total(self.rosters[tid])
        best = None
        for partner in partners:
            pparams = self.params[partner]
            if self.trades_made[partner] >= pparams.max_trades:
                continue
            pbase = self._lineup_total(self.rosters[partner])
            noise = self._accept_noise(week, partner)
            mine = [p for p in self.rosters[tid] if p not in self.protected_for(tid) and self.pos[p] != "K"]
            theirs = [p for p in self.rosters[partner] if p not in self.protected_for(partner) and self.pos[p] != "K"]
            # What each side would happily send: assets the other values most
            # relative to how the sender values them.
            gives = sorted(
                mine,
                key=lambda p: (-(self.worth(pparams, p) - self.worth(params, p)), p),
            )[:CANDIDATES_PER_SIDE]
            gets = sorted(
                theirs,
                key=lambda p: (-(self.worth(params, p) - self.worth(pparams, p)), p),
            )[:CANDIDATES_PER_SIDE]
            combos: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
            for g in gives:
                for r in gets:
                    combos.append(((g,), (r,)))
            for a in range(len(gives)):
                for b in range(a + 1, len(gives)):
                    for r in gets[:2]:
                        combos.append(((gives[a], gives[b]), (r,)))
            for give, get in combos:
                ui = self._utility(tid, base, give, get)
                if ui < params.propose_min:
                    continue
                uj = self._utility(partner, pbase, get, give)
                if uj + noise < pparams.accept_threshold:
                    continue
                score = (ui + uj, tuple(sorted(give)), tuple(sorted(get)))
                if best is None or (-score[0], score[1], score[2]) < (-best[0], best[1], best[2]):
                    best = (score[0], score[1], score[2], partner, ui, uj)
        if best is None:
            return None
        _, give, get, partner, ui, uj = best
        return partner, give, get, ui, uj

    def _apply_trade(
        self, week: int, tid: str, partner: str, give: tuple[str, ...], get: tuple[str, ...],
        key: str, ui: float, uj: float,
    ) -> None:
        a, b = self.rosters[tid], self.rosters[partner]
        for p in give:
            a.remove(p)
        for p in get:
            b.remove(p)
        a.extend(get)
        b.extend(give)
        self.trades_made[tid] += 1
        self.trades_made[partner] += 1
        self._event(
            week, "trade", team=tid, partner=partner,
            involves_user=self.user_tid in (tid, partner), key=key,
            gives=[self._asset(p) for p in give], gets=[self._asset(p) for p in get],
            initiator_gain=round(ui, 2), partner_gain=round(uj, 2),
        )
        for t in (tid, partner):
            self._enforce_cap(week, t)

    def _enforce_cap(self, week: int, tid: str) -> None:
        roster = self.rosters[tid]
        params = self.params[tid]
        while len(roster) > self.cap[tid]:
            starters = {pid for _, pid in pick_lineup(self.plan, self._lineup_entries(roster))[0] if pid}
            candidates = sorted(
                (p for p in roster if p not in starters and p not in self.protected_for(tid)),
                key=lambda p: (self.worth(params, p), p),
            )
            if not candidates:
                break
            drop = candidates[0]
            roster.remove(drop)
            self.fa.add(drop)
            self._event(week, "drop", team=tid, involves_user=tid == self.user_tid, player=self._asset(drop))

    # ----------------------------------------------------------------- weeks

    def _asset(self, pid: str) -> dict[str, Any]:
        return {"player_id": pid, "name": self.name[pid], "pos": self.pos[pid]}

    def _event(self, week: int, kind: str, **fields: Any) -> None:
        self.events.append({"week": week, "seq": len(self.events), "type": kind, **fields})

    def _week_points(self, week: int) -> np.ndarray:
        n = len(self.pids)
        z = self.rng.stream(week, "score", 0).standard_normal(n)
        zt = self.rng.stream(week, "score", 1).standard_normal(self.nfl_count)
        shared = math.sqrt(TEAM_CORRELATION)
        own = math.sqrt(1.0 - TEAM_CORRELATION)
        form = np.array(self.form)
        pts = self.mean_arr * form + self.sd * (own * z + shared * zt[self.nfl_of])
        pts = np.maximum(pts, 0.0)
        out = np.array(self.out) > 0
        pts[out] = 0.0
        return pts

    def _lineup_for(self, tid: str) -> Assignment:
        roster = self.rosters[tid]
        entries = [(self.proj(p), p, self.pos[p]) for p in roster if self.out[self.idx[p]] == 0]
        if tid == self.user_tid and not self.strategy.lineup_auto_set:
            self.user_assign = carry_lineup(self.plan, self.user_assign, entries)
            return self.user_assign
        assignment = pick_lineup(self.plan, entries)[0]
        if tid == self.user_tid:
            self.user_assign = assignment
        return assignment

    def _score_team(self, tid: str, pts: np.ndarray) -> float:
        return sum(float(pts[self.idx[pid]]) for _, pid in self._lineup_for(tid) if pid)

    def _optimal_actual(self, tid: str, pts: np.ndarray) -> float:
        entries = [
            (float(pts[self.idx[p]]), p, self.pos[p]) for p in self.rosters[tid]
        ]
        return pick_lineup(self.plan, entries)[1]

    def _play_week(self, week: int, pairs: tuple[tuple[str, str], ...], pts: np.ndarray) -> dict[str, Any]:
        scores = {tid: self._score_team(tid, pts) for tid in self.tids}
        games = []
        for home, away in pairs:
            hs, aws = scores[home], scores[away]
            games.append({"home": home, "away": away, "home_pts": round(hs, 1), "away_pts": round(aws, 1)})
            sh, sa = self.stand[home], self.stand[away]
            sh.pf += hs
            sh.pa += aws
            sa.pf += aws
            sa.pa += hs
            if abs(hs - aws) < 1e-9:
                sh.ties += 1
                sa.ties += 1
            elif hs > aws:
                sh.wins += 1
                sa.losses += 1
            else:
                sa.wins += 1
                sh.losses += 1
        playing = {t for pair in pairs for t in pair}
        if self.user_tid in playing:
            self.user_games += 1
            self.user_pts_started += scores[self.user_tid]
            self.user_pts_optimal += self._optimal_actual(self.user_tid, pts)
            others = [scores[t] for t in playing if t != self.user_tid]
            if others:
                beaten = sum(1 for s in others if scores[self.user_tid] > s)
                self.all_play_expected += beaten / len(others)
        return {"week": week, "games": games}

    # -------------------------------------------------------------- playoffs

    def _seeds(self) -> list[str]:
        ranked = sorted(
            self.tids,
            key=lambda t: (-self.stand[t].win_pct_points, -self.stand[t].pf, t),
        )
        return ranked

    def _playoffs(self) -> tuple[list[dict[str, Any]], str, dict[str, str]]:
        settings = self.snap.settings
        seeds = self._seeds()[: max(0, min(settings.playoff_teams, len(self.tids)))]
        result_label = {t: "missed" for t in self.tids}
        for t in seeds:
            result_label[t] = "lost_round_1"
        if len(seeds) < 2:
            return [], seeds[0] if seeds else "", result_label
        size = 1
        while size < len(seeds):
            size *= 2
        order = [1]
        while len(order) < size:
            total = len(order) * 2 + 1
            order = [x for s in order for x in (s, total - s)]
        slots: list[str | None] = [seeds[s - 1] if s <= len(seeds) else None for s in order]
        rounds = int(math.log2(size))
        rounds_log: list[dict[str, Any]] = []
        week0 = settings.regular_season_end
        alive = slots
        for r in range(1, rounds + 1):
            week = week0 + r
            self._roll_injuries_and_form(week)
            pts = self._week_points(week)
            nxt: list[str | None] = []
            games = []
            for i in range(0, len(alive), 2):
                a, b = alive[i], alive[i + 1]
                if a is None or b is None:
                    nxt.append(a or b)
                    continue
                sa, sb = self._score_team(a, pts), self._score_team(b, pts)
                winner = a if (sa > sb or (sa == sb and seeds.index(a) < seeds.index(b))) else b
                games.append({"home": a, "away": b, "home_pts": round(sa, 1), "away_pts": round(sb, 1), "winner": winner})
                nxt.append(winner)
                loser = b if winner == a else a
                result_label[loser] = (
                    "runner_up" if r == rounds else
                    "semifinal" if r == rounds - 1 and rounds >= 2 else f"lost_round_{r}"
                )
            rounds_log.append({"round": r, "week": week, "games": games})
            alive = nxt
        champion = alive[0] or ""
        if champion:
            result_label[champion] = "champion"
        return rounds_log, champion, result_label

    # ------------------------------------------------------------------ run

    def run(self) -> SeasonOutcome:
        settings = self.snap.settings
        weekly: list[dict[str, Any]] = []
        for offset, pairs in enumerate(self.snap.schedule):
            week = settings.start_week + offset
            if week > settings.regular_season_end:
                break
            self._roll_injuries_and_form(week)
            self._waiver_phase(week)
            self._trade_phase(week)
            pts = self._week_points(week)
            weekly.append(self._play_week(week, pairs, pts))
        playoff_rounds, champion, labels = self._playoffs()
        seeds = self._seeds()
        seed_of = {t: i + 1 for i, t in enumerate(seeds)}
        standings = []
        for tid in seeds:
            s = self.stand[tid]
            persona = self.personas.get(tid)
            standings.append({
                "team_id": tid, "name": self.teams[self.team_index[tid]].name,
                "owner": self.teams[self.team_index[tid]].owner, "is_user": tid == self.user_tid,
                "persona_id": persona.pid if persona else "you",
                "wins": s.wins, "losses": s.losses, "ties": s.ties,
                "pf": round(s.pf, 1), "pa": round(s.pa, 1), "seed": seed_of[tid],
                "made_playoffs": seed_of[tid] <= settings.playoff_teams,
                "playoff_result": labels[tid],
            })
        user_stand = self.stand[self.user_tid]
        user = {
            "team_id": self.user_tid, "wins": user_stand.wins, "losses": user_stand.losses,
            "ties": user_stand.ties, "pf": round(user_stand.pf, 1), "pa": round(user_stand.pa, 1),
            "seed": seed_of[self.user_tid], "playoff_result": labels[self.user_tid],
            "made_playoffs": seed_of[self.user_tid] <= settings.playoff_teams,
            "lineup_efficiency": round(self.user_pts_started / self.user_pts_optimal, 4)
            if self.user_pts_optimal > 0 else 1.0,
            "expected_wins": round(self.all_play_expected, 2),
            "games": self.user_games,
        }
        return SeasonOutcome(
            engine_version=ENGINE_VERSION, seed=self.seed, mode=self.snap.mode,
            start_week=settings.start_week, standings=standings, weekly=weekly,
            playoffs=playoff_rounds, champion=champion, events=self.events,
            personas=self._persona_reports(), user=user,
        )

    def _persona_reports(self) -> list[dict[str, Any]]:
        """Scouting report per team from the opening snapshot: persona, strength
        and age context. (Computed from setup-time values, stored on self.)"""

        out = []
        for tid in self.tids:
            persona = self.personas.get(tid)
            out.append({
                "team_id": tid,
                "name": self.teams[self.team_index[tid]].name,
                "is_user": tid == self.user_tid,
                "persona_id": persona.pid if persona else "you",
                "label": persona.label if persona else "You",
                "blurb": persona.blurb if persona else "Your strategy drives this team.",
                "power_percentile": round(self.power_pct[tid], 2),
                "avg_age": round(self.avg_age[tid], 1),
            })
        return out


def simulate_season(
    snapshot: LeagueSnapshot,
    strategy: Strategy,
    seed: int,
    *,
    veto: Iterable[str] = (),
) -> SeasonOutcome:
    """Run one season. ``veto`` is a set of user-decision keys (see
    ``decision_key_trade`` / ``decision_key_waiver``) to skip, for counterfactual
    replays."""

    return _World(snapshot, strategy, int(seed), frozenset(veto)).run()


__all__ = [
    "SeasonOutcome", "simulate_season", "decision_key_trade", "decision_key_waiver",
    "PERSONAS",
]
