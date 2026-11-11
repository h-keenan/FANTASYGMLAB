"""Fantasy Sim: bye weeks and draft-pick trade assets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from modules.sim.analysis import run_world
from modules.sim.engine import _World, simulate_season
from modules.sim.inputs import RealSimInputs
from modules.sim.picks import pick_market_value
from modules.sim.synthetic import build_synthetic_snapshot
from modules.sim.types import LeagueSnapshot, SimPick, Strategy

SNAP = build_synthetic_snapshot(7)


def _world(snap=SNAP, strategy=None, seed=3) -> _World:
    return _World(snap, strategy or Strategy(), seed, frozenset())


def _starter_on_bye(world: _World):
    """(tid, pid, bye_week): a healthy starter of a team whose NFL team has a bye."""
    for tid in world.tids:
        for slot, pid in world._lineup_for(tid, 1):
            if pid is None:
                continue
            week = int(world.bye_arr[world.idx[pid]])
            if week:
                return tid, pid, week
    raise AssertionError("synthetic league has no starter on a bye")


# ------------------------------------------------------------------ bye weeks


def test_player_on_bye_scores_zero_only_that_week():
    world = _world()
    _, pid, week = _starter_on_bye(world)
    i = world.idx[pid]
    assert world._week_points(week)[i] == 0.0
    assert world._week_points(week - 1)[i] > 0.0 or world.out[i] > 0


def test_bye_starter_is_replaced_by_a_bench_player():
    world = _world()
    tid, pid, week = _starter_on_bye(world)
    lineup = [p for _, p in world._lineup_for(tid, week) if p]
    assert pid not in lineup
    assert len(lineup) == len([s for s, _ in world._lineup_for(tid, 1)])  # slot still filled
    assert all(not world._on_bye(p, week) for p in lineup)
    # ... and he starts again the week after
    assert pid in [p for _, p in world._lineup_for(tid, week + 1)] or world._on_bye(pid, week + 1)


def test_set_and_forget_user_gets_a_one_week_substitute():
    world = _world(strategy=Strategy(lineup_auto_set=False))
    user = world.user_tid
    starters = {p for _, p in world._lineup_for(user, 1) if p}
    pid = next((p for p in sorted(starters) if world.pos[p] != "K" and int(world.bye_arr[world.idx[p]]) > 1), None)  # K has no bench cover
    assert pid is not None, "user has no starter on a later bye"
    week = int(world.bye_arr[world.idx[pid]])
    on_bye_week = [p for _, p in world._lineup_for(user, week) if p]
    assert pid not in on_bye_week and len(on_bye_week) == len(starters)
    after = [p for _, p in world._lineup_for(user, week + 1) if p]
    assert pid in after  # the standing lineup was not rewritten by the bye


def test_byes_lower_total_scoring_without_changing_decisions():
    no_byes = replace(SNAP, bye_weeks={})
    a = simulate_season(SNAP, Strategy(), 5)
    b = simulate_season(no_byes, Strategy(), 5)
    # Same dice, but benching bye starters costs the league points overall.
    assert sum(r["pf"] for r in a.standings) < sum(r["pf"] for r in b.standings)


def test_snapshot_without_byes_or_picks_still_loads_and_runs():
    raw = json.loads(json.dumps(SNAP.to_dict()))
    raw.pop("bye_weeks")
    raw.pop("picks")
    old = LeagueSnapshot.from_dict(raw)
    assert old.bye_weeks == {} and old.picks == ()
    out = simulate_season(old, Strategy(), 5)
    assert not any(a.get("kind") == "pick" for e in out.events if e["type"] == "trade" for a in e["gives"] + e["gets"])


def test_bye_and_pick_snapshot_round_trips():
    again = LeagueSnapshot.from_dict(json.loads(json.dumps(SNAP.to_dict())))
    assert again.bye_weeks == SNAP.bye_weeks and again.picks == SNAP.picks


# ----------------------------------------------------------------- draft picks


def test_pick_value_falls_through_the_draft_and_into_the_future():
    first = pick_market_value(1, 0.0, 0, 12)
    last_of_round_one = pick_market_value(1, 1.0, 0, 12)
    second = pick_market_value(2, 0.0, 0, 12)
    assert first > last_of_round_one > second > pick_market_value(4, 1.0, 0, 12) > 0
    assert pick_market_value(1, 0.5, 2, 12) < pick_market_value(1, 0.5, 0, 12)
    assert 0 < pick_market_value(1, 0.0, 0, 12) <= 100


def test_picks_trade_and_ownership_is_conserved():
    owner = {p.pid: p.owner for p in SNAP.picks}
    moved = 0
    for seed in range(1, 7):
        out = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0), seed)
        holders = dict(owner)
        for e in out.events:
            if e["type"] != "trade":
                continue
            for asset in e["gives"]:
                if asset.get("kind") == "pick":
                    assert holders[asset["player_id"]] == e["team"]
                    holders[asset["player_id"]] = e["partner"]
                    moved += 1
            for asset in e["gets"]:
                if asset.get("kind") == "pick":
                    assert holders[asset["player_id"]] == e["partner"]
                    holders[asset["player_id"]] = e["team"]
                    moved += 1
    assert moved > 0, "AI managers never traded a pick"


def test_pick_assets_are_labelled_and_deterministic():
    a = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0), 2)
    b = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0), 2)
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)
    picks = [x for e in a.events if e["type"] == "trade" for x in e["gives"] + e["gets"] if x.get("kind") == "pick"]
    assert picks and all(x["name"].endswith("pick") or "(via" in x["name"] for x in picks)


def test_rebuilders_value_picks_above_contenders():
    world = _world()
    from modules.sim.personas import PERSONAS

    pid = SNAP.picks[0].pid
    contender = world._pick_worth(PERSONAS["contender"].params, pid)
    rebuilder = world._pick_worth(PERSONAS["rebuilder"].params, pid)
    assert rebuilder > contender > 0


def test_user_protected_players_are_still_never_traded_with_picks_around():
    user = SNAP.user_team
    keep = tuple(user.roster[:5])
    out = simulate_season(SNAP, Strategy(trade_aggressiveness=1.0, protected_player_ids=keep), 4)
    for e in out.events:
        if e["type"] == "trade" and e["involves_user"]:
            sent = e["gives"] if e["team"] == user.tid else e["gets"]
            assert not {a["player_id"] for a in sent} & set(keep)


def test_pick_trades_carry_a_grading_caveat():
    for seed in range(1, 12):
        result = run_world(SNAP, Strategy(trade_aggressiveness=1.0), seed)
        pick_trades = [
            d for d in result["decisions_that_mattered"]
            if d["kind"] == "trade" and "pick" in d["title"]
        ]
        if pick_trades:
            assert all("not scored" in d["detail"] for d in pick_trades)
            return
    pytest.skip("no user pick trade surfaced in the sampled seeds")


def test_snapshot_rejects_bad_picks():
    tid = SNAP.teams[0].tid
    with pytest.raises(ValueError):
        replace(SNAP, picks=(SimPick(2027, 1, "nope", tid),)).validate()
    dup = SimPick(2027, 1, tid, tid)
    with pytest.raises(ValueError):
        replace(SNAP, picks=(dup, dup)).validate()


# --------------------------------------------------------------------- inputs

_TEAMS = [f"T{i:02d}" for i in range(32)]


def _games_csv(path: Path, *, season=2026, drop_teams=0, double_bye=None) -> None:
    """17 regular-season games per team over weeks 1-18; team i byes week 5 + i % 9."""
    lines = ["season,game_type,week,home_team,away_team"]
    teams = _TEAMS[: 32 - drop_teams]
    for week in range(1, 19):
        playing = [t for i, t in enumerate(teams) if 5 + i % 9 != week]
        if double_bye == teams[0] and week == 3:
            playing = [t for t in playing if t != teams[0]]
        if len(playing) % 2:
            playing.append("ZZZ")  # odd count: the leftover team plays a dummy
        for a, b in zip(playing[::2], playing[1::2]):
            lines.append(f"{season},REG,{week},{a},{b}")
    lines.append(f"{season},POST,19,{teams[0]},{teams[1]}")
    lines.append(f"{season - 1},REG,1,{teams[0]},{teams[1]}")  # other season ignored
    path.write_text("\n".join(lines) + "\n")


def test_bye_weeks_come_from_the_cached_schedule_read_only(tmp_path):
    csv_path = tmp_path / "games.csv"
    _games_csv(csv_path)
    before = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    byes = RealSimInputs(games_csv_path=str(csv_path))._bye_weeks(2026)
    assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == before
    assert byes["T00"] == 5 and byes["T04"] == 9 and byes["T09"] == 5
    assert len(byes) == 32 and "ZZZ" not in byes


def test_bye_weeks_unknown_rather_than_guessed(tmp_path):
    csv_path = tmp_path / "games.csv"
    inputs = RealSimInputs(games_csv_path=str(csv_path))
    assert inputs._bye_weeks(2026) == {}  # no file
    _games_csv(csv_path, drop_teams=8)
    assert RealSimInputs(games_csv_path=str(csv_path))._bye_weeks(2026) == {}  # partial schedule
    _games_csv(csv_path, double_bye="T00")
    byes = RealSimInputs(games_csv_path=str(csv_path))._bye_weeks(2026)
    assert "T00" not in byes and "T01" in byes  # two open weeks: not a single bye
    assert RealSimInputs(games_csv_path=str(csv_path))._bye_weeks(0) == {}


def test_draft_picks_use_traded_ownership_and_defaults():
    class Sleeper:
        @staticmethod
        def get_traded_picks(league_id):
            return [
                {"season": "2027", "round": 1, "roster_id": 1, "owner_id": 3},
                {"season": "2030", "round": 1, "roster_id": 1, "owner_id": 3},  # out of range
                {"season": "2027", "round": 9, "roster_id": 1, "owner_id": 3},  # past the last round
                {"season": "2027", "round": 1, "roster_id": 99, "owner_id": 3},  # unknown team
            ]

    league = {"season": "2026", "status": "in_season"}
    picks = RealSimInputs._draft_picks(Sleeper, "L", league, {"draft_rounds": 3}, ["1", "2", "3"])
    by_id = {p.pid: p for p in picks}
    assert len(picks) == 2 * 3 * 3 and {p.season for p in picks} == {2027, 2028}
    assert by_id["pick:2027:1:1"].owner == "3" and by_id["pick:2027:1:2"].owner == "2"
    pre = RealSimInputs._draft_picks(Sleeper, "L", {"season": "2026", "status": "pre_draft"}, {}, ["1", "2"])
    assert {p.season for p in pre} == {2026, 2027} and {p.round for p in pre} == {1, 2, 3, 4}
    assert RealSimInputs._draft_picks(Sleeper, "L", {}, {}, ["1", "2"]) == ()

    class Broken:
        @staticmethod
        def get_traded_picks(league_id):
            raise RuntimeError("down")

    assert all(p.owner == p.orig for p in RealSimInputs._draft_picks(Broken, "L", league, {}, ["1", "2"]))
