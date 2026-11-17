"""Stale-while-revalidate over the shared Redis cache.

Round 4 (2026-11-17): the 120 s time-bucket caches made nearly every low-traffic visit a cold recompute (valued frame 3.4 s,
dashboard 4.2 s). ``redis_swr_cache`` keeps ``redis_single_flight_cache``'s guarantees but separates *fresh* from *usable*:

* The key names the INPUTS: callers pass a content fingerprint (league settings, rosters, players/values file versions), never
  a clock bucket. A real data change is therefore a different key, a miss and a synchronous compute: stale data is never served
  across a changed fingerprint.
* A hit younger than ``fresh_ttl_seconds`` is served as is. An older hit (up to ``stale_ttl_seconds``, the Redis expiry) is
  served immediately and one background thread, cluster-wide (Redis lock), recomputes and overwrites the entry.
* Fail-open exactly like ``redis_single_flight_cache``: any Redis error computes directly.

``SWR_CACHE=0`` disables the stale path (an aged entry is a miss, as with the old TTL)."""

from __future__ import annotations

import contextvars
import logging
import os
import pickle
import threading
import time
import uuid
from typing import Any, Callable, TypeVar

from modules import redis_cache
from modules.redis_cache import redis_exceptions

logger = logging.getLogger("fantasygm.swr_cache")
T = TypeVar("T")

ENABLED = os.environ.get("SWR_CACHE", "1").strip().lower() not in {"0", "false", "no", "off"}
_REFRESH_FAILURE_BACKOFF_SECONDS = 30.0
_local_lock = threading.Lock()
_inflight: set[str] = set()
_failed_until: dict[str, float] = {}


def _spawn_refresh(target: Callable[[], None]) -> None:
    """Run ``target`` off the request path. Tests replace this with a synchronous or captured runner."""

    ctx = contextvars.copy_context()
    threading.Thread(target=lambda: ctx.run(target), name="dgm-swr-refresh", daemon=True).start()


def _store(client: Any, cache_key: str, value: Any, stale_ttl_seconds: int, now: float) -> None:
    try:
        client.set(cache_key, pickle.dumps((now, value)), ex=int(stale_ttl_seconds))
    except redis_exceptions.RedisError:
        logger.warning("Redis unreachable caching SWR result for %s.", cache_key, exc_info=True)


def _decode(raw: bytes | None) -> tuple[float, Any] | None:
    if raw is None:
        return None
    try:
        stamped, value = pickle.loads(raw)
        return float(stamped), value
    except Exception:
        logger.exception("Corrupt SWR entry; treating as a miss.")
        return None


def _refresh_in_background(
    client: Any, cache_key: str, stale_ttl_seconds: int, compute: Callable[[], Any], lock_timeout_seconds: float,
    clock: Callable[[], float],
) -> None:
    with _local_lock:
        if cache_key in _inflight or _failed_until.get(cache_key, 0.0) > clock():
            return
        _inflight.add(cache_key)

    lock_key = f"lock:{cache_key}"
    token = uuid.uuid4().hex.encode("utf-8")

    def _run() -> None:
        acquired = False
        try:
            try:
                acquired = bool(client.set(lock_key, token, nx=True, px=max(1000, int(lock_timeout_seconds * 1000))))
            except redis_exceptions.RedisError:
                return
            if not acquired:
                return  # another worker is already refreshing this key
            try:
                value = compute()
            except Exception:
                logger.warning("Background SWR refresh failed for %s; keeping the stale entry.", cache_key, exc_info=True)
                with _local_lock:
                    _failed_until[cache_key] = clock() + _REFRESH_FAILURE_BACKOFF_SECONDS
                return
            _store(client, cache_key, value, stale_ttl_seconds, clock())
        finally:
            if acquired:
                redis_cache._release_lock(client, lock_key, token)
            with _local_lock:
                _inflight.discard(cache_key)

    try:
        _spawn_refresh(_run)
    except Exception:
        with _local_lock:
            _inflight.discard(cache_key)


def redis_swr_cache(
    *,
    cache_key: str,
    fresh_ttl_seconds: float,
    stale_ttl_seconds: int,
    compute: Callable[[], T],
    lock_timeout_seconds: float = 15.0,
    clock: Callable[[], float] = time.time,
) -> T:
    """Stale-while-revalidate (see module docstring). ``cache_key`` MUST embed a fingerprint of every input of ``compute``
    (never a time bucket) so a changed input can only miss."""

    if not ENABLED:
        return redis_cache.redis_single_flight_cache(
            cache_key=cache_key, ttl_seconds=int(fresh_ttl_seconds), compute=compute, lock_timeout_seconds=lock_timeout_seconds
        )
    client = redis_cache.get_redis_client()
    try:
        entry = _decode(client.get(cache_key))
    except redis_exceptions.RedisError:
        logger.warning("Redis unreachable reading SWR cache %s; computing uncached (fail-open).", cache_key, exc_info=True)
        return compute()

    if entry is not None:
        stamped, value = entry
        if clock() - stamped >= fresh_ttl_seconds:
            _refresh_in_background(client, cache_key, stale_ttl_seconds, compute, lock_timeout_seconds, clock)
        return value

    lock_key = f"lock:{cache_key}"
    token = uuid.uuid4().hex.encode("utf-8")
    lock_ttl_ms = max(1000, int(lock_timeout_seconds * 1000))
    deadline = time.monotonic() + lock_timeout_seconds
    while True:
        try:
            acquired = client.set(lock_key, token, nx=True, px=lock_ttl_ms)
        except redis_exceptions.RedisError:
            return compute()
        if acquired:
            try:
                result = compute()
                _store(client, cache_key, result, stale_ttl_seconds, clock())
            finally:
                redis_cache._release_lock(client, lock_key, token)
            return result
        if time.monotonic() >= deadline:
            return compute()
        time.sleep(redis_cache._LOCK_POLL_INTERVAL_SECONDS)
        try:
            entry = _decode(client.get(cache_key))
        except redis_exceptions.RedisError:
            return compute()
        if entry is not None:
            return entry[1]
