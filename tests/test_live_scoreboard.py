"""Real game clock (ESPN scoreboard) -> remaining share, projected final, feed."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modules import live_big_plays as lbp
from modules import live_scoreboard as sb
from modules.matchup_win_probability import (
    compute_live_win_probability,
    game_fraction_remaining,
    projected_final,
)

KICKOFF = datetime(2026, 11, 20, 1, 15, tzinfo=timezone.utc)


def _event(state, name, period, clock_s, display, *, home=("HOU", "34", 14), away=("IND", "11", 3), down=None):
    return {
        "status": {"clock": clock_s, "displayClock": display, "period": period, "type": {"state": state, "name": name}},
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "score": str(home[2]), "team": {"abbreviation": home[0], "id": home[1]}},
                    {"homeAway": "away", "score": str(away[2]), "team": {"abbreviation": away[0], "id": away[1]}},
                ],
                "situation": {"downDistanceText": down or "2nd & 7 at HOU 25", "possession": home[1]},
            }
        ],
    }


def _board(*events, week=11):
    return sb.parse_scoreboard({"week": {"number": week}, "events": list(events)})


@pytest.mark.parametrize(
    "period,clock,expected",
    [(1, 900, 1.0), (1, 450, 0.875), (2, 392, 0.6089), (3, 900, 0.5), (4, 0, 0.0), (4, 300, 0.0833)],
)
def test_fraction_remaining_from_real_clock(period, clock, expected):
    assert sb.fraction_remaining(period, clock, "in") == pytest.approx(expected, abs=1e-3)


def test_halftime_overtime_final_and_not_started():
    assert sb.fraction_remaining(2, 0, "in", halftime=True) == 0.5
    assert sb.fraction_remaining(5, 600, "in") == sb.OVERTIME_FRACTION_REMAINING > 0
    assert sb.fraction_remaining(4, 0, "post") == 0.0
    assert sb.fraction_remaining(0, 0, "pre") is None
    assert sb.clock_label(2, "5:54", "in") == "Q2 5:54"
    assert sb.clock_label(2, "0:00", "in", halftime=True) == "Half"
    assert sb.clock_label(5, "9:12", "in") == "OT 9:12"
    assert sb.clock_label(4, "0:00", "post") == "Final"
    assert sb.clock_label(0, "0:00", "pre") is None


def test_parse_scoreboard_both_sides_scores_and_situation():
    board = _board(_event("in", "STATUS_IN_PROGRESS", 2, 392, "6:32"))
    hou, ind = board["teams"]["HOU"], board["teams"]["IND"]
    assert hou["label"] == "Q2 6:32" and hou["team_score"] == 14 and hou["opponent_score"] == 3
    assert ind["team_score"] == 3 and ind["opponent"] == "HOU" and ind["is_home"] is False
    assert hou["situation"] == "2nd & 7 at HOU 25" and hou["has_ball"] is True and ind["has_ball"] is False
    assert board["week"] == 11


def test_team_info_requires_matching_week_and_normalizes_codes():
    board = _board(_event("in", "STATUS_IN_PROGRESS", 1, 100, "1:40", home=("WSH", "28", 0), away=("LAR", "14", 0)))
    assert sb.team_info(board, "WAS", 11)["opponent"] == "LAR"
    assert sb.team_info(board, "WAS", 12) is None
    assert sb.team_info(None, "WAS", 11) is None


def test_flag_off_returns_no_board(monkeypatch):
    monkeypatch.setenv(sb.FLAG, "0")
    assert sb.current_board() is None


def test_bad_payload_fails_open():
    assert sb.parse_scoreboard(None) is None
    assert sb.parse_scoreboard({"events": [{"bogus": 1}]}) == {"week": None, "teams": {}}


def _starter(actual, *, remaining=None, started=True, final=False, mean=15.0, now_kick=KICKOFF, **extra):
    return {
        "actual_points": actual,
        "game_started": started,
        "game_final": final,
        "game_kickoff_at": now_kick.isoformat(),
        "game_remaining": remaining,
        "projection": {"status": "ok", "point_estimate": mean, "low": mean - 7, "high": mean + 7},
        **extra,
    }


def test_real_clock_beats_wall_clock():
    # Wall clock 30 min after kickoff says ~84% left; the real clock says halftime.
    now = KICKOFF + timedelta(minutes=30)
    assert game_fraction_remaining(_starter(5.0), now=now) == pytest.approx(1 - 30 / 190, abs=1e-3)
    assert game_fraction_remaining(_starter(5.0, remaining=0.5), now=now) == 0.5


def test_projected_final_golden_blend_across_the_game():
    now = KICKOFF + timedelta(minutes=60)
    # Not started: no live projection.
    assert projected_final(_starter(0.0, started=False), now=now) is None
    # On pace at the half: 7.5 + 0.5 * 15 = 15.0 (pace gap is zero).
    assert projected_final(_starter(7.5, remaining=0.5), now=now) == 15.0
    # Hot start at the half: 12 actual, expected 7.5, gap 4.5, weight 0.25 -> 12 + 7.5 + 0.25*4.5*0.5.
    assert projected_final(_starter(12.0, remaining=0.5), now=now) == pytest.approx(12 + 7.5 + 0.5625, abs=0.05)
    # Early Q1 with 90% left leans almost fully on the pregame projection.
    assert projected_final(_starter(0.0, remaining=0.9), now=now) == pytest.approx(13.5, abs=0.3)
    # OT keeps a small live remainder rather than going blank.
    ot = projected_final(_starter(16.0, remaining=sb.OVERTIME_FRACTION_REMAINING), now=now)
    assert ot is not None and 16.0 < ot < 17.5
    # Final: nothing to project.
    assert projected_final(_starter(18.0, final=True, remaining=0.0), now=now) is None
    # Exited / injured mid-game: projected final is what he has.
    assert projected_final(_starter(6.0, remaining=0.5, exited_game=True), now=now) == 6.0
    assert projected_final(_starter(6.0, remaining=0.5, injury_status="Out"), now=now) == 6.0


def test_win_probability_uses_the_real_clock():
    mine = [_starter(20.0, remaining=0.1)]
    theirs = [_starter(10.0, remaining=0.1)]
    late = compute_live_win_probability(mine, theirs)
    early_mine = [_starter(20.0, remaining=0.9)]
    early_theirs = [_starter(10.0, remaining=0.9)]
    early = compute_live_win_probability(early_mine, early_theirs)
    assert late["available"] and early["available"]
    assert late["probability"] > early["probability"]


def test_bye_week_has_no_clock():
    assert game_fraction_remaining({"game_started": None, "game_kickoff_at": None}) == 1.0
    assert projected_final({"game_started": None, "actual_points": 0.0}) is None


# ---- live feed ----

SCORING = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "rush_td": 6.0, "pass_td": 4.0, "pass_int": -2.0}


def _snap(stats, clock="Q2 6:32"):
    return lbp.snapshot_from_sides(
        [("1", [{"player_id": "p1", "name": "C. Stroud", "position": "QB", "team": "HOU", "game_started": True,
                 "actual_points": 9.0, "stats": stats, "game_clock_label": clock}])]
    )


def test_so_far_events_read_the_current_line_honestly():
    events = lbp.so_far_events(_snap({"pass_td": 2, "pass_int": 1, "pass_yd": 118}), now=1000.0, scoring_settings=SCORING)
    assert len(events) == 1
    e = events[0]
    assert e["description"] == "2 TD so far, 1 turnover so far" and e["so_far"] and e["approx"]
    assert e["clock"] == "Q2 6:32" and e["points"] == 6.0  # 2 TD * 4 - 1 INT * 2
    assert lbp.so_far_events(_snap({"pass_yd": 300}), now=1.0, scoring_settings=SCORING) == []


def test_events_carry_the_clock():
    events = lbp.derive_events(_snap({"rec": 3}, "Q1 9:00"), _snap({"rec": 4, "rec_td": 1, "rec_yd": 30}, "Q2 6:32"), now=5.0, scoring_settings=SCORING)
    assert events and events[0]["clock"] == "Q2 6:32"
    assert lbp.present(events, "1")[0]["clock"] == "Q2 6:32"


def test_redis_down_still_shows_so_far(monkeypatch):
    def boom():
        raise RuntimeError("no redis")

    monkeypatch.setattr(lbp.redis_cache, "get_redis_client", boom)
    out = lbp.ingest("L", 11, [("1", [{"player_id": "p1", "name": "C. Stroud", "position": "QB", "team": "HOU",
                                        "game_started": True, "actual_points": 9.0, "stats": {"pass_td": 1}}])],
                     scoring_settings=SCORING, now=1000.0)
    assert out and out[0]["so_far"]
