"""Precompute the expensive per-league derived data before the user asks for it (Round 4).

The valued frame, league rankings / draft capital and roster-health frames are what a cold Dashboard, Team Rankings or Trade Hub
request spends seconds building. They are cached stale-while-revalidate (``modules.swr_cache``) keyed on the league-state
fingerprint, so warming them is just calling the same front doors:

* ``touch`` (league open): record the league as recently active and warm it in the background.
* ``warm_recent`` / ``start_scheduler``: periodically re-warm every league active in the last day, so a visit finds a fresh
  entry instead of a cold or stale one. One worker per interval does the tick (Redis lock); the heavy computes are themselves
  single-flighted cluster-wide.
* ``warm_recent`` at worker boot: a restarted worker serves its first request from Redis instead of computing for ~3.4 s.

Everything here is best effort and fail-open: a failure is logged at debug level and the request path computes exactly as before.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from typing import Callable

from modules import league_rankings, league_value_settings, redis_cache

logger = logging.getLogger("fantasygm.league_prewarm")

ACTIVE_KEY = "prewarm:active_leagues"
ACTIVE_WINDOW_SECONDS = 24 * 3600
RETAIN_SECONDS = 7 * 24 * 3600
MAX_LEAGUES_PER_TICK = 12
TICK_INTERVAL_SECONDS = 90.0
_LOCAL_DEBOUNCE_SECONDS = 60.0

_lock = threading.Lock()
_recent_local: dict[str, float] = {}
_scheduler_started = False


def _disabled() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("DYNASTYGM_TEST_MODE")) or os.environ.get(
        "LEAGUE_PREWARM", "1"
    ).strip().lower() in {"0", "false", "no", "off"}


def _member(league_id: str, lens: str) -> str:
    return f"{league_id}|{lens}"


def prewarm_league(league_id: str, lens: str, players_db_path: str) -> None:
    """Build (or refresh) the shared derived frames for one league/lens. Never raises."""

    steps: tuple[Callable[[], object], ...] = (
        lambda: league_value_settings.build_valued_players_frame_cached(league_id=league_id, lens=lens, players_db_path=players_db_path),
        lambda: league_rankings.build_league_summary_and_draft_capital_cached(league_id=league_id, lens=lens, players_db_path=players_db_path),
        lambda: league_rankings.build_league_rankings_frame_cached(league_id=league_id, lens=lens, players_db_path=players_db_path),
    )
    for step in steps:
        try:
            step()
        except Exception:
            logger.debug("league prewarm step failed for %s/%s", league_id, lens, exc_info=True)


def record_active(league_id: str, lens: str, *, now: float | None = None) -> None:
    try:
        client = redis_cache.get_redis_client()
        stamp = time.time() if now is None else now
        client.zadd(ACTIVE_KEY, {_member(league_id, lens): stamp})
        client.zremrangebyscore(ACTIVE_KEY, "-inf", stamp - RETAIN_SECONDS)
    except redis_cache.RedisError:
        logger.debug("could not record active league", exc_info=True)


def recent_leagues(*, within: float = ACTIVE_WINDOW_SECONDS, limit: int = MAX_LEAGUES_PER_TICK, now: float | None = None) -> list[tuple[str, str]]:
    try:
        stamp = time.time() if now is None else now
        raw = redis_cache.get_redis_client().zrevrangebyscore(ACTIVE_KEY, "+inf", stamp - within, start=0, num=limit)
    except redis_cache.RedisError:
        return []
    out: list[tuple[str, str]] = []
    for member in raw:
        text = member.decode("utf-8") if isinstance(member, bytes) else str(member)
        league_id, _, lens = text.partition("|")
        if league_id and lens:
            out.append((league_id, lens))
    return out


def touch(league_id: str, lens: str, players_db_path: str, *, background: bool = True) -> bool:
    """League open: remember it and warm it off the request path. Returns True when a warm-up was started."""

    if _disabled() or not league_id:
        return False
    record_active(league_id, lens)
    member = _member(league_id, lens)
    now = time.monotonic()
    with _lock:
        if now - _recent_local.get(member, -1e9) < _LOCAL_DEBOUNCE_SECONDS:
            return False
        _recent_local[member] = now
        if len(_recent_local) > 512:
            for key in sorted(_recent_local, key=_recent_local.get)[:128]:
                _recent_local.pop(key, None)
    if not background:
        prewarm_league(league_id, lens, players_db_path)
        return True
    threading.Thread(target=prewarm_league, args=(league_id, lens, players_db_path), name="dgm-league-prewarm", daemon=True).start()
    return True


def warm_recent(players_db_path: str, *, limit: int = MAX_LEAGUES_PER_TICK) -> int:
    """Warm every recently active league (sequentially, most recent first). Returns how many were warmed."""

    leagues = recent_leagues(limit=limit)
    for league_id, lens in leagues:
        prewarm_league(league_id, lens, players_db_path)
    return len(leagues)


def _tick(players_db_path: str, interval: float) -> int:
    """One scheduled pass; only the worker that wins the Redis lock for this interval does the work."""

    try:
        won = redis_cache.get_redis_client().set("lock:prewarm:tick", uuid.uuid4().hex, nx=True, px=int(interval * 900))
    except redis_cache.RedisError:
        return 0
    return warm_recent(players_db_path) if won else 0


def start_background(players_db_path: str, *, interval: float = TICK_INTERVAL_SECONDS) -> None:
    """Worker boot: warm recent leagues now, then re-warm on a schedule. Idempotent; a no-op under tests."""

    global _scheduler_started
    if _disabled():
        return
    with _lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    def _loop() -> None:
        try:
            warm_recent(players_db_path)  # boot: every worker, single-flighted by the cache locks
        except Exception:
            logger.debug("boot prewarm failed", exc_info=True)
        while True:
            time.sleep(interval)
            try:
                _tick(players_db_path, interval)
            except Exception:
                logger.debug("scheduled prewarm failed", exc_info=True)

    threading.Thread(target=_loop, name="dgm-league-prewarm-scheduler", daemon=True).start()
