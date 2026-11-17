"""need_v 1: the Needs / Strength tags come from real roster holes (docs/audits/2026-11-realism-advice-audit-2.md): strict starting slots with a superflex counted
as a second QB and flex slots never a need, a shortfall against the league median after what the wire adds, one report shared by the tags and the trade AI."""

from __future__ import annotations

import hashlib
import json

from modules.sim import game_rules as rules
from modules.sim.calibration import realism_p1_report as rep
from modules.sim.game_ai import TradeDesk
from modules.sim.game_eval import Evaluator
from modules.sim.game_need import position_report, starter_slots
from modules.sim.game_types import NEED_VERSION, GameSettings

PIN_OLD_SUPERFLEX_SEED1 = "9309f4f3e2dfe73d"


def _report(seed: int, need_v: int, **extra):
    snap, state = rep._new_game(seed, {"need_v": need_v, "cap_v": 0}, extra)  # the digest pin predates cap_v
    return snap, state, position_report(snap, Evaluator(snap, state))


def _digest(report) -> str:
    return hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()[:16]


def test_gate_and_serialization():
    s = GameSettings.parse({})
    assert NEED_VERSION == 1 and s.need_v == 1 and s.to_dict()["need_v"] == 1
    d = s.to_dict()
    d.pop("need_v")
    old = GameSettings.from_dict(d)
    assert old.need_v == 0 and "need_v" not in old.to_dict()
    assert rules.UPGRADABLE_FLAGS["need_v"] == (1, rules.NOW) and rules.FLAGS["need_v"]["dynasty_only"] is False


def test_starting_slots_count_a_superflex_qb_and_never_a_flex():
    one = GameSettings.parse({})
    sf = GameSettings.parse({"superflex": True})
    assert starter_slots(one)["QB"] == 1 and starter_slots(sf)["QB"] == 2
    assert starter_slots(one)["TE"] == 1 and starter_slots(one)["RB"] == 2 and starter_slots(one)["WR"] == 2  # a flex is nobody's hole


def test_old_saves_keep_the_bottom_tercile_and_replay_pinned():
    for seed in (1, 2, 3):
        _, _, r = _report(seed, 0)
        for pos in {e["pos"] for e in r["1"]}:
            assert sum(1 for t in r.values() for e in t if e["pos"] == pos and e["level"] == "need") == 4  # exactly a third of twelve, always
    assert _digest(_report(1, 0, superflex=True)[2]) == PIN_OLD_SUPERFLEX_SEED1


def test_tags_follow_real_holes_not_a_fixed_count():
    counts = set()
    for seed in (1, 2, 3):
        snap, state, r = _report(seed, 1)
        for pos in {e["pos"] for e in r["1"]}:
            counts.add(sum(1 for t in r.values() for e in t if e["pos"] == pos and e["level"] == "need"))
        for t in r.values():
            for e in t:
                assert e["level"] != "need" or e["hole"] or e["ratio"] < 0.88  # a need is a hole or a real shortfall
                assert e["level"] != "strength" or e["ratio"] >= 1.12
    assert len(counts) > 1 and counts != {4}


def test_an_empty_starting_slot_the_wire_cannot_fill_is_a_need():
    snap, state, r = _report(1, 1, superflex=True)
    tid = next(t for t in snap.tids if t != snap.user_team.tid)
    qbs = [p for p in state.rosters[tid] if snap.players[p].pos == "QB"]
    state.rosters[tid] = [p for p in state.rosters[tid] if p not in qbs[:-1]]  # a superflex team down to one quarterback
    owned = state.owner_map()
    for p in snap.pids:  # nobody usable on the wire
        if snap.players[p].pos == "QB" and p not in owned:
            state.out[p] = 9
    entry = next(e for e in position_report(snap, Evaluator(snap, state))[tid] if e["pos"] == "QB")
    assert entry["starters"] == 2 and entry["hole"] and entry["level"] == "need"


def test_the_trade_ai_reads_the_same_tags():
    snap, state, r = _report(2, 1)
    assert snap.settings.pos_rules
    desk = TradeDesk(Evaluator(snap, state), 1)
    for tid in snap.tids:
        needy = [e for e in r[tid] if e["level"] == "need"]
        pos, ratio = desk.need_position(tid)
        assert (ratio == 0.0 and any(e["pos"] == pos for e in needy)) or (ratio == 1.0 and not needy)
        if needy:
            assert pos == min(needy, key=lambda e: (e["ratio"], e["pos"]))["pos"]
