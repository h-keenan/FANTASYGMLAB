"""Off-season behavior with the calendar frozen in February, May and August.

Sleeper keeps a finished league's last week in ``settings.leg`` (17 or 18) and
reports status ``complete`` until the league rolls to a new ``league_id`` in
``pre_draft``. Every endpoint below must read that as "between seasons" and
never as "this week". "Today" comes from ``modules.season_clock`` only, so
the tests freeze it in one place.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from modules import (
    gm_plan,
    league_calendar,
    league_standings,
    playoff_simulator,
    season_clock,
    this_week,
    trade_ideas,
    waivers_logic,
)

# (frozen day, Sleeper payload an app user would see then)
FEB = date(2027, 2, 10)
MAY = date(2027, 5, 15)
AUG = date(2027, 8, 20)
IN_SEASON = date(2026, 11, 17)

LEAGUE_BY_DAY = {
    # Last season's league: over, but `leg` still says 18.
    FEB: {"status": "complete", "season": "2026", "settings": {"leg": 18, "playoff_week_start": 15, "playoff_teams": 6}},
    # Same league after the draft, before rolling over.
    MAY: {"status": "complete", "season": "2026", "settings": {"leg": 18, "playoff_week_start": 15, "playoff_teams": 6}},
    # Rolled-over league (new league_id): pre_draft, and Sleeper sometimes reports leg 1.
    AUG: {"status": "pre_draft", "season": "2027", "settings": {"leg": 1, "playoff_week_start": 15, "playoff_teams": 6}},
}


@pytest.fixture
def freeze(monkeypatch):
    """Freeze the season clock (the only 'now' the season logic may use)."""

    def _freeze(day: date) -> None:
        monkeypatch.setenv(season_clock.OFFLINE_ENV, "1")
        monkeypatch.setattr(season_clock, "_today_utc", lambda: day)
        monkeypatch.setattr(season_clock, "_clock_today", lambda now=None: day)
        season_clock.reset_cache()

    yield _freeze
    season_clock.reset_cache()


@pytest.mark.parametrize(
    "day, season, phase, week, draft_year",
    [
        (IN_SEASON, 2026, "regular", 11, 2027),
        (FEB, 2026, "post", 0, 2027),
        (MAY, 2026, "offseason", 0, 2028),
        (AUG, 2026, "preseason", 0, 2028),
    ],
)
def test_season_clock_phases_on_frozen_days(freeze, day, season, phase, week, draft_year):
    freeze(day)
    clock = season_clock.season_clock()
    assert (clock.season, clock.phase) == (season, phase)
    assert season_clock.nfl_week() == week
    assert season_clock.upcoming_draft_year() == draft_year
    assert season_clock.calendar_year() == day.year


@pytest.mark.parametrize("day", [FEB, MAY, AUG])
def test_offseason_league_has_no_current_week(freeze, day):
    freeze(day)
    league = LEAGUE_BY_DAY[day]
    assert league_calendar.is_offseason(league)
    assert league_calendar.active_league_week(league) is None
    assert not league_calendar.is_in_season(league)
    # A payload with no status is unknown, not off-season.
    assert not league_calendar.is_offseason({"settings": {"leg": 5}})
    assert league_calendar.active_league_week({"status": "in_season", "settings": {"leg": 5}}) == 5


@pytest.mark.parametrize("day", [FEB, MAY, AUG])
def test_playoff_odds_say_offseason_not_a_finished_simulation(freeze, day):
    freeze(day)
    with patch("modules.sleeper.get_league", return_value=LEAGUE_BY_DAY[day]):
        result = playoff_simulator.build_league_playoff_odds(
            "L1", lens="Dynasty", players_db_path="unused.db"
        )
    assert result == {"ok": True, "reason": "offseason", "teams": []}


def _standings_inputs(status: str, leg: int):
    rosters = [
        {"roster_id": i, "owner_id": f"o{i}", "settings": {"wins": 14 - i, "losses": i, "ties": 0, "fpts": 1500 - i}}
        for i in range(1, 5)
    ]
    league = {"status": status, "season": "2026", "settings": {"leg": leg, "playoff_week_start": 15, "playoff_teams": 2}}
    return rosters, league


def _standings_label(status: str, leg: int) -> str:
    rosters, league = _standings_inputs(status, leg)
    team_frame = pd.DataFrame([{"roster_id": r["roster_id"], "team_name": f"T{r['roster_id']}"} for r in rosters])
    bundle = league_standings.build_league_standings_bundle(
        rosters=rosters, roster_profiles={}, league=league, team_frame=team_frame
    )
    assert bundle["available"]
    return bundle["week_label"]


def test_standings_label_is_never_week_18_after_the_season():
    assert _standings_label("complete", 18) == "Final standings"
    assert _standings_label("complete", 17) == "Final standings"
    # Fantasy playoffs: the standings stop at the end of the regular season.
    assert _standings_label("post_season", 17) == "Through Week 14"
    assert _standings_label("in_season", 9) == "Through Week 9"


@pytest.mark.parametrize("day", [FEB, MAY, AUG])
def test_dashboard_this_week_offers_one_next_step(freeze, day):
    freeze(day)
    block = this_week.offseason_this_week(LEAGUE_BY_DAY[day])
    assert block and block["mode"] == "next_action" and block["rows"] == []
    action = block["next_action"]
    assert action["headline"] and action["cta_label"] and action["route"]
    assert "Week 18" not in str(block)


@pytest.mark.parametrize("day", [FEB, MAY, AUG])
def test_gm_plan_reads_offseason_not_playoff_push(freeze, day):
    freeze(day)
    league = LEAGUE_BY_DAY[day]
    week = None if league_calendar.is_offseason(league) else league["settings"]["leg"]
    assert gm_plan.derive_season_phase(week, 15, None) == gm_plan.PHASE_OFFSEASON_ADJACENT
    # The bug this guards: the raw leg of a finished league reads as the playoffs.
    assert gm_plan.derive_season_phase(17, 15, None) == gm_plan.PHASE_PLAYOFF_PUSH


@pytest.mark.parametrize("day", [FEB, MAY, AUG])
def test_waiver_has_played_gate_is_off_between_seasons(freeze, day):
    """Rookies and new signings have not 'played' yet; the gate would hide all of
    them from the wire until Week 1."""

    freeze(day)
    with patch("modules.sleeper.get_season_player_stats", side_effect=AssertionError("must not fetch stats")):
        assert waivers_logic.default_played_ids(LEAGUE_BY_DAY[day]) is None
    with patch("modules.sleeper.get_season_player_stats", return_value={}) as stats, patch(
        "modules.sleeper.default_player_stats_season", return_value=2026
    ):
        waivers_logic.default_played_ids({"status": "in_season", "settings": {"leg": 5}})
    assert stats.called


@pytest.mark.parametrize(
    "day, pick_year, expected",
    [
        (FEB, 2026, False),  # last year's pick is spent
        (FEB, 2027, True),  # this spring's rookie pick is live until the draft
        (FEB, 2028, True),
    ],
)
def test_pick_capital_uses_the_injected_year(freeze, day, pick_year, expected):
    freeze(day)
    assert (
        trade_ideas.pick_is_actionable_capital(
            pick_year,
            current_pick_year=2027,
            current_year_picks_active=True,
            settings={"type": 2},
            as_of_year=season_clock.calendar_year(),
        )
        is expected
    )


@pytest.mark.parametrize("day", [FEB, MAY, AUG])
def test_matchup_endpoint_between_seasons_says_no_current_week(freeze, monkeypatch, day):
    freeze(day)
    from test_mobile_api_service import _MATCHUP_LEAGUE, _client, _matchup_world

    client = _client(monkeypatch)
    league = {**_MATCHUP_LEAGUE, **LEAGUE_BY_DAY[day], "settings": {**_MATCHUP_LEAGUE["settings"], **LEAGUE_BY_DAY[day]["settings"]}}
    # Last season's final Sleeper week would pair two rosters if the endpoint read `leg`.
    with _matchup_world([{"roster_id": 1, "matchup_id": 1}, {"roster_id": 2, "matchup_id": 1}], league=league):
        response = client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})
    body = response.json()
    assert response.status_code == 200
    assert body["reason"] == "no_current_week"
    assert body["my_team"] is None and body["week"] is None


def test_matchup_endpoint_in_season_still_works(freeze, monkeypatch):
    freeze(IN_SEASON)
    from test_mobile_api_service import _MATCHUP_LEAGUE, _client, _matchup_world

    client = _client(monkeypatch)
    league = {**_MATCHUP_LEAGUE, "status": "in_season"}
    with _matchup_world([{"roster_id": 1, "matchup_id": None}], league=league):
        response = client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})
    assert response.json()["reason"] == "bye_week"
