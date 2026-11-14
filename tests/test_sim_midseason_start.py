"""League import "Start from: current point in the season": the engine opens at the real league's current week with its real
records, played weeks and lineups, replays exactly, and leaves every other game (old saves included) untouched."""

from __future__ import annotations

import dataclasses
import json

import pytest

from modules.sim import game_api
from modules.sim.game_engine import advance, start_from_league
from modules.sim.game_result import build_result, replay_game
from modules.sim.game_setup import build_league_snapshot, league_settings
from modules.sim.game_state import Emitter, GameState, fold
from modules.sim.game_types import GameSettings, GameSnapshot, RealWeek
from modules.sim.synthetic import round_robin
from tests.test_sim_game_settings import BYES, H, MODEL, ROWS, FakeSleeper, Inputs, imported_league, make_app, real_inputs

SEED = 7
WEEK = 6  # the real league's current week: weeks 1-5 are played


def real_league(*, week=WEEK, results=True, records=True, deadline=0, lineups=True, regular_weeks=14):
    base = imported_league()
    tids = [t.tid for t in base.teams]
    sched = round_robin(tids, regular_weeks)
    teams = []
    for t in base.teams:
        starters = ()
        if lineups:  # a real lineup that fits the game's slots: the two best at each position, by roster order
            pool = list(t.roster)
            pick = {}
            for slot, pos in (("QB", "QB"), ("RB", "RB"), ("RB", "RB"), ("WR", "WR"), ("WR", "WR"), ("TE", "TE"), ("FLEX", "RB"), ("SUPER_FLEX", "QB"), ("K", "K"), ("DEF", "DEF")):
                pid = next((p for p in pool if p not in pick and next(r for r in ROWS if r["pid"] == p)["pos"] == pos), None) if not p_is_def(pos) else next((p for p in pool if p not in pick and p.startswith("DEF-")), None)
                if pid:
                    pick[pid] = slot
            starters = tuple((slot, pid) for pid, slot in pick.items())
        teams.append(dataclasses.replace(t, starters=starters))
    played = []
    for w in range(1, week):
        games = tuple((a, b, 100.0 + w + int(a), 90.0 + w + int(b)) for a, b in sched[w - 1])
        pts = {pid: 5.0 + w for tm in base.teams for pid in tm.roster[:3]}
        played.append(RealWeek(week=w, games=games, points=pts))
    recs = {}
    for t in tids:
        w_ = sum(1 for r in played for a, b, x, y in r.games if (a == t and x > y) or (b == t and y > x))
        recs[t] = (w_, len(played) - w_, 0, 500.0 + int(t), 480.0)
    return dataclasses.replace(
        base, teams=tuple(teams), current_week=week, regular_weeks=regular_weeks, trade_deadline=deadline,
        schedule=tuple(sched), results=tuple(played) if results else (), records=recs if records else {},
    )


def p_is_def(pos):
    return pos == "DEF"


def snap_for(imp, **kw):
    settings = league_settings(imp, difficulty="normal", auto_lineup=False, current=True, **kw)
    return build_league_snapshot(ROWS, BYES, imp, settings, SEED, scoring_model=MODEL)


def run_to_end(snap):
    state = GameState(snap)
    em = Emitter(state, snap)
    start_from_league(em, snap, state, SEED)
    return state, em


def test_default_settings_never_serialize_start_week_and_round_trip():
    s = GameSettings.parse({})
    assert s.start_week == 0 and not s.mid_season and "start_week" not in s.to_dict()
    old = s.to_dict()
    assert GameSettings.from_dict(old).to_dict() == old
    mid = dataclasses.replace(s, start_week=6)
    assert mid.to_dict()["start_week"] == 6 and GameSettings.from_dict(mid.to_dict()).start_week == 6


def test_preseason_import_is_unchanged_by_the_new_fields():
    imp = real_league()
    pre = league_settings(imp, difficulty="normal", auto_lineup=False)  # current not asked for
    assert pre.start_week == 0 and pre.regular_weeks == 14 and pre.trade_deadline_week == 10
    snap = build_league_snapshot(ROWS, BYES, imp, pre, SEED, scoring_model=MODEL)
    assert not snap.mid_start and "mid_start" not in snap.to_dict() and "start_week" not in snap.to_dict()["settings"]
    state, _ = run_to_end(snap)
    assert state.week == 1 and not state.history


