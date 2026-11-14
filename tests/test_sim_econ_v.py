"""econ_v 1: the consensus-anchored league economy (docs/audits/2026-11-sim-realism-audit-3.md).

Gate and serialization, old saves replaying byte-for-byte (golden digests on the synthetic pool, explicit model ids, trade verdicts included),
the pick curve, the consensus anchor on user trades, the injury discount, the replacement level and the free-agent cover."""

from __future__ import annotations

import hashlib
import json

import pytest

from modules.sim import game_dynasty as dyn
from modules.sim import picks as pk
from modules.sim.game_ai import CONSENSUS_TOL_BASE, TradeDesk
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import USER_PARAMS, Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import ECON_VERSION, GameSettings
from modules.sim.personas import PERSONAS
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
SEED = 11

# Digests of games made BEFORE econ_v (settings carry no econ_v key): state digest plus the trade verdicts (decision, margin) of a fixed set of
# offers at several moments, so the trade desk is covered. Captured on origin/main at a131203e's successor (7947a61c, before econ_v existed)
# and reproduced here with econ_v absent. Synthetic pool only (no data/ files), explicit model ids as a save records them.
GOLDEN = {
    ("player_model-player-model-5", "redraft"): "b27ce816ca7add8413e17ce5c1fa53432df770aa6f2c04a8fb5510abfe641249",
    ("player_model-player-model-5", "dynasty"): "c07dfb5ca65321810bb4102cd0b9729d39699ed1f0c7e3afa507993d82736fe9",
    ("player_model-player-model-6", "redraft"): "1c6dbfde7664549bb29b7ffdaaad539125d4f47bd3d046d42085c8cb770d55e1",
    ("player_model-player-model-6", "dynasty"): "beb1dde24efbb5595f0d6f09bada650ccbc9d65dcf9d089dd4ef03224388949e",
}


def _settings(econ: bool, **extra) -> GameSettings:
    d = GameSettings.parse({"user_slot": 4, "superflex": True, **extra}).to_dict()
    if not econ:
        d.pop("econ_v", None)  # a save from before econ_v
    return GameSettings.from_dict(d)


def _verdicts(snap, state, sd):
    desk = TradeDesk(Evaluator(snap, state), sd, state.week)
    user = snap.user_team.tid
    out = []
    mine = sorted(desk.tradable(user))[:3]
    for tid in snap.tids:
        if tid == user:
            continue
        for g in mine:
            for t in sorted(desk.tradable(tid))[:3]:
                v = desk.verdict(tid, [g], [t])
                out.append([tid, g, t, v.decision, round(v.margin, 6)])
    return out


def _digest(model: str, kind: str, econ: bool) -> str:
    if kind == "redraft":
        snap = build_snapshot(ROWS, BYES, _settings(econ), SEED, scoring_model=model)
        state = GameState(snap)
        em = Emitter(state, snap)
        run_ai_picks(DraftContext(snap, state), em, SEED)
        auto_for_user(DraftContext(snap, state), em, SEED)
        finish_draft(em, snap, state, SEED)
        vs = []
        for _ in range(6):
            vs.append(_verdicts(snap, state, SEED))
            advance(em, snap, state, SEED)
        return hashlib.sha256((state.digest() + json.dumps(vs)).encode()).hexdigest()
    snap = build_snapshot(ROWS, BYES, _settings(econ, mode="dynasty", seasons=3, start_year=2026, rookie_rounds=2, scoring="ppr"), SEED, scoring_model=model)
    root, state = snap, GameState(snap)
    em = Emitter(state, root)
    auto_for_user(DraftContext(root, state), em, SEED)
    finish_draft(em, root, state, SEED)
    vs = []
    while True:
        sn, sd = root.season_view(state.view_no), dyn.season_seed(SEED, state.view_no)
        em.snap = sn
        while state.status in ("in_season", "playoffs"):
            if state.status == "in_season" and state.week in (2, 5):
                vs.append(_verdicts(sn, state, sd))
            advance(em, sn, state, sd)
        if state.status != "offseason":
            break
        sn, sd = root.season_view(state.view_no), dyn.season_seed(SEED, state.view_no)
        em.snap = sn
        vs.append(_verdicts(sn, state, sd))
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        dyn.start_next_season(em, sd)
    return hashlib.sha256((state.digest() + json.dumps(vs)).encode()).hexdigest()


