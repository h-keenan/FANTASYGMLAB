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
import time
from datetime import datetime, timedelta, timezone
from typing import Any

LIVE_TTL_SECONDS = 20
IDLE_TTL_SECONDS = 60
# Recommended client poll interval while live (>= server TTL so a poll is
# normally served by the shared cache; client lag <= poll + TTL).
LIVE_POLL_SECONDS = 30
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


def reset_for_tests() -> None:
    with _lock:
        _memo.update(at=0.0, value=None)


def is_live(now: datetime | None = None) -> bool:
    return live_nfl_week(now) is not None


def matchups_ttl(round_num: int, now: datetime | None = None) -> int:
    """Cache TTL for ``/league/{id}/matchups/{round_num}``: short only for the
    week being played right now (past weeks never get hammered)."""

    live_week = live_nfl_week(now)
    try:
        week = int(round_num)
    except (TypeError, ValueError):
        return IDLE_TTL_SECONDS
    return LIVE_TTL_SECONDS if live_week is not None and week == live_week else IDLE_TTL_SECONDS


def poll_hint_seconds(round_num: int | None, now: datetime | None = None) -> int | None:
    """Seconds a client should wait between refreshes, or None when nothing is live."""

    if round_num is None:
        return None
    return LIVE_POLL_SECONDS if matchups_ttl(round_num, now) == LIVE_TTL_SECONDS else None
