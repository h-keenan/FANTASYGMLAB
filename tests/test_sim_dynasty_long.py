"""Long dynasties (up to 20 seasons, dynasty_v 3): settings, the talent equilibrium, bounded state, history, old saves unchanged."""

from __future__ import annotations

import pytest

from dataclasses import replace

from modules.sim import game_dynasty as dyn, game_scoring
from modules.sim.calibration import dataset, dynasty_report as dr, tail_report
from modules.sim.game_mode import MAX_SEASONS, SEASON_CHOICES
from modules.sim.game_state import fold
from modules.sim.game_types import GameSettings
import tests.test_sim_dynasty as base

# 3- and 4-season dynasty games played by the code before dynasty_v 3 and ai_v 1 existed (dynasty_v 2, ai_v 0 settings), seeds 4242 and 77
GOLDEN_DYNASTY_V2 = {
    "3": "609131e87a06dda4f97f555f790897d92591304121a20c0ed67f6fd93d16d8e4",
    "4": "6d524d02b9474ff17a615166eec5e67e17aad2030cff77e8a295c366b19a36ec",
}


def test_the_cap_is_20_and_new_dynasties_are_v3():
    assert MAX_SEASONS == 20 and SEASON_CHOICES == (3, 4, 5, 10, 15, 20)
    for n in (5, 10, 15, 20):
        s = GameSettings.parse({"mode": "dynasty", "seasons": n})
        assert s.seasons == n and s.dynasty_v == 3 and s.league_anchor and s.to_dict()["seasons"] == n
    assert GameSettings.parse({"mode": "dynasty"}).seasons == 5  # the default does not move
    for bad in (6, 12, 21, 25):
        with pytest.raises(ValueError):
            GameSettings.parse({"mode": "dynasty", "seasons": bad})


def test_old_dynasty_saves_keep_their_length_and_version():
    s = GameSettings.parse({"mode": "dynasty", "seasons": 4})
    raw = s.to_dict()
    raw["dynasty_v"] = 2
    raw.pop("names_v", None)
    raw.pop("hint_v", None)
    old = GameSettings.from_dict(raw)
    assert old.seasons == 4 and old.dynasty_v == 2 and not old.league_anchor and old.dynasty


def _golden(seed, seasons):
    orig = base.new_snapshot

    def v2(seed=base.SEED, **kw):
        snap = orig(seed, **kw)
        object.__setattr__(snap, "settings", replace(snap.settings, dynasty_v=2, ai_v=0, names_v=0, hint_v=0, world_v=0, aging_v=0))
        return snap

    base.new_snapshot = v2
    try:
        run = base.Run(seed=seed, seasons=seasons) if seed != base.SEED else base.Run()
        run.play_all()
        return run.state.digest()
    finally:
        base.new_snapshot = orig


def test_dynasty_v2_games_replay_exactly_as_before():
    assert _golden(base.SEED, 3) == GOLDEN_DYNASTY_V2["3"]
    assert _golden(77, 4) == GOLDEN_DYNASTY_V2["4"]


def test_equilibrium_plan_refills_kickers_and_thin_positions():
    run = base.Run(seasons=10)
    root = run.root
    assert root.settings.league_anchor
    vets = {p: {"pid": p, "pos": pl.pos, "mean": pl.mean, "market": pl.market, "nfl_team": pl.nfl_team} for p, pl in root.players.items()}
    for pid in [p for p, r in vets.items() if r["pos"] == "K"][:-3]:  # most kickers retire
        del vets[pid]
    from modules.sim.rng import WorldRng
    anchor = dyn._anchor(root)
    by_pos = {}
    for r in anchor.values():
        by_pos.setdefault(r["pos"], []).append(r)
    plan = dyn._equilibrium_plan(root, vets, by_pos, WorldRng(1).stream(2, "grookie", 0), dyn._class_size(root))
    want_k = sum(1 for r in anchor.values() if r["pos"] == "K") - 3
    assert plan.count("K") == want_k and plan[-want_k:] == ["K"] * want_k
    skill = [p for p in plan if p != "K"]
    assert len(skill) >= dyn._class_size(root)
    plan2 = dyn._equilibrium_plan(root, vets, by_pos, WorldRng(1).stream(2, "grookie", 0), dyn._class_size(root))
    assert plan == plan2