def test_econ_v_is_on_for_new_games_serialized_and_absent_on_old_saves():
    s = GameSettings.parse({"user_slot": 4})
    assert ECON_VERSION == 1 and s.econ_v == 1 and s.to_dict()["econ_v"] == 1
    d = s.to_dict()
    d.pop("econ_v")
    old = GameSettings.from_dict(d)
    assert old.econ_v == 0 and "econ_v" not in old.to_dict()


@pytest.mark.parametrize("model", ["player_model-player-model-5", "player_model-player-model-6"])
@pytest.mark.parametrize("kind", ["redraft", "dynasty"])
def test_old_saves_replay_identically_with_the_trade_desk_included(model, kind):
    assert _digest(model, kind, econ=False) == GOLDEN[(model, kind)]


def test_a_new_game_differs_from_an_old_save_only_through_the_economy():
    # econ_v 1 changes verdicts (and so trades), never the engine: the redraft draft itself is identical.
    a = build_snapshot(ROWS, BYES, _settings(False), SEED, scoring_model="player_model-player-model-6")
    b = build_snapshot(ROWS, BYES, _settings(True), SEED, scoring_model="player_model-player-model-6")
    assert a.players == b.players and a.schedule == b.schedule


# ------------------------------------------------------------------------------------------------ picks


def test_pick_curve_follows_the_rookies_and_is_monotone_and_size_free():
    vals = [pk.rookie_slot_value(s) for s in range(1, 61)]
    assert all(a > b for a, b in zip(vals, vals[1:]))
    assert vals[0] == pytest.approx(95.0) and vals[11] == pytest.approx(30.0, rel=0.02) and vals[35] == pytest.approx(7.3, rel=0.02)
    # the old curve undervalued the top and overvalued rounds 2-3 against the rookie taken there: the new one is the rookie
    assert pk.pick_market_value_v2(1, 0.0, 0, 12) > pk.pick_market_value(1, 0.0, 0, 12) * 1.25
    assert pk.pick_market_value_v2(3, 0.5, 0, 12) < pk.pick_market_value(3, 0.5, 0, 12) * 0.8
    # an unknown slot is the round's average (the curve is convex, so it beats the mid-round slot), further out is discounted
    assert pk.pick_market_value_v2(1, None, 1, 12) > pk.pick_market_value_v2(1, 0.5, 1, 12)
    assert pk.pick_market_value_v2(2, None, 2, 12) == pytest.approx(pk.pick_market_value_v2(2, None, 0, 12) * pk.YEAR_DISCOUNT ** 2)


# ------------------------------------------------------------------------------------- a game to probe


def _dynasty_game(econ: bool, weeks: int = 2):
    snap = build_snapshot(ROWS, BYES, _settings(econ, mode="dynasty", seasons=3, start_year=2026, rookie_rounds=2, scoring="ppr"), SEED,
                          scoring_model="player_model-player-model-6")
    state = GameState(snap)
    em = Emitter(state, snap)
    auto_for_user(DraftContext(snap, state), em, SEED)
    finish_draft(em, snap, state, SEED)
    sn, sd = snap.season_view(state.view_no), dyn.season_seed(SEED, state.view_no)
    em.snap = sn
    for _ in range(weeks):
        advance(em, sn, state, sd)
    return sn, state, sd


def _accepted_gains(snap, state, sd):
    """Every one-for-one swap an AI accepts, with what the league's neutral lens says the user gains."""

    ev = Evaluator(snap, state)
    desk = TradeDesk(ev, sd, state.week)
    user = snap.user_team.tid
    gains = []
    for tid in snap.tids:
        if tid == user:
            continue
        theirs = desk.tradable(tid)
        for g in desk.tradable(user):
            for t in theirs:
                if desk.ai_accepts(tid, [g], [t])[0]:
                    gains.append(ev.worth(USER_PARAMS, t, healthy=True) - ev.worth(USER_PARAMS, g))
    return gains


def test_the_consensus_anchor_caps_what_a_user_can_take_from_an_ai_in_one_deal():
    old = _accepted_gains(*_dynasty_game(False))
    new = _accepted_gains(*_dynasty_game(True))
    assert old and new
    # before: some deals hand the user a large gain in the league's own lens (the farmed disagreement); after: bounded by the tolerance
    assert max(old) > 12.0
    assert max(new) <= CONSENSUS_TOL_BASE + 0.05 * 100 + 0.5 * max(p.params.noise_sd for p in PERSONAS.values()) + 1e-6
    assert max(new) < max(old)


