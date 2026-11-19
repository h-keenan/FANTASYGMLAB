from modules.wrapped_real_data import roster_season


def _wk(a, b, c, bench=False):
    return [
        {"roster_id": 1, "matchup_id": 1, "points": a, "starters": ["x"], "players_points": {"x": a, "y": 20.0, "z": 5.0} if bench else None},
        {"roster_id": 2, "matchup_id": 1, "points": b, "starters": [], "players_points": None},
        {"roster_id": 3, "matchup_id": 2, "points": c, "starters": [], "players_points": None},
        {"roster_id": 4, "matchup_id": 2, "points": 50.0, "starters": [], "players_points": None},
    ]


def test_expected_wins_and_bench():
    future = [{"roster_id": r, "matchup_id": 1, "points": 0, "starters": []} for r in (1, 2, 3, 4)]
    out = roster_season([_wk(100, 90, 80, True), _wk(60, 70, 80, True), future], 1)
    assert out["games"] == 2  # the all-zero future week is skipped
    assert out["actual_wins"] == 1.0
    assert out["expected_wins"] == 1.33
    assert out["diff"] < 0
    assert out["bench"] == {"available": True, "total": 50.0, "best": {"week": 1, "player_id": "y", "pts": 20.0}}


def test_no_bench_data_is_not_invented():
    out = roster_season([_wk(100, 90, 80)], 1)
    assert out["bench"] == {"available": False, "total": None, "best": None}
