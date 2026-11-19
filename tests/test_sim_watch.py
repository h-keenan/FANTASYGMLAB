"""Draft & Watch (watch_v 1): sliders play the user's waivers and trades; nothing changes for any other game."""

from __future__ import annotations

import pytest

from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings
from tests.test_sim_game_engine import make_snapshot


def play(seed=5, **opts):
    snap = make_snapshot(seed, user_slot=4, **opts)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    while state.status != "complete":
        advance(em, snap, state, seed)
    return snap, state, em


def user_moves(snap, em):
    user = snap.user_team.tid
    claims = [e for e in em.events if e["type"] == "waiver_result" and e["payload"].get("team") == user and e["payload"].get("ok")]
    trades = [e for e in em.events if e["type"] == "trade" and e["actor"] == "user"]
    return claims, trades


def test_settings_parse_roundtrip_and_defaults():
    s = GameSettings.parse({"watch": True, "user_slot": 1})
    assert s.watch_v == 1 and s.auto_lineup is True
    assert (s.watch_waivers, s.watch_trades) == ("balanced", "light")  # the approved defaults
    assert GameSettings.from_dict(s.to_dict()) == s
    plain = GameSettings.parse({})
    assert plain.watch_v == 0 and "watch_v" not in plain.to_dict()
    with pytest.raises(ValueError):
        GameSettings.parse({"watch": True, "watch_waivers": "wild"})
    with pytest.raises(ValueError):
        GameSettings.parse({"watch": True, "watch_trades": "wild"})
    with pytest.raises(ValueError):
        GameSettings.parse({"watch": True, "mode": "dynasty"})


def test_watch_game_plays_to_the_end_with_sliders_respected():
    snap, state, em = play(5, watch=True, watch_waivers="aggressive", watch_trades="active")
    assert state.status == "complete"
    claims, _ = user_moves(snap, em)
    assert claims, "an aggressive, need-based manager makes at least one add over a season"
    snap0, state0, em0 = play(5, watch=True, watch_waivers="hands_off", watch_trades="off")
    claims0, trades0 = user_moves(snap0, em0)
    assert not trades0
    assert len(claims0) <= len(claims)


def test_trades_off_never_trades_and_light_is_capped():
    _, _, em_off = play(7, watch=True, watch_trades="off")
    assert not [e for e in em_off.events if e["type"] == "trade" and e["actor"] == "user"]
    snap, _, em = play(7, watch=True, watch_trades="light")
    assert len([e for e in em.events if e["type"] == "trade" and e["actor"] == "user"]) <= 2


def test_watch_game_is_deterministic():
    a = play(9, watch=True)
    b = play(9, watch=True)
    assert a[1].digest() == b[1].digest()


def test_ordinary_game_is_untouched():
    snap, state, em = play(5)
    assert snap.settings.watch_v == 0
    assert not [e for e in em.events if e["type"] == "waiver_claim" and e["actor"] == "user"]
