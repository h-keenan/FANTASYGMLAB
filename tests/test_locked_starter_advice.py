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
