"""Long-run regression (docs/audits/2026-11-sim-longrun.md): a short dynasty stays inside the soak's bounds, and the stability_v 4 fixes are gated.

The 30-season soak (``python -m modules.sim.calibration.longrun_soak run``) is too slow for CI; this plays 5 seasons of one seed (about 15 s) and holds the same
metrics to ``longrun_soak.BOUNDS`` and to a loose trend against season 1, so a change that starts a drift (scoring, depth, age mix, market) shows up here first."""

from __future__ import annotations

import numpy as np
import pytest

from modules.sim import aging, game_dynasty as dyn
from modules.sim.calibration import dynasty_run, longrun_soak as ls
from modules.sim.game_types import GameSettings
from tests.test_sim_rookie_v import _digest, _root


@pytest.fixture(scope="module")
def table():
    return ls.metrics_table([dynasty_run.run(2, 5, profiles=True)])


def test_a_short_dynasty_stays_inside_the_soak_bounds(table):
    for key, (lo, hi, why) in ls.BOUNDS.items():
        v = table[key][0][1:]  # seasons 2-5 (season 1 has no rookie class)
        v = v[~np.isnan(v)]
        assert v.size, key
        assert lo <= float(v.mean()) <= hi, f"{key} {v.mean():.2f} outside [{lo}, {hi}] ({why})"


def test_a_short_dynasty_does_not_drift_against_season_1(table):
    t = lambda k, sl: float(np.nanmean(table[k][0][sl]))
    assert t("score_mean", slice(3, 5)) >= 0.88 * t("score_mean", slice(0, 2))
    for pos in ("RB", "WR", "TE"):
        assert t(f"{pos}12_ppg", slice(3, 5)) >= 0.75 * t(f"{pos}12_ppg", slice(0, 2))
    assert t("QB12_ppg", slice(3, 5)) >= 0.75 * t("QB12_ppg", slice(0, 2))
    assert t("top_market", slice(3, 5)) >= 0.8 * t("top_market", slice(0, 2))
    assert t("pool", slice(3, 5)) >= 0.9 * t("pool", slice(0, 2))
    assert t("starter_age", slice(3, 5)) <= t("starter_age", slice(0, 2)) + 1.5


def test_stability_v_4_is_gated_and_a_v3_save_builds_the_pool_it_always_did():
    """The pools of a save made while stability_v 3 was current are byte-for-byte what origin/main built before stability_v 4 existed."""

    assert [_digest(_root(3, 1, stability_v=3), n) for n in (2, 5, 12)] == ["9bf56ac402fabca5", "e5387d1d7ddbe65e", "1edd2ee579459e81"]
    new, old = _root(3, 1, stability_v=4), _root(3, 1, stability_v=3)
    assert _digest(new, 1) == _digest(old, 1)  # season 1 is the real pool
    assert _digest(new, 2) != _digest(old, 2)  # the market (and the quarterback class) follow the new rules from the first offseason


def test_the_v4_rules_are_exactly_the_market_exponent_and_the_quarterback_depth_cap():
    s3 = GameSettings.parse({"mode": "dynasty", "seasons": 3})
    old, new = GameSettings.from_dict({**s3.to_dict(), "stability_v": 3}), s3
    assert not old.stable4 and new.stable4
    assert dyn._depth_cap(old, "QB") == dyn.DEPTH_CAP and dyn._depth_cap(new, "QB") == dyn.DEPTH_CAP_QB > dyn.DEPTH_CAP
    assert dyn._depth_cap(new, "RB") == dyn.DEPTH_CAP  # only the one-to-four-player quarterback class
    args = ("WR", 25.0, 14.0, 0.0, 0.0, 0.5, 0.5)
    base = aging.progress(*args, mult=1.1)
    assert aging.progress(*args, mult=1.1, market_exp=None) == base  # the default path is untouched
    up = aging.progress(*args, mult=1.1, market_exp=aging.MARKET_EXP_V4)
    assert up[3] == 0.0 and base[3] == 0.0 and up[:3] == base[:3]  # only the market moves
    mk = aging.progress("WR", 25.0, 14.0, 10.0, 40.0, 0.5, 0.5, mult=1.1)[3], aging.progress("WR", 25.0, 14.0, 10.0, 40.0, 0.5, 0.5, mult=1.1, market_exp=aging.MARKET_EXP_V4)[3]
    assert mk[1] > mk[0]  # a production gain moves the price further under the pool's own elasticity
