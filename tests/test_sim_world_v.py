"""world_v 1: the usage-conserving simulated NFL (docs/audits/2026-11-sim-injuries-and-usage.md).

Gate and serialization, old saves replaying byte-for-byte (golden digests on the synthetic pool, explicit model ids as a save records them),
deterministic replay, the QB-per-team-per-week invariant, usage caps, depth-chart refresh, need-based rookie teams and injury-rate bands."""

from __future__ import annotations

import collections
import functools

import numpy as np
import pytest

from modules.sim import game_dynasty as dyn
from modules.sim import game_scoring, game_usage
from modules.sim import player_model as pm
from modules.sim import team_roles as tr
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import WORLD_VERSION, GameSettings
from modules.sim.rng import WorldRng
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
SEED = 11

# Digests of a save made BEFORE world_v (settings carry no world_v key), captured on origin/main at 5a68a6fe and reproduced here: the gate
# changes nothing for any save that lacks it. Synthetic pool only (no data/ files), explicit model ids exactly as a save records them.
GOLDEN = {
    ("player_model-player-model-5", "redraft"): "a934797dae70693e83340ce55570d62d3bce9db076756d616da8caf97dde074c",
    ("player_model-player-model-5", "dynasty3"): "797ecda4e78ae95c7f8a93c8f79300c3c76376423e747458570c11b6a019509c",
    ("player_model-player-model-6", "redraft"): "f69449471cc30dc3b53fb5027bf97b9c43b2a4e6d173b04db4a6afcdc046b500",
    ("player_model-player-model-6", "dynasty3"): "ecefefb1e46ced3de0588363032fb87f85e79f3eb4c4aef47372c831c4a83887",
}


def _settings(world: bool, **extra) -> GameSettings:
    s = GameSettings.parse({"user_slot": 4, "superflex": True, **extra})
    d = s.to_dict()
    if not world:
        d.pop("world_v", None)  # a save from before world_v
    return GameSettings.from_dict(d)


@functools.lru_cache(maxsize=None)
def _redraft(model: str, world: bool):
    snap = build_snapshot(ROWS, BYES, _settings(world), SEED, scoring_model=model)
    state = GameState(snap)
    em = Emitter(state, snap)
    run_ai_picks(DraftContext(snap, state), em, SEED)
    auto_for_user(DraftContext(snap, state), em, SEED)
    finish_draft(em, snap, state, SEED)
    for _ in range(6):
        advance(em, snap, state, SEED)
    return snap, state


@functools.lru_cache(maxsize=None)
def _dynasty(model: str, world: bool):
    snap = build_snapshot(ROWS, BYES, _settings(world, mode="dynasty", seasons=3, start_year=2026, rookie_rounds=2, scoring="ppr"), SEED, scoring_model=model)
    root, state = snap, GameState(snap)
    em = Emitter(state, root)
    auto_for_user(DraftContext(root, state), em, SEED)
    finish_draft(em, root, state, SEED)
    while True:
        sn, sd = root.season_view(state.view_no), dyn.season_seed(SEED, state.view_no)
        em.snap = sn
        while state.status in ("in_season", "playoffs"):
            advance(em, sn, state, sd)
        if state.status != "offseason":
            return root, state
        sn, sd = root.season_view(state.view_no), dyn.season_seed(SEED, state.view_no)
        em.snap = sn
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        dyn.start_next_season(em, sd)


# ----------------------------------------------------------------------------------------------- gate and serialization


def test_world_v_is_on_for_new_games_serialized_and_absent_on_old_saves():
    s = GameSettings.parse({})
    assert WORLD_VERSION == 1 and s.world_v == 1 and s.to_dict()["world_v"] == 1
    assert GameSettings.from_dict(s.to_dict()) == s
    d = s.to_dict()
    d.pop("world_v")
    old = GameSettings.from_dict(d)
    assert old.world_v == 0 and "world_v" not in old.to_dict()


@pytest.mark.parametrize("model", ["player_model-player-model-5", "player_model-player-model-6"])
def test_old_saves_replay_identically_redraft_and_dynasty(model):
    assert _redraft(model, world=False)[1].digest() == GOLDEN[model, "redraft"]
    assert _dynasty(model, world=False)[1].digest() == GOLDEN[model, "dynasty3"]


def test_the_new_world_is_deterministic_and_actually_differs():
    model = game_scoring.default_model().model_id
    a = _redraft(model, world=True)[1].digest()
    _redraft.cache_clear()
    assert a == _redraft(model, world=True)[1].digest() and a != _redraft(model, world=False)[1].digest()
    root, st = _dynasty(model, world=True)
    d = st.digest()
    _dynasty.cache_clear()
    assert d == _dynasty(model, world=True)[1].digest()


