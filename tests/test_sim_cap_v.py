"""cap_v 1: one shared position limit for auto-pick, the draft hint, the AI draft and the AI waiver planner (docs/audits/2026-11-realism-advice-audit-2.md)."""

from __future__ import annotations

from collections import Counter

from modules.sim import game_rules as rules
from modules.sim.calibration import realism_p1_report as rep
from modules.sim.game_ai_depth import _cap, slot_need
from modules.sim.game_caps import position_cap
from modules.sim.game_eval import Evaluator
from modules.sim.game_types import CAP_VERSION, GameSettings

PIN_OLD = ["bb874e74dee2ca76", "577ee83b16c58d3e"]


def _counts(snap, state, tid):
    return Counter(snap.players[p].pos for p in state.rosters[tid])


def test_gate_and_serialization():
    s = GameSettings.parse({})
    assert CAP_VERSION == 1 and s.cap_v == 1 and s.to_dict()["cap_v"] == 1
    d = s.to_dict()
    d.pop("cap_v")
    old = GameSettings.from_dict(d)
    assert old.cap_v == 0 and "cap_v" not in old.to_dict()
    assert rules.UPGRADABLE_FLAGS["cap_v"] == (1, rules.NOW) and rules.FLAGS["cap_v"]["dynasty_only"] is False


def test_the_limit_is_slots_plus_flex_plus_backups():
    one = GameSettings.parse({})
    sf = GameSettings.parse({"superflex": True})
    assert position_cap(one, "QB") == 2 and position_cap(sf, "QB") == 3  # a superflex QB is a start
    assert position_cap(one, "K") == 1 and position_cap(one, "DEF") == 1
    assert position_cap(one, "TE") >= 3 and position_cap(one, "RB") >= 5 and position_cap(one, "WR") >= 5  # a flex is shared bench value
    for s in (one, sf, GameSettings.parse({"bench": 10}), GameSettings.parse({"flex_type": "rb_wr", "bench": 9})):  # a deep bench still has somewhere legal to go
        assert sum(position_cap(s, p) for p in s.pool_positions) >= s.roster_limit


def test_the_waiver_planner_reads_the_same_limit():
    snap, state = rep._new_game(1, {"cap_v": 1})
    ev = Evaluator(snap, state)
    need = slot_need(ev)
    for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
        if pos in snap.settings.pool_positions:
            assert _cap(ev, pos, need) == position_cap(snap.settings, pos)


def test_auto_draft_and_the_ai_draft_stop_at_two_quarterbacks_in_a_one_qb_league():
    for seed in (1, 2, 3, 4):
        snap, state = rep._new_game(seed, {"cap_v": 1})
        assert all(_counts(snap, state, t)["QB"] <= 2 for t in snap.tids)  # the user's auto-pick included
        assert all(_counts(snap, state, t)["QB"] >= 1 for t in snap.tids)


def test_old_saves_keep_the_old_caps_and_replay_pinned():
    digests = []
    three = 0
    for seed in (1, 2):
        snap, state = rep._new_game(seed, {"cap_v": 0})
        digests.append(state.digest()[:16])
        three += sum(_counts(snap, state, t)["QB"] == 3 for t in snap.tids)
    assert three > 0  # the old draft cap (QB 3) is what an old save keeps
    assert digests == PIN_OLD
