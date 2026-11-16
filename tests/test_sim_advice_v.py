"""advice_v 1: the draft hint / Auto-pick weigh value, need against starting slots, runs and thin tiers, byes and injuries,
and explain themselves. Old saves (advice_v 0) keep the hint_v 1 rule."""

from __future__ import annotations

import dataclasses

from modules.sim import game_draft as draft
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import ADVICE_VERSION, GameSettings
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
MODEL = "player_model-player-model-5"


def snap_of(advice_v: int):
    s = build_snapshot(ROWS, BYES, GameSettings.parse({"user_slot": 4}), 11, scoring_model=MODEL)
    return dataclasses.replace(s, settings=dataclasses.replace(s.settings, advice_v=advice_v))


def late_round_ctx(advice_v: int = 1, rb_gap: float = 3.0):
    """The user is on the clock holding a QB, TE and four WRs and no RB: best available WR vs best available RB."""
    snap = snap_of(advice_v)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = draft.DraftContext(snap, state)
    user = snap.user_team.tid
    draft.run_ai_picks(ctx, em, 11)
    for pos in ["QB", "WR", "WR", "WR", "WR", "TE"]:
        while ctx.order[state.pick_index] != user:
            draft.run_ai_picks(ctx, em, 11)
        pid = next(p for p in ctx.by_adp if p not in ctx.taken() and snap.players[p].pos == pos)
        draft.user_pick(ctx, em, pid, 11)
    assert ctx.order[state.pick_index] == user
    assert ctx.counts(user)["RB"] == 0
    cands = draft._candidates(ctx, user, state.pick_index)
    wr = min((p for p in cands if snap.players[p].pos == "WR"), key=lambda p: snap.players[p].adp)
    rb = min((p for p in cands if snap.players[p].pos == "RB"), key=lambda p: snap.players[p].adp)
    players = dict(snap.players)
    players[wr] = dataclasses.replace(players[wr], adp=1.0)  # the best player on the board, so only WR vs RB is in play
    rbs = sorted((p for p in cands if snap.players[p].pos == "RB"), key=lambda p: (snap.players[p].adp, p))
    for i, p in enumerate(rbs):  # every RB sits rb_gap behind the best WR, in his original order
        players[p] = dataclasses.replace(players[p], adp=players[wr].adp + rb_gap + 0.5 * i)
    snap2 = dataclasses.replace(snap, players=players)
    ctx2 = draft.DraftContext(snap2, state)
    return ctx2, wr, rb


def test_new_games_carry_advice_v_and_old_saves_do_not_serialize_it():
    s = GameSettings.parse({})
    assert s.advice_v == ADVICE_VERSION == 1 and s.to_dict()["advice_v"] == 1
    raw = {k: v for k, v in s.to_dict().items() if k != "advice_v"}
    old = GameSettings.from_dict(raw)
    assert old.advice_v == 0 and "advice_v" not in old.to_dict()


def test_close_value_rb_beats_wr_when_the_team_needs_an_rb():
    ctx, wr, rb = late_round_ctx(rb_gap=3.0)
    assert draft.best_for_user(ctx, 11) == rb
    why = draft.advice_reason(ctx, rb)
    assert "RB" in why and "need" in why


def test_huge_value_gap_still_takes_value_and_says_why():
    ctx, wr, rb = late_round_ctx(rb_gap=60.0)
    assert draft.best_for_user(ctx, 11) == wr
    why = draft.advice_reason(ctx, wr)
    assert "Value override" in why and "need" in why


def test_old_save_keeps_the_original_rule():
    ctx, wr, rb = late_round_ctx(advice_v=0, rb_gap=3.0)
    assert draft.best_for_user(ctx, 11) == draft.choose_public(ctx, ctx.snap.user_team.tid, ctx.state.pick_index)