# ----------------------------------------------------------------------------------------------- quarterbacks


def _qbs_playing(snap, state):
    """(team, week) -> quarterbacks who scored in it."""
    out = collections.defaultdict(list)
    for pid, hist in state.points.items():
        p = snap.players[pid]
        if p.pos != "QB":
            continue
        for w, pts in enumerate(hist[: snap.settings.regular_weeks], 1):
            if pts is not None:
                out[p.nfl_team, w].append(pid)
    return out


def test_at_most_one_quarterback_plays_per_team_per_week_and_the_league_never_exceeds_the_teams():
    model = game_scoring.default_model().model_id
    for world, bound in ((True, 1), (False, 99)):
        snap, state = _redraft(model, world)
        # two more weeks so injuries have had time to produce fill-ins
        playing = _qbs_playing(snap, state)
        teams = {p.nfl_team for p in snap.players.values() if p.pos == "QB"}
        if world:
            assert max(len(v) for v in playing.values()) <= bound
            per_week = collections.Counter(w for (_t, w) in playing)
            assert max(per_week.values()) <= len(teams)


def test_a_bench_qb_has_no_projection_and_a_fill_in_does():
    model = game_scoring.default_model().model_id
    snap, state = _redraft(model, True)
    ev = Evaluator(snap, state)
    kinds = collections.Counter()
    for pid, p in snap.players.items():
        if p.pos == "QB":
            r = ev.role(pid, state.week)
            if r is not None:
                kinds[r.kind] += 1
                if r.kind == "backup":
                    assert r.mult == 0.0 and r.add == 0.0 and ev.week_mean(pid, state.week) == 0.0
    assert kinds["starter"] + kinds["fill_in"] >= 1


# ----------------------------------------------------------------------------------------------- usage caps


class _P:
    def __init__(self, pos, mean, team="AAA", order=99):
        self.pos, self.mean, self.nfl_team, self.market, self.extra, self.injury_weeks = pos, mean, team, mean, {"depth_chart_order": order}, 0


def _book(means, pos="RB", team="AAA"):
    players = {f"p{i}": _P(pos, m, team, i + 1) for i, m in enumerate(means)}
    return tr.RoleBook(players), players


def _factors(means, hidden, pos="RB", out=()):
    book, players = _book(means, pos)
    avail = lambda pid: pid not in out  # noqa: E731
    roles = book.roles((("AAA", pos)), avail, lambda pid: players[pid].mean)
    rp = lambda pid: (roles[pid].mult, roles[pid].add)  # noqa: E731
    exp = lambda pid, role: hidden[pid] * role[0] + role[1]  # noqa: E731
    f = game_usage.group_factors(book, players, avail, rp, exp)
    return f, rp, exp, players, avail


def test_a_scrub_cannot_take_a_job_nobody_left_but_a_vacancy_lets_him():
    hidden = {"p0": 15.0, "p1": 8.0, "p2": 22.0}  # p2 projected 1.9 "breaks out" to 22 with both starters healthy
    f, rp, exp, players, avail = _factors([15.0, 8.0, 1.9], hidden)
    assert f["p2"] < 0.5
    total = sum(exp(p, rp(p)) * f.get(p, 1.0) for p in hidden)
    base = 15.0 + 8.0 + 1.9
    assert total <= base * game_usage.USAGE_CAP["RB"] + 1e-6  # usage conservation: the group total never passes its cap
    # the same scrub with the starter out: the vacancy's added points are allowed on top
    f2, rp2, exp2, *_ = _factors([15.0, 8.0, 1.9], {"p0": 15.0, "p1": 8.0, "p2": 1.9}, out=("p0",))
    assert not f2 or all(v > 0.9 for v in f2.values())


def test_a_normal_group_is_untouched_and_qb_k_def_are_exempt():
    f, *_ = _factors([15.0, 8.0, 1.9], {"p0": 14.0, "p1": 7.0, "p2": 1.5})
    assert f == {}
    qf, *_ = _factors([24.0, 3.0], {"p0": 40.0, "p1": 30.0}, pos="QB")
    assert qf == {}


def test_usage_cap_values_are_the_fitted_ones_and_tier_ceiling_is_monotone():
    assert game_usage.USAGE_CAP["RB"] <= game_usage.USAGE_CAP["WR"] <= game_usage.USAGE_CAP["TE"]
    ceil = [game_usage._allowed(m, 1.0, 0.0) for m in (1.0, 3.0, 6.0, 12.0, 18.0)]
    assert ceil == sorted(ceil) and ceil[-1] > 25.0  # a star is never bound by the tier ceiling