def test_preseason_league_game_is_byte_identical_whether_or_not_the_setting_is_asked_for():
    """Data-independent: the same import built twice in this run, once the way it was built before the setting existed
    (no start_point) and once asking for the preseason / a current point the league cannot offer."""
    imp = imported_league()

    def play(**kw):
        snap = build_league_snapshot(ROWS, BYES, imp, league_settings(imp, difficulty="normal", auto_lineup=False, **kw), SEED, scoring_model=MODEL)
        state, em = run_to_end(snap)
        week1 = state.digest()
        while state.status != "complete":
            advance(em, snap, state, SEED)
        return json.dumps(snap.to_dict(), sort_keys=True), week1, state.digest(), em.events

    before = play()
    for kw in ({"current": False}, {"current": True}):  # current=True with no current week read falls back to the preseason
        assert play(**kw) == before
    blob = before[0]
    assert "start_week" not in blob and "mid_start" not in blob
    assert not any(e["type"] in ("league_midseason", "midseason_start") for e in before[3])


def test_mid_season_start_opens_at_the_real_week_with_real_records_lineups_and_results():
    imp = real_league(deadline=12)
    snap = snap_for(imp)
    assert snap.settings.start_week == WEEK and snap.settings.regular_weeks == 14 and snap.settings.trade_deadline_week == 12
    assert snap.schedule[0] == tuple(imp.schedule[0]) and len(snap.schedule) == 14  # the real pairings
    state, em = run_to_end(snap)
    assert (state.status, state.week) == ("in_season", WEEK) and state.boundary_seq == state.seq
    assert [h["week"] for h in state.history] == [1, 2, 3, 4, 5]
    for tid, (w, l, t, pf, pa) in imp.records.items():  # the league's own record, not the sum of the weeks
        assert (state.stand[tid]["w"], state.stand[tid]["l"], state.stand[tid]["pf"]) == (w, l, pf)
    assert all(any(row[1] for row in state.lineups[t.tid]) for t in snap.teams)
    real_user = next(t for t in imp.teams if t.is_user)
    assert {pid for _, pid in real_user.starters} <= {pid for _, pid in state.lineups[real_user.tid] if pid}
    assert set(state.recaps) == {"1", "2", "3", "4", "5"} and state.recaps["5"]["your_game"]["result"] in ("win", "loss", "tie")
    assert state.streak[real_user.tid] and state.points  # streaks and player form carry over
    assert all(len(h) == WEEK - 1 for h in state.points.values())


def test_a_mid_season_game_plays_forward_replays_strictly_and_is_deterministic():
    imp = real_league()
    snap = snap_for(imp)
    snap = GameSnapshot.from_dict(json.loads(json.dumps(snap.to_dict())))  # as the store hands it back
    state, em = run_to_end(snap)
    weeks_played = 0
    while state.status != "complete":
        assert state.week >= WEEK
        advance(em, snap, state, SEED)
        weeks_played += 1
    assert 1 <= weeks_played <= (14 - WEEK + 1) + snap.settings.playoff_weeks and state.week > 14
    assert len(state.history) == 14 + snap.settings.playoff_weeks and state.champion
    assert sorted(len(v) for v in state.points.values()) and max(len(v) for v in state.points.values()) == len(state.history)
    assert fold(snap, em.events).digest() == state.digest()
    assert replay_game(snap, SEED, em.events, strict=True).digest() == state.digest()
    again, em2 = run_to_end(snap)
    while again.status != "complete":
        advance(em2, snap, again, SEED)
    assert again.digest() == state.digest()  # same inputs, same season
    assert build_result(snap, SEED, em.events, state, explain=False)["champion"]["team_id"] == state.champion


def test_missing_played_weeks_keep_the_real_record_and_say_so():
    imp = real_league(results=False)
    snap = snap_for(imp)
    state, _ = run_to_end(snap)
    assert state.week == WEEK and not state.history and any(v["w"] + v["l"] == WEEK - 1 for v in state.stand.values())
    assert sum("schedule_estimated" in n for n in snap.notes) == 0  # the league's own schedule was on hand


