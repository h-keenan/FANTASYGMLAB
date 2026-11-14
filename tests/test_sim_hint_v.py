"""hint_v 1: the user's helpers (draft hint, Auto-pick, rookie auto-draft, counter asks, trade spotlight, draft recap) use public
information only. Old saves (hint_v absent) keep the hidden-value helpers and replay identically."""

from __future__ import annotations

import dataclasses

import pytest

from modules.sim import game_dynasty as dyn
from modules.sim import game_draft as draft
from modules.sim import game_grades
from modules.sim import game_scoring, game_view
from modules.sim.game_ai import TradeDesk
from modules.sim.game_eval import Evaluator
from modules.sim.game_home import _trade_weight
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import HINT_VERSION, GameSettings
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
MODEL = "player_model-player-model-5"  # explicit, like the id recorded in a save


def snap_of(hint_v: int, seed: int = 11):
    s = build_snapshot(ROWS, BYES, GameSettings.parse({"user_slot": 4}), seed, scoring_model=MODEL)
    return dataclasses.replace(s, settings=dataclasses.replace(s.settings, hint_v=hint_v))


def scrambled(snap):
    """The same game with every hidden value replaced by an unrelated number (public fields untouched)."""
    n = len(snap.pids)
    players = {pid: dataclasses.replace(p, value=float((i * 37) % n), market=float((i * 53) % n)) for i, (pid, p) in enumerate(snap.players.items())}
    return dataclasses.replace(snap, players=players)


def draft_all(snap, seed: int = 11):
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = draft.DraftContext(snap, state)
    draft.run_ai_picks(ctx, em, seed)
    draft.auto_for_user(ctx, em, seed)
    user = snap.user_team.tid
    return [p["pid"] for p in state.picks if p["team"] == user], state


def test_new_games_carry_hint_v_and_old_saves_do_not_serialize_it():
    s = GameSettings.parse({})
    assert s.hint_v == HINT_VERSION == 1 and s.to_dict()["hint_v"] == 1
    assert GameSettings.from_dict(s.to_dict()) == s
    raw = {k: v for k, v in s.to_dict().items() if k != "hint_v"}
    old = GameSettings.from_dict(raw)
    assert old.hint_v == 0 and "hint_v" not in old.to_dict()


def test_old_save_hint_and_autopick_are_the_original_hidden_value_choice():
    snap = snap_of(0)
    state = GameState(snap)
    ctx = draft.DraftContext(snap, state)
    draft.run_ai_picks(ctx, Emitter(state, snap), 11)
    assert draft.best_for_user(ctx, 11) == draft.choose_pick(ctx, snap.user_team.tid, state.pick_index, 11, human=True)


def test_public_autopick_ignores_the_hidden_value(monkeypatch):
    # Grades derive from the hidden value (they are the shown, noisy quantity); hold them constant to isolate the rule itself.
    monkeypatch.setattr(game_grades, "sort_key", lambda *a, **k: 0)
    snap = snap_of(1)
    scr = scrambled(snap)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx, sctx = draft.DraftContext(snap, state), draft.DraftContext(scr, state)
    draft.run_ai_picks(ctx, em, 11)
    n = 0
    while state.pick_index < ctx.total:  # the same board, hidden values scrambled: every pick is identical
        pid = draft.best_for_user(ctx, 11)
        assert pid == draft.best_for_user(sctx, 11)
        draft.user_pick(ctx, em, pid, 11, auto=True)
        n += 1
    assert n == snap.settings.rounds


def test_public_autopick_differs_from_the_old_oracle_and_is_not_absurd():
    new, state = draft_all(snap_of(1))
    old, _ = draft_all(snap_of(0))
    assert new != old
    snap = snap_of(1)
    adps = [snap.players[p].adp for p in new]
    picks = [p["n"] + 1 for p in state.picks if p["team"] == snap.user_team.tid]
    assert max(a - n for a, n in zip(adps, picks)) < 40  # never a wild reach
    positions = [snap.players[p].pos for p in new]
    assert positions.count("QB") >= 1 and positions.count("K") <= 1 and positions.count("DEF") <= 1
    assert len(new) == snap.settings.rounds


