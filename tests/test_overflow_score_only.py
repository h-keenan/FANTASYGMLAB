"""Round 4: ``drops_for_overflow`` ranks candidate cuts on ``rvm.swap_score`` (the lineup model's ``trade_score`` without the
informational future-year / confidence / position story) and builds the full verdict for the winner only. The chosen cuts and
every number in the plan must equal the original all-full-evaluation selection, for every posture."""

from __future__ import annotations

import pytest

from modules import drop_candidates as dc
from modules import roster_value_model as rvm
from tests.test_drop_candidates import _byes, _core, _make, _row  # noqa: F401
from tests.test_trade_roster_overflow import _bench, _incoming


def _reference_drops(rvc, *, need, protect_ids, untouchable, usage):
    """The pre-Round-4 selection: a full ``evaluate_swap`` per candidate, strictly-greater score wins."""

    dropped: list[str] = []
    for _ in range(need):
        ids, _ = dc.candidate_pool(rvc, untouchable=untouchable, usage=usage, exclude=set(dropped) | set(protect_ids), dropped=dropped)
        if not ids:
            break
        best_id, best = None, None
        for pid in sorted(ids, key=lambda p: (rvc.healthy_value.get(p, 0.0), p))[: dc.CANDIDATES_PER_ADD * 2]:
            res = rvm.evaluate_swap(rvc, [*dropped, pid], ())
            if best is None or res["trade_score"] > best["trade_score"]:
                best_id, best = pid, res
        dropped.append(best_id)
    return dropped


@pytest.mark.parametrize("strategy", ["contend", "retool", "rebuild"])
@pytest.mark.parametrize("n_bench,need", [(4, 1), (6, 2), (9, 3), (12, 4)])
def test_ranked_cuts_equal_the_full_evaluation_selection(strategy, n_bench, need):
    roster = _core() + _bench(n_bench) + [_row("OLD", "RB", 900, ppg=2, age=33), _row("YNG", "WR", 1100, ppg=1, age=21)]
    incoming = _incoming(need)
    rvc_a = _make(roster, strategy=strategy, limit=len(roster))
    rvc_b = _make(roster, strategy=strategy, limit=len(roster))
    protect = {r["player_id"] for r in incoming}
    new = dc.drops_for_overflow(rvc_a, need=need, protect_ids=protect, untouchable=set(), usage={})
    ref = _reference_drops(rvc_b, need=need, protect_ids=protect, untouchable=set(), usage={})
    assert new["dropped_ids"] == ref and len(ref) == need
    final = rvm.evaluate_swap(rvc_b, ref, ())
    assert new["effect"] == dc._effect(final)


@pytest.mark.parametrize("strategy", ["contend", "retool", "rebuild"])
def test_swap_score_is_bit_identical_to_the_full_verdict_score(strategy):
    roster = _core() + _bench(6)
    rvc = _make(roster, strategy=strategy, limit=len(roster))
    for drop in (["B0"], ["B0", "B3"], ["RD1"], ["WD2", "TE2"], ["QB2"]):
        fast = rvm.swap_score(rvc, drop)
        full = rvm.evaluate_swap(_make(roster, strategy=strategy, limit=len(roster)), drop, ())["trade_score"]
        assert fast == full
