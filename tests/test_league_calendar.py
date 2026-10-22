"""modules.league_calendar — Sleeper trade_deadline / best_ball parsing.

Fixture settings mirror real Sleeper league payloads probed 2026-10-21
(e.g. an in-season league at leg 7 with trade_deadline 14, completed 2025
leagues with deadlines 13/14, and leagues using 99 for "no deadline").
"""

from modules import gm_plan, league_calendar


def _league(status="in_season", **settings):
    return {"status": status, "settings": settings}


def test_trade_deadline_week_reads_a_real_week_and_treats_99_as_none():
    assert league_calendar.trade_deadline_week(_league(trade_deadline=14)) == 14
    assert league_calendar.trade_deadline_week(_league(trade_deadline="11")) == 11
    assert league_calendar.trade_deadline_week(_league(trade_deadline=99)) is None
    assert league_calendar.trade_deadline_week(_league(trade_deadline=0)) is None
    assert league_calendar.trade_deadline_week(_league()) is None
    assert league_calendar.trade_deadline_week(None) is None


def test_trades_stay_open_through_the_deadline_week():
    league = _league(trade_deadline=11, leg=11)
    assert league_calendar.trade_deadline_passed(league) is False


def test_deadline_passes_the_week_after_the_deadline_week():
    league = _league(trade_deadline=11, leg=12)
    assert league_calendar.trade_deadline_passed(league) is True
    window = league_calendar.trade_window(league)
    assert window == {
        "trade_deadline_week": 11,
        "current_week": 12,
        "trade_deadline_passed": True,
        "message": "Trade deadline has passed; trades reopen after the season.",
    }


def test_post_season_status_is_still_past_the_deadline():
    assert league_calendar.trade_deadline_passed(_league("post_season", trade_deadline=13, leg=16)) is True


def test_offseason_leagues_reopen_trades_regardless_of_last_deadline():
    # A completed league keeps leg=17 and its old deadline on Sleeper.
    for status in ("complete", "pre_draft", "drafting", ""):
        league = _league(status, trade_deadline=13, leg=17)
        assert league_calendar.trade_deadline_passed(league) is False
        assert league_calendar.trade_window(league)["message"] == ""


def test_no_deadline_never_passes():
    assert league_calendar.trade_deadline_passed(_league(trade_deadline=99, leg=17)) is False


def test_current_week_falls_back_to_week_and_ignores_zero():
    assert league_calendar.current_league_week(_league(leg=0, week=5)) == 5
    assert league_calendar.current_league_week(_league(leg=0)) is None


def test_best_ball_flag():
    assert league_calendar.is_best_ball(_league(best_ball=1)) is True
    assert league_calendar.is_best_ball(_league(best_ball=0)) is False
    assert league_calendar.is_best_ball(_league()) is False
    assert league_calendar.is_best_ball(None) is False


# --- GM Plan phase driven by the real deadline -----------------------------


def test_gm_plan_deadline_phase_runs_through_a_late_real_deadline():
    # Deadline 14 / playoffs 15: weeks 12-14 used to read "Playoff Push"
    # even though trades were still open; the real deadline wins now.
    for week in (4, 11, 12, 14):
        assert gm_plan.derive_season_phase(week, 15, 14) == gm_plan.PHASE_TRADE_DEADLINE_APPROACH
    assert gm_plan.derive_season_phase(15, 15, 14) == gm_plan.PHASE_PLAYOFF_PUSH


def test_gm_plan_weeks_after_an_early_deadline_are_post_deadline_not_deadline_approach():
    # Deadline 9 / playoffs 15: weeks 10-11 used to read "Trade Deadline
    # Approaching" (hardcoded weeks 4-11) after trades had already closed.
    assert gm_plan.derive_season_phase(9, 15, 9) == gm_plan.PHASE_TRADE_DEADLINE_APPROACH
    assert gm_plan.derive_season_phase(10, 15, 9) == gm_plan.PHASE_POST_DEADLINE
    assert gm_plan.derive_season_phase(11, 15, 9) == gm_plan.PHASE_POST_DEADLINE
    assert gm_plan.derive_season_phase(12, 15, 9) == gm_plan.PHASE_PLAYOFF_PUSH
    assert gm_plan.phase_label(gm_plan.PHASE_POST_DEADLINE) == "Past the Trade Deadline"


def test_gm_plan_early_weeks_stay_early_with_a_real_deadline():
    assert gm_plan.derive_season_phase(2, 15, 11) == gm_plan.PHASE_EARLY_SEASON


def test_gm_plan_unknown_deadline_keeps_the_original_buckets():
    assert gm_plan.derive_season_phase(11, 15, None) == gm_plan.PHASE_TRADE_DEADLINE_APPROACH
    assert gm_plan.derive_season_phase(12, 15, 99) == gm_plan.PHASE_PLAYOFF_PUSH


def test_gm_plan_trade_focus_area_stops_pushing_trades_after_the_deadline():
    plan = gm_plan.build_gm_plan(
        season_phase=gm_plan.PHASE_POST_DEADLINE,
        trade_ideas=[{"partner_team_name": "Team Two", "my_player": "A", "their_player": "B"}],
        trade_deadline_passed=True,
    )
    trade_area = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    assert trade_area["items"] == []
    assert trade_area["status"] == gm_plan.STATUS_NO_SIGNAL
    assert trade_area["watch_for"] == "Trade deadline has passed; trades reopen after the season."
    assert trade_area["trade_deadline_passed"] is True
    assert plan["season_phase_label"] == "Past the Trade Deadline"
