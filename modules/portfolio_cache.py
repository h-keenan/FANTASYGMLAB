"""Stale-while-revalidate cache for Portfolio league rows.

Every layer under a Portfolio row (valued players frame, league rankings
frame, trade ideas, league summary) lives in 120 s time buckets, so a user who
comes back to Portfolio more than two minutes later pays the FULL cold cost of
every saved league again (docs/performance-audit-portfolio-2026-11.md: about
2.5 s of CPU per league, 25 s for a 12-league account in one process). A
Portfolio card is an at-a-glance summary (record, rank, archetype, a few
signals), not a live feed, so the finished *row* is cached on top of those
layers with a much longer life:

* fresh   (< ``FRESH_SECONDS``): served as is, no work at all.
* stale   (< ``STALE_SECONDS``): served immediately AND refreshed in the
  background (one refresher per row, cluster-wide, via a Redis ``SET NX``
  lock), so the next visit is fresh without anyone waiting for it.
* absent / too old: computed in the request, single-flight across workers.

The key embeds a fingerprint of every per-user input the row depends on
(entitlement, the row's Sleeper username, declared team stance, GM Targets and
untouchables), so changing any of them is an automatic miss: there is no
invalidation hook to forget. Only successful rows are cached (a failed or
timed-out league is retried on every visit).

Fail-open like modules.redis_cache: any Redis problem means "compute it".
Values are the JSON-safe final response rows, so a cached row serializes
exactly like a freshly built one.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
import threading
import time
import uuid
from typing import Any, Callable

from modules import redis_cache

logger = logging.getLogger("fantasygm.portfolio_cache")

FRESH_SECONDS = 120
STALE_SECONDS = 30 * 60
# The Redis entry outlives STALE_SECONDS a little so "too old" is decided by the
# envelope timestamp, never by a key that vanished mid-request.
_REDIS_TTL_SECONDS = STALE_SECONDS + 60
_REFRESH_LOCK_SECONDS = 60
_LOCK_WAIT_SECONDS = 20.0
_POLL_SECONDS = 0.05
_MAX_BACKGROUND_REFRESHES = 2

_refresh_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=_MAX_BACKGROUND_REFRESHES, thread_name_prefix="dgm-portfolio-swr"
)
_inflight_lock = threading.Lock()
_inflight: set[str] = set()
_stats = {"fresh": 0, "stale": 0, "miss": 0, "refresh": 0}


def stats() -> dict[str, int]:
    with _inflight_lock:
        return dict(_stats)


def _bump(name: str) -> None:
    with _inflight_lock:
        _stats[name] += 1


def inputs_fingerprint(*parts: Any) -> str:
    """Stable short digest of the per-user inputs a row depends on."""

    normalized = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def cache_key(user_id: str, league_id: str, lens: str, fingerprint: str) -> str:
    return redis_cache.build_cache_key("portfolio_row", user_id, league_id, lens, fingerprint)


def _read(client: Any, key: str, now: float) -> tuple[dict[str, Any] | None, float]:
    raw = client.get(key)
    if raw is None:
        return None, 0.0
    try:
        envelope = json.loads(raw)
        return envelope["row"], max(0.0, now - float(envelope["ts"]))
    except Exception:
        return None, 0.0


def _write(client: Any, key: str, row: dict[str, Any], now: float) -> None:
    client.set(key, json.dumps({"ts": now, "row": row}, separators=(",", ":")), ex=_REDIS_TTL_SECONDS)


def _release(client: Any, lock_key: str, token: bytes) -> None:
    try:
        if client.get(lock_key) == token:
            client.delete(lock_key)
    except Exception:
        pass


def _refresh_in_background(client: Any, key: str, build: Callable[[], dict[str, Any] | None]) -> None:
    with _inflight_lock:
        if key in _inflight:
            return
        _inflight.add(key)

    def run() -> None:
        lock_key = f"lock:{key}:refresh"
        token = uuid.uuid4().hex.encode("utf-8")
        try:
            if not client.set(lock_key, token, nx=True, ex=_REFRESH_LOCK_SECONDS):
                return
            try:
                row = build()
                if row is not None:
                    _write(client, key, row, time.time())
                    _bump("refresh")
            finally:
                _release(client, lock_key, token)
        except Exception:
            logger.warning("Portfolio background refresh failed for %s", key, exc_info=True)
        finally:
            with _inflight_lock:
                _inflight.discard(key)

    try:
        _refresh_pool.submit(run)
    except Exception:
        with _inflight_lock:
            _inflight.discard(key)


def peek(key: str, *, now: Callable[[], float] = time.time) -> dict[str, Any] | None:
    """The cached row if it is fresh or stale-but-servable, else None; never
    computes anything (the caller's follow-up full request is what refreshes a
    stale row)."""

    try:
        client = redis_cache.get_redis_client()
        row, age = _read(client, key, now())
    except Exception:
        return None
    if row is None or age >= STALE_SECONDS:
        return None
    _bump("fresh" if age < FRESH_SECONDS else "stale")
    return row


def get_row(
    key: str,
    build: Callable[[], dict[str, Any] | None],
    *,
    allow_stale: bool = True,
    now: Callable[[], float] = time.time,
) -> tuple[dict[str, Any] | None, str]:
    """`(row, source)` where source is "fresh" | "stale" | "miss".

    `build()` returns the JSON-safe row to cache, or None when the league has
    no cacheable row (failed/timed out); None is returned to the caller as is
    and nothing is stored. On a miss the build happens here, single-flight: one
    caller per key computes while the rest poll the cache, and anyone who waits
    past ``_LOCK_WAIT_SECONDS`` just computes for themselves.
    """

    try:
        client = redis_cache.get_redis_client()
        row, age = _read(client, key, now())
    except Exception:
        logger.warning("Redis unreachable for portfolio row %s; computing uncached.", key, exc_info=True)
        return build(), "miss"

    if row is not None:
        if age < FRESH_SECONDS:
            _bump("fresh")
            return row, "fresh"
        if allow_stale and age < STALE_SECONDS:
            _bump("stale")
            _refresh_in_background(client, key, build)
            return row, "stale"

    _bump("miss")
    lock_key = f"lock:{key}"
    token = uuid.uuid4().hex.encode("utf-8")
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    while True:
        try:
            acquired = client.set(lock_key, token, nx=True, px=int(_LOCK_WAIT_SECONDS * 1000))
        except Exception:
            return build(), "miss"
        if acquired:
            try:
                built = build()
                if built is not None:
                    try:
                        _write(client, key, built, now())
                    except Exception:
                        logger.warning("Could not cache portfolio row %s", key, exc_info=True)
                return built, "miss"
            finally:
                _release(client, lock_key, token)
        if time.monotonic() >= deadline:
            return build(), "miss"
        time.sleep(_POLL_SECONDS)
        try:
            row, age = _read(client, key, now())
        except Exception:
            return build(), "miss"
        if row is not None and age < FRESH_SECONDS:
            return row, "fresh"
