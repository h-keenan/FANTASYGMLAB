"""Opponent profile card: pure reads over the league's per-room scores."""

from __future__ import annotations

import pandas as pd

from modules import opponent_profile as op


def _summary():
    rows = []
    for i in range(1, 7):
        rows.append(
            {
                "roster_id": i,
                "qb_score": 1000 * (7 - i),  # roster 1 best QB
                "rb_score": 1000 * i,  # roster 6 best RB
                "wr_score": 5000,
                "te_score": 100 * i,
            }
        )
    return pd.DataFrame(rows)


def test_position_ranks_rank_each_room_within_league():
    ranks = {r["position"]: r for r in op.position_ranks(_summary(), 1)}
    assert ranks["QB"]["rank"] == 1
    assert ranks["RB"]["rank"] == 6
    assert ranks["WR"]["rank"] == 1  # all tied -> shared best rank
    assert ranks["QB"]["of"] == 6


def test_position_ranks_unknown_roster_is_empty():
    assert op.position_ranks(_summary(), 99) == []


def test_room_reads_surplus_needs_and_strongest_weakest():
    ranks = op.position_ranks(_summary(), 1)
    rooms, surplus, needs = op.room_reads(ranks, {"QB": "covered", "RB": "short_term_need", "TE": "covered"})
    assert "QB" in surplus
    assert "RB" in needs
    strongest, weakest = op.strongest_weakest(rooms)
    assert weakest["rank"] == 6
    assert strongest["position"] in {"QB", "WR"}


def test_surplus_requires_covered_room():
    ranks = op.position_ranks(_summary(), 1)
    _rooms, surplus, needs = op.room_reads(ranks, {"QB": "short_term_need"})
    assert "QB" not in surplus
    assert "QB" in needs


def test_tiny_league_has_no_rank_reads():
    small = _summary().head(3)
    rooms, surplus, needs = op.room_reads(op.position_ranks(small, 1), {})
    assert surplus == [] and needs == []
    assert op.strongest_weakest(rooms) == (None, None)
    assert op.starter_bench_read(1, 3, 3) is None


def test_starter_bench_read_labels():
    assert op.starter_bench_read(1, 10, 12)["label"] == "Starter-heavy"
    assert op.starter_bench_read(10, 1, 12)["label"] == "Deep bench"
    assert op.starter_bench_read(5, 6, 12)["label"] == "Balanced"
    assert op.starter_bench_read(None, 6, 12) is None


def _lineup():
    return pd.DataFrame(
        [
            {"player_id": "1", "name": "A", "position": "RB", "team": "KC", "value_score": 900, "suggested_starter": True},
            {"player_id": "2", "name": "B", "position": "RB", "team": "KC", "value_score": 500, "suggested_starter": False},
            {"player_id": "3", "name": "C", "position": "RB", "team": "KC", "value_score": 700, "suggested_starter": False},
            {"player_id": "4", "name": "D", "position": "WR", "team": "KC", "value_score": 0, "suggested_starter": False},
        ]
    )


def test_bench_candidates_excludes_starters_and_zero_value():
    bench = op.bench_candidates(_lineup(), "value_score")
    assert [p["player_id"] for p in bench["RB"]] == ["3", "2"]
    assert "WR" not in bench


def test_trade_angle_receive_and_send_and_none():
    their_bench = op.bench_candidates(_lineup(), "value_score")
    angle = op.trade_angle(
        my_needs=["RB"], my_surplus=[], their_needs=[], their_surplus=["RB"], their_bench=their_bench, my_bench={}
    )
    assert angle["target"]["player_id"] == "3"
    assert angle["target"]["side"] == "receive"
    assert "short at RB" in angle["text"]

    angle = op.trade_angle(
        my_needs=[], my_surplus=["RB"], their_needs=["RB"], their_surplus=[], their_bench={}, my_bench=their_bench
    )
    assert angle["target"]["side"] == "send"

    assert (
        op.trade_angle(my_needs=["QB"], my_surplus=[], their_needs=[], their_surplus=["RB"], their_bench={}, my_bench={})
        is None
    )


def test_trade_angle_without_bench_player_has_text_but_no_target():
    angle = op.trade_angle(
        my_needs=["RB"], my_surplus=[], their_needs=[], their_surplus=["RB"], their_bench={}, my_bench={}
    )
    assert angle["target"] is None


def test_pick_capital_hides_when_unknown():
    assert op.pick_capital({}, None, 12) is None
    cap = op.pick_capital({"draft_capital_rank": 2, "pick_count": 7, "first_rounders": 3}, {"firsts_acquired": 2}, 12)
    assert cap == {
        "rank": 2,
        "of": 12,
        "pick_count": 7,
        "first_rounders": 3,
        "firsts_acquired": 2,
        "firsts_sent": 0,
    }


def test_trade_angle_picks_widest_gap_room_with_a_bench_player():
    bench = {
        "RB": [{"player_id": "r", "name": "R", "position": "RB", "team": "", "_value": 1.0}],
        "WR": [{"player_id": "w", "name": "W", "position": "WR", "team": "", "_value": 1.0}],
    }
    angle = op.trade_angle(
        my_needs=["RB", "WR"],
        my_surplus=[],
        their_needs=[],
        their_surplus=["RB", "WR"],
        their_bench=bench,
        my_bench={},
        my_ranks={"RB": 8, "WR": 12},
        their_ranks={"RB": 1, "WR": 2},
    )
    assert angle["target"]["player_id"] == "w"  # WR gap 10 beats RB gap 7
    assert "short at WR" in angle["text"] and "RB" not in angle["text"]
