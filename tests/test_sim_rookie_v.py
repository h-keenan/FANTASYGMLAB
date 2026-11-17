"""rookie_v 1: dynasty rookie classes sized like real ones (docs/audits/2026-11-realism-advice-audit-2.md). Seeded distribution pins on the real 2025 panel
pool (no games played), the gate, the old-save guarantees and the Realism update."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from modules.sim import game_dynasty as dyn, game_rules as rules, game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_engine import session_for
from modules.sim.game_setup import build_snapshot
from modules.sim.game_types import ROOKIE_VERSION, GameSettings

SEEDS, SEASONS = 6, 10
POS = ("QB", "RB", "WR", "TE")


def _root(seed: int, rookie_v: int, seasons: int = SEASONS, **kw):
    rows, byes = tail_report.pool_from_panel(dataset.load_panel())
    base = GameSettings.parse({"mode": "dynasty", "teams": 12, "user_slot": 3, "start_year": 2026, "seasons": seasons, "rookie_rounds": 3, "scoring": "ppr"})
    return build_snapshot(rows, byes, replace(base, rookie_v=rookie_v, **kw), seed, scoring_model=game_scoring.default_model().model_id)


def _digest(root, season: int) -> str:
    pool = root.season_view(season).players
    text = ";".join(f"{pid}:{p.mean:.6f}:{p.age:.1f}:{p.market:.4f}" for pid, p in sorted(pool.items()))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _stats(rookie_v: int) -> dict:
    """Rookies per position top 12 / top 24 after the first offseason, the best rookie against the 12th veteran, class rank 1-12 busts and the level of the pool by season."""

    top12 = {p: [] for p in POS}
    top24 = {p: [] for p in POS}
    best = {p: [] for p in POS}
    bust: list[bool] = []
    levels: dict[tuple[int, str], list[float]] = {}
    for seed in range(1, SEEDS + 1):
        root = _root(seed, rookie_v)
        for n in range(1, SEASONS + 1):
            snap = root.season_view(n)
            sess = session_for(snap, dyn.season_seed(seed, n))
            pool = [p for p in snap.players.values() if p.pos in POS and p.mean > 0]
            for pos in POS:
                ps = sorted((p.mean for p in pool if p.pos == pos), reverse=True)
                levels.setdefault((n, f"{pos}12"), []).append(ps[11])
                levels.setdefault((n, f"{pos}24"), []).append(float(np.mean(ps[:24])))
                if len(ps) >= 36:
                    levels.setdefault((n, f"{pos}36"), []).append(float(np.mean(ps[:36])))
                if n == 1:
                    continue
                vets = sorted((p.mean for p in pool if p.pos == pos and not p.extra.get("is_rookie")), reverse=True)
                rk = sorted((p.mean for p in pool if p.pos == pos and p.extra.get("is_rookie")), reverse=True)
                if rk and len(vets) >= 12:
                    top12[pos].append(sum(1 for x in rk if x >= ps[11]))
                    top24[pos].append(sum(1 for x in rk if x >= ps[23]))
                    best[pos].append(rk[0] / vets[11])
            if n > 1:
                rank = sorted((p for p in pool if p.extra.get("is_rookie")), key=lambda p: -p.mean)[:12]
                for p in rank:
                    prof = sess.profile(p.pid)
                    if sum(1 for m in prof.games_available_mask if m) >= 8:
                        bust.append(float(prof.season_mean_ppg) / p.mean < 0.6)
    return {"top12": {p: float(np.mean(v)) for p, v in top12.items()}, "top24": {p: float(np.mean(v)) for p, v in top24.items()},
            "best": {p: float(np.mean(v)) for p, v in best.items()}, "bust": float(np.mean(bust)), "levels": levels}


def _level(st: dict, key: str, seasons: range) -> float:
    return float(np.mean([np.mean(st["levels"][(n, key)]) for n in seasons]))


@pytest.fixture(scope="module")
def new():
    return _stats(1)


@pytest.fixture(scope="module")
def old():
    return _stats(0)


def test_gate_and_serialization():
    s = GameSettings.parse({"mode": "dynasty", "seasons": 3})
    assert ROOKIE_VERSION == 1 and s.rookie_v == 1 and s.rookie_sized and s.to_dict()["rookie_v"] == 1
    assert GameSettings.from_dict(s.to_dict()).rookie_v == 1
    assert GameSettings.parse({}).rookie_v == 0 and not GameSettings.parse({}).rookie_sized  # no offseasons, nothing to size
    d = s.to_dict()
    d.pop("rookie_v")
    old = GameSettings.from_dict(d)
    assert old.rookie_v == 0 and not old.rookie_sized and "rookie_v" not in old.to_dict()
    assert not replace(s, stability_v=0).rookie_sized  # it sits on the stability rules
    assert rules.UPGRADABLE_FLAGS["rookie_v"] == (1, rules.SEASON) and rules.FLAGS["rookie_v"]["dynasty_only"] is True


def test_scarcity_never_reaches_the_best_rookies():
    assert dyn._scarcity(1.4, 1) == 1.0 and dyn._scarcity(0.9, 1) == 1.0
    assert dyn._scarcity(1.4, dyn.SUPPLY_FULL_SLOT) == pytest.approx(1.4) and dyn._scarcity(1.4, 60) == pytest.approx(1.4)
    assert 1.0 < dyn._scarcity(1.4, 10) < 1.4


def test_the_depth_response_is_capped_and_a_quarterback_class_is_not_tapered():
    assert dyn._depth_response(5.0, 3, 2.0, 16.0) == 5.0  # through the first middle slot nothing changes
    assert dyn._depth_response(5.0, 30, 2.0, 16.0) == pytest.approx(10.0)  # full effect from slot 20 down
    assert dyn._depth_response(8.0, 30, 4.0, 16.0) == pytest.approx(dyn.DEPTH_CAP * 16.0)  # a solid starter, never a star
    assert dyn._depth_response(14.0, 30, 4.0, 16.0) == 14.0  # and never lowered
    assert dyn._scarcity(1.3, 1, "QB") == 1.3 and dyn._scarcity(1.3, 1, "RB") == 1.0


def test_a_rookie_v_0_save_builds_the_class_it_always_did():
    """The pool of a save without rookie_v is byte-for-byte what origin/main built before rookie_v existed."""

    assert _digest(_root(3, 0, stability_v=2), 4) == "d92d072e4e4053f2"  # (a save made while stability_v 2 was current)
    assert _digest(_root(3, 1), 1) == _digest(_root(3, 0), 1)  # season 1 is the real pool
    assert _digest(_root(3, 1), 2) != _digest(_root(3, 0), 2)


def test_classes_are_sized_like_real_ones(new, old):
    """Real 2021-25 classes put 0.8 RB, 0.0 WR, 0.4 QB and 0.4 TE in a position's top 12 (1.6 in all) and the best rookie RB at 0.91 of the 12th veteran.
    Without rookie_v the controllers over-supplied the thin positions (RB and QB, after the first offseason)."""

    assert sum(new["top12"].values()) < 2.7 < sum(old["top12"].values())
    assert new["top12"]["RB"] < 1.0 and old["top12"]["RB"] > new["top12"]["RB"] + 0.4
    assert new["top12"]["QB"] < 0.9 and old["top12"]["QB"] > new["top12"]["QB"] + 0.4
    assert max(new["best"].values()) < 1.08  # the best rookie at a position is about the 12th veteran, not 1.3x him


def test_top_12_rookies_still_bust_about_one_time_in_five(new):
    assert 0.14 <= new["bust"] <= 0.26


def test_ten_seasons_stay_stationary(new):
    late = range(6, SEASONS + 1)
    for key in ("RB12", "WR12", "QB12", "TE12", "RB24", "WR24", "TE24"):
        assert 0.88 < _level(new, key, late) / _level(new, key, range(1, 2)) < 1.20, key
    for key in ("RB36", "WR36"):  # the depth tier the wire is covered from still refills
        assert _level(new, key, late) / _level(new, key, range(1, 2)) > 0.88, key


def test_a_rookie_v_0_dynasty_upgrades_at_the_next_offseason_and_replays():
    from tests import test_sim_realism_update as ru

    old = replace(GameSettings.parse({"mode": "dynasty", "seasons": 4, "start_year": 2026, "rookie_rounds": 2, "scoring": "ppr", "user_slot": 4}), rookie_v=0)
    assert rules.pending_flags(old, []) == {"rookie_v": 1}
    snap, state, em = ru._dynasty((1, "offseason"), 4, ru.MODEL, old)
    plain = ru._dynasty(None, 4, ru.MODEL, old)[0]
    (entry,) = state.rules
    assert entry["flags"] == {"rookie_v": 1} and entry["bounds"] == {"rookie_v": "season"} and entry["view_from"] == 3
    view = snap.under(state.rules)
    for season in (1, 2):
        assert dict(view.season_view(season).players) == dict(plain.season_view(season).players)
    assert view.season_view(2).settings.rookie_v == 0 and view.season_view(3).settings.rookie_v == 1
    assert dict(view.season_view(3).players) != dict(plain.season_view(3).players)
    assert ru._replay(snap, em) == state.digest()
