"""wire_v 1: the waiver wire is contested (docs/audits/2026-11-realism-advice-audit-2.md). The AI claims the players it wants even when the user queued
them, and every claim settles in waiver-priority order. Gate, old-save digest pins and the Realism update."""

from __future__ import annotations

from modules.sim import game_rules as rules
from modules.sim.calibration import realism_p1_report as rep
from modules.sim.game_engine import advance, waiver_order
from modules.sim.game_state import Emitter
from modules.sim.game_types import WIRE_VERSION, GameSettings

SEEDS = (1, 2, 3)
PIN_OLD = ["bc7e1fb5de41ec70", "5ab40a2ba2b41aad", "f50dbd192cdfdd5d"]


def _play(seed: int, wire_v: int):
    snap, state = rep._new_game(seed, {"wire_v": wire_v, "cap_v": 0})  # the digest pins predate cap_v
    user = snap.user_team.tid
    results = []  # (user priority index, ok, reason) for the user's claims
    while state.status == "in_season":
        em = Emitter(state, snap)
        if state.week < snap.settings.regular_weeks:
            rep._user_queue_best(em, snap, state)
        pri = waiver_order(snap, state).index(user)
        advance(em, snap, state, seed)
        results += [(pri, e["payload"]["ok"], e["payload"]["reason"]) for e in em.events
                    if e["type"] == "waiver_result" and e["payload"].get("team") == user and e["payload"].get("claim_id")]
    return state, results


def test_gate_and_serialization():
    s = GameSettings.parse({})
    assert WIRE_VERSION == 1 and s.wire_v == 1 and s.to_dict()["wire_v"] == 1
    d = s.to_dict()
    d.pop("wire_v")
    old = GameSettings.from_dict(d)
    assert old.wire_v == 0 and "wire_v" not in old.to_dict()
    assert rules.UPGRADABLE_FLAGS["wire_v"] == (1, rules.WEEK) and rules.FLAGS["wire_v"]["dynasty_only"] is False


def test_old_saves_never_lose_a_contested_claim_and_replay_pinned():
    digests = []
    for seed in SEEDS:
        state, results = _play(seed, 0)
        assert results and all(ok or reason != "taken" for _, ok, reason in results)  # the user wins every contest
        digests.append(state.digest()[:16])
    assert digests == PIN_OLD


def test_contested_claims_follow_priority():
    top, bottom = [0, 0], [0, 0]
    for seed in SEEDS:
        _, results = _play(seed, 1)
        for pri, ok, reason in results:
            if not ok and reason != "taken":
                continue
            (top if pri < 6 else bottom)[0 if ok else 1] += 1
    assert top[1] + bottom[1] > 0  # the AI does contest the user's claims now
    assert top[0] / max(1, sum(top)) > bottom[0] / max(1, sum(bottom))  # and a better priority wins more often
