"""stability_v 1: long-run stability (docs/audits/2026-11-sim-desk-logic-realism-audit.md, "Implemented"). Seeded distribution pins on the real
2025 panel pool (no games played), the gate, and the old-save guarantees."""

from __future__ import annotations

import pytest

from modules.sim import aging, game_rules as rules, player_model, player_model_v6
from modules.sim.calibration import stability_report as sr
from modules.sim.game_types import STABILITY_VERSION, GameSettings
import tests.test_sim_dynasty as base

SEEDS, SEASONS = 6, 10


@pytest.fixture(scope="module")
def new():
    return sr.pool_stats(SEEDS, SEASONS, stability_v=1)


@pytest.fixture(scope="module")
def old():
    return sr.pool_stats(SEEDS, SEASONS, stability_v=0, model_id=sr.OLD_MODEL)


def test_gate_and_serialization():
    for raw in ({}, {"mode": "dynasty", "seasons": 3}):
        s = GameSettings.parse(raw)
        assert STABILITY_VERSION == 1 and s.stability_v == 1 and s.stable and s.to_dict()["stability_v"] == 1
        assert GameSettings.from_dict(s.to_dict()).stability_v == 1
    d = GameSettings.parse({}).to_dict()
    d.pop("stability_v")
    old = GameSettings.from_dict(d)
    assert old.stability_v == 0 and not old.stable and "stability_v" not in old.to_dict()
    assert rules.UPGRADABLE_FLAGS["stability_v"] == (1, rules.SEASON) and "stability_v" in rules.FLAGS


def test_old_curves_and_progress_unchanged_by_default():
    assert aging.age_mult("WR", 22, 0) == pytest.approx(1.07) and aging.age_mult("TE", 23, 1) == pytest.approx(aging.age_mult("TE", 23, 0))
    a = aging.progress("WR", 24.0, 12.0, 5.0, 60.0, 0.3, 0.5)
    assert a == aging.progress("WR", 24.0, 12.0, 5.0, 60.0, 0.3, 0.5, outcome=0.0, ceiling=None)
    for pos in ("RB", "WR", "TE"):
        assert aging.age_mult(pos, 22, 2) > 1.1  # early-career growth exists in the v2 knots


def test_growth_has_diminishing_returns_near_the_ceiling():
    low = aging.progress("WR", 22.0, 8.0, 4.0, 40.0, 0.0, 0.99, knots_v=2, ceiling=27.0)[1]
    high = aging.progress("WR", 22.0, 24.0, 4.0, 40.0, 0.0, 0.99, knots_v=2, ceiling=27.0)[1]
    assert low / 8.0 > 1.10 and high / 24.0 < 1.04


def test_early_career_growth_matches_the_panel(new, old):
    assert 1.00 <= sr.ratio(new, "WR", (22,)) <= 1.14 and 0.98 <= sr.ratio(new, "RB", (22,)) <= 1.14 and 1.02 <= sr.ratio(new, "TE", (23,)) <= 1.25
    assert sr.ratio(old, "WR", (22,)) < 0.97 and sr.ratio(old, "TE", (23,)) < 0.95
    assert 0.74 <= sr.ratio(new, "WR", (27, 28)) <= 0.86 and 0.62 <= sr.ratio(new, "RB", (27, 28)) <= 0.76  # later ages stay where the panel has them


def test_rookie_bust_rate_and_unchanged_mean(new, old):
    b_new, b_old = sr.bust_rate(new, 1, 12), sr.bust_rate(old, 1, 12)
    assert 0.14 <= b_new[0] <= 0.26 and b_old[0] < 0.17 and b_new[0] > b_old[0] + 0.03
    assert abs(b_new[2] - b_old[2]) < 0.06  # variance, not a nerf: the class's mean outcome does not move
    assert not hasattr(player_model_v6.SEASON, "bust_sd_rook")
    assert player_model.SEASON.bust_sd_rook > 0.0


def test_ten_seasons_stay_stationary(new, old):
    late = range(6, SEASONS + 1)
    for key in ("RB24", "WR24", "QB12", "TE12"):
        assert 0.88 < sr.mean_level(new, key, late) / sr.mean_level(new, key, range(1, 2)) < 1.12, key
    for key in ("RB36", "WR36"):  # the depth tier (the wire every bye and injury is covered from) no longer thins out
        assert sr.mean_level(new, key, late) / sr.mean_level(new, key, range(1, 2)) > 0.82, key
    assert abs(sr.mean_level(new, "age", late) - sr.mean_level(new, "age", range(1, 2))) < 0.8


def test_ai_ai_trades_never_swap_picks_when_stable():
    from modules.sim.types import is_pick_id

    def ai_trades(v):
        run = base.Run(seasons=3, stability_v=v)
        run.play_all()
        return [e["payload"] for e in run.em.events if e["type"] == "trade" and e["payload"].get("source") == "ai_ai"]

    assert all(not is_pick_id(p) for t in ai_trades(1) for p in (*t["give"], *t["get"]))
