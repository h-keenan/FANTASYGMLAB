"""The single NFL season clock.

Every "what season is it" question in the app resolves through this module.
Before it existed there were three divergent answers: a server-timezone
``time.localtime()`` Sep-1 flip (``sleeper.default_player_stats_season``), a May-1
rookie-draft cutoff (``external_interesting_trades``) and calendar-year
arithmetic inside the eligibility gate.

Source of truth is Sleeper's ``/state/nfl`` (the same clock Sleeper's own
leagues roll on). It is cached in-process; when it cannot be reached (offline
tests, outage) a pure calendar rule keyed to the NFL kickoff takes over, so the
answer is always defined and never raises.

Pure functions take an explicit ``today`` so they are deterministic in tests;
``season_clock()`` with no argument is the only entry that touches the network.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

SLEEPER_STATE_URL = "https://api.sleeper.app/v1/state/nfl"
OFFLINE_ENV = "FANTASYDESK_SEASON_CLOCK_OFFLINE"

STATE_TTL_SECONDS = 60 * 60
FAILURE_BACKOFF_SECONDS = 5 * 60
REQUEST_TIMEOUT_SECONDS = 3

PHASE_OFFSEASON = "offseason"
PHASE_PRESEASON = "preseason"
PHASE_REGULAR = "regular"
PHASE_POST = "post"
PHASES = (PHASE_OFFSEASON, PHASE_PRESEASON, PHASE_REGULAR, PHASE_POST)

# Sleeper ``season_type`` -> our phase.
_SLEEPER_PHASES = {"off": PHASE_OFFSEASON, "pre": PHASE_PRESEASON, "regular": PHASE_REGULAR, "post": PHASE_POST}

REGULAR_SEASON_WEEKS = 18
# The fantasy week rolls over on this weekday (Mon=0 ... Sun=6) at this hour,
# US Eastern, so Monday Night Football still belongs to the week it closes.
# Product default: Tuesday morning. Owner may pick Thursday (kickoff day): set
# WEEK_ROLLOVER_WEEKDAY = 3. This is the ONLY place the roll day is defined.
WEEK_ROLLOVER_WEEKDAY = 1
WEEK_ROLLOVER_HOUR_ET = 6
_EASTERN = ZoneInfo("America/New_York")
_KICKOFF_WEEKDAY = 3  # NFL kickoff is always a Thursday
PRESEASON_START_MONTH = 8  # camps/preseason games: August until kickoff
POST_SEASON_END = (2, 20)  # (month, day) after which the league year is "offseason"
# The NFL rookie draft is held in late April. Sleeper exposes no draft date, so
# "the draft has happened" is approximated by the calendar month, in one place.
DRAFT_COMPLETE_MONTH = 5


@dataclass(frozen=True)
class SeasonClock:
    season: int
    phase: str
    week: int | None
    source: str  # "sleeper" | "calendar"

    @property
    def prior_season(self) -> int:
        return self.season - 1


def nfl_kickoff(year: int) -> date:
    """Thursday after Labor Day (first Monday of September): NFL kickoff."""

    labor_day = date(year, 9, 1)
    while labor_day.weekday() != 0:
        labor_day += timedelta(days=1)
    return labor_day + timedelta(days=3)


def season_from_calendar(today: date) -> int:
    """NFL season in effect on ``today`` (flips at kickoff, not Sep 1)."""

    return today.year if today >= nfl_kickoff(today.year) else today.year - 1


def _first_rollover_offset() -> int:
    """Days from kickoff to the first week rollover (week 2 begins)."""

    return (WEEK_ROLLOVER_WEEKDAY - _KICKOFF_WEEKDAY) % 7 or 7


def _calendar_week(days_since_kickoff: int) -> int:
    first = _first_rollover_offset()
    return 1 if days_since_kickoff < first else (days_since_kickoff - first) // 7 + 2


def clock_from_calendar(today: date) -> SeasonClock:
    season = season_from_calendar(today)
    days = (today - nfl_kickoff(season)).days
    week = _calendar_week(days)
    if week <= REGULAR_SEASON_WEEKS:
        return SeasonClock(season, PHASE_REGULAR, week, "calendar")
    if today <= date(season + 1, *POST_SEASON_END):
        return SeasonClock(season, PHASE_POST, None, "calendar")
    if today.month >= PRESEASON_START_MONTH:  # camps/preseason: Aug until the next kickoff
        return SeasonClock(season, PHASE_PRESEASON, None, "calendar")
    return SeasonClock(season, PHASE_OFFSEASON, None, "calendar")


def clock_from_sleeper_state(state: Mapping[str, Any] | None) -> SeasonClock | None:
    """Parse a Sleeper ``/state/nfl`` payload; None when it is unusable."""

    if not isinstance(state, Mapping):
        return None
    try:
        season = int(str(state.get("season")).strip())
    except (TypeError, ValueError):
        return None
    if not 2000 <= season <= 2100:
        return None
    phase = _SLEEPER_PHASES.get(str(state.get("season_type") or "").strip().lower())
    if phase is None:
        return None
    try:
        week = int(state.get("week"))
    except (TypeError, ValueError):
        week = None
    return SeasonClock(season, phase, week if week and week > 0 else None, "sleeper")


_lock = threading.Lock()
_cached: dict[str, Any] = {"clock": None, "fetched_at": 0.0, "failed_at": 0.0}


def _fetch_state() -> Mapping[str, Any] | None:
    import requests

    response = requests.get(SLEEPER_STATE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, Mapping) else None


def _offline() -> bool:
    return os.environ.get(OFFLINE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def reset_cache() -> None:
    with _lock:
        _cached.update(clock=None, fetched_at=0.0, failed_at=0.0)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _clock_today(now: datetime | None = None) -> date:
    """Calendar day the fantasy week is counted on: US Eastern, shifted so the
    rollover hour (not midnight) starts the new day. Only the calendar fallback
    uses it; Sleeper's own state is authoritative when reachable."""

    moment = (now or datetime.now(timezone.utc)).astimezone(_EASTERN)
    return (moment - timedelta(hours=WEEK_ROLLOVER_HOUR_ET)).date()


