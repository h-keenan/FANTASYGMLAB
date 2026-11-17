"""Realism P1 (2026-11 audit 2): the trade window follows the league's own playoff calendar
(playoff start, bracket size, the last scored week, the team's chance to be alive)."""

import pytest

from modules import league_value_settings, trade_grade
from tests.test_trade_lineup_model import SETTINGS, _byes, _deep_roster, _evaluate, _pick  # noqa: F401  (fixture)

PLAYOFFS = {"playoff_week_start": 15, "playoff_teams": 6, "league_size": 12}


def _window(week=10, **extra):
    return trade_grade.season_window({**PLAYOFFS, "current_week": week, **extra})


def test_no_playoff_settings_keeps_the_old_flat_window():
    w = trade_grade.season_window({"current_week": 10})
    assert (w.remaining_weeks, w.last_week, w.playoff_start_week) == (8, 17, None)
    assert w.effective_weeks == 8.0 and all(w.weight(k) == 1.0 for k in range(1, 18))
    assert w.describe() == "8 fantasy weeks left"


def test_playoff_weeks_are_weighted_by_the_chance_the_team_is_alive():
    w = _window(10)
    assert w.playoff_start_week == 15 and w.last_week == 17  # 6 teams = 3 rounds: weeks 15-17
    assert [w.weight(k) for k in (10, 14)] == [1.0, 1.0]
    assert w.weight(15) == pytest.approx(0.5)  # 6 of 12 teams make it
    assert w.weight(15) > w.weight(16) > w.weight(17) > 0
    assert w.effective_weeks == pytest.approx(5 + 0.5 + 0.5 * 0.6 + 0.5 * 0.36)
    assert "5 regular-season weeks left, then the playoffs (weeks 15-17) counted at about 50% to be alive" in w.describe()


def test_the_bracket_size_sets_the_last_scored_week():
    four = trade_grade.season_window({**PLAYOFFS, "playoff_teams": 4, "current_week": 10})
    assert four.last_week == 16 and four.weight(17) == 0.0
    over = trade_grade.season_window({**PLAYOFFS, "playoff_teams": 4, "current_week": 17})
    assert over.in_season is False  # the league's season already ended


def test_an_eliminated_team_gets_no_playoff_weeks_and_a_strong_one_gets_more():
    out = _window(10, playoff_odds=0.0)
    assert out.weight(15) == 0.0 and out.effective_weeks == 5.0
    assert "out of contention" in out.describe()
    assert _window(10, playoff_odds=0.9).effective_weeks > _window(10).effective_weeks > _window(10, playoff_odds=0.1).effective_weeks


def test_league_settings_detection_reads_the_playoff_calendar():
    league = {"total_rosters": 12, "roster_positions": ["QB", "RB", "WR", "BN"],
              "settings": {"playoff_week_start": 15, "playoff_teams": 6, "trade_deadline": 12}}
    detected = league_value_settings.detect_league_value_settings_from_payload(league)
    assert detected["playoff_week_start"] == 15 and detected["playoff_teams"] == 6 and detected["trade_deadline_week"] == 12
    # a league that reports none of it is unchanged
    bare = league_value_settings.detect_league_value_settings_from_payload({"total_rosters": 12, "settings": {}})
    assert "playoff_week_start" not in bare and "trade_deadline_week" not in bare
    # 99 means "no deadline"
    none = league_value_settings.detect_league_value_settings_from_payload({"settings": {"trade_deadline": 99}})
    assert "trade_deadline_week" not in none


def test_injury_cost_counts_only_the_weeks_that_matter():
    absence = trade_grade.InjuryAbsence(status_label="Out", weeks=8.0, season_ending=False, basis="test")
    flat = trade_grade.injury_availability_cost(5000, absence, strategy="contender", window=trade_grade.season_window({"current_week": 10}), starts=True)
    out = trade_grade.injury_availability_cost(5000, absence, strategy="contender", window=_window(10, playoff_odds=0.0), starts=True)
    assert out < flat  # a 5-week window cannot lose 8 weeks of value


def _fit(extra):
    return _evaluate(_deep_roster(), ["RB1"], [], receive_assets=[_pick(4800)], settings={**SETTINGS, **extra})[0]["lineup_model"]


def test_lineup_points_are_summed_over_the_leagues_own_weeks_and_say_so():
    flat = _fit({})
    assert flat["weeks"]["last"] == 17 and flat["weeks"]["effective"] == float(flat["weeks"]["count"])
    four_team = _fit({"playoff_week_start": 12, "playoff_teams": 4, "league_size": 12})
    assert four_team["weeks"]["last"] == 13  # weeks 12-13 are the whole bracket
    assert four_team["weeks"]["effective"] < four_team["weeks"]["count"]
    assert four_team["weeks"]["note"].startswith("4 regular-season weeks left, then the playoffs (weeks 12-13)")
    assert abs(four_team["points"]["ros_delta"]) < abs(flat["points"]["ros_delta"])
    assert "per_week_delta" in four_team["points"]
    # eliminated: the playoff weeks drop out, only the regular season is left
    dead = _fit({"playoff_week_start": 12, "playoff_teams": 4, "league_size": 12, "playoff_odds": 0.0})
    assert dead["weeks"]["last"] == 11 and dead["weeks"]["effective"] == float(dead["weeks"]["count"]) == 4.0
    assert abs(dead["points"]["ros_delta"]) < abs(four_team["points"]["ros_delta"])


def test_the_analyzer_response_and_risk_text_name_the_playoff_schedule():
    fit, verdict = _evaluate(_deep_roster(), ["RB1"], [], receive_assets=[_pick(4800)],
                             settings={**SETTINGS, "playoff_week_start": 12, "playoff_teams": 4, "league_size": 12})
    season = fit["season_week"]
    assert season["last_week"] == 13 and season["playoff_start_week"] == 12 and season["effective_weeks"] < season["remaining_weeks"]
    assert "playoffs (weeks 12-13)" in season["note"]
    assert "playoffs (weeks 12-13)" in verdict.risk_summary
