"""cover_v 1: an AI team covers a starting slot its only player cannot fill, and a defense is never injured (docs/audits/2026-11-realism-advice-audit-2.md)."""

from __future__ import annotations

from modules.sim import game_rules as rules
from modules.sim.calibration import realism_p1_report as rep
from modules.sim.game_engine import advance
from modules.sim.game_state import Emitter
from modules.sim.game_types import COVER_VERSION, GameSettings


def test_gate_and_serialization():
    s = GameSettings.parse({})
    assert COVER_VERSION == 1 and s.cover_v == 1 and s.to_dict()["cover_v"] == 1
    d = s.to_dict()
    d.pop("cover_v")
    old = GameSettings.from_dict(d)
    assert old.cover_v == 0 and "cover_v" not in old.to_dict()
    assert rules.UPGRADABLE_FLAGS["cover_v"] == (1, rules.WEEK) and rules.FLAGS["cover_v"]["dynasty_only"] is False


def _empty_ai_slots(cover_v: int, seed: int = 2) -> tuple[int, int]:
    snap, state = rep._new_game(seed, {"cover_v": cover_v}, {"include_def": True})
    user = snap.user_team.tid
    empty = total = 0
    while state.status == "in_season" and state.week <= snap.settings.regular_weeks:
        advance(Emitter(state, snap), snap, state, seed)
        for tid in snap.tids:
            if tid != user:
                total += 1
                empty += sum(1 for _slot, pid in state.lineups[tid] if not pid)
    return empty, total


def test_ai_lineups_have_no_empty_kicker_or_defense_slot_once_covered():
    old, n = _empty_ai_slots(0)
    new, _ = _empty_ai_slots(1)
    assert old >= 10  # a lone K / DEF on his bye was left as an empty slot (about one team-week in seven)
    assert new <= max(1, old // 10), (old, new, n)


def test_a_defense_is_never_hurt_with_cover_v():
    snap, state = rep._new_game(3, {"cover_v": 1}, {"include_def": True})
    while state.status == "in_season" and state.week <= snap.settings.regular_weeks:
        advance(Emitter(state, snap), snap, state, 3)
    defenses = [p for p in snap.pids if snap.players[p].pos == "DEF"]
    assert defenses and all(state.out.get(p, 0) == 0 for p in defenses)
    played = [pts for p in defenses for pts in state.points.get(p, []) if pts is not None]
    assert len(played) >= 12 * 10  # every defense plays every week but its bye
