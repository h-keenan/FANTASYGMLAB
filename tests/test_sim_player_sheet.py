"""The Fantasy Sim player sheet payload: one rest-of-season line, a flat-projection flag, value ranks.

The sheet renders the real Player Quick View with these numbers; the payload says when the weekly
projection carries no information so the client shows one summary instead of a list of identical rows."""

from __future__ import annotations

import json

from modules.sim import game_view as view
from modules.sim.game_eval import Evaluator
from tests.test_sim_game_engine import drafted


def _detail(week_advance=0):
    from modules.sim.game_engine import advance

    snap, state, em = drafted(7, user_slot=2)
    for _ in range(week_advance):
        advance(em, snap, state, 7)
    pid = sorted(state.rosters[snap.user_team.tid])[0]
    return snap, state, pid, view.player_detail(snap, state, pid)


def test_flat_projection_is_flagged_and_summarised():
    snap, state, pid, d = _detail(2)
    json.dumps(d, allow_nan=False)
    playable = {(w["projection"], w["floor"], w["ceiling"]) for w in d["weeks"] if not w["bye"] and not w["out"]}
    assert len(playable) == 1  # the engine has no per-week opponent model: every healthy week is the same number
    assert d["projection_flat"] is True
    ros = d["ros"]
    ev = Evaluator(snap, state)
    assert ros["mean"] == round(ev.ros_mean(pid), 1) and ros["floor"] <= ros["mean"] <= ros["ceiling"]
    assert ros["weeks_left"] == len(d["weeks"]) and ros["playable_weeks"] <= ros["weeks_left"]
    assert ros["bye_week"] == (snap.bye_of(pid) if any(w["bye"] for w in d["weeks"]) else None)


def test_projection_is_not_flat_when_weeks_differ():
    weeks = [
        {"week": 3, "projection": 8.0, "floor": 4.0, "ceiling": 12.0, "bye": False, "out": False},
        {"week": 4, "projection": 9.5, "floor": 5.0, "ceiling": 14.0, "bye": False, "out": False},
        {"week": 5, "projection": 0.0, "floor": 0.0, "ceiling": 0.0, "bye": True, "out": False},
    ]
    assert view.projection_is_flat(weeks) is False
    assert view.projection_is_flat(weeks[:1] + weeks[2:]) is True  # a bye week alone is not variation
    assert view.projection_is_flat([]) is True


def test_detail_carries_value_ranks_and_zero_value_is_not_hidden():
    snap, state, pid, d = _detail()
    p = d["player"]
    assert 1 <= p["value_rank"] <= len(snap.pids)
    same = [q for q in snap.pids if snap.players[q].pos == p["pos"]]
    assert 1 <= p["pos_value_rank"] <= len(same)
    best = max(same, key=lambda q: (snap.players[q].value, q))
    assert view.player_detail(snap, state, best)["player"]["pos_value_rank"] == 1
