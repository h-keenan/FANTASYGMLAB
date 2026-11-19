"""Golden test: the weekly lineup solves are shared, the numbers are not.

``trade_lineup_model.run_weeks`` solves every roster's lineup for every week and
availability scenario. The baseline ("before") side of those solves is the same
for every candidate trade/swap built on one roster, so it is solved once and
reused. This test pins the complete ``evaluate_trade`` / ``swap_score`` output
of several fixture leagues (different slots, postures, injuries, flex rules) to
a file captured from the implementation that solved every lineup from scratch;
sharing must not move a single digit.

Regenerate (only for an intentional model change, never for a perf change):
    LINEUP_GOLDEN_REGEN=1 pytest tests/test_lineup_solve_golden.py
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import test_drop_candidates as tdc
import test_performance_equivalence as tpe
from modules import roster_value_model as rvm

GOLDEN = Path(__file__).parent / "fixtures" / "lineup_solve_golden.json"


@pytest.fixture(autouse=True)
def _byes(monkeypatch):
    from modules import nfl_schedule

    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99)


def _leagues():
    out = {"base_retool": tpe._league()}
    roster = tdc._core() + [
        tdc._row("BN_WR", "WR", 700, ppg=4, age=30),
        tdc._row("INJ_RB", "RB", 3000, ppg=9, injury="Out", age=27),
        tdc._row("Q_WR", "WR", 2600, ppg=8, injury="Questionable", age=28),
        tdc._row("D_TE", "TE", 2200, ppg=6, injury="Doubtful", age=29),
        tdc._row("Q_RB", "RB", 2800, ppg=7, injury="Questionable", age=25),
        tdc._row("Q_QB", "QB", 2300, ppg=9, injury="Questionable", age=33),
    ]
    pool = tdc._pool(("WR", 1500, 9), ("RB", 1200, 8), ("TE", 900, 6), ("QB", 800, 7), ("WR", 1100, 7.5))
    pool.append(tdc._row("FA_Q", "RB", 1000, ppg=7, injury="Questionable", age=25))
    for name, strat in (("injury_contend", "contend"), ("injury_rebuild", "rebuild")):
        out[name] = tdc._make(roster, pool, limit=len(roster), strategy=strat)
    out["superflex"] = tdc._make(
        roster + [tdc._row("SF_QB", "QB", 4000, ppg=15, age=28)], pool,
        settings=tdc.SF_SETTINGS, positions=tdc.SF_POSITIONS, limit=len(roster) + 1,
    )
    out["no_pool"] = tdc._make(roster, (), limit=len(roster), strategy="contend")
    return out


def _cases(rvc):
    ids = [str(p) for p in rvc.frame["player_id"]]
    pool = {}
    if rvc.pool is not None and not rvc.pool.empty:
        pool = {r["player_id"]: r for r in rvc.pool.to_dict("records")}
    adds = [None, *[pool[k] for k in sorted(pool)[:4]]]
    drops = [[], *[[p] for p in ids], [ids[0], ids[-1]], [ids[3], ids[5], ids[9]], ["NOT_ON_ROSTER"]]
    for d in drops:
        for a in adds:
            yield d, ([a] if a is not None else [])


def _snapshot():
    snap = {}
    for name, rvc in _leagues().items():
        rows = []
        for drops, add_rows in _cases(rvc):
            full = rvm.evaluate_swap(rvc, drops, add_rows)
            payload = {"full": full}
            if not add_rows:
                payload["score"] = rvm.swap_score(rvc, drops)
            digest = hashlib.sha256(json.dumps(payload, default=repr, sort_keys=True).encode()).hexdigest()[:16]
            rows.append([",".join(drops), ",".join(r["player_id"] for r in add_rows), full["trade_score"], digest])
        snap[name] = rows
    return json.loads(json.dumps(snap))


def test_lineup_solve_sharing_leaves_every_number_unchanged():
    got = _snapshot()
    if os.environ.get("LINEUP_GOLDEN_REGEN"):
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(json.dumps(got, sort_keys=True, indent=0))
        pytest.skip("regenerated")
    want = json.loads(GOLDEN.read_text())
    assert sum(len(v) for v in got.values()) >= 200
    assert got == want