def test_no_records_sum_the_played_weeks_and_a_missing_schedule_is_generated():
    imp = dataclasses.replace(real_league(records=False), schedule=())
    snap = snap_for(imp)
    state, _ = run_to_end(snap)
    assert all(v["w"] + v["l"] == WEEK - 1 for v in state.stand.values())
    assert any(n.startswith("schedule_estimated_weeks:") for n in snap.notes) and len(snap.schedule) == 14


def test_lineups_that_do_not_fit_are_auto_set():
    imp = real_league(lineups=False)
    snap = snap_for(imp)
    assert "lineups_auto_set:12" in snap.notes
    state, _ = run_to_end(snap)
    assert all(sum(1 for _, pid in state.lineups[t.tid] if pid) >= 8 for t in snap.teams)


def test_trade_deadline_already_passed_is_noted_and_blocks_trades():
    imp = real_league(deadline=4)
    snap = snap_for(imp)
    assert "trade_deadline_passed" in snap.notes and snap.settings.trade_deadline_week == 4
    state, em = run_to_end(snap)
    advance(em, snap, state, SEED)
    assert not [t for t in state.transactions if t["type"] == "trade"]


def test_no_current_week_falls_back_to_the_preseason_start():
    imp = dataclasses.replace(real_league(), current_week=0, notes=("start_fell_back_to_preseason:offseason",))
    settings = league_settings(imp, difficulty="normal", auto_lineup=False, current=True)
    assert settings.start_week == 0 and settings.regular_weeks == 14
    snap = build_league_snapshot(ROWS, BYES, imp, settings, SEED, scoring_model=MODEL)
    assert "start_fell_back_to_preseason:offseason" in snap.notes
    assert run_to_end(snap)[0].week == 1


# ------------------------------------------------------------- the input door


