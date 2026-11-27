"""Regression: a starter who went Out mid-game (his game already started) is
locked, so no advice surface may tell the owner to bench/swap him. The same
player pre-kickoff still gets the advice. See modules/lineup_lock.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from modules import lineup_lock, matchup_what_if, push_triggers, this_week


def test_lineup_lock_helper_only_trusts_an_explicit_started_flag():
    assert lineup_lock.is_locked({"game_started": True}) is True
    assert lineup_lock.is_locked({"game_started": False}) is False
    assert lineup_lock.is_locked({"game_started": None}) is False
    assert lineup_lock.is_locked({}) is False
    assert lineup_lock.is_locked(None) is False
    assert lineup_lock.any_locked({"game_started": False}, None, {"game_started": True}) is True
    assert matchup_what_if._is_locked({"game_started": True}) is True


def _this_week_row(locked):
    rows = {
        "1": {"name": "Woody Marks", "position": "RB", "status": "Active", "injury_status": "Out"},
        "2": {"name": "Bench RB", "position": "RB", "status": "Active", "injury_status": ""},
    }
    return this_week.build_this_week(
        league={"status": "in_season", "settings": {"leg": 7, "trade_deadline": 12}},
        roster={"starters": ["1"]},
        roster_rows=rows,
        bye_player_ids=[],
        locked_player_ids=locked,
        items=[],
        trade_records=None,
    )["rows"][0]


def test_today_todo_does_not_say_to_bench_a_locked_out_starter():
    pre = _this_week_row([])
    assert pre["tone"] == "risk" and "Woody Marks is out" in pre["headline"]
    locked = _this_week_row(["1"])
    assert locked["tone"] == "positive" and "Woody Marks" not in locked["headline"]
    assert "locked" in locked["why"].lower()


def _matchup_moves(started):
    from services import mobile_api_service as svc

    def mv(pid, injury, started_flag):
        return {
            "player_id": pid,
            "name": pid,
            "position": "RB",
            "slot": "RB",
            "game_started": started_flag,
            "injury_status": injury,
            "ruled_out": bool(injury),
            "projection": {"status": "ok", "expected_points": 0.0 if injury else 10.0, "low": 5, "high": 15},
        }

    side = {
        "has_live_data": True,
        "starters": [mv("bench", "", False)],
        "real_starters": [mv("woody", "Out", started)],
        "real_empty_slots": [],
    }
    return svc._suggested_lineup_moves(side)


def test_matchup_moves_never_swap_a_locked_starter_but_do_pre_kickoff():
    assert _matchup_moves(True) == []
    pre = _matchup_moves(False)
    assert len(pre) == 1 and pre[0]["locked"] is False


def test_lineup_lock_push_skips_an_out_starter_whose_game_started():
    now = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
    df = pd.DataFrame([{"player_id": "1", "name": "Woody Marks", "team": "HOU", "injury_status": "Out"}])

    def run(kickoff):
        game = {"kickoff_at": kickoff.isoformat()}
        with patch.object(push_triggers.nfl_schedule, "team_matchup_for_week", return_value=game), patch.object(
            push_triggers.nfl_schedule, "team_bye_week", return_value=None
        ):
            return push_triggers.lineup_lock_push_items(
                league_id="L",
                league_name="L",
                league={"status": "in_season", "season": "2026", "settings": {"leg": 10}},
                my_roster={"starters": ["1"], "players": ["1"]},
                players_df=df,
                games=pd.DataFrame([{"x": 1}]),
                now=now,
            )

    assert run(now + timedelta(minutes=30))
    assert run(now - timedelta(minutes=30)) == []


# --- lock-aware lineup issues: modules/lineup_lock.py is the one rule --------------------------------------------


def _starter(**kw):
    return {"ruled_out": True, "injury_label": "Out", "game_started": False, "game_locked": False, **kw}


def test_out_before_kickoff_is_an_actionable_issue_not_left_game():
    p = _starter()
    assert lineup_lock.is_actionable_issue(p) is True
    assert lineup_lock.left_game(p) is False


def test_injured_mid_game_is_locked_information_not_an_issue():
    p = _starter(game_started=True, game_locked=True)
    assert lineup_lock.is_actionable_issue(p) is False
    assert lineup_lock.left_game(p) is True


def test_final_game_is_not_an_issue():
    # game_has_started is True once the game is played, so a final game is locked too.
    assert lineup_lock.is_actionable_issue(_starter(game_started=True)) is False


def test_missing_kickoff_never_invents_a_lock():
    p = _starter(game_started=None)
    assert lineup_lock.is_locked(p) is False
    assert lineup_lock.is_actionable_issue(p) is True


def test_bye_is_actionable_and_never_locked():
    p = {"on_bye": True, "start_ineligible_reason": "Bye", "game_started": True}
    assert lineup_lock.is_locked(p) is False
    assert lineup_lock.is_actionable_issue(p) is True


def test_game_started_reason_is_a_lock_not_a_problem():
    assert lineup_lock.is_actionable_issue({"start_ineligible_reason": "Game started", "game_locked": True}) is False


def test_lineup_rows_carry_the_shared_verdicts_for_a_mixed_lineup():
    import pandas as pd
    from services import mobile_api_service as svc

    def row(pid, started):
        return pd.Series({"player_id": pid, "name": pid, "ruled_out": True, "injury_status": "Out", "status": "Active",
                          "game_locked": started, "slot": "FLEX", "suggested_starter": True})

    locked = svc._project_lineup_row(row("hurt_mid_game", True), "score", reserve_ids=set(), taxi_ids=set())
    open_ = svc._project_lineup_row(row("out_pre_kickoff", False), "score", reserve_ids=set(), taxi_ids=set())
    assert (locked["lineup_issue"], locked["left_game"]) == (False, True)
    assert (open_["lineup_issue"], open_["left_game"]) == (True, False)


def test_commissioner_lineup_does_not_flag_a_locked_hurt_starter():
    from modules import commissioner_lineups

    def player(pid, started):
        return {"player_id": pid, "name": pid, "slot": "FLEX", "status": "Active", "injury_status": "Out", "game_started": started}

    row = commissioner_lineups.build_team_row(
        roster_id="1", team_name="T", owner_name=None, avatar_url=None,
        real={"real_starters": [player("locked", True), player("open", False)], "real_empty_slots": [], "has_live_data": True},
        suggested_starters=[], moves=[], projection_ready=False,
    )
    assert [f["player"] for f in row["flags"]] == ["open"]
    assert [i["player"] for i in row["info"]] == ["locked"]
