"""AI managers for the GM game: lineups, waiver claims, trades.

Same ideas as the season engine's AI (personas as parameter vectors, convex
value, lineup need, persona noise), reimplemented over this game's state so
nothing real is called. Everything is deterministic in ``(seed, week, team)``:
trade verdicts use noise keyed by (week, team) only, never by the offer, so a
preview and the real send agree and re-rolling an offer changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Iterable, Sequence

from modules.sim.game_eval import NEED_K, USER_PARAMS, Evaluator, convex, team_params
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot, slot_positions
from modules.sim.lineup import pick_lineup
from modules.sim.personas import PERSONAS, TeamParams
from modules.sim.rng import WorldRng

MAX_TRADE_SIDE = 3
MAX_AI_TRADES_PER_WEEK = 3
MAX_OFFERS_PER_WEEK = 3
AI_SEASON_TRADE_CAP = 6  # with anyone, the user included
CANDIDATES_PER_SIDE = 4
PARTNERS_PER_SEARCH = 3
FLOOR_BASE = 3.0  # linear worth an AI will give up before it refuses outright
FLOOR_MAX = 10.0
OFFER_USER_FLOOR = -2.0  # AI never proposes a deal the user is clearly robbed in

PERSONA_PITCH = {
    "contender": "wants proven production for the title run",
    "rebuilder": "is selling vets for younger upside",
    "value_shark": "thinks this is a fair swap",
    "youth_hoarder": "likes the youth on your roster",
    "specialist": "is loading up at one position",
    "passive": "rarely deals, but likes this one",
    "chaos": "had a feeling about this one",
}


def _idx(snap: GameSnapshot, tid: str) -> int:
    return [t.tid for t in snap.teams].index(tid)


def floor_tolerance(params: TeamParams) -> float:
    return min(FLOOR_MAX, FLOOR_BASE + 0.5 * params.noise_sd)


# ------------------------------------------------------------------ lineups


def ai_lineup(ev: Evaluator, tid: str, week: int, seed: int) -> list[list]:
    """Optimal by projection, excluding injured and bye players. Passive
    managers (and, on easy, wildcards) sometimes just carry last week's lineup
    over, so they are beatable."""

    snap, state = ev.snap, ev.state
    roster = state.rosters[tid]
    team = snap.team(tid)
    lag = {"passive": 0.35, "chaos": 0.10}.get(team.persona_id, 0.0)
    if snap.settings.difficulty == "easy":
        lag += 0.15 if lag else 0.05
    elif snap.settings.difficulty == "hard":
        lag *= 0.5
    prev = state.lineups.get(tid)
    if lag > 0 and prev and any(row[1] for row in prev):
        roll = float(WorldRng(seed).stream(week, "gsetup", 200 + _idx(snap, tid)).random())
        if roll < lag:
            return ev.sticky_lineup(roster, week, prev)
    return ev.best_lineup(roster, week)[0]


# ------------------------------------------------------------------ waivers


def ai_waiver_claim(
    ev: Evaluator, tid: str, week: int, seed: int, exclude: Iterable[str] = (),
) -> dict[str, Any] | None:
    """At most one claim per AI team per week: the add/drop with the best mix of
    lineup gain and value gain, if it clears the persona's bar."""

    snap, state = ev.snap, ev.state
    params = team_params(snap, tid)
    r = WorldRng(seed).stream(week, "gwaiver", _idx(snap, tid))
    roster = state.rosters[tid]
    # A starting slot nobody healthy can fill (injuries, a bye, a lone kicker) is an
    # emergency: no manager leaves it empty, so the random gate and the bar are waived.
    vacant = sorted({
        pos for slot, pid in ev.best_lineup(roster, week)[0] if not pid for pos in slot_positions(slot)
    })
    roll = r.random()
    if not vacant and (params.waiver_aggr <= 0 or roll > params.waiver_aggr):
        return None
    limit = snap.settings.roster_limit
    base_total = ev.lineup_total(roster)
    starters = {pid for _, pid in pick_lineup(ev.plan, ev.entries(roster, week, bye=False))[0] if pid}
    k_count = sum(1 for p in roster if snap.players[p].pos == "K")
    droppable = sorted(
        (p for p in roster if p not in starters and not (snap.players[p].pos == "K" and k_count <= 1)),
        key=lambda p: (ev.worth(params, p), p),
    )[:3]
    room = len(roster) < limit
    drops: list[str | None] = [None] if room else list(droppable)
    if not drops:
        return None
    owned = state.owner_map()
    taken = set(exclude)  # already claimed by someone ahead of this team in the order
    fas = sorted(
        (p for p in snap.pids if p not in owned and p not in taken and state.out.get(p, 0) == 0),
        key=lambda p: (-ev.worth(params, p), p),
    )[:8]
    if vacant:
        owned_now = set(owned)
        fill = sorted(
            (p for p in snap.pids if p not in owned_now and p not in taken and snap.players[p].pos in vacant
             and state.out.get(p, 0) == 0 and not ev.on_bye(p, week)),
            key=lambda p: (-ev.worth(params, p), p),
        )[:3]
        fas = fill or fas  # the vacancy is the whole point of this claim
    best: tuple[float, str, str | None] | None = None
    h = ev.horizon_now(params)
    for add in fas:
        for drop in drops:
            new_roster = [p for p in roster if p != drop] + [add]
            gain_pts = ev.lineup_total(new_roster) - base_total
            gain_worth = ev.worth(params, add) - (ev.worth(params, drop) if drop else 0.0)
            score = gain_pts * NEED_K * (0.4 + h) + 0.5 * gain_worth
            if best is None or (-score, add) < (-best[0], best[1]):
                best = (score, add, drop)
    if best is None or (best[0] < 6.0 - 4.0 * params.waiver_aggr and not vacant):
        return None
    return {"team": tid, "add": best[1], "drop": best[2], "start_slot": None, "gain": round(best[0], 2)}


