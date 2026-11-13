"""Generated rookies: scouting profiles, development archetypes and the curve the multi-season sim plays."""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import replace

import pytest

from modules.sim import aging, game_dynasty as dyn, game_view as view, scouting as sc
from modules.sim.game_eval import Evaluator
from modules.sim.rng import WorldRng
from tests.test_sim_dynasty import Run, new_snapshot

POS = ("QB", "RB", "WR", "TE")


def rookie(pos="WR", z=0.0, seed=1234, rank=10, size=60, age=23.0, mean=9.0):
    extra = {"is_rookie": 1.0, "years_exp": 0.0, "draft_year": 2027.0, **sc.rookie_dev_fields(pos, age, z, seed, rank, size)}
    return {"pos": pos, "age": age, "name": "Brock Briggs", "extra": extra, "mean": mean, "draft_year": 2027}


def profile(r, **kw):
    return sc.build_profile(**{**r, **kw})


# ------------------------------------------------------------------ determinism


def test_profile_is_deterministic_json_safe_and_seed_dependent():
    a, b = profile(rookie(seed=7)), profile(rookie(seed=7))
    assert a == b
    json.dumps(a, allow_nan=False)
    assert profile(rookie(seed=8)) != a
    assert a["source"] == "generated" and a["label"] == "Generated prospect"
    assert {"draft", "measurables", "college", "analytics", "tags", "blurb", "development"} <= set(a)


def test_class_generation_is_deterministic_and_adds_fields_only_when_gated():
    snap = new_snapshot()
    vets = {p.pid: {"pid": p.pid, "pos": p.pos, "mean": p.mean, "market": p.market, "nfl_team": p.nfl_team} for p in snap.players.values() if p.pos != "DEF"}
    snap = replace(snap, settings=replace(snap.settings, dynasty_v=2))  # dynasty_v 3 draws a different (equilibrium) class; see test_sim_dynasty_long
    a, b = dyn.rookie_class(snap, vets, 2), dyn.rookie_class(snap, vets, 2)
    assert a == b and all(sc.has_curve(r["extra"]) and "scout_seed" in r["extra"] for r in a)
    old = replace(snap, settings=replace(snap.settings, dynasty_v=1))
    o = dyn.rookie_class(old, vets, 2)
    assert all("dev_arch" not in r["extra"] and "scout_seed" not in r["extra"] for r in o)
    # the world (who, where, how good) is the same either way: gating only adds the new fields
    strip = lambda rows: [{k: v for k, v in r.items() if k != "extra"} for r in rows]  # noqa: E731
    assert strip(a) == strip(o)


# ------------------------------------------------------------------ distributions by position

MEAS = {"QB": (74.8, 222, 4.82), "RB": (70.6, 212, 4.53), "WR": (72.6, 200, 4.50), "TE": (76.5, 249, 4.73)}


def _ht(display):
    ft, inch = display.rstrip('"').split("'")
    return int(ft) * 12 + int(inch)


@pytest.mark.parametrize("pos", POS)
def test_measurables_and_college_lines_are_realistic_by_position(pos):
    ps = [profile(rookie(pos, z=(i % 9 - 4) / 3.0, seed=1000 + i, rank=1 + i % 60)) for i in range(400)]
    meas = [{m["key"]: m for m in p["measurables"]} for p in ps]
    hm, wm, fm = MEAS[pos]
    assert abs(statistics.mean(_ht(m["height"]["display"]) for m in meas) - hm) < 0.6
    assert abs(statistics.mean(int(m["weight"]["display"].split()[0]) for m in meas) - wm) < 4
    assert abs(statistics.mean(float(m["forty"]["display"].rstrip("s")) for m in meas) - fm) < 0.06
    assert all(1 <= m[k]["percentile"] <= 99 for m in meas for k in m)
    finals = [p["college"]["seasons"][-1]["stats"] for p in ps]
    if pos == "QB":
        assert 56 <= statistics.mean(f["comp_pct"] for f in finals) <= 70 and 6.5 <= statistics.mean(f["ypa"] for f in finals) <= 9.5
        assert all(f["pass_td"] >= 0 and f["pass_int"] >= 0 and f["pass_cmp"] <= f["pass_att"] for f in finals)
    elif pos == "RB":
        assert 4.8 <= statistics.mean(f["ypc"] for f in finals) <= 6.6 and all(f["rush_yd"] <= f["rush_att"] * 8.1 for f in finals)
    else:
        assert all(f["rec_yd"] <= f["rec"] * 21.5 and 0.5 <= f["yprr"] <= 4.6 for f in finals)
    for p in ps[:50]:
        assert all(1 <= a["percentile"] <= 99 for a in p["analytics"])
        assert len(p["college"]["seasons"]) >= 2 and p["college"]["seasons"][-1]["stats"] == {**p["college"]["seasons"][-1]["stats"]}


