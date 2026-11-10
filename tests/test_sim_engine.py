"""Fantasy Sim engine: determinism, invariants, strategy effects, grading."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from modules.sim.analysis import letter_for, run_world
from modules.sim.engine import decision_key_trade, simulate_season
from modules.sim.lineup import SlotPlan, carry_lineup, pick_lineup
from modules.sim.personas import PERSONAS, assign_personas
from modules.sim.rng import WorldRng
from modules.sim.synthetic import build_synthetic_snapshot, round_robin
from modules.sim.types import LeagueSnapshot, Strategy

SNAP = build_synthetic_snapshot(7)


def _dump(outcome) -> str:
    return json.dumps(outcome.to_dict(), sort_keys=True)


# ------------------------------------------------------------------ determinism


def test_deterministic_replay_same_seed_identical_outcome():
    a = simulate_season(SNAP, Strategy(), 12345)
    b = simulate_season(SNAP, Strategy(), 12345)
    assert _dump(a) == _dump(b)


def test_deterministic_replay_survives_snapshot_round_trip():
    restored = LeagueSnapshot.from_dict(json.loads(json.dumps(SNAP.to_dict())))
    assert _dump(simulate_season(restored, Strategy(), 99)) == _dump(simulate_season(SNAP, Strategy(), 99))


def test_full_run_with_grade_is_deterministic():
    a = run_world(SNAP, Strategy(posture="win_now", trade_aggressiveness=0.9), 5)
    b = run_world(SNAP, Strategy(posture="win_now", trade_aggressiveness=0.9), 5)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_different_seeds_differ():
    assert _dump(simulate_season(SNAP, Strategy(), 1)) != _dump(simulate_season(SNAP, Strategy(), 2))


def test_rng_streams_are_order_independent():
    rng = WorldRng(42)
    first = rng.stream(3, "trade", 5).random(4)
    rng.stream(1, "score", 0).random(100)  # unrelated draws in between
    again = WorldRng(42).stream(3, "trade", 5).random(4)
    assert np.array_equal(first, again)
    assert not np.array_equal(first, rng.stream(3, "trade", 6).random(4))
    assert not np.array_equal(first, rng.stream(3, "waiver", 5).random(4))


def test_personas_deterministic_from_seed_and_capped():
    tids = [str(i) for i in range(2, 13)]
    pct = {t: i / 10 for i, t in enumerate(tids)}
    ages = {t: 24 + i * 0.5 for i, t in enumerate(tids)}
    a = assign_personas(WorldRng(8).stream(0, "persona", 0), tids, pct, ages)
    b = assign_personas(WorldRng(8).stream(0, "persona", 0), tids, pct, ages)
    assert {k: v.pid for k, v in a.items()} == {k: v.pid for k, v in b.items()}
    assert set(a) == set(tids)
    from collections import Counter

    assert max(Counter(p.pid for p in a.values()).values()) <= 3
    assert all(p.pid in PERSONAS for p in a.values())


# -------------------------------------------------------------------- invariants


def test_season_invariants():
    out = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0, waiver_aggressiveness=1.0), 3)
    rows = out.standings
    assert len(rows) == len(SNAP.teams)
    games = len(SNAP.schedule)
    for r in rows:
        assert r["wins"] + r["losses"] + r["ties"] == games
    assert sum(r["wins"] for r in rows) == sum(r["losses"] for r in rows)
    assert out.champion in {r["team_id"] for r in rows if r["made_playoffs"]}
    assert [r["playoff_result"] for r in rows if r["playoff_result"] == "champion"] == ["champion"]
    assert sum(1 for r in rows if r["made_playoffs"]) == SNAP.settings.playoff_teams
    assert len(out.weekly) == games
    assert [e["seq"] for e in out.events] == list(range(len(out.events)))


def test_every_player_has_one_owner_through_trades_and_waivers():
    """Replay the event log and check no player is duplicated or lost."""

    out = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0, waiver_aggressiveness=1.0), 11)
    rosters = {t.tid: set(t.roster) for t in SNAP.teams}
    fa = set(SNAP.free_agents)
    for e in out.events:
        if e["type"] == "trade":
            a, b = rosters[e["team"]], rosters[e["partner"]]
            for g in e["gives"]:
                a.remove(g["player_id"])
                b.add(g["player_id"])
            for g in e["gets"]:
                b.remove(g["player_id"])
                a.add(g["player_id"])
        elif e["type"] == "waiver":
            fa.remove(e["add"]["player_id"])
            rosters[e["team"]].add(e["add"]["player_id"])
            if e["drop"]:
                rosters[e["team"]].remove(e["drop"]["player_id"])
                fa.add(e["drop"]["player_id"])
        elif e["type"] == "drop":
            rosters[e["team"]].remove(e["player"]["player_id"])
            fa.add(e["player"]["player_id"])
    owned = [p for r in rosters.values() for p in r]
    assert len(owned) == len(set(owned))
    assert not (set(owned) & fa)
    assert any(e["type"] == "trade" for e in out.events)


def test_trades_respect_deadline_and_caps():
    out = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0), 21)
    trades = [e for e in out.events if e["type"] == "trade"]
    assert all(e["week"] <= SNAP.settings.trade_deadline_week for e in trades)
    per_week: dict[int, int] = {}
    for e in trades:
        per_week[e["week"]] = per_week.get(e["week"], 0) + 1
    assert max(per_week.values(), default=0) <= 3
    for t in SNAP.teams:
        assert sum(1 for e in trades if t.tid in (e["team"], e["partner"])) <= 4


def test_mutually_beneficial_trades_only():
    out = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0), 21)
    for e in out.events:
        if e["type"] == "trade":
            assert e["initiator_gain"] > 0


def test_user_never_trades_at_zero_aggressiveness():
    for seed in range(6):
        out = simulate_season(SNAP, Strategy(trade_aggressiveness=0.0), seed)
        assert not [e for e in out.events if e["type"] == "trade" and e["involves_user"]]


def test_protected_players_are_never_traded_or_dropped():
    protected = SNAP.user_team.roster[:12]
    for seed in range(6):
        out = simulate_season(
            SNAP, Strategy(trade_aggressiveness=1.0, waiver_aggressiveness=1.0, protected_player_ids=protected), seed
        )
        for e in out.events:
            if not e.get("involves_user"):
                continue
            if e["type"] == "trade":
                user_gives = e["gives"] if e["team"] == SNAP.user_team.tid else e["gets"]
                assert not {a["player_id"] for a in user_gives} & set(protected)
            if e["type"] == "waiver" and e["drop"]:
                assert e["drop"]["player_id"] not in protected


def test_waiver_aggressiveness_zero_means_no_user_pickups():
    out = simulate_season(SNAP, Strategy(waiver_aggressiveness=0.0), 4)
    assert not [e for e in out.events if e["type"] == "waiver" and e["involves_user"]]


def test_remaining_mode_keeps_real_records_and_starts_late():
    base = build_synthetic_snapshot(7, start_week=6)
    teams = tuple(replace(t, wins=3.0, losses=2.0, pf=500.0, pa=480.0) for t in base.teams)
    snap = replace(base, teams=teams, mode="remaining")
    out = simulate_season(snap, Strategy(), 2)
    assert out.start_week == 6
    assert len(out.weekly) == 14 - 6 + 1
    for r in out.standings:
        assert r["wins"] + r["losses"] + r["ties"] == 5 + len(snap.schedule)


def test_strategy_posture_changes_trade_behavior():
    """Win-now and rebuild auto-GMs do not make the same trades."""

    now = [simulate_season(SNAP, Strategy(posture="win_now", trade_aggressiveness=1.0), s) for s in range(8)]
    rebuild = [simulate_season(SNAP, Strategy(posture="rebuild", trade_aggressiveness=1.0), s) for s in range(8)]

    def keys(outs):
        return {e["key"] for o in outs for e in o.events if e["type"] == "trade" and e["involves_user"]}

    assert keys(now) and keys(rebuild)
    assert keys(now) != keys(rebuild)


def test_lineup_auto_set_off_is_sticky_but_valid():
    out = simulate_season(SNAP, Strategy(lineup_auto_set=False), 9)
    assert out.user["games"] == len(SNAP.schedule)
    assert 0 < out.user["lineup_efficiency"] <= 1.0


# ------------------------------------------------------------- counterfactuals


def test_veto_removes_exactly_that_user_decision():
    strategy = Strategy(trade_aggressiveness=1.0, waiver_aggressiveness=1.0)
    for seed in range(12):
        base = simulate_season(SNAP, strategy, seed)
        user_events = [e for e in base.events if e["involves_user"] and e["type"] in ("trade", "waiver")]
        if not user_events:
            continue
        victim = user_events[0]
        alt = simulate_season(SNAP, strategy, seed, veto=[victim["key"]])
        assert victim["key"] not in {e.get("key") for e in alt.events}
        # a no-op veto changes nothing
        same = simulate_season(SNAP, strategy, seed, veto=["trade:w99:give=x:get=y"])
        assert _dump(same) == _dump(base)
        return
    pytest.fail("no user decision found to veto")


def test_decision_key_is_order_independent():
    assert decision_key_trade(3, ["b", "a"], ["d", "c"]) == decision_key_trade(3, ["a", "b"], ["c", "d"])


# ------------------------------------------------------------------ grade/decisions


def test_grade_and_decisions_shape():
    result = run_world(SNAP, Strategy(posture="win_now", trade_aggressiveness=0.9), 5)
    grade = result["grade"]
    assert grade["letter"] in {"A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"}
    assert 0 <= grade["score"] <= 100
    assert abs(sum(c["weight"] for c in grade["components"]) - 1.0) < 1e-9
    decisions = result["decisions_that_mattered"]
    assert 3 <= len(decisions) <= 4
    magnitudes = [abs(d["impact"]["season_value"]) for d in decisions]
    assert magnitudes == sorted(magnitudes, reverse=True)
    for d in decisions:
        assert d["title"] and d["detail"] and "wins" in d["impact"]
    assert result["strategy"]["posture"] == "win_now"


def test_letter_bands():
    assert letter_for(95) == "A"
    assert letter_for(73) == "C"
    assert letter_for(10) == "F"


def test_grade_rewards_better_outcomes_on_average():
    """A real signal, not noise: across seeds, finishing high grades higher."""

    results = [run_world(SNAP, Strategy(), s, explain=True) for s in range(10)]
    by_finish = sorted(results, key=lambda r: r["grade"]["summary"]["finish"])
    top = sum(r["grade"]["score"] for r in by_finish[:4]) / 4
    bottom = sum(r["grade"]["score"] for r in by_finish[-4:]) / 4
    assert top > bottom


# ---------------------------------------------------------------------- lineups


def test_pick_lineup_fills_strict_then_flex_without_reuse():
    plan = SlotPlan(("QB", "RB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX"))
    entries = [
        (20, "q1", "QB"), (18, "q2", "QB"), (15, "r1", "RB"), (14, "r2", "RB"), (13, "r3", "RB"),
        (12, "w1", "WR"), (11, "w2", "WR"), (9, "t1", "TE"),
    ]
    assignment, total = pick_lineup(plan, entries)
    pids = [p for _, p in assignment if p]
    assert len(pids) == len(set(pids)) == 7
    assert dict(assignment)["QB"] == "q1"
    assert dict(assignment)["SUPER_FLEX"] == "q2"  # 18 beats the remaining RB/WR
    assert total == 20 + 15 + 14 + 12 + 9 + 13 + 18


def test_carry_lineup_keeps_healthy_starters_and_replaces_missing():
    plan = SlotPlan(("QB", "RB", "WR"))
    start, _ = pick_lineup(plan, [(10, "q1", "QB"), (9, "r1", "RB"), (8, "w1", "WR"), (7, "w2", "WR"), (6, "r2", "RB")])
    # a better WR arrives but r1 is injured: w1 stays (sticky), RB is replaced
    entries = [(10, "q1", "QB"), (6, "r2", "RB"), (8, "w1", "WR"), (20, "w9", "WR")]
    carried = dict(carry_lineup(plan, start, entries))
    assert carried == {"QB": "q1", "RB": "r2", "WR": "w1"}


def test_round_robin_covers_everyone_each_week():
    tids = [str(i) for i in range(1, 13)]
    for week in round_robin(tids, 14):
        flat = [t for pair in week for t in pair]
        assert sorted(flat) == sorted(tids)
