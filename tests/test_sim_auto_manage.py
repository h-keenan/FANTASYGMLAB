"""Auto-manage my lineup: a runtime switch, best healthy lineup each week unless the user set this week's by hand."""

from __future__ import annotations

from modules.sim import game_actions as act
from modules.sim.game_engine import advance
from modules.sim.game_state import auto_manage_on, fold
from modules.sim.game_view import lineup_view

from tests.test_sim_game_engine import drafted


def _user_slots(state, snap):
    return [list(r) for r in state.lineups[snap.user_team.tid]]


def test_new_setting_default_and_switch_event_round_trip():
    snap, state, em = drafted(11, user_slot=7)
    assert snap.settings.auto_lineup is False and auto_manage_on(snap, state) is False  # tests build with the engine default
    act.set_auto_manage(em, True)
    assert state.auto_manage is True and auto_manage_on(snap, state) is True
    replayed = fold(snap, em.events)
    assert replayed.auto_manage is True
    act.set_auto_manage(em, False)
    assert auto_manage_on(snap, state) is False


def test_digest_unchanged_until_the_switch_or_a_manual_edit_is_used():
    snap, state, em = drafted(11, user_slot=7)
    assert state.auto_manage is None and state.manual_lineup_week == 0
    d0 = state.digest()
    act.set_auto_manage(em, True)
    assert state.digest() != d0


def test_auto_manage_sets_best_lineup_but_keeps_a_hand_set_week():
    snap, state, em = drafted(11, user_slot=7)
    user = snap.user_team.tid
    act.auto_lineup(em)
    slots = _user_slots(state, snap)
    bench = [p for p in state.rosters[user] if p not in {pid for _, pid in slots if pid}]
    # Replace a starter with a bench player of the same position, if any (keeps the lineup legal).
    swapped = False
    for i, (slot, pid) in enumerate(slots):
        for b in bench:
            if snap.players[b].pos == snap.players[pid].pos and b != pid:
                slots[i] = [slot, b]
                swapped = True
                break
        if swapped:
            break
    assert swapped
    act.set_lineup(em, slots)
    assert state.manual_lineup_week == state.week
    act.set_auto_manage(em, True)
    week, n = state.week, len(em.events)
    advance(em, snap, state, 11)
    # The engine did not overwrite the hand-set lineup in the week the user edited.
    assert not any(e["actor"] == "engine" and e["payload"].get("auto") is True and e["payload"]["team"] == user and e["week"] == week for e in em.events[n:])
    # Next week the user did not edit, so auto-manage sets the best lineup.
    next_week, n = state.week, len(em.events)
    advance(em, snap, state, 11)
    assert any(e["actor"] == "engine" and e["type"] == "lineup_set" and e["payload"]["team"] == user and e["week"] == next_week for e in em.events[n:])


def test_switch_off_leaves_the_lineup_alone():
    snap, state, em = drafted(11, user_slot=7)
    user = snap.user_team.tid
    act.auto_lineup(em)
    act.set_auto_manage(em, False)
    week, n = state.week, len(em.events)
    advance(em, snap, state, 11)
    assert not any(e["actor"] == "engine" and e["type"] == "lineup_set" and e["payload"]["team"] == user and e["week"] == week for e in em.events[n:])


def test_lineup_view_reports_the_switch_and_edit_state():
    snap, state, em = drafted(11, user_slot=7)
    v = lineup_view(snap, state)
    assert v["auto_manage"] is False and v["lineup_edited"] is False
    act.set_auto_manage(em, True)
    act.auto_lineup(em)  # an auto-set is not a hand edit
    v = lineup_view(snap, state)
    assert v["auto_manage"] is True and v["lineup_edited"] is False
    act.set_lineup(em, [[s, p] for s, p in state.lineups[snap.user_team.tid]])
    assert lineup_view(snap, state)["lineup_edited"] is True