def test_hint_equals_what_autopick_takes_and_names_public_reasoning():
    snap = snap_of(1)
    state = GameState(snap)
    ctx = draft.DraftContext(snap, state)
    em = Emitter(state, snap)
    draft.run_ai_picks(ctx, em, 11)
    hint_pid = draft.best_for_user(ctx, 11)
    view = game_view.draft_view(snap, state, ctx, 11)
    assert view["hint"]["player"]["id"] == hint_pid
    assert "ADP" in view["hint"]["why"] and "value" not in view["hint"]["why"].lower()
    draft.user_pick(ctx, em, hint_pid, 11)  # the one-tap Draft button
    assert any(p["pid"] == hint_pid for p in state.picks)
    old = snap_of(0)
    ostate = GameState(old)
    octx = draft.DraftContext(old, ostate)
    draft.run_ai_picks(octx, Emitter(ostate, old), 11)
    assert game_view.draft_view(old, ostate, octx, 11)["hint"]["why"].startswith("Best available for your need")


def _no_hidden_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in ("value", "overall", "value_rank", "market", "net_value"), path + "." + k
            _no_hidden_keys(v, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _no_hidden_keys(v, f"{path}[{i}]")


def test_hint_response_carries_no_hidden_value_field():
    snap = snap_of(1)
    state = GameState(snap)
    ctx = draft.DraftContext(snap, state)
    draft.run_ai_picks(ctx, Emitter(state, snap), 11)
    _no_hidden_keys(game_view.draft_view(snap, state, ctx, 11)["hint"])


def test_replay_is_deterministic_under_hint_v():
    a, sa = draft_all(snap_of(1))
    b, sb = draft_all(snap_of(1))
    assert a == b and sa.digest() == sb.digest()


def test_queue_still_wins_over_the_public_rule():
    snap = snap_of(1)
    state = GameState(snap)
    ctx = draft.DraftContext(snap, state)
    em = Emitter(state, snap)
    draft.run_ai_picks(ctx, em, 11)
    target = ctx.by_adp[60]
    draft.set_queue(ctx, em, [target])
    assert draft.best_for_user(ctx, 11) == target
    assert draft.hint_reason(ctx, target) == "Next on your queue"


def test_counter_ask_cost_and_spotlight_weight_are_public():
    snap = snap_of(1)
    state = GameState(snap)
    desk = TradeDesk(Evaluator(snap, state), 11)
    scr = scrambled(snap)
    desk2 = TradeDesk(Evaluator(scr, GameState(scr)), 11)
    for pid in list(snap.pids)[:40]:
        assert desk.user_cost(pid) == desk2.user_cost(pid)
        assert _trade_weight(snap, pid) == _trade_weight(scr, pid)
    by_adp = sorted(snap.pids, key=lambda p: snap.players[p].adp)
    assert desk.user_cost(by_adp[0]) > desk.user_cost(by_adp[-1])
    old = snap_of(0)
    assert TradeDesk(Evaluator(old, GameState(old)), 11).user_cost(by_adp[0]) != desk.user_cost(by_adp[0])


def test_rookie_autopick_is_public_and_old_saves_keep_the_worth_pick():
    from tests.test_sim_dynasty import Run

    run = Run(hint_v=1)
    assert run.root.settings.hint_v == 1
    run.play_season()
    run.em.snap = run.snap
    dyn.start_rookie_draft(run.em)
    dyn.run_ai_rookie_picks(run.em, run.sd)
    snap, state = run.snap, run.state
    ev = Evaluator(snap, state)
    user = snap.user_team.tid
    new_pick = dyn.choose_rookie(snap, state, ev, user, state.offseason["pick_index"], run.sd, human=True)
    avail = dyn.rookies_available(snap, state)
    assert new_pick in avail[:30]
    old_snap = dataclasses.replace(snap, settings=dataclasses.replace(snap.settings, hint_v=0))
    old_pick = dyn.choose_rookie(old_snap, state, Evaluator(old_snap, state), user, state.offseason["pick_index"], run.sd, human=True)
    assert old_pick in avail[:30]
    # the public pick moves with ADP, not with the hidden value
    scr = dataclasses.replace(snap, players={pid: dataclasses.replace(p, value=float(len(pid) * 7 % 13), market=3.0) if p.extra.get("is_rookie") else p for pid, p in snap.players.items()})
    assert dyn.choose_rookie(scr, state, Evaluator(scr, state), user, state.offseason["pick_index"], run.sd, human=True) == new_pick
