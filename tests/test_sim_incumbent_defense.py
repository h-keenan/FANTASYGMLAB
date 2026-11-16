"""incumbent_v 1 (starters keep their jobs, depth changes are logged) and defense_v 1 (opponent defenses scale a player's week and projection).

Product report: a QB went from QB2 (18 ppg) to QB41 (backup) in one offseason because every depth chart was re-sorted purely by projection; and the sim
had no opponent modeling at all."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from modules.sim import depth_incumbency as inc
from modules.sim import game_dynasty as dyn
from modules.sim import game_scoring, matchups
from modules.sim.game_draft import DraftContext, auto_for_user
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
MODEL = game_scoring.default_model().model_id


# ------------------------------------------------------------------------------------------ incumbent depth charts (unit)


class _P:
    def __init__(self, pid, pos, team, mean, order, age=27.0):
        self.pid, self.pos, self.nfl_team, self.mean, self.market, self.age = pid, pos, team, mean, mean, age
        self.extra = {"depth_chart_order": float(order)}
        self.injury_weeks = 0


def _row(pid, pos, team, mean, age=27.0):
    return {"pid": pid, "pos": pos, "nfl_team": team, "mean": float(mean), "market": float(mean), "age": age, "extra": {}}


def _qb_room(challenger_mean, last_ppg, inc_age=28.0, inc_mean=15.0):
    prev = {"inc": _P("inc", "QB", "AAA", 16.0, 1), "bak": _P("bak", "QB", "AAA", 9.0, 2)}
    # other teams give the position a starter line of 16 ppg
    for i in range(6):
        prev[f"x{i}"] = _P(f"x{i}", "QB", f"T{i}", 16.0, 1)
    rows = {"inc": _row("inc", "QB", "AAA", inc_mean, inc_age), "ch": _row("ch", "QB", "AAA", challenger_mean)}
    ppg = {"inc": last_ppg, "bak": 9.0, **{f"x{i}": 16.0 for i in range(6)}}
    log = inc.refresh(rows, prev, ppg)
    return rows, log


def test_a_strong_incumbent_survives_a_small_projection_gap():
    rows, log = _qb_room(challenger_mean=16.5, last_ppg=20.0)  # challenger 10 percent better, QB margin is 45 percent
    assert rows["inc"]["extra"]["depth_chart_order"] == 1.0 and rows["ch"]["extra"]["depth_chart_order"] == 2.0
    assert log == []


def test_a_clearly_better_challenger_takes_the_job_and_it_is_logged():
    rows, log = _qb_room(challenger_mean=26.0, last_ppg=20.0)
    assert rows["ch"]["extra"]["depth_chart_order"] == 1.0
    (c,) = log
    assert (c["nfl_team"], c["pos"], c["slot"], c["pid"], c["replaced_pid"]) == ("AAA", "QB", 1, "ch", "inc")
    assert c["reason"] == "outperformed_incumbent" and c["gap"] > c["needed"] > 1.0 and c["incumbent_season"] == "strong"


def test_a_bust_season_protects_weakly():
    strong, _ = _qb_room(challenger_mean=18.5, last_ppg=20.0)
    bust, log = _qb_room(challenger_mean=18.5, last_ppg=9.0)  # last year at 0.56 of the line
    assert strong["inc"]["extra"]["depth_chart_order"] == 1.0
    assert bust["ch"]["extra"]["depth_chart_order"] == 1.0 and log[0]["incumbent_season"] == "down"


def test_an_old_incumbent_loses_his_protection():
    young, _ = _qb_room(challenger_mean=18.5, last_ppg=17.0, inc_age=30.0)
    old, log = _qb_room(challenger_mean=18.5, last_ppg=17.0, inc_age=43.0)
    assert young["inc"]["extra"]["depth_chart_order"] == 1.0
    assert old["ch"]["extra"]["depth_chart_order"] == 1.0 and log[0]["reason"] == "incumbent_aged"


def test_a_retired_incumbent_is_replaced_and_says_so():
    prev = {"inc": _P("inc", "QB", "AAA", 16.0, 1), "bak": _P("bak", "QB", "AAA", 9.0, 2)}
    rows = {"bak": _row("bak", "QB", "AAA", 10.0)}
    log = inc.refresh(rows, prev, {"inc": 16.0, "bak": 9.0})
    assert rows["bak"]["extra"]["depth_chart_order"] == 1.0
    assert log == [{"nfl_team": "AAA", "pos": "QB", "slot": 1, "pid": "bak", "replaced_pid": "inc", "reason": "incumbent_retired", "gap": None, "needed": None}]


def test_a_high_pick_needs_a_smaller_edge_than_a_late_pick():
    def room(rookie_pid):
        prev = {"inc": _P("inc", "QB", "AAA", 16.0, 1), **{f"x{i}": _P(f"x{i}", "QB", f"T{i}", 16.0, 1) for i in range(6)}}
        rows = {"inc": _row("inc", "QB", "AAA", 16.0), rookie_pid: _row(rookie_pid, "QB", "AAA", 21.0, 21.0)}
        inc.refresh(rows, prev, {"inc": 16.0, **{f"x{i}": 16.0 for i in range(6)}})
        return rows[rookie_pid]["extra"]["depth_chart_order"]

    assert room("R2026-001") == 1.0  # the first pick, 31 percent better: inside the 45 percent QB margin only with the draft-capital edge
    assert room("R2026-040") == 2.0  # a slot-40 rookie with the same projection waits


def test_rookie_and_older_chart_sorts_are_identical_without_incumbents():
    """No incumbency history (a team with no previous chart): the sticky sort is the plain projection sort."""

    rows = {f"r{i}": _row(f"r{i}", "RB", "AAA", m) for i, m in enumerate([3, 12, 7])}
    inc.refresh(rows, {}, {})
    assert [rows[p]["extra"]["depth_chart_order"] for p in ("r0", "r1", "r2")] == [3.0, 1.0, 2.0]


# ------------------------------------------------------------------------------------------ matchups (unit)

TEAMS = tuple(f"T{i:02d}" for i in range(32))


def test_matchups_are_deterministic_and_public():
    a = matchups.strengths(5, TEAMS, 3)
    assert a == matchups.strengths(5, TEAMS, 3)
    assert a != matchups.strengths(6, TEAMS, 3)
    m = matchups.Matchups(5, 2, TEAMS, {"T00": 6})
    assert m.opponent("T01", 3) == m.opponent("T01", 3)
    assert m.opponent("T00", 6) is None  # on a bye
    opp = m.opponent("T05", 4)
    assert opp is not None and m.opponent(opp, 4) == "T05"
    assert [m.opponent("T05", w) for w in range(1, 15)] != [opp] * 14  # not the same opponent every week


@pytest.mark.parametrize("pos,lo,hi", [("QB", 0.07, 0.16), ("RB", 0.08, 0.18), ("WR", 0.09, 0.20), ("TE", 0.10, 0.22)])
def test_best_to_worst_defense_spread_is_about_ten_to_fifteen_percent(pos, lo, hi):
    spreads = []
    for seed in range(1, 13):
        v = sorted(math.exp(matchups.strengths(seed, TEAMS, 4)[t][pos]) for t in TEAMS)
        spreads.append(v[-1] / v[0] - 1.0)
    mean = sum(spreads) / len(spreads)
    assert lo <= mean <= hi, (pos, mean)


def test_defense_strength_regresses_but_persists_season_to_season():
    xs = [matchups.strengths(9, TEAMS, 3)[t]["WR"] for t in TEAMS]
    ys = [matchups.strengths(9, TEAMS, 4)[t]["WR"] for t in TEAMS]
    mx, my = sum(xs) / 32, sum(ys) / 32
    corr = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    assert 0.1 < corr < 0.9
    assert xs != ys


def test_kickers_and_defenses_have_no_matchup():
    assert matchups.Matchups(5, 1, TEAMS, {}).factor("T01", "K", 2) == 1.0
    assert matchups.Matchups(5, 1, TEAMS, {}).factor("T01", "DEF", 2) == 1.0


# ------------------------------------------------------------------------------------------ engine (integration)


def _game(seed=31, **flags):
    d = GameSettings.parse({"mode": "dynasty", "teams": 8, "user_slot": 3, "start_year": 2026, "seasons": 3, "rookie_rounds": 3}).to_dict()
    for k in ("incumbent_v", "defense_v"):
        d.pop(k, None)
    d.update({k: v for k, v in flags.items() if v})
    snap = build_snapshot(ROWS, BYES, GameSettings.from_dict(d), seed, scoring_model=MODEL)
    state = GameState(snap)
    em = Emitter(state, snap)
    auto_for_user(DraftContext(snap, state), em, seed)
    finish_draft(em, snap, state, seed)
    return snap, state, em, seed


def test_new_games_carry_both_flags_and_old_ones_do_not():
    d = GameSettings.parse({"mode": "dynasty"}).to_dict()
    assert d["incumbent_v"] == 1 and d["defense_v"] == 1
    old = GameSettings.from_dict({k: v for k, v in d.items() if k not in ("incumbent_v", "defense_v")})
    assert old.incumbent_v == 0 and old.defense_v == 0
    assert "incumbent_v" not in old.to_dict() and "defense_v" not in old.to_dict()


def test_projections_follow_the_opponent_defense():
    snap0, state0, _, _ = _game()
    snap1, state1, _, _ = _game(defense_v=1)
    ev0, ev1 = Evaluator(snap0, state0), Evaluator(snap1, state1)
    mu = matchups.for_snapshot(snap1, state1.view_no)
    seen = set()
    for pid, p in snap1.players.items():
        if p.pos not in ("QB", "RB", "WR", "TE") or snap1.bye_of(pid) == 1:
            continue
        base, with_m = ev0.week_mean(pid, 1), ev1.week_mean(pid, 1)
        if base < 3.0:
            continue
        f = mu.factor(p.nfl_team, p.pos, 1)
        assert with_m == pytest.approx(base * f, rel=0.02)
        seen.add(f > 1.0)
    assert seen == {True, False}  # some soft, some tough matchups in the same week


def test_the_matchup_reaches_the_scored_week_and_the_shown_role():
    snap, state, em, seed = _game(defense_v=1)
    ev = Evaluator(snap, state)
    pid = max((p for p in snap.players if snap.players[p].pos == "WR" and snap.bye_of(p) != 1), key=lambda p: snap.players[p].mean)
    scale, add = ev.role_param(pid, 1)
    plain_scale, plain_add = ev.role_param(pid, 1, matchup=False)
    assert scale == pytest.approx(plain_scale * ev.matchup(pid, 1)) and add == pytest.approx(plain_add * ev.matchup(pid, 1))
    info = ev.role_info(pid, 1)
    assert info and info["matchup"]["opponent"] and info["matchup"]["factor"] == pytest.approx(ev.matchup(pid, 1), abs=1e-3)
    advance(em, snap, state, seed)
    assert state.history  # a week was played with the matchups on


def test_defense_off_changes_nothing():
    snap, state, _, _ = _game()
    ev = Evaluator(snap, state)
    assert ev.matchup(next(iter(snap.players)), 1) == 1.0
    wr = next(p for p in snap.players if snap.players[p].pos == "WR")
    assert "matchup" not in (ev.role_info(wr, 1) or {})


def _season_cycle(snap_of, em, state, seed):
    from modules.sim.game_eval import USER_PARAMS
    from modules.sim.game_actions import cut_player

    def play():
        while state.status in ("in_season", "playoffs"):
            snap = snap_of()
            em.snap = snap
            advance(em, snap, state, dyn.season_seed(seed, state.view_no))

    play()
    snap = snap_of()
    em.snap = snap
    sd = dyn.season_seed(seed, state.view_no)
    dyn.start_rookie_draft(em)
    dyn.run_ai_rookie_picks(em, sd)
    dyn.auto_rookie_draft(em, sd)
    user = snap.user_team.tid
    while len(state.rosters[user]) > snap.settings.roster_limit:
        ev = Evaluator(snap, state)
        cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
    dyn.start_next_season(em, sd)


def test_depth_chart_events_are_logged_with_a_clean_shape_and_only_when_on():
    changes_on = 0
    for flags in ({"incumbent_v": 1}, {}):
        snap, state, em, seed = _game(**flags)
        _season_cycle(lambda: snap.season_view(state.view_no), em, state, seed)
        events = [e for e in em.events if e["type"] == "depth_chart"]
        if not flags:
            assert events == []
            continue
        assert any(e["payload"]["phase"] == "offseason" for e in events)
        for e in events:
            p = e["payload"]
            assert set(p) == {"season_no", "year", "phase", "changes"} and p["phase"] in ("offseason", "in_season")
            for c in p["changes"]:
                assert {"nfl_team", "pos", "slot", "pid", "replaced_pid", "reason"} <= set(c)
                assert c["pos"] in ("QB", "RB", "WR", "TE") and c["slot"] >= 1
                assert c["reason"] in {
                    "outperformed_incumbent", "rookie_won_job", "incumbent_aged", "incumbent_retired", "incumbent_left", "filled_open_slot",
                    "injury", "returned_from_injury",
                }
                changes_on += 1
    assert changes_on > 0


def test_a_starter_who_gets_hurt_is_replaced_and_gets_the_job_back():
    snap, state, em, seed = _game(incumbent_v=1)
    for _ in range(snap.settings.regular_weeks):
        if state.status not in ("in_season", "playoffs"):
            break
        advance(em, snap, state, seed)
    reasons = [c["reason"] for e in em.events if e["type"] == "depth_chart" for c in e["payload"]["changes"]]
    assert "injury" in reasons
    hurt = [c for e in em.events if e["type"] == "depth_chart" for c in e["payload"]["changes"] if c["reason"] == "injury"]
    back = [c for e in em.events if e["type"] == "depth_chart" for c in e["payload"]["changes"] if c["reason"] == "returned_from_injury"]
    assert hurt and all(c["pid"] != c["replaced_pid"] and c["weeks"] >= 1 for c in hurt)
    assert back  # a long enough season sees starters return
    assert any(h["replaced_pid"] == c["pid"] for c in back for h in hurt)  # a returning starter is one the log saw go down
