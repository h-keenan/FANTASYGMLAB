from modules.live_activity import build_live_activity_snapshot


def _matchup(game_state="live", live=True):
    side = lambda n, p: {"team_name": n, "real_points": p, "has_live_data": live}  # noqa: E731
    return {
        "week": 8,
        "reason": "",
        "my_team": side("Me", 71.5),
        "opponent": side("Them", 64.0),
        "real_comparison": {"margin": 7.5} if live else None,
        "game_state": game_state,
        "win_probability": {"available": True, "probability": 0.62},
    }


def test_live_snapshot_uses_real_points_only():
    snap = build_live_activity_snapshot(_matchup())
    assert snap["available"] and snap["should_run"]
    assert snap["me"]["points"] == 71.5 and snap["opponent"]["points"] == 64.0
    assert snap["margin"] == 7.5 and snap["win_probability"] == 0.62


def test_no_live_data_is_unavailable_not_zero():
    snap = build_live_activity_snapshot(_matchup(live=False))
    assert not snap["available"] and not snap["should_run"]
    assert snap["reason"] == "no_live_data"
    assert snap["me"]["points"] is None


def test_final_and_pregame_do_not_run():
    assert not build_live_activity_snapshot(_matchup("final"))["should_run"]
    assert not build_live_activity_snapshot(_matchup("pregame"))["should_run"]


def test_empty_matchup_passthrough_reason():
    snap = build_live_activity_snapshot({"week": 3, "reason": "bye_week", "my_team": None, "opponent": None})
    assert snap["reason"] == "bye_week" and not snap["available"]
