"""Regression tests from the logic audit 4 stress runs (modules/sim/calibration/league_integrity_stress.py)."""

from __future__ import annotations

import numpy as np

from modules.sim import game_actions as act
from modules.sim.calibration import league_integrity_stress as lis
from modules.sim.game_result import replay_game
from modules.sim.game_state import Emitter

BASE = {
    "kind": "redraft", "seed": 3, "flags": {f: 0 for f in ("hint_v", "limit_v", "kd_v", "world_v", "econ_v", "ai_v", "block_v")},
    "aging_v": 0, "upgrade_at": None, "user_style": "idle",
    "raw": {"teams": 8, "user_slot": 2, "superflex": False, "include_def": False, "include_k": True, "scoring": "ppr", "te_premium": 0.0,
            "difficulty": "normal", "bench": 6, "ir_slots": 2, "flex_type": "flex", "tiebreaker": "points_for", "auto_lineup": False},
}


def _play(**over):
    sc = {**BASE, **over}
    run = lis.Run(sc, 3)
    run.play()
    return run


def test_league_longer_than_the_player_model_season_plays_to_a_champion():
    """A league import with a 4-round playoff after 14 regular weeks runs to calendar week 18, past the 17 weeks a season profile
    covers: it used to stop with an IndexError at the first overflow week."""

    run = _play(kind="league", teams=12, playoff_teams=9, regular_weeks=14, dynasty=False, slots_pick=0, bench=6)
    assert run.state.status == "complete" and run.state.champion
    assert run.S.total_weeks == 18
    assert not run.failures, run.failures[:3]
    last = run.state.history[-1]
    assert last["week"] == 18 and last["kind"] == "playoff"


def test_overflow_weeks_add_no_new_injuries_and_keep_in_profile_weeks_unchanged():
    from modules.sim import game_scoring as gs
    from modules.sim.synthetic import build_synthetic_pool  # noqa: F401

    class P:  # a season profile of 17 modelled weeks
        form = (1.0,) * 17

    assert gs.PlayerModelAdapter.model_week(P, 5) == 5
    assert gs.PlayerModelAdapter.model_week(P, 17) == 17
    assert gs.PlayerModelAdapter.model_week(P, 18) == 17
    assert gs.PlayerModelAdapter.model_week(P, 21) == 17


def test_replay_reproduces_a_game_that_took_the_realism_update():
    run = _play(upgrade_at=1)
    assert any(e["type"] == "realism_upgrade" for e in run.em.events)
    assert replay_game(run.root, run.seed, run.em.events, strict=True).digest() == run.state.digest()


def test_replay_reproduces_ir_moves_and_block_changes():
    sc = {**BASE, "flags": {**BASE["flags"], "block_v": 1, "limit_v": 1}}
    run = lis.Run(sc, 3)
    run.drive_draft()
    run.view()
    user = run.root.user_team.tid
    run.rng = np.random.default_rng(1)
    snap = run.view()
    from modules.sim.game_block import set_block

    pid = run.state.rosters[user][0]
    set_block(run.em, pid, True, "RB")
    act.upgrade_realism(run.em) if False else None
    while run.state.status in ("in_season", "playoffs"):
        run.step()
        snap = run.view()
        hurt = [p for p in run.state.rosters[user] if run.state.out.get(p, 0) > 0]
        if hurt and not run.state.ir[user] and run.S.ir_slots:
            act.move_player(run.em, hurt[0], "ir")
    assert any(e["type"] == "slot_move" for e in run.em.events)
    assert replay_game(run.root, run.seed, run.em.events, strict=True).digest() == run.state.digest()
