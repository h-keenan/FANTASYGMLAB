"""aging_v 1: position hazard retirement (age x role x production), flatter kicker/QB aging, older kicker rookies. Data-independent:
the synthetic pool and pure functions only; old saves (aging_v 0) replay through the pinned goldens in tests/test_sim_dynasty_long.py."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from modules.sim import aging, game_dynasty as dyn
from modules.sim.game_types import AGING_VERSION, GameSettings
import tests.test_sim_dynasty as base


def _career_ends(pos, start_age, role, n=4000, seed=1, v=1):
    """Retirement ages of ``n`` players of one position walked year by year with the real ``progress`` (flat production)."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        age, mean, sd, market = float(start_age), 10.0, 5.0, 50.0
        while True:
            age, mean, sd, market, retired = aging.progress(pos, age, mean, sd, market, float(rng.standard_normal()), float(rng.random()), aging_v=v, role=role)
            mean = 10.0  # hold production level: isolates the age/role hazard
            if retired or age > 60:
                out.append(age)
                break
    return np.array(out)


def test_gate_and_serialization():
    s = GameSettings.parse({"mode": "dynasty", "seasons": 5})
    assert AGING_VERSION == 1 and s.aging_v == 1 and s.aging_curves and s.to_dict()["aging_v"] == 1
    assert GameSettings.from_dict(s.to_dict()).aging_v == 1
    raw = s.to_dict()
    raw.pop("aging_v")  # a save from before the flag
    old = GameSettings.from_dict(raw)
    assert old.aging_v == 0 and not old.aging_curves and "aging_v" not in old.to_dict()
    assert "aging_v" not in GameSettings.parse({}).to_dict()  # redraft saves never carry it


def test_old_settings_use_the_original_curves_exactly():
    for pos in ("QB", "RB", "WR", "TE", "K"):
        a = aging.progress(pos, 33.0, 12.0, 5.0, 40.0, 0.3, 0.2, flat_k=True)
        b = aging.progress(pos, 33.0, 12.0, 5.0, 40.0, 0.3, 0.2, flat_k=True, aging_v=0, role=0.9)
        assert a == b
    assert aging.age_mult("K", 36.0) == aging.age_mult("K", 36.0, 0) != aging.age_mult("K", 36.0, 1)


def test_deterministic_replay_and_resume():
    r1 = base.new_snapshot(seed=77, aging_v=1, seasons=5)
    r2 = base.new_snapshot(seed=77, aging_v=1, seasons=5)
    a = r1.season_view(5)
    b = r2.season_view(5)
    assert sorted(a.players) == sorted(b.players)
    assert all(a.players[p].age == b.players[p].age and a.players[p].mean == b.players[p].mean for p in a.players)
    old = base.new_snapshot(seed=77, aging_v=0, seasons=5).season_view(5)
    assert sorted(old.players) != sorted(a.players) or any(old.players[p].age != a.players[p].age for p in a.players if p in old.players)


def test_kicker_retirement_ages():
    ends = _career_ends("K", 24, role=0.8)
    assert 35.5 <= np.median(ends) <= 39.5
    assert np.mean(ends >= 40) >= 0.08  # a real share to 40+
    assert np.mean(ends <= 33) < 0.10  # no mass retirement of 33-year-olds
    # the chance a 33-year-old starting kicker retires this offseason is small
    assert aging.retire_prob_v1("K", 33.0, 0.9, 0.5) < 0.03
    assert aging.retire_prob_v1("K", 33.0, 0.9, 0.5) < aging.retire_prob("K", 33.0, 0.5) * 6  # and was ~1% in the old curve


def test_position_ordering_and_ranges():
    med = {pos: float(np.median(_career_ends(pos, 22, role=0.7, n=2500))) for pos in ("QB", "RB", "WR", "TE", "K")}
    assert med["RB"] < med["WR"] < med["TE"] < med["QB"] < med["K"]
    assert 26.5 <= med["RB"] <= 30.0 and 28.5 <= med["WR"] <= 32.5 and 29.5 <= med["TE"] <= 33.5
    assert 33.0 <= med["QB"] <= 37.5
    qb = _career_ends("QB", 22, role=0.9, n=2500)
    assert np.percentile(qb, 95) >= 38.0 and qb.max() <= 55  # a tail into the 40s


def test_role_and_production_move_the_hazard():
    for pos in ("QB", "RB", "WR", "TE", "K"):
        age = {"QB": 35.0, "RB": 29.0, "WR": 31.0, "TE": 32.0, "K": 38.0}[pos]
        starter = aging.retire_prob_v1(pos, age, 1.0, 0.5)
        bench = aging.retire_prob_v1(pos, age, 0.0, 0.5)
        assert bench > starter
        assert aging.retire_prob_v1(pos, age, 0.8, 0.5, ratio=0.7) > aging.retire_prob_v1(pos, age, 0.8, 0.5, ratio=1.0)
        ps = [aging.retire_prob_v1(pos, a, 0.7, 0.5) for a in range(26, 46)]
        assert all(0.0 < x < 1.0 for x in ps) and ps[-1] > ps[2]  # smooth, never a certainty, rising with age
    assert aging.retire_prob_v1("DEF", 40.0, 0.0, 0.0) == 0.0
    assert aging.retire_prob_v1("RB", 22.0, 0.5, 0.5) < 0.01  # no injury floor below 23 ... and tiny age hazard


def test_kicker_and_qb_skill_aging_is_flatter():
    assert aging.age_mult("K", 37.0, 1) == 1.0 and aging.age_mult("K", 37.0, 0) < 1.0
    assert aging.age_mult("QB", 36.0, 1) > aging.age_mult("QB", 36.0, 0)
    assert aging.age_mult("RB", 28.0, 1) == aging.age_mult("RB", 28.0, 0)  # other positions keep the panel curves


def test_kicker_rookies_arrive_older():
    r = base.new_snapshot(seed=5, aging_v=1, seasons=5)
    r0 = base.new_snapshot(seed=5, aging_v=0, seasons=5)
    ks = [p.age for s in (2, 3, 4, 5) for p in r.season_view(s).players.values() if p.pos == "K" and p.extra.get("is_rookie")]
    ks0 = [p.age for s in (2, 3, 4, 5) for p in r0.season_view(s).players.values() if p.pos == "K" and p.extra.get("is_rookie")]
    assert ks and min(ks) >= 22 and max(ks) <= 28
    assert not ks0 or max(ks0) <= 25
