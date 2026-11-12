from datetime import date

import pytest

from modules import season_clock as sc


@pytest.fixture(autouse=True)
def _reset():
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_kickoff_is_thursday_after_labor_day():
    assert sc.nfl_kickoff(2026) == date(2026, 9, 10)
    assert sc.nfl_kickoff(2025) == date(2025, 9, 4)
    assert sc.nfl_kickoff(2026).weekday() == 3


@pytest.mark.parametrize(
    "today,season,phase",
    [
        (date(2026, 1, 15), 2025, "post"),
        (date(2026, 3, 1), 2025, "offseason"),
        (date(2026, 8, 15), 2025, "preseason"),
        (date(2026, 9, 1), 2025, "preseason"),  # old Sep-1 flip: empty current-season file
        (date(2026, 9, 10), 2026, "regular"),
        (date(2026, 11, 20), 2026, "regular"),
        (date(2026, 12, 31), 2026, "regular"),
        (date(2027, 1, 20), 2026, "post"),
    ],
)
def test_calendar_fallback(today, season, phase):
    clock = sc.clock_from_calendar(today)
    assert (clock.season, clock.phase, clock.source) == (season, phase, "calendar")
    assert sc.current_season(today) == season
    assert sc.prior_season(today) == season - 1


def test_week_counts_from_kickoff():
    assert sc.clock_from_calendar(date(2026, 9, 10)).week == 1
    assert sc.clock_from_calendar(date(2026, 9, 17)).week == 2


def test_sleeper_payload_parsing():
    payload = {"season": "2026", "season_type": "regular", "week": 10, "league_season": "2027"}
    clock = sc.clock_from_sleeper_state(payload)
    assert (clock.season, clock.phase, clock.week, clock.source) == (2026, "regular", 10, "sleeper")
    assert sc.clock_from_sleeper_state({"season": "2026", "season_type": "off", "week": 0}).phase == "offseason"
    assert sc.clock_from_sleeper_state({"season": "garbage", "season_type": "off"}) is None
    assert sc.clock_from_sleeper_state({"season": "2026", "season_type": "???"}) is None
    assert sc.clock_from_sleeper_state(None) is None


def test_live_clock_uses_sleeper_and_caches(monkeypatch):
    monkeypatch.delenv(sc.OFFLINE_ENV, raising=False)
    calls = []

    def fake_fetch():
        calls.append(1)
        return {"season": "2031", "season_type": "pre", "week": 1}

    monkeypatch.setattr(sc, "_fetch_state", fake_fetch)
    assert sc.current_season() == 2031
    assert sc.season_clock().phase == "preseason"
    assert len(calls) == 1  # cached


def test_live_clock_falls_back_to_calendar_and_backs_off(monkeypatch):
    monkeypatch.delenv(sc.OFFLINE_ENV, raising=False)
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("network down")

    monkeypatch.setattr(sc, "_fetch_state", boom)
    expected = sc.clock_from_calendar(sc._today_utc()).season
    assert sc.current_season() == expected
    assert sc.current_season() == expected
    assert len(calls) == 1  # failure backoff: no hammering a dead endpoint


def test_offline_mode_never_touches_network(monkeypatch):
    monkeypatch.setenv(sc.OFFLINE_ENV, "1")
    monkeypatch.setattr(sc, "_fetch_state", lambda: pytest.fail("network used"))
    assert sc.season_clock().source == "calendar"


@pytest.mark.parametrize(
    "today,year",
    [
        (date(2026, 10, 27), 2027),
        (date(2027, 2, 1), 2027),
        (date(2027, 4, 30), 2027),
        (date(2027, 5, 1), 2028),  # draft done: next class is a year further out
        (date(2027, 8, 31), 2028),
        (date(2027, 9, 20), 2028),
    ],
)
def test_upcoming_draft_year(today, year):
    assert sc.upcoming_draft_year(today) == year


def test_every_season_definition_goes_through_the_clock():
    import time

    from modules import sleeper

    for d, current in ((date(2026, 9, 1), 2025), (date(2026, 9, 10), 2026), (date(2027, 2, 1), 2026)):
        now = time.struct_time((d.year, d.month, d.day, 12, 0, 0, 0, 0, -1))
        assert sleeper.default_player_stats_season(now) == current == sc.current_season(d)
        assert sleeper.prior_player_stats_season(now) == current - 1
