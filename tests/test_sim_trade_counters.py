"""AI trade counters: the invariants a counter must hold, swept over many random offers.

A counter must (1) match its stated reason (a "needs a TE" counter asks for a TE, otherwise the reason is the value
shortfall it really was), (2) be legal for both rosters (nobody is pushed over the roster limit by the counter, and
the AI never takes a roster it would have to cut down), (3) be something the AI would accept, (4) explain itself in
labeled terms with the value delta, and (5) never be a roster-dump consolidation. Decisions on the offer itself
(accept / decline) are unchanged by the counter rules, so replay (events record outcomes) is unaffected.
"""

from __future__ import annotations

import random

from modules.sim.game_ai import TradeDesk, floor_tolerance
from modules.sim.game_eval import Evaluator
from modules.sim.types import is_pick_id

from tests.test_sim_game_engine import drafted


def _offers(snap, state, rng, n):
    user = snap.user_team.tid
    partners = [t for t in snap.tids if t != user]
    tradable = lambda tid: [p for p in state.rosters[tid] if snap.players[p].pos not in ("K", "DEF")]  # noqa: E731
    for _ in range(n):
        partner = rng.choice(partners)
        give = rng.sample(tradable(user), rng.randint(1, 3))
        get = rng.sample(tradable(partner), rng.randint(1, 3))
        yield partner, give, get


def sweep(seeds=(3, 11, 19), per_seed=120):
    stats = {"offers": 0, "accept": 0, "counter": 0, "decline": 0, "violations": [], "needs_position": 0, "needs_position_asked_pos": 0}
    for seed in seeds:
        snap, state, _ = drafted(seed, user_slot=(seed % 12) + 1)
        rng = random.Random(seed)
        for tid in snap.tids:  # some injured players on every roster, so OUT valuation is exercised on both sides
            for pid in rng.sample(sorted(state.rosters[tid]), 2):
                state.out[pid] = rng.randint(1, 6)
        desk = TradeDesk(Evaluator(snap, state), seed)
        limit = snap.settings.roster_limit
        user = snap.user_team.tid
        for partner, give, get in _offers(snap, state, rng, per_seed):
            stats["offers"] += 1
            v = desk.verdict(partner, give, get)
            stats[v.decision] += 1
            if v.decision != "counter":
                assert v.counter is None and v.counter_note is None
                continue
            cg, cr = v.counter["give"], v.counter["get"]
            bad = lambda why: stats["violations"].append((seed, partner, tuple(give), tuple(get), why))  # noqa: E731
            if not desk.ai_accepts(partner, cg, cr)[0]:
                bad("AI would not accept its own counter")
            for tid, g, r, who in ((partner, cr, cg, "AI"), (user, cg, cr, "user")):
                after = desk.roster_size_after(tid, g, r)
                if after > limit and after > len(state.rosters[tid]):
                    bad(f"{who} pushed over the roster limit ({after}/{limit})")
            if len(cg) > snap.settings.policy.max_trade_side or len(cr) > snap.settings.policy.max_trade_side:
                bad("counter side too long")
            if len(cg) - len(cr) >= 3 and desk.roster_size_after(partner, cr, cg) > limit:
                bad("roster-dump consolidation the AI cannot hold")
            if not v.counter_note or not v.counter_delta or "user_net_change" not in v.counter_delta:
                bad("counter does not explain itself with a value delta")
            asked = v.counter_delta["asked"]
            removed = v.counter_delta["removed"]
            if len(asked) + len(removed) != 1:
                bad("counter changes more than one asset")
            if set(cg) != (set(give) | set(asked)) or set(cr) != (set(get) - set(removed)):
                bad("counter does not equal the offer plus its stated change")
            if v.reason_code == "needs_position":
                stats["needs_position"] += 1
                pos = desk.need_position(partner)[0]
                if asked and all(not is_pick_id(p) and snap.players[p].pos == pos for p in asked) and f"{pos}" in v.counter_note:
                    stats["needs_position_asked_pos"] += 1
                else:
                    bad(f"says needs {pos} but did not ask for one")
            if v.reason_code == "fair_floor" and desk.linear_loss(partner, cr, cg) > floor_tolerance(desk.params(partner)):
                bad("counter still breaks the fairness floor")
    return stats


def test_counters_hold_their_invariants_over_many_random_offers():
    stats = sweep()
    assert stats["violations"] == [], stats["violations"][:5]
    assert stats["offers"] >= 300
    assert stats["counter"] > 0, "the sweep never produced a counter, so it proved nothing"
    # a "needs X" verdict only survives when the counter really asked for X
    assert stats["needs_position"] == stats["needs_position_asked_pos"]


def test_verdicts_are_deterministic_and_the_counter_is_stable():
    snap, state, _ = drafted(11, user_slot=4)
    rng = random.Random(5)
    user = snap.user_team.tid
    partner = next(t for t in snap.tids if t != user)
    give = rng.sample(sorted(state.rosters[user]), 2)
    get = rng.sample(sorted(state.rosters[partner]), 1)
    a = TradeDesk(Evaluator(snap, state), 11).verdict(partner, give, get).to_dict()
    b = TradeDesk(Evaluator(snap, state), 11).verdict(partner, give, get).to_dict()
    assert a == b


def test_needs_a_position_but_failing_on_value_is_a_value_counter_not_a_need_claim():
    """The reported bug: the AI said 'Needs a TE' while its counter asked for no TE. Whatever the AI is thin at, the
    reason names the factor that actually decided the offer."""
    snap, state, _ = drafted(11, user_slot=4)
    desk = TradeDesk(Evaluator(snap, state), 11)
    user = snap.user_team.tid
    seen_value_reason_while_thin = False
    for partner in (t for t in snap.tids if t != user):
        pos, ratio = desk.need_position(partner)
        for give in state.rosters[user]:
            for get in list(state.rosters[partner])[:6]:
                if snap.players[give].pos in ("K", "DEF") or snap.players[get].pos in ("K", "DEF"):
                    continue
                if desk.ai_accepts(partner, [give], [get])[0]:
                    continue
                code = desk.failure_cause(partner, [give], [get])[0]
                _, margin, _, need, _ = desk.ai_accepts(partner, [give], [get])
                if margin - need < 0 and ratio < 0.92:
                    assert code != "needs_position"
                    seen_value_reason_while_thin = True
    assert seen_value_reason_while_thin


def test_full_rosters_never_get_a_roster_dump_counter():
    """Both rosters at the limit: a counter may not add a player to a side that has no spot for him."""
    snap, state, _ = drafted(11, user_slot=4)
    limit = snap.settings.roster_limit
    user = snap.user_team.tid
    rng = random.Random(2)
    for tid in snap.tids:
        free = sorted(state.free_agents(snap))
        while len(state.rosters[tid]) < limit and free:
            state.rosters[tid].append(free.pop())
    desk = TradeDesk(Evaluator(snap, state), 11)
    counters = 0
    for partner, give, get in _offers(snap, state, rng, 250):
        v = desk.verdict(partner, give, get)
        if v.decision != "counter":
            continue
        counters += 1
        cg, cr = v.counter["give"], v.counter["get"]
        assert desk.roster_size_after(partner, cr, cg) <= limit, "AI would have to cut to take the counter"
        assert desk.roster_size_after(user, cg, cr) <= limit, "counter pushes the user over the limit"
    assert counters > 0
