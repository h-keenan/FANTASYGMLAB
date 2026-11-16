"""Audit 2026-11 P1-1 / P1-2 regressions: one waiver verdict, absolute elite bar."""

import itertools

import pandas as pd

from modules import waivers_logic as wl


def _rank(scores, **extra):
    n = len(scores)
    fa = pd.DataFrame({
        "player_id": [f"p{i}" for i in range(n)],
        "position": ["RB", "WR"] * (n // 2),
        "score": scores,
        "waiver_actionable": [True] * n,
        **extra,
    })
    return wl.rank_priority_add_candidates(
        fa, score_field="score", needed_positions=[], league_settings={},
        roster_df=pd.DataFrame(), max_items=n,
    )


def test_no_need_third_on_wire_kicker_is_not_add():
    row = {"position": "K", "priority_need_fit": False, "priority_value_opportunity": False,
           "score": 5, "age": 31}
    label, tone, conf, reason = wl.waiver_recommendation(row, 3)
    assert label != "Add" and conf != "High"
    assert "#3 K on the wire" in reason


def test_need_filling_ninth_on_wire_is_add_and_confidence_agrees():
    row = {"position": "RB", "priority_need_fit": True, "score": 900, "age": 29}
    label, tone, conf, reason = wl.waiver_recommendation(row, 9)
    assert (label, tone, conf) == ("Add", "opportunity", "High")
    assert "need" in reason.lower() and "#9 RB" in reason


def test_junk_wire_gets_no_elite_but_real_wire_does():
    assert _rank([6, 5, 4, 3, 2, 1]).empty
    out = _rank([900, 850, 800, 700, 650, 600])
    assert out["priority_value_opportunity"].any()


def test_elite_uses_league_wide_rating_when_present():
    low = _rank([900, 850, 800, 700, 650, 600], _overall_rating_col=[50] * 6)
    assert low.empty
    high = _rank([900, 850, 800, 700, 650, 600], _overall_rating_col=[90] * 6)
    assert high["priority_value_opportunity"].any()


def test_label_and_confidence_never_contradict_over_grid():
    flags = [False, True]
    for need, value, stash, bigger, inj, stale, age, opp, rank, score in itertools.product(
        flags, flags, flags, flags, flags, flags, (22, 28, 33), ("", "Committee Back"), (1, 3, 9), (0, 40)
    ):
        row = {"priority_need_fit": need, "priority_value_opportunity": value,
               "priority_stash_for_need": stash, "priority_bigger_upgrade": bigger,
               "injury_replacement_fit": inj, "stale_free_agent": stale, "age": age,
               "opportunity_label": opp, "score": score, "position": "WR"}
        label, _tone, conf, reason = wl.waiver_recommendation(row, rank)
        assert reason
        if label == "Add":
            assert conf == "High"
        if label == "Watch":
            assert conf == "Low"
        if conf == "High":
            assert label == "Add"
        assert wl.waiver_recommendation_label(row, rank)[0] == label
        assert wl.waiver_confidence_label(row, rank)[0] == conf


def test_rank_never_decides_label():
    row = {"priority_need_fit": False, "priority_value_opportunity": False, "score": 40, "age": 28}
    assert {wl.waiver_recommendation(row, r)[0] for r in (1, 2, 3, 9, 30)} == {"Watch"}
