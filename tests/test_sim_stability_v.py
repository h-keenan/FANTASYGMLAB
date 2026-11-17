"""stability_v 1: long-run stability (docs/audits/2026-11-sim-desk-logic-realism-audit.md, "Implemented") and stability_v 2: late-career aging and
persistence (docs/audits/2026-11-realism-advice-audit-2.md). Seeded distribution pins on the real 2025 panel pool (no games played), the gate, and the
old-save guarantees."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from modules.sim import aging, game_dynasty as dyn, game_rules as rules, player_model, player_model_v6
from modules.sim.calibration import dataset, stability_report as sr, tail_report
from modules.sim.game_engine import session_for
from modules.sim.game_setup import build_snapshot
from modules.sim.game_types import STABILITY_VERSION, GameSettings
import tests.test_sim_dynasty as base

SEEDS, SEASONS = 6, 10


@pytest.fixture(scope="module")
def new():
    return sr.pool_stats(SEEDS, SEASONS, stability_v=1)


@pytest.fixture(scope="module")
def new2():
    return sr.pool_stats(SEEDS, SEASONS, stability_v=2)


@pytest.fixture(scope="module")
def old():
    return sr.pool_stats(SEEDS, SEASONS, stability_v=0, model_id=sr.OLD_MODEL)


def test_gate_and_serialization():
    for raw in ({}, {"mode": "dynasty", "seasons": 3}):
        s = GameSettings.parse(raw)
        assert STABILITY_VERSION == 4 and s.stability_v == 4 and s.stable and s.stable2 and s.stable3 and s.stable4 and s.to_dict()["stability_v"] == 4
        assert GameSettings.from_dict(s.to_dict()).stability_v == 4
    d = GameSettings.parse({}).to_dict()
    mid = GameSettings.from_dict({**d, "stability_v": 1})  # a save made while stability_v 1 was current: the first generation of the rules, not the second
    assert mid.stability_v == 1 and mid.stable and not mid.stable2 and not mid.stable3 and not mid.stable4 and mid.to_dict()["stability_v"] == 1
    d.pop("stability_v")
    old = GameSettings.from_dict(d)
    assert old.stability_v == 0 and not old.stable and not old.stable2 and "stability_v" not in old.to_dict()
    assert rules.UPGRADABLE_FLAGS["stability_v"] == (4, rules.SEASON) and "stability_v" in rules.FLAGS


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


# ------------------------------------------------------------------------------------------------ stability_v 2


def test_v3_knots_are_flatter_from_25_and_leave_everything_else_alone():
    for pos in ("RB", "WR", "TE"):
        for age in (27, 28, 30):
            assert aging.age_mult(pos, age, 3) > aging.age_mult(pos, age, 2), (pos, age)
        for age in (31, 33):
            assert aging.age_mult(pos, age, 3) >= aging.age_mult(pos, age, 2), (pos, age)
        assert aging.age_mult(pos, 22 if pos != "TE" else 23, 3) > 1.1  # early-career growth is still there
    for pos in ("QB", "K", "DEF"):
        for age in (22, 26, 30, 36):
            assert aging.age_mult(pos, age, 3) == aging.age_mult(pos, age, 2), (pos, age)
    # the generations a save can already be on are untouched
    assert aging.age_mult("RB", 27, 2) == pytest.approx(0.78) and aging.age_mult("WR", 28, 2) == pytest.approx(0.82) and aging.age_mult("TE", 28, 2) == pytest.approx(0.90)
    assert aging.age_mult("WR", 22, 1) == pytest.approx(1.07) and aging.age_mult("RB", 27, 0) == pytest.approx(0.84)


def test_the_outcome_carry_is_stronger_and_set_per_position():
    for pos in ("QB", "RB", "WR", "TE"):
        assert aging.OUTCOME_WEIGHT_V2[pos] >= aging.OUTCOME_WEIGHT and aging.REVERSION_V2[pos] < aging.REVERSION + 0.1
    assert aging.OUTCOME_WEIGHT == 0.5 and aging.REVERSION == 0.40  # stability_v 1 keeps its own


def _digest(root, season: int) -> str:
    pool = root.season_view(season).players
    text = ";".join(f"{pid}:{p.mean:.6f}:{p.age:.1f}:{p.market:.4f}" for pid, p in sorted(pool.items()))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _panel_root(seed: int, v: int, seasons: int = 5):
    from modules.sim import game_scoring

    rows, byes = tail_report.pool_from_panel(dataset.load_panel())
    base_settings = GameSettings.parse({"mode": "dynasty", "teams": 12, "user_slot": 3, "start_year": 2026, "seasons": seasons, "rookie_rounds": 3, "scoring": "ppr"})
    return build_snapshot(rows, byes, replace(base_settings, stability_v=v, rookie_v=0), seed, scoring_model=game_scoring.default_model().model_id)


def test_a_stability_1_save_replays_exactly_as_it_did_and_2_differs():
    """The pool of a save that carries stability_v 1 (or 0) is byte-for-byte what origin/main built before stability_v 2 existed."""

    v1, v2 = _panel_root(3, 1), _panel_root(3, 2)
    assert _digest(v1, 1) == _digest(v2, 1)  # season 1 is the real pool
    assert _digest(v1, 4) == "810031208611d484"
    assert _digest(v2, 2) != _digest(v1, 2) and _digest(v2, 4) != _digest(v1, 4)


def _persistence(v: int) -> float:
    """corr(log of last season's realized / projected, next projection change) over the top 24 of RB / WR / TE by projection (season story only, no games)."""

    xs, ys = [], []
    for seed in range(1, 5):
        root = _panel_root(seed, v, 5)
        prev = None
        for n in range(1, 6):
            snap = root.season_view(n)
            sess = session_for(snap, dyn.season_seed(seed, n))
            cur = {pid: (p.pos, p.mean, float(sess.profile(pid).season_multiplier)) for pid, p in snap.players.items() if p.pos in ("RB", "WR", "TE") and p.mean > 0}
            if prev:
                for pos in ("RB", "WR", "TE"):
                    for pid, (_, mean, mult) in sorted(((k, x) for k, x in prev.items() if x[0] == pos and k in cur), key=lambda kv: -kv[1][1])[:24]:
                        xs.append(np.log(mult))
                        ys.append(np.log(cur[pid][1] / mean))
            prev = cur
    return float(np.corrcoef(xs, ys)[0, 1])


def test_last_seasons_result_carries_further_into_the_next_projection():
    assert 0.60 <= _persistence(2) <= 0.85 and _persistence(2) > _persistence(1) + 0.15  # the panel: 0.66-0.77 (stability_v 1 here: about 0.5)


def test_late_career_ratios_move_toward_the_panel(new, new2):
    """Realized next / this ppg for 27-28 year olds (6+ ppg, 8+ games both years): flatter under v2, early career and 25-26 still on the panel's side."""

    for pos in ("RB", "WR", "TE"):
        assert sr.ratio(new2, pos, (27, 28)) > sr.ratio(new, pos, (27, 28)) + 0.04, pos
    assert 0.72 <= sr.ratio(new2, "RB", (27, 28)) <= 0.90 and 0.84 <= sr.ratio(new2, "WR", (27, 28)) <= 0.98 and 0.90 <= sr.ratio(new2, "TE", (27, 28)) <= 1.05
    assert 1.00 <= sr.ratio(new2, "WR", (22,)) <= 1.16 and 1.00 <= sr.ratio(new2, "RB", (22,)) <= 1.14 and 1.02 <= sr.ratio(new2, "TE", (23,)) <= 1.22


def test_ten_seasons_stay_stationary_under_v2(new2):
    late = range(6, SEASONS + 1)
    for key in ("RB24", "WR24", "QB12", "TE12", "RB12", "WR12"):
        assert 0.88 < sr.mean_level(new2, key, late) / sr.mean_level(new2, key, range(1, 2)) < 1.16, key
    for key in ("RB36", "WR36"):
        assert sr.mean_level(new2, key, late) / sr.mean_level(new2, key, range(1, 2)) > 0.88, key
    assert abs(sr.mean_level(new2, "age", late) - sr.mean_level(new2, "age", range(1, 2))) < 0.8
    assert 0.14 <= sr.bust_rate(new2, 1, 12)[0] <= 0.26  # the rookie bust variance is the model's, not the age curve's


def test_a_stability_1_dynasty_upgrades_to_2_at_the_next_offseason_and_replays():
    """A save made on stability_v 1 (everything else current) is offered exactly stability_v 4; seasons already built stay as they were, the next ones age under the
    flatter curves, and the log replays to the same digest."""

    from tests import test_sim_realism_update as ru

    mid = replace(GameSettings.parse({"mode": "dynasty", "seasons": 4, "start_year": 2026, "rookie_rounds": 2, "scoring": "ppr", "user_slot": 4}), stability_v=1)
    assert rules.pending_flags(mid, []) == {"stability_v": 4}
    snap, state, em = ru._dynasty((1, "offseason"), 4, ru.MODEL, mid)
    plain = ru._dynasty(None, 4, ru.MODEL, mid)[0]
    (entry,) = state.rules
    assert entry["flags"] == {"stability_v": 4} and entry["bounds"] == {"stability_v": "season"} and entry["view_from"] == 3
    view = snap.under(state.rules)
    for season in (1, 2):
        assert dict(view.season_view(season).players) == dict(plain.season_view(season).players)
    assert view.season_view(2).settings.stability_v == 1 and view.season_view(3).settings.stability_v == 4
    assert dict(view.season_view(3).players) != dict(plain.season_view(3).players)
    assert ru._replay(snap, em) == state.digest()


# ------------------------------------------------------------------------------------------------ stability_v 3


def test_v3_lightens_only_the_wr_te_pull():
    for pos in ("QB", "RB"):
        assert aging.REVERSION_V3[pos] == aging.REVERSION_V2[pos], pos
    for pos in ("WR", "TE"):
        assert aging.REVERSION_V3[pos] < aging.REVERSION_V2[pos], pos
    assert aging.REVERSION_V2 == {"QB": 0.15, "RB": 0.10, "WR": 0.45, "TE": 0.35}  # the generation a stability_v 2 save is on is untouched


def test_a_stability_2_save_replays_exactly_as_it_did_and_3_differs():
    """Season 1 is the real pool; from season 2 a v3 game ages WR / TE under the lighter pull, a v2 game exactly as it did before v3 existed."""

    v2, v3 = _panel_root(3, 2), _panel_root(3, 3)
    assert _digest(v2, 1) == _digest(v3, 1)
    assert _digest(v2, 4) == "d92d072e4e4053f2"
    assert _digest(v3, 2) != _digest(v2, 2) and _digest(v3, 4) != _digest(v2, 4)
    a, b = v2.season_view(2).players, v3.season_view(2).players  # QB / RB projections are unchanged in the first offseason (same carry, same pull); only WR / TE move
    assert all(a[pid].mean == b[pid].mean for pid in a if pid in b and a[pid].pos in ("QB", "RB") and not pid.startswith("R"))
    assert any(a[pid].mean != b[pid].mean for pid in a if pid in b and a[pid].pos in ("WR", "TE"))
