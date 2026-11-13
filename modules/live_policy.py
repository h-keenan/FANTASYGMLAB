"""Live-aware freshness policy for in-progress NFL scoring.

One place answers "are real NFL games being played right now, and how fresh
must a live score read be?" so every layer (Sleeper matchups cache, API
payload, client polling hint) agrees instead of each stacking its own TTL.

- Live window: any regular-season kickoff of the current NFL week has
  happened and ``GAME_IN_PROGRESS_WINDOW`` (nfl_schedule) has not elapsed,
  or kickoff is within ``PRE_KICKOFF_LEAD`` (lineup locks / first points).
- Inside the window a matchups read is cached ``LIVE_TTL_SECONDS`` cluster
  wide (modules.sleeper_cache single-flight: one upstream fetch per league
  per interval no matter how many users or workers). Outside it the cache
  keeps ``IDLE_TTL_SECONDS``.

Pure arithmetic over the (already cached) nflverse schedule; the window is
memoised for a few seconds so hot paths do not rescan the schedule.
"""

from __future__ import annotations

import threading
import zlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any

LIVE_TTL_SECONDS = 20  # fastest live TTL (pressure < 40% of the Sleeper budget)
IDLE_TTL_SECONDS = 60
# Recommended client poll interval while live: never faster than the server TTL
# (a faster poll would only re-read the same cached payload).
LIVE_POLL_SECONDS = 30
# Adaptive live TTL: (enter-pressure, ttl). Pressure = Sleeper calls in the last
# minute / budget (modules.sleeper_budget). Tiers step up at the enter value and
# only step back down below it minus HYSTERESIS, so the TTL does not flap.
ADAPTIVE_TIERS = ((0.0, 20), (0.4, 30), (0.6, 45), (0.8, 75), (0.9, 90))
HYSTERESIS = 0.05
SEVERE_PRESSURE = 0.9
# Leagues need a request within this window to get a live (fast) TTL; a league
# nobody is looking at gets the idle TTL and is never refreshed in the background.
ACTIVE_LEAGUE_WINDOW_SECONDS = 120.0
# Under severe pressure free-tier reads may be deferred to last-known data, but
# never older than this.
SEVERE_DEFER_MAX_AGE_SECONDS = 180.0
_ACTIVE_MAX_ENTRIES = 20000
PRE_KICKOFF_LEAD = timedelta(minutes=20)
_MEMO_SECONDS = 10.0

_lock = threading.Lock()
_memo: dict[str, Any] = {"at": 0.0, "value": None}


def _compute_live_week(now: datetime) -> int | None:
    try:
        from modules import nfl_schedule, sleeper
        from modules.trade_grade import estimate_nfl_week

        season = sleeper.default_player_stats_season()
        week = estimate_nfl_week(now.date())
        if not week or week <= 0:
            return None
        import os

        if not os.path.exists(nfl_schedule.GAMES_CACHE_PATH):
            return None  # never block a score read on a cold schedule download
        games = nfl_schedule.load_games()
        # Thursday kickoffs belong to `week`; a Monday-night tail can run
        # past the calendar week boundary, so look one week back too.
        for candidate in (week, week - 1):
            if candidate <= 0:
                continue
            for kickoff in nfl_schedule.week_kickoffs(season, candidate, games=games):
                if kickoff - PRE_KICKOFF_LEAD <= now < kickoff + nfl_schedule.GAME_IN_PROGRESS_WINDOW:
                    return candidate
    except Exception:
        return None
    return None


def live_nfl_week(now: datetime | None = None) -> int | None:
    """The NFL week with games in (or about to be in) progress, else None."""

    if now is not None:
        return _compute_live_week(now if now.tzinfo else now.replace(tzinfo=timezone.utc))
    mono = time.monotonic()
    with _lock:
        if _memo["value"] is not None and mono - _memo["at"] < _MEMO_SECONDS:
            return _memo["value"][0]
    week = _compute_live_week(datetime.now(timezone.utc))
    with _lock:
        _memo.update(at=mono, value=(week,))
    return week


class AdaptiveTtl:
    """Pressure -> live TTL with hysteresis (stateful so it cannot flap)."""

    def __init__(self) -> None:
        self.tier = 0
        self._lock = threading.Lock()

    def update(self, pressure: float) -> int:
        with self._lock:
            while self.tier + 1 < len(ADAPTIVE_TIERS) and pressure >= ADAPTIVE_TIERS[self.tier + 1][0]:
                self.tier += 1
            while self.tier > 0 and pressure < ADAPTIVE_TIERS[self.tier][0] - HYSTERESIS:
                self.tier -= 1
            return ADAPTIVE_TIERS[self.tier][1]


_adaptive = AdaptiveTtl()
_active: dict[str, float] = {}


def pressure_fraction() -> float:
    try:
        from modules import sleeper_budget

        return sleeper_budget.calls_in_last_minute() / max(1, sleeper_budget.BUDGET_PER_MINUTE)
    except Exception:
        return 0.0


def is_severe_pressure() -> bool:
    return pressure_fraction() >= SEVERE_PRESSURE


def current_live_ttl() -> int:
    return _adaptive.update(pressure_fraction())


def _touch_league(league_id: str | None, now: float) -> bool:
    """Record a request; True when this league was also requested within the window."""

    if not league_id:
        return True
    with _lock:
        previous = _active.get(league_id)
        _active[league_id] = now
        if len(_active) > _ACTIVE_MAX_ENTRIES:
            for k in [k for k, v in _active.items() if now - v > ACTIVE_LEAGUE_WINDOW_SECONDS]:
                _active.pop(k, None)
    return previous is not None and now - previous <= ACTIVE_LEAGUE_WINDOW_SECONDS


def reset_for_tests() -> None:
    with _lock:
        _memo.update(at=0.0, value=None)
        _active.clear()
    _adaptive.tier = 0


def is_live(now: datetime | None = None) -> bool:
    return live_nfl_week(now) is not None


def matchups_ttl(round_num: int, now: datetime | None = None, league_id: str | None = None) -> float:
    """Cache TTL for ``/league/{id}/matchups/{round_num}``: adaptive-short only
    for the week being played right now and only for leagues that are being
    watched (a request within ACTIVE_LEAGUE_WINDOW_SECONDS); otherwise idle."""

    live_week = live_nfl_week(now)
    try:
        week = int(round_num)
    except (TypeError, ValueError):
        return IDLE_TTL_SECONDS
    if live_week is None or week != live_week:
        return IDLE_TTL_SECONDS
    if not _touch_league(league_id, time.time()):
        return IDLE_TTL_SECONDS
    return league_jittered_ttl(current_live_ttl(), league_id)


def league_jittered_ttl(ttl: float, league_id: str | None) -> float:
    """Deterministic +-15% per league so leagues that first loaded together do
    not all expire (and refetch) in the same second."""

    if not league_id:
        return ttl
    frac = (zlib.crc32(str(league_id).encode("utf-8")) % 1000) / 1000.0
    return ttl * (0.85 + 0.3 * frac)


def poll_hint_seconds(round_num: int | None, now: datetime | None = None) -> int | None:
    """Seconds a client should wait between refreshes (never faster than the
    server's current live TTL), or None when nothing is live."""

    if round_num is None:
        return None
    live_week = live_nfl_week(now)
    if live_week is None or int(round_num) != live_week:
        return None
    return max(LIVE_POLL_SECONDS, current_live_ttl())