def current_sleeper(*, status="in_season", leg=6, start=15):
    s = FakeSleeper(league={
        "name": "L", "season": "2026", "status": status,
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "BN", "BN"],
        "scoring_settings": {"rec": 0.5, "pass_td": 4},
        "settings": {"playoff_teams": 4, "leg": leg, "playoff_week_start": start, "trade_deadline": 9},
    })
    for r in s._rosters:
        r["settings"] = {"wins": 3, "losses": 2, "ties": 0, "fpts": 500, "fpts_decimal": 25, "fpts_against": 480}
        r["starters"] = ["0", f"p{r['roster_id']}a"]
    ids = [r["roster_id"] for r in s._rosters]

    def matchups(league_id, week):
        return [{"roster_id": rid, "matchup_id": (i // 2) + 1, "points": 100.0 + i, "players_points": {f"p{rid}a": 12.5, "SF": 0.0}}
                for i, rid in enumerate(ids)]

    s.get_matchups_for_weeks = lambda league_id, weeks: {w: matchups(league_id, w) for w in weeks}
    return s


def test_league_import_current_reads_week_records_schedule_results_and_lineups():
    imp = real_inputs(current_sleeper()).league_import("L1", username="user3", current=True)
    assert (imp.current_week, imp.regular_weeks, imp.trade_deadline) == (6, 14, 9)
    assert len(imp.schedule) == 14 and all(len(w) == 6 for w in imp.schedule)
    assert [r.week for r in imp.results] == [1, 2, 3, 4, 5] and imp.results[0].points["p1a"] == 12.5
    assert imp.records["1"] == (3, 2, 0, 500.25, 480.0)
    assert imp.teams[0].starters == (("RB", "p1a"),)  # "0" (empty) leaves a slot out; the second slot is the first RB
    assert imp.notes.count("records_unavailable") == 0


@pytest.mark.parametrize("kwargs,reason", [
    ({"status": "complete", "leg": 18}, "offseason"), ({"status": "pre_draft", "leg": 0}, "offseason"),
    ({"leg": 16}, "playoffs"), ({"leg": 1}, "season_not_started"),
])
def test_league_import_current_falls_back_to_preseason_outside_the_regular_season(kwargs, reason):
    imp = real_inputs(current_sleeper(**kwargs)).league_import("L1", username="user3", current=True)
    assert imp.current_week == 0 and f"start_fell_back_to_preseason:{reason}" in imp.notes and not imp.results


def test_league_import_without_current_reads_no_season_state():
    sleeper = current_sleeper()
    imp = real_inputs(sleeper).league_import("L1", username="user3")
    assert imp.current_week == 0 and not imp.results and not imp.teams[0].starters and not imp.notes


def test_a_week_sleeper_did_not_return_is_reported_not_invented():
    sleeper = current_sleeper()
    full = sleeper.get_matchups_for_weeks
    sleeper.get_matchups_for_weeks = lambda lid, weeks: {w: ([] if w == 3 else v) for w, v in full(lid, weeks).items()}
    imp = real_inputs(sleeper).league_import("L1", username="user3", current=True)
    assert [r.week for r in imp.results] == [1, 2, 4, 5] and "played_weeks_unavailable:3" in imp.notes
    assert imp.schedule[2] == ()


# ----------------------------------------------------------------------- API


class CurrentInputs(Inputs):
    def league_import(self, league_id, *, username="", roster_id="", dynasty=False, current=False):
        self.import_args = (league_id, username, roster_id)
        self.current = current
        return real_league() if current else self.imported


def test_api_starts_from_the_current_week_and_the_option_is_advertised():
    game_api.clear_pool_cache()
    inputs = CurrentInputs(imported_league())
    client, _ = make_app(inputs)
    assert client.get("/v1/sim/games/options", headers=H).json()["options"]["start_point"] == {"values": ["preseason", "current"], "default": "preseason"}
    res = client.post("/v1/sim/games", json={"start": "league", "league_id": "L1", "start_point": "current"}, headers=H).json()
    assert res["reason"] == "" and inputs.current is True
    g = res["game"]
    assert g["week"] == WEEK and g["status"] == "in_season" and g["settings"]["start_week"] == WEEK
    gid = g["id"]
    adv = client.post(f"/v1/sim/games/{gid}/advance", json={"week": WEEK}, headers=H).json()
    assert adv["recap"]["week"] == WEEK and adv["game"]["week"] == WEEK + 1
    played = client.post(f"/v1/sim/games/{gid}/advance", json={"week": 2}, headers=H)
    assert played.status_code == 200 and played.json()["replayed"] is True  # a week the game replays from its recap
    assert client.post(f"/v1/sim/games/{gid}/advance", json={"week": 9}, headers=H).json().get("reason") != ""
    again = client.get(f"/v1/sim/games/{gid}", headers=H).json()["game"]
    assert again["week"] == WEEK + 1 and again["settings"]["start_week"] == WEEK


def test_api_default_league_start_is_the_preseason_and_never_asks_for_the_current_week():
    game_api.clear_pool_cache()
    inputs = CurrentInputs(imported_league())
    client, _ = make_app(inputs)
    res = client.post("/v1/sim/games", json={"start": "league", "league_id": "L1"}, headers=H).json()
    assert inputs.current is False and res["game"]["week"] == 1 and "start_week" not in res["game"]["settings"]


def test_api_validates_start_point():
    game_api.clear_pool_cache()
    client, _ = make_app(CurrentInputs(imported_league()))
    assert client.post("/v1/sim/games", json={"start": "league", "league_id": "L1", "start_point": "playoffs"}, headers=H).status_code == 422
    assert client.post("/v1/sim/games", json={"start_point": "current"}, headers=H).status_code == 422


def test_free_account_cannot_open_a_game_already_past_the_free_weeks():
    from fastapi import FastAPI, Header
    from fastapi.testclient import TestClient
    from modules.sim import api as sim_api
    from modules.sim.store import InMemoryBackend
    game_api.clear_pool_cache()
    backend = InMemoryBackend()
    app = FastAPI()
    sim_api.mount(app, sim_api.SimApiDeps(
        require_user=lambda authorization=Header(default="free"): {"id": "free", "_access_token": "t"}, is_pro=lambda u: False,
        sleeper_username=lambda u: "turbo", backend_for=lambda u: backend, inputs=CurrentInputs(imported_league())),
        environ={"SIM_ENABLED": "1"})
    res = TestClient(app).post("/v1/sim/games", json={"start": "league", "league_id": "L1", "start_point": "current"}).json()
    assert res["reason"] == "premium_required" and not backend.tables.get("sim_games")