def test_production_percentile_tracks_talent_and_draft_slot_is_monotone():
    lo = statistics.mean(profile(rookie("WR", z=-1.5, seed=i, rank=55))["analytics"][0]["percentile"] for i in range(200))
    hi = statistics.mean(profile(rookie("WR", z=1.5, seed=i, rank=3))["analytics"][0]["percentile"] for i in range(200))
    assert hi > lo + 25
    picks = [profile(rookie("RB", rank=r))["draft"]["pick"] for r in range(1, 61)]
    assert picks == sorted(picks) and picks[0] <= 5 and picks[-1] > 60
    assert profile(rookie("RB", rank=1))["draft"]["round"] == 1


# ------------------------------------------------------------------ archetypes and the curve


def test_archetype_mix_follows_talent():
    def mix(z):
        n = {a: 0 for a in sc.ARCHETYPES}
        for i in range(2000):
            n[sc.archetype_of(sc.rookie_dev_fields("WR", 23.0, z, 500 + i, 5, 60))] += 1
        return {a: v / 2000 for a, v in n.items()}

    top, tail = mix(1.6), mix(-1.6)
    assert top["star"] > 3 * tail["star"] and tail["bust"] > 3 * top["bust"]
    assert all(0.0 < v < 0.6 for v in (*top.values(), *tail.values()))
    # the population still follows the calibrated age curve: archetypes average out near 1.0
    rel = [statistics.mean(sc.ARCHETYPE_REL[a][k] * w for a, w in sc.archetype_weights(0.0).items()) for k in range(1)]
    avg = sum(sc.ARCHETYPE_REL[a][0] * w for a, w in sc.archetype_weights(0.0).items())
    assert 0.97 < avg < 1.05, (avg, rel)


def test_displayed_curve_converges_to_the_curve_the_sim_plays():
    r = rookie("WR", z=0.8, seed=42)
    extra = r["extra"]
    truth = [extra[f"dev_r{k}"] for k in range(1, 5)]
    # fully revealed: the displayed steps ARE the stored ratios
    full = sc.expected_curve("WR", 23.0, 10.0, extra, years_exp=0.0, games=17)
    # confidence at years_exp 0 is below 1; force it by playing years
    assert full["points"][0]["mean"] == 10.0
    c = sc.confidence(extra, 0.0, 17)
    level = 10.0
    for k, pt in enumerate(full["points"][1:]):
        plain = aging.age_mult("WR", 23.0 + k)
        ratio = math.exp(math.log(plain) + c * (math.log(truth[k]) - math.log(plain)))
        level *= ratio
        assert abs(pt["mean"] - round(level, 1)) < 0.06
    assert full["revealed"] is False and full["archetype"] is None
    late = sc.expected_curve("WR", 25.0, 10.0, {**extra, "years_exp": 2.0}, years_exp=2.0, games=17)
    assert late["revealed"] is True and late["archetype"] == sc.archetype_of(extra)
    assert late["confidence"] > full["confidence"] and late["points"][0]["year"] == 3
    # the band narrows as scouting certainty rises
    wide = full["points"][-1]["hi"] / full["points"][-1]["lo"]
    assert wide > 1.0
    # hint tag: early on it can mislead, never claims the revealed label, and gets truthful with confidence
    tag_lo, conf_lo = sc.hint_tag(extra, 0.3)
    tag_hi, conf_hi = sc.hint_tag(extra, 0.98)
    assert conf_hi > conf_lo and tag_hi == sc.ARCHETYPE_TAG[sc.archetype_of(extra)]


