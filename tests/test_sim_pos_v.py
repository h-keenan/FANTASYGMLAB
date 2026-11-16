"""pos_v 1: a kicker (or defense) trades like any position. The AI values an incoming one by the upgrade over its own starter, resolves the second
one by cutting the worse, its NEEDS tag and its valuation read one report, and the trade block takes K/DEF. A save without pos_v is unchanged
(the one-per-team refusal, a K/DEF-free block)."""

from __future__ import annotations

import numpy as np
import pytest

from modules.sim import game_actions as act
from modules.sim import game_block as blockmod
from modules.sim.calibration.kicker_trade_stress import Stress, make_settings
from modules.sim.game_ai import TradeDesk, singleton_violations, validate_offer
from modules.sim.game_eval import Evaluator
from modules.sim.game_need import position_report
from modules.sim.game_state import Emitter
from modules.sim.game_types import GameError, GameSettings
from modules.sim.types import is_pick_id


def world(seed: int, pos_v: int = 1):
    r = np.random.default_rng(seed)
    flags = {"limit_v": 1, "econ_v": 1, "hint_v": 1, "vorp_v": 1, "pos_v": pos_v}
    s = Stress(seed, make_settings(r, kd_v=1, dynasty=False, flags=flags), r)
    return s, s.view()


def k_of(snap, st, tid):
    return [p for p in st.holdings(tid) if not is_pick_id(p) and snap.players[p].pos == "K"]


def level(snap, ev, tid, pos="K"):
    return next(e["level"] for e in position_report(snap, ev)[tid] if e["pos"] == pos)


def scenarios(better: bool):
    """(seed, partner, my_k, their_k) where the partner's kicker is clearly worse (better=True: a NEEDS K team) or clearly better (a set team)."""

    for seed in (3, 4, 5, 8, 11, 12, 13, 14):
        s, snap = world(seed)
        st, user = s.state, snap.user_team.tid
        ev = Evaluator(snap, st)
        mine = k_of(snap, st, user)
        if not mine or "K" not in snap.settings.slots:
            continue
        for t in snap.tids:
            theirs = k_of(snap, st, t)
            if t == user or len(theirs) != 1:
                continue
            gap = ev.ros_mean(mine[0]) - ev.ros_mean(theirs[0])
            if (better and gap > 1.0 and level(snap, ev, t) == "need") or (not better and gap < -0.8 and level(snap, ev, t) == "strength"):
                yield s, snap, t, mine[0], theirs[0]


def asks(snap, st, partner):
    """What the partner could give for a kicker: its non-K players, best value first."""

    ev = Evaluator(snap, st)
    return sorted((p for p in st.rosters[partner] if snap.players[p].pos != "K"), key=lambda p: -ev.worth(USER, p))


from modules.sim.game_eval import USER_PARAMS as USER  # noqa: E402


def test_a_team_that_needs_a_kicker_takes_a_better_one_for_fair_value_and_cuts_its_old_one():
    done = 0
    for s, snap, partner, my_k, their_k in scenarios(better=True):
        st = s.state
        desk = TradeDesk(Evaluator(snap, st), s.seed_now())
        assert desk.need_position(partner)[0] == "K" or level(snap, Evaluator(snap, st), partner) == "need"
        validate_offer(snap, st, partner, [my_k], [asks(snap, st, partner)[-1]])  # not refused as "a team keeps just one"
        assert not singleton_violations(snap, st, partner, [my_k], [asks(snap, st, partner)[-1]])
        for ask in reversed(asks(snap, st, partner)):
            v = act.preview_trade(desk, partner, [my_k], [ask])
            if v.decision != "accept":
                continue
            em = Emitter(st, snap)
            verdict, trade = act.send_trade(em, desk, partner, [my_k], [ask])
            assert trade is not None and verdict.decision == "accept"
            ks = k_of(snap, st, partner)
            assert ks == [my_k], "the team keeps exactly one kicker: the better one"
            assert their_k not in st.rosters[partner] and their_k not in st.holdings(partner)
            assert len(st.rosters[partner]) <= snap.settings.roster_limit
            assert their_k not in st.owner_map()  # cut to the wire
            assert any(t.get("type") == "drop" and t.get("pid") == their_k and t.get("reason") == "one_per_roster" for t in st.transactions)
            done += 1
            break
        if done:
            break  # the world moved on: one executed deal is the proof
    assert done >= 1


def test_a_team_with_a_strong_kicker_declines_a_worse_one_on_value():
    done = 0
    for s, snap, partner, my_k, their_k in scenarios(better=False):
        st = s.state
        desk = TradeDesk(Evaluator(snap, st), s.seed_now())
        ev = desk.ev  # the desk prices over the starter line (vorp_v)
        for ask in [p for p in asks(snap, st, partner) if ev.worth(USER, p) >= 15][:6]:  # a real asset, not a throw-in
            v = act.preview_trade(desk, partner, [my_k], [ask])
            assert v.decision != "accept", "a worse kicker for a real asset is not worth it"
            assert v.reason_code in ("wants_more_value", "fair_floor", "roster_fit", "needs_position")
            assert "needs K" not in v.chips  # a team set at kicker never claims to need one
        done += 1
    assert done >= 1


def test_the_needs_tag_and_the_trade_valuation_read_the_same_report():
    checked = 0
    for seed in (3, 5, 8, 11):
        s, snap = world(seed)
        st = s.state
        ev = Evaluator(snap, st)
        desk = TradeDesk(ev, s.seed_now())
        report = position_report(snap, ev)
        assert desk.position_levels() == report
        for t in snap.tids:
            if t == snap.user_team.tid:
                continue
            pos, ratio = desk.need_position(t)
            tagged = [e["pos"] for e in report[t] if e["level"] == "need"]
            assert (pos in tagged and ratio < 0.92) if tagged else ratio >= 0.95  # a Needs tag IS a need to the AI, and no tag is not
            checked += 1
    assert checked > 10


def test_a_better_kicker_is_worth_more_to_a_team_tagged_needs_k_than_to_a_set_team():
    for s, snap, partner, my_k, their_k in scenarios(better=True):
        st = s.state
        desk = TradeDesk(Evaluator(snap, st), s.seed_now())
        ask = asks(snap, st, partner)[-1]
        _, dval_need, need_part = desk.utility(partner, [ask], [my_k])
        assert need_part > 0  # the lineup upgrade is a gain for the team that is tagged as needing the position
        return
    pytest.skip("no NEEDS K scenario in the seeds")


def test_kickers_can_go_on_the_block_with_pos_v_and_not_without():
    s, snap = world(3)
    st = s.state
    k = k_of(snap, st, snap.user_team.tid)[0]
    em = Emitter(st, snap)
    blockmod.set_block(em, k, True)
    assert k in blockmod.user_block(snap, st)
    s0, snap0 = world(3, pos_v=0)
    with pytest.raises(ValueError):
        blockmod.set_block(Emitter(s0.state, snap0), k_of(snap0, s0.state, snap0.user_team.tid)[0], True)


def test_a_save_without_pos_v_still_refuses_a_second_kicker():
    s, snap = world(3, pos_v=0)
    st, user = s.state, snap.user_team.tid
    partner = next(t for t in snap.tids if t != user and k_of(snap, st, t))
    other = next(p for p in st.rosters[partner] if snap.players[p].pos != "K")
    with pytest.raises(GameError) as exc:
        validate_offer(snap, st, partner, [k_of(snap, st, user)[0]], [other])
    assert exc.value.code == "singleton_limit"
    assert not GameSettings.from_dict({**snap.settings.to_dict(), "pos_v": 0}).pos_rules