def test_a_below_market_deal_is_declined_as_too_lopsided_not_countered_into_one():
    snap, state, sd = _dynasty_game(True)
    desk = TradeDesk(Evaluator(snap, state), sd, state.week)
    user = snap.user_team.tid
    seen = 0
    for tid in snap.tids:
        if tid == user:
            continue
        for g in desk.tradable(user):
            for t in desk.tradable(tid):
                if desk.below_market(tid, [g], [t]):
                    v = desk.verdict(tid, [g], [t])
                    seen += 1
                    assert v.decision != "accept"
                    if v.counter:  # a counter is only ever offered if it clears the anchor too
                        assert not desk.below_market(tid, v.counter["give"], v.counter["get"])
    assert seen > 0


def test_econ_v_0_never_flags_a_deal_as_below_market():
    snap, state, sd = _dynasty_game(False)
    desk = TradeDesk(Evaluator(snap, state), sd, state.week)
    user = snap.user_team.tid
    assert not any(desk.below_market(t, [g], [x]) for t in snap.tids if t != user for g in desk.tradable(user)[:5] for x in desk.tradable(t)[:5])


# ------------------------------------------------------------------------ injury, replacement, cover


def _star(ev, snap, state):
    owned = state.owner_map()
    return max((p for p in snap.pids if p in owned and snap.players[p].pos in ("RB", "WR")), key=lambda p: ev.base_value(p))


def test_an_injury_costs_the_share_of_the_season_missed_not_a_capped_sixty_percent():
    contender = PERSONAS["contender"].params
    for econ in (False, True):
        snap, state, _ = _dynasty_game(econ, weeks=1)
        pid = _star(Evaluator(snap, state), snap, state)
        healthy = Evaluator(snap, state).worth(contender, pid)
        state.out[pid] = snap.settings.regular_weeks - state.week + 1  # out for the rest of the regular season
        gone = Evaluator(snap, state).worth(contender, pid)
        if econ:
            assert gone < 0.4 * healthy  # a contender's value is almost all "now": none of it is left
            assert Evaluator(snap, state).worth(contender, pid, healthy=True) > 0.8 * healthy  # a seller anchors on the healthy price (his role shifts a little while out)
        else:
            assert gone > 0.4 * healthy  # the old cap (6 weeks, 60% of the "now" half) left most of it


def test_production_at_the_free_agent_level_is_worth_nothing_and_a_star_is_not():
    snap, state, _ = _dynasty_game(True, weeks=3)
    ev = Evaluator(snap, state)
    contender = PERSONAS["contender"].params
    owned = state.owner_map()
    fa = max((p for p in snap.pids if p not in owned and snap.players[p].pos == "WR" and state.out.get(p, 0) == 0), key=ev.ros_mean)
    assert ev.replacement("WR") > 0
    # a free agent has no "now" worth over the wire's level (what is left is his long-run market half)
    assert ev.worth(contender, fa) <= (1.0 - ev.horizon_now(contender)) * ev.base_value(fa) + 1e-9 + 0.0 or ev.ros_mean(fa) <= ev.replacement("WR") + 3.0
    star = _star(ev, snap, state)
    assert ev.worth(contender, star) > 3 * ev.worth(contender, fa)


def test_cover_is_only_free_agents_and_empty_for_old_saves():
    snap, state, sd = _dynasty_game(True, weeks=2)
    desk = TradeDesk(Evaluator(snap, state), sd, state.week)
    owned = state.owner_map()
    assert desk.cover() and all(p not in owned and state.out.get(p, 0) == 0 for p in desk.cover())
    snap0, state0, sd0 = _dynasty_game(False, weeks=2)
    assert TradeDesk(Evaluator(snap0, state0), sd0, state0.week).cover() == []


def test_a_player_no_better_than_the_wire_does_not_improve_an_ai_lineup():
    """The old desk paid a lineup 'need' premium for any body at a thin position; with the wire counted, a free-agent-level player adds nothing."""

    snap, state, sd = _dynasty_game(True, weeks=3)
    ev = Evaluator(snap, state)
    desk = TradeDesk(ev, sd, state.week)
    owned = state.owner_map()
    best_fa = max((p for p in snap.pids if p not in owned and snap.players[p].pos == "WR"), key=ev.ros_mean)
    for tid in snap.tids:
        if tid == snap.user_team.tid:
            continue
        roster = list(state.rosters[tid])
        base = desk.base_total(tid)
        with_fa = ev.lineup_total([*roster, *desk.cover(), best_fa])
        assert with_fa - base < 1e-6  # the cover already holds the best free WR
