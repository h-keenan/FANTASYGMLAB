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
from modules.sim.game_types import NON_TRADABLE, SINGLETON_POSITIONS, GameError, GameSnapshot, slot_positions
from modules.sim.lineup import pick_lineup
from modules.sim.personas import PERSONAS, TeamParams
from modules.sim.rng import WorldRng
from modules.sim.types import is_pick_id

MAX_TRADE_SIDE = 3
MAX_AI_TRADES_PER_WEEK = 3
MAX_OFFERS_PER_WEEK = 3
AI_SEASON_TRADE_CAP = 6  # with anyone, the user included
CANDIDATES_PER_SIDE = 4
PARTNERS_PER_SEARCH = 3
FLOOR_BASE = 3.0  # linear worth an AI will give up before it refuses outright
FLOOR_MAX = 10.0
OFFER_USER_FLOOR = -2.0  # AI never proposes a deal the user is clearly robbed in

PERSONA_PITCH = {  # original (dynasty-flavored) pitches; modes override via the policy
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
    kept = {pos: sum(1 for p in roster if snap.players[p].pos == pos) for pos in SINGLETON_POSITIONS}
    droppable = sorted(
        (p for p in roster if p not in starters and not (snap.players[p].pos in kept and kept[snap.players[p].pos] <= 1)),
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
    # What the counter changed and why, in plain labeled terms ("They want a TE: asking for X"), plus the value delta.
    counter_note: str | None = None
    counter_delta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        delta = self.counter_delta
        if delta is not None:
            # The API never carries the model's trade-value numbers (they are the hidden rating): only the direction
            # of the change (-1 / 0 / +1), which is all the client turns into words.
            change = float(delta.get("user_net_change") or 0.0)
            delta = {k: v for k, v in delta.items() if k not in ("user_net_before", "user_net_after")}
            delta["user_net_change"] = 0 if abs(change) < 0.5 else (1 if change > 0 else -1)
        return {
            "decision": self.decision, "reason_code": self.reason_code, "reason": self.reason,
            "chips": list(self.chips), "counter": self.counter,
            "counter_note": self.counter_note, "counter_delta": delta,
        }


@dataclass
class Counter:
    give: tuple[str, ...]
    get: tuple[str, ...]
    code: str
    reason: str
    chips: list[str]
    note: str
    delta: dict[str, Any]


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
        # Picks never touch the roster; a taxi/IR player who arrives is active (and counts) here.
        roster = [p for p in self.state.rosters[tid] if p not in give_set] + [p for p in get if not is_pick_id(p)]
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

    def tradable(self, tid: str) -> list[str]:
        """What the AI itself puts in or asks for in a trade (its own offers, AI-AI deals, counters): every player it owns
        (active, IR, taxi) except kickers and defenses, plus its picks when the mode trades them. The user may trade a K or
        DEF (settings.kd_v 1, see validate_offer); the AI never builds a deal around one, so it never crafts a nonsense kicker counter."""

        out = [p for p in self.state.holdings(tid) if self.snap.players[p].pos not in NON_TRADABLE]
        if self.snap.settings.policy.dynasty:
            out += self.state.picks_of(tid)
        return out

    # --------------------------------------------------------------- needs

    def need_position(self, tid: str) -> tuple[str, float]:
        """The position ``tid`` is weakest at relative to the league, with the
        ratio (1.0 = league average)."""

        snap, state, ev = self.snap, self.state, self.ev
        slots = snap.settings.slots
        starters = {pos: max(1, sum(1 for s in slots if s == pos)) for pos in ("QB", "RB", "WR", "TE")}
        starters["QB"] += slots.count("SUPER_FLEX")  # a superflex league starts a second quarterback

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

    def roster_size_after(self, tid: str, give: Sequence[str], get: Sequence[str]) -> int:
        """Roster spots ``tid`` uses after the swap, before any forced cut (picks never take a spot)."""

        give_set = set(give)
        kept = sum(1 for p in self.state.rosters[tid] if p not in give_set)
        return kept + sum(1 for p in get if not is_pick_id(p))

    def legal_for_counter(self, tid: str, give: Sequence[str], get: Sequence[str]) -> bool:
        """A counter never forces ``tid`` over the roster limit: it ends within the limit, or no fuller than it is now
        (a team already over is not made worse). The user can therefore never be pushed over without having chosen it,
        and the AI is never asked to take a roster it would have to cut down."""

        limit = self.snap.settings.roster_limit
        after = self.roster_size_after(tid, give, get)
        return after <= limit or after <= len(self.state.rosters[tid])

    def failure_cause(self, ai: str, user_gives: Sequence[str], user_gets: Sequence[str]) -> tuple[str, str, list[str]]:
        """Why the AI said no, from counterfactuals rather than the first matching label: if the value alone would
        pass, the lineup need is what sank it (name the position it is short at); if the value alone fails, the
        offer is simply short on value and that is what it says, however thin the AI is at some position."""

        params = self.params(ai)
        snap = self.snap
        _, margin, dval, need, loss = self.ai_accepts(ai, user_gives, user_gets)
        pos, ratio = self.need_position(ai)
        incoming = {snap.players[p].pos for p in user_gives if not is_pick_id(p)}
        if loss > floor_tolerance(params):
            return "fair_floor", "They will not give up that much value in one deal.", ["too lopsided"]
        value_alone_passes = (margin - need) >= 0
        if value_alone_passes and need < 0:
            if ratio < 0.92 and pos not in incoming:
                return "needs_position", f"Needs a {pos}.", [f"needs {pos}"]
            return "roster_fit", "This would leave a hole in their lineup.", ["hurts their lineup"]
        return "wants_more_value", "They want more value back.", ["wants more value"]

    def verdict(self, ai: str, user_gives: Sequence[str], user_gets: Sequence[str]) -> Verdict:
        ok, margin, dval, need, loss = self.ai_accepts(ai, user_gives, user_gets)
        params = self.params(ai)
        if ok:
            fits = need >= max(2.0, 0.35 * abs(dval + need))
            return Verdict(
                "accept", "fits_need" if fits else "fair_value",
                "They like how this fits their roster." if fits else "They see this as a fair deal.",
                chips=["fits their need"] if fits else ["fair value"], margin=margin,
            )
        code, reason, chips = self.failure_cause(ai, user_gives, user_gets)
        counter = self.build_counter(ai, user_gives, user_gets, code)
        if counter is not None:
            # The stated reason must match what the counter did: a "needs a TE" counter asks for a TE, otherwise
            # the reason is restated as what it really was (value) and the note says what was asked and why.
            if counter.code != code:
                code, reason, chips = counter.code, counter.reason, counter.chips
            return Verdict(
                "counter", code, reason + " They countered.", chips=chips,
                counter={"give": list(counter.give), "get": list(counter.get)}, margin=margin,
                counter_note=counter.note, counter_delta=counter.delta,
            )
        return Verdict("decline", code, reason, chips=chips, margin=margin)

    def build_counter(self, ai: str, user_gives: Sequence[str], user_gets: Sequence[str], code: str = "wants_more_value") -> "Counter | None":
        """The cheapest change, for the user, that the AI will accept AND that both rosters can legally hold: ask for
        one more of the user's assets, or take one of the asked players off the table. Never the AI paying more.

        Multi-factor: candidates are ranked by what they cost the user (neutral lens), tie-broken by how much the AI
        wants them (its horizon: age and injury, its lineup need), so a rebuilder asks for youth and a contender for
        production. When the reason is a position need the counter must ask for that position (and when it cannot, it
        is restated as the value shortfall it was, never left claiming a need it did not act on)."""

        snap, state, ev = self.snap, self.state, self.ev
        user = snap.user_team.tid
        params = self.params(ai)
        need_pos: str | None = None
        if code == "needs_position":
            need_pos = self.need_position(ai)[0]
        options: list[tuple[tuple, str, tuple[str, ...], tuple[str, ...], list[str], list[str], str]] = []

        def consider(give: tuple[str, ...], get: tuple[str, ...], asked: list[str], removed: list[str], cost: float, tag: str) -> None:
            if not (self.legal_for_counter(ai, get, give) and self.legal_for_counter(user, give, get)):
                return
            ok, margin, _, need, _ = self.ai_accepts(ai, give, get)
            if not ok:
                return
            # Rank: user cost first, then the AI's own lineup fit (higher is better), then ids for determinism.
            options.append(((round(cost, 6), -round(need, 6), tag), tag, give, get, asked, removed, tag))

        pool = [p for p in self.tradable(user) if p not in user_gives]
        extra = sorted(pool, key=lambda p: (-(ev.worth(params, p) - ev.worth(USER_PARAMS, p)), p))[:8]
        if need_pos:
            extra = sorted((p for p in pool if not is_pick_id(p) and snap.players[p].pos == need_pos),
                           key=lambda p: (-ev.worth(params, p), p))[:8]
        if len(user_gives) < snap.settings.policy.max_trade_side:
            for p in extra:
                consider(tuple(user_gives) + (p,), tuple(user_gets), [p], [], ev.worth(USER_PARAMS, p), "add:" + p)
        if len(user_gets) > 1 and not need_pos:
            for p in user_gets:
                consider(tuple(user_gives), tuple(x for x in user_gets if x != p), [], [p], ev.worth(USER_PARAMS, p), "drop:" + p)
        if not options:
            if need_pos:  # could not fix the need the way the reason claims: fall back to an honest value counter
                return self.build_counter(ai, user_gives, user_gets, "wants_more_value")
            return None
        options.sort(key=lambda o: o[0])
        _, _, give, get, asked, removed, _ = options[0]
        return self._describe_counter(ai, code, user_gives, user_gets, give, get, asked, removed)

    def _describe_counter(self, ai, code, old_give, old_get, give, get, asked, removed) -> "Counter":
        snap, ev = self.snap, self.ev

        def label(pid: str) -> str:
            if is_pick_id(pid):
                return ev.pick_name(pid)
            p = snap.players[pid]
            return f"{p.name} ({p.pos})"

        def net(g: Sequence[str], r: Sequence[str]) -> float:  # the user's net trade value (neutral lens)
            return sum(ev.worth(USER_PARAMS, p) for p in r) - sum(ev.worth(USER_PARAMS, p) for p in g)

        pos = self.need_position(ai)[0]
        if asked:
            who = label(asked[0])
            if code == "needs_position":
                note = f"They want a {pos}: asking for {who}."
            elif code == "roster_fit":
                note = f"This leaves a hole in their lineup: asking for {who} to fill it."
            elif code == "fair_floor":
                note = f"They will not give up that much value: asking for {who} to even it out."
            else:
                note = f"They want more value: asking for {who} as well."
        else:
            who = label(removed[0])
            note = f"They want to keep {who}: the counter leaves him out."
        before, after = net(old_give, old_get), net(give, get)
        delta = {
            "user_net_before": round(before, 1), "user_net_after": round(after, 1), "user_net_change": round(after - before, 1),
            "asked": list(asked), "removed": list(removed),
            "your_roster_after": self.roster_size_after(snap.user_team.tid, give, get),
            "their_roster_after": self.roster_size_after(ai, get, give),
            "roster_limit": snap.settings.roster_limit,
        }
        chips = [f"needs {pos}"] if code == "needs_position" else ["wants more value"] if code == "wants_more_value" else ["hurts their lineup"] if code == "roster_fit" else ["too lopsided"]
        reason = f"Needs a {pos}." if code == "needs_position" else "They want more value back." if code == "wants_more_value" else "This would leave a hole in their lineup." if code == "roster_fit" else "They will not give up that much value in one deal."
        return Counter(give=tuple(give), get=tuple(get), code=code, reason=reason, chips=chips, note=note, delta=delta)

    # ------------------------------------------------------------- searching

    def find_deal(self, proposer: str, partners: Sequence[str], *, to_user: bool = False,
                  want: Iterable[str] | None = None, give_pos: str | None = None):
        """Best two-sided deal the ``proposer`` AI would make with one of
        ``partners`` (port of the season engine's search). With ``to_user`` the
        partner is the user and acceptance is judged against a neutral lens. ``want`` (the trade block) restricts what
        the proposer asks for to those assets, and ``give_pos`` prefers sending that position; a block deal must also leave
        both rosters legal (the same rule counters follow). Without ``want`` this is exactly the original search."""

        snap, state, ev = self.snap, self.state, self.ev
        params = self.params(proposer)
        best = None
        for partner in partners:
            if not to_user and state.trades_made[partner] >= self.params(partner).max_trades:
                continue
            pparams = self.params(partner)
            mine = self.tradable(proposer)
            theirs = self.tradable(partner)
            lens = USER_PARAMS if to_user else pparams
            gives = sorted(mine, key=lambda p: (-(ev.worth(lens, p) - ev.worth(params, p)), p))[:CANDIDATES_PER_SIDE]
            gets = sorted(theirs, key=lambda p: (-(ev.worth(params, p) - ev.worth(lens, p)), p))[:CANDIDATES_PER_SIDE]
            if want is not None:
                wanted = set(want)
                gets = sorted((p for p in theirs if p in wanted), key=lambda p: (-(ev.worth(params, p) - ev.worth(lens, p)), p))[:CANDIDATES_PER_SIDE]
                if give_pos:
                    pool = [p for p in mine if not is_pick_id(p) and snap.players[p].pos == give_pos]
                    if pool:
                        gives = sorted(pool, key=lambda p: (-(ev.worth(lens, p) - ev.worth(params, p)), p))[:CANDIDATES_PER_SIDE]
            combos: list[tuple[tuple[str, ...], tuple[str, ...]]] = [((g,), (r,)) for g in gives for r in gets]
            for a, b in combinations(range(len(gives)), 2):
                combos.extend(((gives[a], gives[b]), (r,)) for r in gets[:2])
            for give, get in combos:
                if want is not None and not (self.legal_for_counter(proposer, give, get) and self.legal_for_counter(partner, get, give)):
                    continue
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
    pitches = snap.settings.policy.pitches or PERSONA_PITCH
    return f"{snap.team(tid).name} {pitches.get(persona.pid, 'sent you an offer') if persona else 'sent an offer'}."


def validate_offer(snap: GameSnapshot, state: GameState, partner: str, give: Sequence[str], get: Sequence[str]) -> None:
    """Shape and ownership checks; raises ValueError (422) for client mistakes."""

    user = snap.user_team.tid
    if partner == user or partner not in snap.tids:
        raise ValueError("partner must be another team.")
    side_max = snap.settings.policy.max_trade_side
    for label, side in (("give", give), ("get", get)):
        if not 1 <= len(side) <= side_max:
            raise ValueError(f"{label} must list 1-{side_max} assets.")
        if len(set(side)) != len(side):
            raise ValueError(f"{label} has duplicates.")
    for label, side, owner, who in (("give", give, user, "your"), ("get", get, partner, "that team's")):
        for pid in side:
            if is_pick_id(pid):
                if not snap.settings.policy.dynasty:
                    raise ValueError("Draft picks cannot be traded in this league.")
                if state.pick_owner.get(pid) != owner:
                    raise ValueError(f"You can only trade picks on {who} side that {'you' if label == 'give' else 'they'} own.")
                # Picks are tradable through the whole rookie draft (the draft order follows
                # pick ownership); only a pick that has already been used is spent.
                if state.offseason and any(m.get("pick") == pid for m in state.offseason.get("picks", ())):
                    raise GameError("picks_locked", "That pick has already been used in the draft.")
            elif pid not in snap.players or state.where(owner, pid) is None:
                raise ValueError(f"You can only {'give players on your roster' if label == 'give' else 'ask for players on that team' + chr(39) + 's roster'}.")
            elif snap.players[pid].pos in snap.settings.non_tradable:
                raise ValueError("Kickers and defenses cannot be traded.")
    # Kickers and defenses are one per roster: a trade may not leave either team with two of one (it can swap them one for one).
    if not snap.settings.non_tradable:
        for tid, leaving, arriving in ((user, give, get), (partner, get, give)):
            for pos in SINGLETON_POSITIONS:
                held = sum(1 for p in state.holdings(tid) if snap.players[p].pos == pos and p not in leaving)
                coming = sum(1 for p in arriving if not is_pick_id(p) and snap.players[p].pos == pos)
                if coming and held + coming > 1:  # only a trade that ADDS one is refused (a roster already over, e.g. mid-offseason, is not blocked)
                    who = "You" if tid == user else "They"
                    raise GameError("singleton_limit", f"{who} would end up with two {'kickers' if pos == 'K' else 'defenses'}. Trade yours away in the same deal.")


def offer_key(partner: str, give: Iterable[str], get: Iterable[str]) -> str:
    return f"{partner}|{'+'.join(sorted(give))}|{'+'.join(sorted(get))}"


def trade_window(snap: GameSnapshot, state: GameState) -> str | None:
    """None if trading is open, else the closing reason code."""

    if state.status == "drafting":
        return "wrong_phase"
    if state.status == "offseason":
        # Dynasty's offseason is trade season, until the rookie draft is under way.
        return None if snap.settings.policy.dynasty else "trades_closed"
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