# ------------------------------------------------------------------- trades


@dataclass
class Verdict:
    decision: str  # accept | counter | decline
    reason_code: str
    reason: str
    chips: list[str] = field(default_factory=list)
    counter: dict[str, list[str]] | None = None  # {"give": [...], "get": [...]} from the USER's side
    margin: float = 0.0  # how far above (+) / below (-) the AI's bar

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision, "reason_code": self.reason_code, "reason": self.reason,
            "chips": list(self.chips), "counter": self.counter,
        }


class TradeDesk:
    """Valuation for one moment (a fixed state and week)."""

    def __init__(self, ev: Evaluator, seed: int, week: int | None = None) -> None:
        self.ev = ev
        self.snap = ev.snap
        self.state = ev.state
        self.seed = seed
        self.week = week if week is not None else ev.state.week
        self._base: dict[str, float] = {}
        self._noise: dict[str, float] = {}
        self._params: dict[str, TeamParams] = {}

    def params(self, tid: str) -> TeamParams:
        if tid not in self._params:
            self._params[tid] = team_params(self.snap, tid)
        return self._params[tid]

    def base_total(self, tid: str) -> float:
        if tid not in self._base:
            self._base[tid] = self.ev.lineup_total(self.state.rosters[tid])
        return self._base[tid]

    def noise(self, tid: str) -> float:
        """Per (week, team), not per offer."""

        if tid not in self._noise:
            sd = self.params(tid).noise_sd
            z = WorldRng(self.seed).stream(self.week, "gtrade", 100 + _idx(self.snap, tid)).standard_normal()
            self._noise[tid] = sd * float(z)
        return self._noise[tid]

    def after_roster(self, tid: str, give: Sequence[str], get: Sequence[str]) -> tuple[list[str], list[str]]:
        """Roster after the swap, with the lowest-worth bench players cut to
        restore the roster limit. Returns (roster, auto_dropped)."""

        params = self.params(tid)
        give_set = set(give)
        roster = [p for p in self.state.rosters[tid] if p not in give_set] + list(get)
        dropped: list[str] = []
        limit = self.snap.settings.roster_limit
        while len(roster) > limit:
            starters = {pid for _, pid in pick_lineup(self.ev.plan, self.ev.entries(roster, self.week, bye=False))[0] if pid}
            bench = sorted((p for p in roster if p not in starters), key=lambda p: (self.ev.worth(params, p), p))
            if not bench:
                break
            roster.remove(bench[0])
            dropped.append(bench[0])
        return roster, dropped

    def utility(self, tid: str, give: Sequence[str], get: Sequence[str]) -> tuple[float, float, float]:
        """(utility, value part, need part) for ``tid`` sending ``give`` and
        receiving ``get``: convex value change plus lineup need."""

        params = self.params(tid)
        ev = self.ev
        new_roster, dropped = self.after_roster(tid, give, get)
        dval = (
            sum(convex(ev.worth(params, p)) for p in get)
            - sum(convex(ev.worth(params, p)) for p in give)
            - sum(convex(ev.worth(params, p)) for p in dropped)
        )
        need = (ev.lineup_total(new_roster) - self.base_total(tid)) * NEED_K * (0.4 + ev.horizon_now(params))
        return dval + need, dval, need

    def linear_loss(self, tid: str, give: Sequence[str], get: Sequence[str]) -> float:
        params = self.params(tid)
        return sum(self.ev.worth(params, p) for p in give) - sum(self.ev.worth(params, p) for p in get)

    def ai_accepts(self, ai: str, user_gives: Sequence[str], user_gets: Sequence[str]) -> tuple[bool, float, float, float, float]:
        """Would ``ai`` take ``user_gives`` for ``user_gets``? Returns
        (ok, margin, value part, need part, linear loss)."""

        params = self.params(ai)
        util, dval, need = self.utility(ai, user_gets, user_gives)
        loss = self.linear_loss(ai, user_gets, user_gives)
        margin = util + self.noise(ai) - params.accept_threshold
        ok = margin >= 0 and loss <= floor_tolerance(params)
        return ok, margin, dval, need, loss

    # --------------------------------------------------------------- needs

    def need_position(self, tid: str) -> tuple[str, float]:
        """The position ``tid`` is weakest at relative to the league, with the
        ratio (1.0 = league average)."""

        snap, state, ev = self.snap, self.state, self.ev
        slots = snap.settings.slots
        starters = {pos: max(1, sum(1 for s in slots if s == pos)) for pos in ("QB", "RB", "WR", "TE")}

        def quality(roster: Iterable[str], pos: str) -> float:
            vals = sorted((ev.ros_mean(p) for p in roster if snap.players[p].pos == pos), reverse=True)[: starters[pos]]
            vals += [0.0] * (starters[pos] - len(vals))
            return sum(vals) / starters[pos]

        worst = ("RB", 9.9)
        for pos in ("QB", "RB", "WR", "TE"):
            league = sum(quality(state.rosters[t], pos) for t in snap.tids) / max(1, len(snap.tids))
            ratio = quality(state.rosters[tid], pos) / league if league > 0 else 1.0
            if ratio < worst[1]:
                worst = (pos, ratio)
        return worst

    # ------------------------------------------------------------- verdicts

    def verdict(self, ai: str, user_gives: Sequence[str], user_gets: Sequence[str]) -> Verdict:
        ok, margin, dval, need, loss = self.ai_accepts(ai, user_gives, user_gets)
        params = self.params(ai)
        snap = self.snap
        if ok:
            fits = need >= max(2.0, 0.35 * abs(dval + need))
            return Verdict(
                "accept", "fits_need" if fits else "fair_value",
                "They like how this fits their roster." if fits else "They see this as a fair deal.",
                chips=["fits their need"] if fits else ["fair value"], margin=margin,
            )
        pos, ratio = self.need_position(ai)
        incoming_positions = {snap.players[p].pos for p in user_gives}
        chips: list[str] = []
        if loss > floor_tolerance(params):
            code, reason = "fair_floor", "They will not give up that much value in one deal."
            chips.append("too lopsided")
        elif ratio < 0.92 and pos not in incoming_positions and need < 0:
            code, reason = "needs_position", f"Needs a {pos}."
            chips.append(f"needs {pos}")
        elif need < -3.0:
            code, reason = "roster_fit", "This would leave a hole in their lineup."
            chips.append("hurts their lineup")
        else:
            code, reason = "wants_more_value", "They want more value back."
            chips.append("wants more value")
        counter = self.build_counter(ai, user_gives, user_gets)
        if counter is not None:
            return Verdict(
                "counter", code, reason + " They countered.", chips=chips, counter=counter, margin=margin
            )
        return Verdict("decline", code, reason, chips=chips, margin=margin)

    def build_counter(self, ai: str, user_gives: Sequence[str], user_gets: Sequence[str]) -> dict[str, list[str]] | None:
        """The cheapest change, for the user, that the AI will accept: ask the
        user for one more player, or take one of the asked players off the
        table. Never the AI paying more."""

        snap, state, ev = self.snap, self.state, self.ev
        user = snap.user_team.tid
        options: list[tuple[float, str, tuple[str, ...], tuple[str, ...]]] = []
        extra = sorted(
            (p for p in state.rosters[user] if p not in user_gives and snap.players[p].pos != "K"),
            key=lambda p: (-(ev.worth(self.params(ai), p) - ev.worth(USER_PARAMS, p)), p),
        )[:8]
        if len(user_gives) < MAX_TRADE_SIDE:
            for p in extra:
                give = tuple(user_gives) + (p,)
                if self.ai_accepts(ai, give, user_gets)[0]:
                    options.append((ev.worth(USER_PARAMS, p), "add:" + p, give, tuple(user_gets)))
        if len(user_gets) > 1:
            for p in user_gets:
                get = tuple(x for x in user_gets if x != p)
                if self.ai_accepts(ai, user_gives, get)[0]:
                    options.append((ev.worth(USER_PARAMS, p), "drop:" + p, tuple(user_gives), get))
        if not options:
            return None
        options.sort(key=lambda o: (o[0], o[1]))
        _, _, give, get = options[0]
        return {"give": list(give), "get": list(get)}

    # ------------------------------------------------------------- searching

    def find_deal(self, proposer: str, partners: Sequence[str], *, to_user: bool = False):
        """Best two-sided deal the ``proposer`` AI would make with one of
        ``partners`` (port of the season engine's search). With ``to_user`` the
        partner is the user and acceptance is judged against a neutral lens."""

        snap, state, ev = self.snap, self.state, self.ev
        params = self.params(proposer)
        best = None
        for partner in partners:
            if not to_user and state.trades_made[partner] >= self.params(partner).max_trades:
                continue
            pparams = self.params(partner)
            mine = [p for p in state.rosters[proposer] if snap.players[p].pos != "K"]
            theirs = [p for p in state.rosters[partner] if snap.players[p].pos != "K"]
            lens = USER_PARAMS if to_user else pparams
            gives = sorted(mine, key=lambda p: (-(ev.worth(lens, p) - ev.worth(params, p)), p))[:CANDIDATES_PER_SIDE]
            gets = sorted(theirs, key=lambda p: (-(ev.worth(params, p) - ev.worth(lens, p)), p))[:CANDIDATES_PER_SIDE]
            combos: list[tuple[tuple[str, ...], tuple[str, ...]]] = [((g,), (r,)) for g in gives for r in gets]
            for a, b in combinations(range(len(gives)), 2):
                combos.extend(((gives[a], gives[b]), (r,)) for r in gets[:2])
            for give, get in combos:
                ui, _, _ = self.utility(proposer, give, get)
                if ui < params.propose_min or self.linear_loss(proposer, give, get) > floor_tolerance(params):
                    continue
                uj, _, _ = self.utility(partner, get, give)
                if to_user:
                    if uj < OFFER_USER_FLOOR or self.linear_loss(partner, get, give) > 4.0:
                        continue
                elif uj + self.noise(partner) < pparams.accept_threshold or self.linear_loss(partner, get, give) > floor_tolerance(pparams):
                    continue
                score = (ui + uj, tuple(sorted(give)), tuple(sorted(get)))
                if best is None or (-score[0], score[1], score[2]) < (-best[0], best[1], best[2]):
                    best = (score[0], score[1], score[2], partner, ui, uj)
        if best is None:
            return None
        _, give, get, partner, ui, uj = best
        return partner, list(give), list(get), ui, uj


