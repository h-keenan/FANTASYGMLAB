"""Waivers: an add that is worth far more lineup points than anything at the
biggest need must not be buried behind the need-fit adds.

Owner question (coridian_): the team has a mild need at one position, while a
much better add sits on the wire at another. One shared rule
(``roster_value_model.outsized_adds``) flags it, the Priority Adds rank it first
and carry ``priority_bigger_upgrade``; which position is labelled a need never
changes, and the drop engine prices the same add with the same swap.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import drop_candidates as dc
from modules import roster_value_model as rvm
from modules import waivers_logic
from tests.test_drop_candidates import _byes, _core, _make, _row  # noqa: F401  (autouse fixture is shared)


def _table(my_qb=15.5):
    table = {
        str(t): {"QB": [15.0 + t * 0.5, 8.0], "RB": [18.0, 14.0], "WR": [16.0, 13.0, 11.0], "TE": [10.0]}
        for t in range(2, 13)
    }
    table["1"] = {"QB": [my_qb, 6.0], "RB": [24.0, 20.0], "WR": [22.0, 20.0, 18.0], "TE": [14.0]}
    return table


def _qb(pid, ppg):
    return _row(pid, "QB", 1500, ppg=ppg, age=26, depth_chart_order=1, workload_trend="Stable")


def _rb(pid, ppg, value=3000):
    return _row(pid, "RB", value, ppg=ppg, age=24, workload_trend="Stable")


def _wire(pool):
    df = pd.DataFrame(list(pool))
    df["stale_free_agent"] = False
    df["injury_replacement_fit"] = False
    return df


def _scenario(fa_qb_ppg, fa_rb_ppg, *, roster=None):
    pool = [_qb("FA_QB", fa_qb_ppg), _rb("FA_RB", fa_rb_ppg)]
    roster = roster or [r if r["player_id"] != "QB1" else _row("QB1", "QB", 3500, ppg=15.5) for r in _core()]
    rvc = _make(roster, pool)
    needs = rvm.assess_needs(rvc, _table(), "1", dynasty=True)
    ranked = waivers_logic.rank_priority_add_candidates(
        _wire(pool), score_field="dynasty_score", needed_positions=needs["needed_positions"],
        league_settings={}, roster_df=rvc.frame, needs_model=needs,
    )
    return rvc, needs, ranked


def test_much_bigger_off_need_add_ranks_first_with_the_flag_and_the_need_label_is_unchanged():
    rvc, needs, ranked = _scenario(18.0, 21.0)
    qb = next(p for p in needs["positions"] if p["position"] == "QB")
    rb = next(p for p in needs["positions"] if p["position"] == "RB")
    # Which position is the need does not move: QB stays the biggest need.
    assert needs["biggest_need"] == "QB"
    assert rb["wire"][0]["ppw"] >= 1.5 and 0.25 <= qb["wire"][0]["ppw"] < 1.0
    assert [o["player_id"] for o in needs["outsized_adds"]] == ["FA_RB"]
    assert list(ranked["player_id"])[0] == "FA_RB"
    top = ranked.iloc[0]
    assert bool(top["priority_bigger_upgrade"])
    assert not bool(ranked[ranked["player_id"] == "FA_QB"].iloc[0]["priority_bigger_upgrade"])
    # The headline stays one short sentence plus one short clause.
    headline = waivers_logic.align_headline_with_adds(needs, ranked)
    assert headline.startswith("Biggest need: QB") and "top add is RB FA_RB (+" in headline
    assert len(headline) < 200


def test_close_gains_keep_the_need_order_no_flip_flop():
    # RB (+0.7) beats the QB fix (+0.5) but not by the margin: need order stands.
    _rvc, needs, ranked = _scenario(18.0, 13.0)
    assert needs["outsized_adds"] == []
    assert list(ranked["player_id"])[0] == "FA_QB"
    assert not ranked["priority_bigger_upgrade"].any()


@pytest.mark.parametrize("need_ppw,expected", [
    (0.0, 1.0),      # nothing at the need helps: absolute floor
    (0.5, 1.25),     # need + margin (0.75) dominates
    (2.0, 3.0),      # 1.5x dominates for big need fixes
])
def test_threshold_is_the_larger_of_floor_margin_and_ratio(need_ppw, expected):
    assert rvm.outsized_threshold(need_ppw) == pytest.approx(expected)


def _positions(need_ppw, other_ppw, *, verdict="upgrade"):
    def entry(pos, tier, ppw):
        wire = [{"player_id": f"FA_{pos}", "name": f"FA_{pos}", "position": pos, "ppg": 10.0, "ppw": ppw, "ros": ppw * 10}]
        return {"position": pos, "tier": tier, "upgrade": {"ppw": ppw}, "wire": wire if ppw > 0 else [],
                "wire_verdict": verdict}
    return [entry("QB", "secondary", need_ppw), entry("RB", "covered", other_ppw)]


def test_margin_edges_are_inclusive_at_the_threshold():
    below = rvm.outsized_adds(_positions(0.5, 1.24), "QB")
    at = rvm.outsized_adds(_positions(0.5, 1.25), "QB")
    assert below == [] and [o["player_id"] for o in at] == ["FA_RB"]
    assert at[0]["over_position"] == "QB" and at[0]["over_ppw"] == 0.5


def test_unknown_wire_or_no_need_flags_nothing():
    assert rvm.outsized_adds(_positions(0.5, 3.0, verdict="unknown"), "QB") == []
    assert rvm.outsized_adds(_positions(0.5, 3.0), None) == []


def test_without_a_model_nothing_is_flagged_or_reordered():
    pool = [_qb("FA_QB", 18.0), _rb("FA_RB", 21.0)]
    rvc = _make([r for r in _core()], pool)
    ranked = waivers_logic.rank_priority_add_candidates(
        _wire(pool), score_field="dynasty_score", needed_positions=["QB"], league_settings={}, roster_df=rvc.frame,
    )
    assert "priority_bigger_upgrade" not in ranked.columns or not ranked["priority_bigger_upgrade"].any()


def test_degraded_surface_without_free_agent_data_has_no_outsized_adds():
    rvc = _make([r if r["player_id"] != "QB1" else _row("QB1", "QB", 3500, ppg=15.5) for r in _core()], [])
    rvc.pool = None
    needs = rvm.assess_needs(rvc, _table(), "1", dynasty=True)
    assert needs["outsized_adds"] == []


def test_drop_engine_prices_the_flagged_add_and_never_cuts_a_protected_player():
    # Roster full: the flagged RB needs a cut. Surplus WR depth is the sensible
    # cut; the starters and the untouchable are never named.
    roster = [r if r["player_id"] != "QB1" else _row("QB1", "QB", 3500, ppg=15.5) for r in _core()]
    roster += [_row("SPARE_WR", "WR", 600, ppg=3, age=31), _row("SPARE_RB", "RB", 650, ppg=3, age=31)]
    pool = [_qb("FA_QB", 18.0), _rb("FA_RB", 21.0)]
    rvc = _make(roster, pool, limit=len(roster))
    needs = rvm.assess_needs(rvc, _table(), "1", dynasty=True)
    assert [o["player_id"] for o in needs["outsized_adds"]] == ["FA_RB"]
    add = rvc.pool[rvc.pool["player_id"] == "FA_RB"].iloc[0].to_dict()
    result = dc.suggest_drop_for_add(rvc, add, untouchable={"SPARE_RB"}, usage={})
    assert result["status"] == "ok" and result["drop"] is not None
    named = {result["drop"]["player_id"], *(a["player_id"] for a in result["alternatives"])}
    assert named <= {"SPARE_WR", "SPARE_RB"} - {"SPARE_RB"}
    # It is the same swap the ranking priced: the lineup points gain is positive.
    assert result["drop"]["effect"]["lineup_points_per_week"] > 0