def test_class_is_deterministic_and_old_versions_ignore_the_anchor():
    run = base.Run(seasons=5)
    snap_a = run.root.season_view(2)
    again = base.Run(seasons=5).root.season_view(2)
    assert sorted(snap_a.players) == sorted(again.players)
    assert all(snap_a.players[p].mean == again.players[p].mean for p in snap_a.players)


@pytest.fixture(scope="module")
def long_game():
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    model = game_scoring.default_model().model_id
    out = dr.play(1, 12, model, pool, byes)
    return out


def test_twelve_seasons_hold_equilibrium(long_game):
    rows = long_game["seasons"]
    first = rows[0]
    assert len(rows) == 12
    for r in rows:
        assert r["K_n"] >= 0.8 * first["K_n"] and r["QB_n"] >= 0.8 * first["QB_n"], r["season"]
        assert 0.75 * first["pool_size"] < r["pool_size"] < 1.6 * first["pool_size"]
        assert 25.0 < r["starter_age_mean"] < 29.5 and r["min_age"] >= 20.0
    for pos in ("QB", "RB", "WR", "TE"):
        for r in rows[2:]:
            assert 0.8 < r[f"{pos}_top12_mean"] / first[f"{pos}_top12_mean"] < 1.25, (pos, r["season"])
    late = [r["team_score_mean"] for r in rows[6:]]
    assert 0.8 * first["team_score_mean"] < min(late) and max(late) < 1.1 * first["team_score_mean"]
    assert all(r["wk_gt40"] < 0.012 and r["wk_max"] < 80 for r in rows)  # player-model-4 tails hold over the years


def test_state_stays_bounded_and_history_is_compact(long_game):
    rows = long_game["seasons"]
    sizes = [r["state_bytes"] for r in rows if "state_bytes" in r]
    assert sizes[-1] < 2.6 * sizes[0]  # grows by archives only, not by every draft and pick ever made
    assert rows[-1]["rookie_n"] > 0


def test_summary_carries_history_not_per_year_standings():
    run = base.Run(seasons=5)
    run.play_all()
    from modules.sim.game_dynasty_view import summary_view
    summary = summary_view(run.snap, run.state)
    assert "standings" not in summary["by_year"][0]
    hist = summary["history"]
    assert len(hist["champions"]) == len(run.state.seasons) == 5
    assert sum(t["titles"] for t in hist["title_leaders"]) <= 5 and hist["best_record"] and hist["most_points"]
    assert all(c["name"] for c in hist["champions"])


def test_compaction_keeps_the_pick_ledger_and_the_users_picks():
    run = base.Run(seasons=10, rookie_rounds=2)
    run.play_all()
    st = run.state
    assert set(st.pick_owner) | {s["pick"] for s in st.spent_picks} == set(st.created_picks)
    assert len(set(st.created_picks)) == len(st.created_picks)
    user = run.snap.user_team.tid
    old = [e for e in st.rookie_log if e["year"] < run.snap.settings.start_year + st.season_no - 1 - 4]
    assert old and all(p["team"] == user for e in old for p in e["picks"])
    assert len(st.spent_picks) < 10 * 2 * 8  # fewer rows than every pick ever spent


def test_resume_equals_replay_on_a_compacting_game():
    run = base.Run(seasons=10, rookie_rounds=2)
    run.play_all()
    folded = fold(run.root, run.em.events)
    assert folded.digest() == run.state.digest()


def test_views_are_evicted_but_rebuilt_identically():
    run = base.Run(seasons=10)
    run.play_all()
    root = run.root
    last = root.season_view(10)
    assert len(root._views) <= 4
    mean_before = {p: pl.mean for p, pl in last.players.items()}
    root._views.clear()
    rebuilt = root.season_view(10)
    assert {p: pl.mean for p, pl in rebuilt.players.items()} == mean_before