def offer_message(snap: GameSnapshot, tid: str) -> str:
    persona = PERSONAS.get(snap.team(tid).persona_id)
    return f"{snap.team(tid).name} {PERSONA_PITCH.get(persona.pid, 'sent you an offer') if persona else 'sent an offer'}."


def validate_offer(snap: GameSnapshot, state: GameState, partner: str, give: Sequence[str], get: Sequence[str]) -> None:
    """Shape and ownership checks; raises ValueError (422) for client mistakes."""

    user = snap.user_team.tid
    if partner == user or partner not in snap.tids:
        raise ValueError("partner must be another team.")
    for label, side in (("give", give), ("get", get)):
        if not 1 <= len(side) <= MAX_TRADE_SIDE:
            raise ValueError(f"{label} must list 1-{MAX_TRADE_SIDE} players.")
        if len(set(side)) != len(side):
            raise ValueError(f"{label} has duplicates.")
    for pid in give:
        if pid not in state.rosters[user]:
            raise ValueError("You can only give players on your roster.")
    for pid in get:
        if pid not in state.rosters[partner]:
            raise ValueError("You can only ask for players on that team's roster.")
    for pid in [*give, *get]:
        if snap.players[pid].pos == "K":
            raise ValueError("Kickers cannot be traded.")


def offer_key(partner: str, give: Iterable[str], get: Iterable[str]) -> str:
    return f"{partner}|{'+'.join(sorted(give))}|{'+'.join(sorted(get))}"


def trade_window(snap: GameSnapshot, state: GameState) -> str | None:
    """None if trading is open, else the closing reason code."""

    if state.status == "drafting":
        return "wrong_phase"
    if state.status != "in_season":
        return "trades_closed"
    if state.week > snap.settings.trade_deadline_week:
        return "trade_deadline_passed"
    return None


__all__ = [
    "Verdict", "TradeDesk", "ai_lineup", "ai_waiver_claim", "validate_offer", "offer_key",
    "trade_window", "offer_message", "MAX_TRADE_SIDE", "MAX_AI_TRADES_PER_WEEK", "MAX_OFFERS_PER_WEEK",
    "AI_SEASON_TRADE_CAP", "PARTNERS_PER_SEARCH",
]