def season_clock(today: date | None = None) -> SeasonClock:
    """Current season clock.

    With an explicit ``today`` the answer is the deterministic calendar rule (no
    I/O). Without one it is Sleeper's ``/state/nfl`` (cached for an hour), with the
    calendar rule as the fallback when Sleeper is unreachable or offline mode is on.
    """

    if today is not None:
        return clock_from_calendar(today)
    # The calendar fallback is only needed when offline or when Sleeper's state is unavailable: computing it eagerly cost
    # a kickoff-date calculation on every call, and per-row eligibility checks call this thousands of times a request.
    if _offline():
        return clock_from_calendar(_clock_today())
    now = time.monotonic()
    with _lock:
        cached = _cached["clock"]
        if cached is not None and now - _cached["fetched_at"] < STATE_TTL_SECONDS:
            return cached
        if _cached["failed_at"] and now - _cached["failed_at"] < FAILURE_BACKOFF_SECONDS:
            return cached or clock_from_calendar(_clock_today())
    try:
        clock = clock_from_sleeper_state(_fetch_state())
    except Exception:
        clock = None
    with _lock:
        if clock is None:
            _cached["failed_at"] = now
            return _cached["clock"] or clock_from_calendar(_clock_today())
        _cached.update(clock=clock, fetched_at=now, failed_at=0.0)
        return clock


def calendar_year(today: date | None = None) -> int:
    """The calendar year, from the one injectable "today" (UTC) for callers that
    need a year rather than a season (pick years, fallbacks). Use this instead of
    ``datetime.now().year`` so tests can freeze the date."""

    return (today or _today_utc()).year


def current_season(today: date | None = None) -> int:
    return season_clock(today).season


def prior_season(today: date | None = None) -> int:
    return current_season(today) - 1


def upcoming_draft_year(today: date | None = None) -> int:
    """Class year of the next rookie draft whose picks are still unspent.

    During the season and before the spring draft that is ``season + 1``; once
    the draft has happened (May onward of the new calendar year) the class is
    on rosters and the next draft is a year further out.
    """

    clock = season_clock(today)
    when = today or _today_utc()
    if when.year == clock.season + 1 and when.month >= DRAFT_COMPLETE_MONTH:
        return clock.season + 2
    return clock.season + 1


def nfl_week(today: date | None = None) -> int:
    """Current regular-season NFL week, 0 outside the regular season.

    The one answer to "what week is it" for every caller (grader, bye flags,
    live policy, stats freshness). An explicit ``today`` is the deterministic
    calendar rule; without one it is Sleeper's state with calendar fallback.
    """

    clock = season_clock(today)
    return int(clock.week) if clock.phase == PHASE_REGULAR and clock.week else 0