def test_progression_applies_the_stored_curve_and_old_saves_keep_the_age_curve():
    run = Run()
    object.__setattr__(run.root, "settings", replace(run.root.settings, dynasty_v=2))  # (dynasty_v 3 adds the league anchor and a top bound; that is tested in test_sim_dynasty_long)
    run.play_season()
    run.offseason()  # enters season 2: rookie class 2 is in the pool, played season 2 next
    root = run.root
    v2 = root.season_view(2)
    rookies = [p for p in v2.players.values() if "dev_r1" in p.extra and p.extra.get("years_exp") == 0.0]
    assert len(rookies) >= 24 and all(p.extra["dev_arch"] in (0, 1, 2, 3, 4) for p in rookies)
    v3 = root.season_view(3)
    rng = WorldRng(root.seed)
    checked = 0
    for p in rookies:
        n = v3.players.get(p.pid)
        if n is None:
            continue  # retired
        z = float(rng.stream(2, "gage", aging.stable_key(p.pid)).standard_normal())
        want = max(0.5, p.mean * p.extra["dev_r1"] * math.exp(0.10 * z - 0.005)) if p.pos != "K" else None
        if want is not None:
            assert n.mean == pytest.approx(want, abs=0.06), p.pid
            checked += 1
        assert n.extra["years_exp"] == 1.0 and n.extra["dev_r2"] == p.extra["dev_r2"]
    assert checked >= 20
    # an older save (dynasty_v 1): the plain age curve, bit for bit
    old = Run()
    object.__setattr__(old.root, "settings", replace(old.root.settings, dynasty_v=1))  # a save from before rookie curves
    old.play_season()
    old.offseason()
    ov2, ov3 = old.root.season_view(2), old.root.season_view(3)
    p = next(p for p in ov2.players.values() if p.extra.get("draft_year") and p.pid in ov3.players and p.pos != "K")
    assert "dev_r1" not in p.extra
    z = float(WorldRng(old.root.seed).stream(2, "gage", aging.stable_key(p.pid)).standard_normal())
    assert ov3.players[p.pid].mean == pytest.approx(max(0.5, p.mean * aging.age_mult(p.pos, p.age) * math.exp(0.10 * z - 0.005)), abs=0.06)


def test_year_five_hands_back_to_the_age_curve():
    extra = rookie("RB")["extra"]
    assert sc.step_ratio(extra, 0) == extra["dev_r1"] and sc.step_ratio(extra, 3) == extra["dev_r4"]
    assert sc.step_ratio(extra, 4) is None and sc.step_ratio({}, 0) is None


# ------------------------------------------------------------------ the payload


def test_player_detail_carries_the_scouting_profile_for_generated_rookies_only():
    run = Run()
    run.play_season()
    run.em.snap = run.snap
    dyn.start_rookie_draft(run.em)
    snap = run.snap
    pids = [p.pid for p in snap.players.values() if p.extra.get("draft_year")]
    assert pids
    pid = pids[0]
    d = view.player_detail(snap, run.state, pid)
    json.dumps(d, allow_nan=False)
    s = d["scouting"]
    assert s["label"] == "Generated prospect" and s["development"]["points"][0]["mean"] == round(Evaluator(snap, run.state).ros_mean(pid), 1)
    assert d["player"]["generated"] is True
    vet = next(p.pid for p in snap.players.values() if not p.extra.get("draft_year") and p.pos != "DEF")
    assert "scouting" not in view.player_detail(snap, run.state, vet)
    assert view.player_detail(snap, run.state, pid)["scouting"] == s  # same prospect, same story
