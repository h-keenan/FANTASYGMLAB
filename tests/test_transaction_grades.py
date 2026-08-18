"""Deterministic retrospective grades — no fabricated production or history."""

from __future__ import annotations

from modules import transaction_grades as grades


LOOKUP = {
    "star": {"current_value": 5200, "name": "Star"},
    "ok": {"current_value": 4800, "name": "Solid"},
    "cheap": {"current_value": 1600, "name": "Streamer"},
    "bust": {"current_value": 300, "name": "Bust"},
}


def _trade(*, week=4, hist=None, receive_ids=("star",), send_ids=("ok",), extra=None):
    left_recv = [{"player_id": pid, "name": pid, "kind": "player"} for pid in receive_ids]
    right_recv = [{"player_id": pid, "name": pid, "kind": "player"} for pid in send_ids]
    if hist:
        for asset, value in zip(left_recv, hist[0]):
            asset["value_at_trade"] = value
        for asset, value in zip(right_recv, hist[1]):
            asset["value_at_trade"] = value
    tx = {
        "type": "trade",
        "transaction_id": "t1",
        "week": week,
        "timestamp": 100,
        "sides": [
            {"team_name": "War Room", "receives": left_recv},
            {"team_name": "Lakefront", "receives": right_recv},
        ],
    }
    if extra:
        tx.update(extra)
    return tx


def _waiver(*, week=4, player="cheap", faab=0, dropped_later=False):
    later = []
    if dropped_later:
        later = [
            {
                "type": "waiver",
                "timestamp": 200,
                "sides": [{"drops": [{"player_id": player, "kind": "player"}]}],
            }
        ]
    tx = {
        "type": "waiver",
        "transaction_id": "w1",
        "week": week,
        "timestamp": 100,
        "sides": [
            {
                "team_name": "War Room",
                "faab_spent": faab,
                "receives": [{"player_id": player, "name": player, "kind": "player"}],
            }
        ],
    }
    return tx, later


def test_balanced_trade_both_sides_b_range_not_zero_sum():
    report = grades.grade_trade(_trade(), player_lookup=LOOKUP, current_week=10)
    letters = [side["letter"] for side in report["sides"]]
    assert report["zero_sum"] is False
    assert all(letter.startswith("B") for letter in letters)
    assert not (set(letters) & {"A+", "A", "D", "F"})


def test_one_side_current_value_gain():
    report = grades.grade_trade(
        _trade(receive_ids=("star",), send_ids=("cheap",)),
        player_lookup=LOOKUP,
        current_week=10,
    )
    by_team = {side["team"]: side["letter"] for side in report["sides"]}
    assert by_team["War Room"] in {"A+", "A", "A-", "B+"}
    assert by_team["Lakefront"] in {"C+", "C", "C-", "D", "F"}


def test_both_sides_can_grade_positively_when_values_are_close():
    lookup = {
        "a": {"current_value": 4100},
        "b": {"current_value": 4300},
    }
    report = grades.grade_trade(
        _trade(receive_ids=("a",), send_ids=("b",)),
        player_lookup=lookup,
        current_week=12,
    )
    letters = [side["letter"] for side in report["sides"]]
    assert all(letter.startswith(("A", "B")) for letter in letters)


def test_recent_trade_is_pending():
    report = grades.grade_trade(_trade(week=9), player_lookup=LOOKUP, current_week=10)
    assert report["pending"] is True
    assert all(side["letter"] == grades.PENDING for side in report["sides"])


def test_missing_current_value_is_pending_not_invented():
    report = grades.grade_trade(
        _trade(receive_ids=("ghost",), send_ids=("star",)),
        player_lookup=LOOKUP,
        current_week=10,
    )
    assert report["pending"] is True
    joined = " ".join(side["why"] for side in report["sides"])
    assert "PPG" not in joined
    assert "fabricat" not in joined.casefold()


def test_historical_value_used_only_when_recorded():
    with_hist = grades.grade_trade(
        _trade(hist=([5000], [4000])),
        player_lookup=LOOKUP,
        current_week=10,
    )
    lenses = {lens["lens"] for side in with_hist["sides"] for lens in side["lenses"]}
    assert grades.LENS_VALUE_AT_TRADE in lenses
    without = grades.grade_trade(_trade(), player_lookup=LOOKUP, current_week=10)
    lenses2 = {lens["lens"] for side in without["sides"] for lens in side["lenses"]}
    assert grades.LENS_VALUE_AT_TRADE not in lenses2
    src = (grades.__file__ and open(grades.__file__, encoding="utf-8").read())
    assert "production" not in src.casefold() or "invent" in src.casefold()


def test_pick_heavy_trade_watch_unresolved():
    tx = _trade()
    tx["sides"][0]["receives"].append({"kind": "pick", "name": "2027 1st"})
    report = grades.grade_trade(tx, player_lookup=LOOKUP, current_week=10)
    assert any("Pick" in side["watch"] for side in report["sides"])


def test_zero_faab_useful_pickup_is_not_penalized():
    tx, later = _waiver(faab=0, player="cheap")
    paid = grades.grade_waiver(tx, player_lookup=LOOKUP, current_week=10, later_events=later)
    expensive = dict(tx)
    expensive["sides"] = [dict(tx["sides"][0], faab_spent=5)]
    paid_cost = grades.grade_waiver(expensive, player_lookup=LOOKUP, current_week=10)
    assert paid["letter"] != grades.PENDING
    assert grades.GRADE_SCALE.index(paid["letter"]) <= grades.GRADE_SCALE.index(paid_cost["letter"])
    assert "Zero-cost" in paid["why"]


def test_high_faab_bust_and_quick_drop():
    bust, _ = _waiver(faab=90, player="bust")
    report = grades.grade_waiver(bust, player_lookup=LOOKUP, current_week=10)
    assert report["letter"] in {"D", "F", "C-", "C"}
    dropped_tx, later = _waiver(faab=5, player="cheap", dropped_later=True)
    dropped = grades.grade_waiver(dropped_tx, player_lookup=LOOKUP, current_week=10, later_events=later)
    kept, _ = _waiver(faab=5, player="cheap")
    kept_report = grades.grade_waiver(kept, player_lookup=LOOKUP, current_week=10)
    assert grades.GRADE_SCALE.index(dropped["letter"]) > grades.GRADE_SCALE.index(kept_report["letter"])


def test_recent_waiver_pending():
    tx, later = _waiver(week=10, faab=0)
    report = grades.grade_waiver(tx, player_lookup=LOOKUP, current_week=10, later_events=later)
    assert report["letter"] == grades.PENDING
    assert report["pending"] is True


def test_grades_do_not_mutate_history_records():
    tx = _trade()
    snapshot = str(tx)
    grades.grade_transaction(tx, player_lookup=LOOKUP, current_week=10)
    assert str(tx) == snapshot
