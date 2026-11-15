"""Kickers and defenses in trades (kd_v): counters are always sendable, the singleton warning names who and the way out, old saves are unchanged,
and the randomized stress harness (modules/sim/calibration/kicker_trade_stress.py) stays clean. The deep run: ``python -m modules.sim.calibration.kicker_trade_stress --seeds 40 --seasons 20``."""

from __future__ import annotations

import numpy as np

from modules.sim import game_actions as act
from modules.sim.game_ai import TradeDesk, singleton_message, singleton_violations, validate_offer
from modules.sim.game_eval import Evaluator
from modules.sim.game_types import SINGLETON_POSITIONS, GameError
from modules.sim.types import is_pick_id
from modules.sim.calibration.kicker_trade_stress import Stress, make_settings, run_seed


def world(seed=3, kd_v=1, **flags):
    r = np.random.default_rng(seed)
    s = Stress(seed, make_settings(r, kd_v=kd_v, dynasty=False, flags={"limit_v": 1, "econ_v": 1, "hint_v": 1, **flags}), r)
    return s, s.view()


def pos_of(snap, pid):
    return None if is_pick_id(pid) else snap.players[pid].pos


def test_a_counter_is_never_a_deal_that_leaves_a_team_with_two_kickers_or_defenses():
    """The bug: 'give my K, get their K + X' declined for value made the AI drop THEIR K from the ask, leaving the partner with two."""
    checked = 0
    for seed in (3, 5, 8):
        s, snap = world(seed)
        st, user = s.state, snap.user_team.tid
        desk = TradeDesk(Evaluator(snap, st), s.seed_now())
        for partner in [t for t in snap.tids if t != user]:
            for pos in SINGLETON_POSITIONS:
                mine = [p for p in st.holdings(user) if snap.players[p].pos == pos]
                theirs = [p for p in st.holdings(partner) if snap.players[p].pos == pos]
                if not (mine and theirs):
                    continue
                stars = sorted((p for p in st.holdings(partner) if snap.players[p].pos not in SINGLETON_POSITIONS), key=lambda p: -snap.players[p].value)[:3]
                for star in stars:
                    for give in ([mine[0]], [mine[0], *[p for p in st.holdings(user) if snap.players[p].pos == "WR"][:1]]):
                        get = [theirs[0], star]
                        try:
                            v = act.preview_trade(desk, partner, give, get)
                        except GameError:
                            continue
                        if v.decision != "counter":
                            continue
                        c = v.counter
                        validate_offer(snap, st, partner, c["give"], c["get"])  # sendable: no singleton_limit
                        assert not singleton_violations(snap, st, partner, c["give"], c["get"])
                        checked += 1
    assert checked >= 3


def test_dropping_their_kicker_from_a_counter_takes_your_kicker_off_the_table_too():
    for seed in range(1, 12):
        s, snap = world(seed)
        st, user = s.state, snap.user_team.tid
        desk = TradeDesk(Evaluator(snap, st), s.seed_now())
        for partner in [t for t in snap.tids if t != user]:
            mine = [p for p in st.holdings(user) if snap.players[p].pos == "K"]
            theirs = [p for p in st.holdings(partner) if snap.players[p].pos == "K"]
            if not (mine and theirs):
                continue
            for star in sorted((p for p in st.holdings(partner) if snap.players[p].pos not in SINGLETON_POSITIONS), key=lambda p: -snap.players[p].value)[:4]:
                give = [mine[0], *[p for p in st.holdings(user) if snap.players[p].pos == "RB"][:1]]
                v = desk.verdict(partner, give, [theirs[0], star])
                if v.decision == "counter" and v.counter_delta and theirs[0] in v.counter_delta["removed"]:
                    assert mine[0] in v.counter_delta["removed"] and mine[0] not in v.counter["give"] and theirs[0] not in v.counter["get"]
                    assert "stays with you" in v.counter_note
                    return
    # the scenario is value-dependent: the property above (every counter is sendable) is the guarantee; this only pins the wording when it occurs


def test_the_singleton_message_names_who_what_and_the_way_out():
    s, snap = world(3)
    st, user = s.state, snap.user_team.tid
    partner = next(t for t in snap.tids if t != user)
    name = snap.team(partner).name
    my_k = next(p for p in st.holdings(user) if snap.players[p].pos == "K")
    their_k = next(p for p in st.holdings(partner) if snap.players[p].pos == "K")
    wr = next(p for p in st.holdings(user) if snap.players[p].pos == "WR")
    their_wr = next(p for p in st.holdings(partner) if snap.players[p].pos == "WR")

    def text(give, get):
        try:
            validate_offer(snap, st, partner, give, get)
        except GameError as exc:
            assert exc.code == "singleton_limit"
            return str(exc), exc.detail["singleton"]
        return None, None

    # they would receive a second kicker (the user sends theirs for something that is not a kicker)
    msg, d = text([my_k], [their_wr])
    assert d["them"] == ["K"] and d["you"] == [] and msg.startswith(f"{name} already has a kicker")
    assert "Ask for their kicker back" in msg and "You already" not in msg and "Trade yours away" not in msg
    # you would receive a second kicker
    msg, d = text([wr], [their_k])
    assert d["you"] == ["K"] and d["them"] == [] and msg.startswith("You already have a kicker") and "Send yours in this deal" in msg
    # both: you send a K for their defense...
    their_def = next((p for p in st.holdings(partner) if snap.players[p].pos == "DEF"), None)
    my_def = next((p for p in st.holdings(user) if snap.players[p].pos == "DEF"), None)
    if their_def and my_def:
        msg, d = text([my_k], [their_def])
        assert d["them"] == ["K"] and d["you"] == ["DEF"] and "You already have a defense" in msg and f"{name} already has a kicker" in msg
        msg, d = text([wr], [their_def])
        assert d["you"] == ["DEF"] and "defense" in msg and "kicker" not in msg
        msg, d = text([my_def], [their_wr])
        assert d["them"] == ["DEF"] and f"{name} already has a defense" in msg and "their defense back" in msg
    # a swap, and trades that do not touch K/DEF, say nothing
    assert text([my_k], [their_k]) == (None, None) and text([wr], [their_wr]) == (None, None)
    assert singleton_message(snap, partner, [(partner, "K")]).startswith(name)


def test_a_save_without_kd_v_still_refuses_with_the_old_error_and_never_counters_with_a_kicker():
    s, snap = world(3, kd_v=0)
    st, user = s.state, snap.user_team.tid
    assert snap.settings.non_tradable == ("K", "DEF")
    partner = next(t for t in snap.tids if t != user)
    k = next(p for p in st.holdings(user) if snap.players[p].pos == "K")
    try:
        validate_offer(snap, st, partner, [k], [st.rosters[partner][0]])
        raise AssertionError("expected a refusal")
    except ValueError as exc:
        assert not isinstance(exc, GameError) and str(exc) == "Kickers and defenses cannot be traded."
    desk = TradeDesk(Evaluator(snap, st), s.seed_now())
    for p in desk.tradable(partner):
        assert snap.players[p].pos not in SINGLETON_POSITIONS if not is_pick_id(p) else True


def test_stress_smoke_redraft_and_dynasty_are_clean():
    for seed in (4, 9):
        s = run_seed(seed, seasons=3, attempts=4)
        assert not s.failures, s.failures