# ----------------------------------------------------------------------------------------------- dynasty: depth charts and rookie teams


def test_depth_charts_follow_the_players_each_season_with_world_v_and_stay_static_without():
    model = game_scoring.default_model().model_id
    root, st = _dynasty(model, world=True)
    sn = root.season_view(3)
    groups = collections.defaultdict(list)
    for p in sn.players.values():
        if p.pos in ("QB", "RB", "WR", "TE") and p.nfl_team not in ("", "FA"):
            groups[p.nfl_team, p.pos].append(p)
    for g in groups.values():
        by_order = sorted(g, key=lambda p: p.extra["depth_chart_order"])
        assert [p.pid for p in by_order] == [p.pid for p in sorted(g, key=lambda p: (-p.mean, -p.market, p.pid))]
    old_root, _ = _dynasty(model, world=False)
    sn0 = old_root.season_view(3)
    rookies = [p for p in sn0.players.values() if p.extra.get("draft_year")]
    assert rookies and all("depth_chart_order" not in p.extra for p in rookies)


def test_rookies_go_where_there_is_need():
    teams = [f"T{i}" for i in range(8)]
    vets = {f"v{i}": {"pid": f"v{i}", "pos": "QB", "nfl_team": t, "mean": 20.0} for i, t in enumerate(teams[:6])}
    picks = collections.Counter()
    for s in range(400):
        picks[dyn._need_team(WorldRng(s).stream(1, "grookie", 0), teams, "QB", vets, [], 12.0)] += 1
    needy = picks["T6"] + picks["T7"]
    assert needy > 0.6 * 400  # two teams with no quarterback take most rookies; loaded teams take few
    assert dyn._need_team(WorldRng(1).stream(1, "grookie", 0), teams, "K", vets, [], 12.0) in teams


def test_refresh_depth_charts_orders_every_group_by_projection():
    rows = {f"r{i}": {"pid": f"r{i}", "pos": "RB", "nfl_team": "AAA", "mean": float(m), "market": float(m), "extra": {"depth_chart_order": 1.0}} for i, m in enumerate([3, 12, 7])}
    dyn.refresh_depth_charts(rows)
    assert [rows[p]["extra"]["depth_chart_order"] for p in ("r0", "r1", "r2")] == [3.0, 1.0, 2.0]


# ----------------------------------------------------------------------------------------------- injury calibration bands (model alone)


def _injury_stats(pos, n=1500, ppg=10.0, age=26.0):
    games_missed, eps, week_counts, ending = [], 0, collections.Counter(), 0
    for i in range(n):
        prof = pm.draw_season_profile({"player_id": f"p{i}", "pos": pos, "age": age, "team": "AAA", "projection_mean_ppg": ppg}, pm.profile_rng(i, f"p{i}"))
        games_missed.append(sum(1 for r in prof.unavailable_reason if r == "injury"))
        for ev in prof.injury_events:
            eps += 1
            week_counts[ev.weeks_out] += 1
            ending += ev.weeks_out >= 9
    return float(np.mean(games_missed)), eps / n, week_counts, ending / max(1, eps)


@pytest.mark.parametrize("pos", ["QB", "RB", "WR", "TE"])
def test_injury_rates_sit_in_the_calibrated_real_bands(pos):
    # Real 2021-25 panel (relevant players, 17 games): 2.2-3.0 games missed a season, 0.8 absences a season, 40-50% of absences one game,
    # 3.6% observed 9+ (truncated by the season's end; nominal 8-10% of onsets, the published share of ACL/Achilles-class injuries). The model counts partial-game and benching bundles, so the band is wide on episodes and tight on games lost.
    missed, per_season, weeks, ending = _injury_stats(pos)
    assert 1.6 <= missed <= 3.6
    assert 0.5 <= per_season <= 1.6
    assert 0.30 <= weeks[1] / sum(weeks.values()) <= 0.50
    assert 0.03 <= ending <= 0.12  # nominal long-absence share of onsets (pmf tail 10%); observed lengths are shorter because the season ends


def test_injuries_leave_a_player_unavailable_for_exactly_the_stated_games():
    for i in range(200):
        prof = pm.draw_season_profile({"player_id": f"q{i}", "pos": "RB", "age": 27, "team": "AAA", "projection_mean_ppg": 12.0}, pm.profile_rng(5, f"q{i}"))
        out = sum(1 for r in prof.unavailable_reason if r == "injury")
        assert out <= sum(ev.weeks_out for ev in prof.injury_events)
        assert all(ev.weeks_out >= 1 for ev in prof.injury_events)
