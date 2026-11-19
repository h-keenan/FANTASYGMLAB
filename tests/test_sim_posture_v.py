"""posture_v 1: AI teams' buy / sell posture follows the standings and playoff odds, with hysteresis (docs/audits/2026-11-realism-advice-audit-2.md)."""

from __future__ import annotations

from dataclasses import replace

from modules.sim import game_rules as rules
from modules.sim import game_posture as gp
from modules.sim.calibration import realism_p1_report as rep
from modules.sim.game_engine import advance
from modules.sim.game_eval import team_params
from modules.sim.game_state import Emitter, fold
from modules.sim.game_types import POSTURE_VERSION, GameSettings

PIN_OLD = ["f036e1a1efbc396e", "bba80c9ada7ca5e4"]  # computed on the engine before posture_v existed


def _season(seed: int, posture_v: int):
    """A full redraft game: (snapshot, final state, every event including the draft)."""

    events: list = []
    snap, state = rep._new_game(seed, {"posture_v": posture_v, "cover_v": 0, "wrapped_v": 0}, events=events)
    while state.status == "in_season":
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
        events += em.events
    return snap, state, events


def test_gate_and_serialization():
    s = GameSettings.parse({})
    assert POSTURE_VERSION == 1 and s.posture_v == 1 and s.to_dict()["posture_v"] == 1
    d = s.to_dict()
    d.pop("posture_v")
    old = GameSettings.from_dict(d)
    assert old.posture_v == 0 and "posture_v" not in old.to_dict()
    assert rules.UPGRADABLE_FLAGS["posture_v"] == (1, rules.WEEK) and rules.FLAGS["posture_v"]["dynasty_only"] is False


def test_hysteresis_keeps_a_team_on_the_line_from_flipping():
    ns = gp.next_stance
    assert ns("", 0.5) == "" and ns("", 0.7) == "buy" and ns("", 0.1) == "sell"
    assert ns("buy", 0.5) == "buy" and ns("buy", 0.44) == ""  # it takes a real drop to stop buying
    assert ns("sell", 0.2) == "sell" and ns("sell", 0.31) == ""
    # a team wobbling between 40% and 60% never changes stance, and buy never jumps straight to sell
    stance = "buy"
    for odds in (0.5, 0.6, 0.46, 0.55, 0.5):
        stance = ns(stance, odds)
    assert stance == "buy"
    assert ns("buy", 0.05) == ""


def test_the_odds_use_record_roster_and_games_left():
    snap, state = rep._new_game(1, {"posture_v": 1, "cover_v": 0, "wrapped_v": 0})
    for t in snap.tids:
        state.stand[t] = {"w": 3, "l": 3, "t": 0, "pf": 600.0, "pa": 600.0}
    good, bad = snap.tids[0], snap.tids[1]
    state.stand[good].update(w=6, l=0)
    state.stand[bad].update(w=0, l=6)
    odds = gp.playoff_odds(snap, state)
    assert odds[good] > 0.8 > 0.2 > odds[bad]
    assert all(0.0 <= o <= 1.0 for o in odds.values())


def test_a_posture_event_changes_the_ai_horizon_and_only_in_posture_v_1():
    snap, state = rep._new_game(1, {"posture_v": 1, "cover_v": 0, "wrapped_v": 0})
    tid = next(t.tid for t in snap.teams if not t.is_user)
    base = team_params(snap, tid, state)
    state.posture[tid] = {"stance": "buy", "week": 6, "odds": 0.9}
    buy = team_params(snap, tid, state)
    state.posture[tid] = {"stance": "sell", "week": 6, "odds": 0.05}
    sell = team_params(snap, tid, state)
    assert sell.horizon < base.horizon < buy.horizon and buy.activity >= base.activity
    old = replace(snap, settings=replace(snap.settings, posture_v=0))
    assert team_params(old, tid, state).horizon == base.horizon  # an old save ignores the posture
    assert team_params(snap, tid).horizon == base.horizon  # and so does a caller that passes no state


def test_old_saves_never_emit_a_posture_and_replay_pinned():
    digests = []
    for seed in (1, 2):
        snap, state, events = _season(seed, 0)
        assert not state.posture and not any(e["type"] == "posture" for e in events)
        digests.append(state.digest()[:16])
    assert digests == PIN_OLD


def test_a_season_with_posture_replays_exactly_and_does_not_flip_flop():
    snap, state, events = _season(1, 1)
    posture_events = [e for e in events if e["type"] == "posture"]
    assert posture_events and all(e["week"] >= gp.MIN_GAMES + 1 for e in posture_events)
    replay = fold(snap, events)
    assert replay.digest() == state.digest()
    last: dict[str, int] = {}
    for e in posture_events:
        for tid, row in e["payload"]["teams"].items():
            assert tid not in last or row["week"] - last[tid] >= gp.MIN_TENURE  # a posture is held for at least the tenure
            last[tid] = row["week"]
            assert row["stance"] in ("buy", "sell", "")
    stances = [row["stance"] for e in posture_events for row in e["payload"]["teams"].values()]
    assert "buy" in stances or "sell" in stances
