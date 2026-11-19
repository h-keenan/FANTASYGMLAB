"""wrapped_v 1: the data Season Wrapped / the Draft & Watch report read.

Records only: a wrapped_v 1 game plays out exactly like a wrapped_v 0 game (same scores, standings, champion).
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from modules.sim import game_wrapped_data as wd
from modules.sim.game_state import GameState
from modules.sim.game_types import WRAPPED_VERSION, GameSettings


def _with_flag(v):
    def run(seed=5):
        from tests import test_sim_game_engine as eng

        snap0 = eng.make_snapshot(seed, user_slot=4)
        snap = dataclasses.replace(snap0, settings=dataclasses.replace(snap0.settings, wrapped_v=v))
        return snap

    return run


def _play(v, seed=5):
    from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
    from modules.sim.game_engine import advance, finish_draft
    from modules.sim.game_state import Emitter

    snap = _with_flag(v)(seed)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    while state.status != "complete":
        advance(em, snap, state, seed)
    return snap, state, em


@pytest.fixture(scope="module")
def on():
    return _play(1)


@pytest.fixture(scope="module")
def off():
    return _play(0)


def test_flag_roundtrips_and_defaults_off():
    assert GameSettings.parse({"user_slot": 4}).wrapped_v == WRAPPED_VERSION
    raw = GameSettings.parse({"user_slot": 4}).to_dict()
    assert raw["wrapped_v"] == WRAPPED_VERSION
    old = {k: v for k, v in raw.items() if k != "wrapped_v"}
    assert GameSettings.from_dict(old).wrapped_v == 0


def test_flag_changes_no_outcome(on, off):
    s1, st1, _ = on
    s0, st0, _ = off
    assert st1.stand == st0.stand
    assert st1.champion == st0.champion
    assert st1.points == st0.points
    assert st1.history == st0.history


def test_old_game_stores_nothing_extra(off):
    _, st0, _ = off
    assert st0.proj_hist == {}
    assert "proj_hist" not in st0.to_dict() or st0.to_dict()["proj_hist"] == {}
    assert st0.digest()
    assert all("bench_pts" not in (rc.get("your_game") or {}) for rc in st0.recaps.values())


def test_projection_history_recorded(on):
    snap, st, _ = on
    assert st.proj_hist
    weeks = {w for h in st.proj_hist.values() for w in h}
    assert weeks == {str(i) for i in range(1, snap.settings.regular_weeks + 1)}
    json.dumps(st.proj_hist, allow_nan=False)


def test_bench_points_and_expected_wins(on):
    snap, st, _ = on
    user = snap.user_team.tid
    b = wd.bench_points(st)
    assert b["complete"] and b["total"] >= 0
    assert len(b["weeks"]) == snap.settings.regular_weeks
    lk = wd.luck(st, user)
    assert 0 <= lk["expected_wins"] <= lk["games"]
    assert lk["diff"] == pytest.approx(lk["actual_wins"] - lk["expected_wins"], abs=0.02)
    # all-play over a league sums to half the games: league-wide expected wins equal league-wide games / 2
    total = sum(wd.expected_wins(st, t.tid) for t in snap.teams)
    assert total == pytest.approx(len(snap.teams) * lk["games"] / 2, abs=0.5)


def test_season_data_shape_and_reason_tags(on):
    snap, st, _ = on
    data = wd.season_data(snap, st)
    json.dumps(data, allow_nan=False)
    assert data["wrapped_v"] == 1 and data["rank_journey"] and data["players"]
    bw = data["best_worst_week"]
    assert bw["best"]["pts"] >= bw["worst"]["pts"]
    assert data["mvp"]["over_proj"] >= data["bust"]["over_proj"]
    for p in data["players"]:
        assert set(p["tag"]) == {"tag", "text", "games_missed", "injury"}


def test_reason_tag_rules():
    snap, st, _ = _play(1, 6)
    pid = next(iter(snap.pids))
    st.news = [{"week": 3, "pid": pid, "weeks": 5, "kind": "hamstring"}]
    t = wd.reason_tag(snap, st, pid, games=8, proj=100.0, pts=60.0)
    assert t["tag"] == wd.TAG_INJURY and t["text"] == "Missed 5 games: hamstring"
    st.news = []
    st.role_hist = {pid: {"1": [1.0, 0.0], "2": [1.0, 0.0], "3": [0.9, 0.0], "4": [0.5, 0.0], "5": [0.4, 0.0], "6": [0.4, 0.0]}}
    assert wd.reason_tag(snap, st, pid, games=6, proj=60.0, pts=40.0)["tag"] == wd.TAG_LOST_JOB
    st.role_hist = {}
    assert wd.reason_tag(snap, st, pid, games=8, proj=60.0, pts=110.0)["tag"] == wd.TAG_BREAKOUT
    assert wd.reason_tag(snap, st, pid, games=8, proj=60.0, pts=50.0)["tag"] == wd.TAG_MISS
    assert wd.reason_tag(snap, st, pid, games=8, proj=60.0, pts=62.0)["tag"] is None


def test_old_save_fallback_is_flagged_incomplete(off):
    snap, st, _ = off
    assert wd.bench_points(st)["complete"] is False
    assert wd.season_data(snap, st)["players"]
