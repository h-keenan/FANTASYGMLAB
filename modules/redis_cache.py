"""Shared Redis client + distributed single-flight cache helper.

Self-hosted deployment (see docker-compose.yml/docs/SELF_HOSTED_MIGRATION.md)
moved mobile-api from one always-on uvicorn worker to several (`--workers N`)
to actually use the box's cores under concurrent load — see
docker-compose.yml's mobile-api comment for the full "why" (one GIL per
process means one CPU-heavy request, e.g. Trade Hub's idea-generation pass,
previously stalled every other concurrent request on the single worker).

That change is only safe because two kinds of per-process state got moved
here, into Redis, so every worker shares them instead of each keeping its
own separate (and therefore sometimes wrong, or redundantly recomputed)
copy:

  1. services/mobile_api_service.py's rate limiter (see its own "Rate
     limiting" section) — a plain Redis INCR/EXPIRE counter now, not a
     dict living in one process's memory.
  2. The three `@lru_cache` + per-process `threading.Lock` single-flight
     caches (modules.trade_hub_engine, modules.league_rankings x2,
     modules.playoff_simulator) — `redis_single_flight_cache` below is
     their shared replacement: a distributed lock (so only ONE worker,
     cluster-wide, ever runs a given expensive computation at a time) plus
     the computed result itself cached in Redis (so a cache hit in worker A
     actually serves a request landing on worker B, not just worker A's
     own future requests).

Both are intentionally FAIL OPEN on any Redis error (connection refused,
timeout, ...): Redis here is a pure performance/correctness-under-scale
aid, not data of record, and this codebase's existing convention elsewhere
(e.g. Team Situation fetch failures) is that an auxiliary system's outage
degrades gracefully — here, "behave like the old single-process code: no
shared rate-limit state, no shared cache, just compute directly" — rather
than ever taking down the main request path. A Redis outage means every
worker goes back to being an independent single-flight-less process (and
the rate limiter stops limiting) until Redis comes back; it never turns
into a 500.
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
import time
import uuid
from typing import Any, Callable, TypeVar

import redis
from redis import exceptions as redis_exceptions

logger = logging.getLogger("fantasygm.redis_cache")

T = TypeVar("T")

# Matches docker-compose.yml's `redis` service name/port/db — overridable
# per docs/SELF_HOSTED_MIGRATION.md and .env.example for anyone running a
# differently-named/located Redis (or pointing at a managed one).
DEFAULT_REDIS_URL = "redis://redis:6379/0"

# Short socket timeouts: a request stuck waiting on a half-dead TCP
# connection to Redis would be worse than the fail-open path below, which
# depends on a RedisError actually being raised promptly.
_SOCKET_CONNECT_TIMEOUT_SECONDS = 0.5
_SOCKET_TIMEOUT_SECONDS = 0.5

RedisError = redis_exceptions.RedisError

_TEST_OVERRIDE_SENTINEL = "__test_override__"

_client: "redis.Redis | None" = None
_client_bound_url: str | None = None


def _current_redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL).strip() or DEFAULT_REDIS_URL


def get_redis_client() -> "redis.Redis":
    """Lazily construct (and memoize) the process-wide Redis client.

    redis-py connections are themselves lazy (nothing is actually dialed
    until the first command), so constructing this doesn't raise even if
    Redis is down — every call site below handles the RedisError that
    surfaces on the actual command instead.

    Re-binds if REDIS_URL changes (e.g. a test flipping env vars between
    cases) rather than silently keeping a client pointed at a stale URL —
    except while a test override (set_redis_client_for_testing) is active,
    which always wins regardless of REDIS_URL.
    """

    global _client, _client_bound_url
    if _client_bound_url == _TEST_OVERRIDE_SENTINEL:
        return _client
    url = _current_redis_url()
    if _client is None or _client_bound_url != url:
        _client = redis.Redis.from_url(
            url,
            socket_connect_timeout=_SOCKET_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_SOCKET_TIMEOUT_SECONDS,
            decode_responses=False,
        )
        _client_bound_url = url
    return _client


def set_redis_client_for_testing(client: Any) -> None:
    """Test-only hook: inject a client directly (e.g. fakeredis.FakeRedis(),
    or a stub that raises RedisError to exercise the fail-open paths),
    bypassing REDIS_URL/real-network connection entirely."""

    global _client, _client_bound_url
    _client = client
    _client_bound_url = _TEST_OVERRIDE_SENTINEL


def reset_redis_client_for_testing() -> None:
    """Test-only hook: drop the memoized client so the next get_redis_client()
    call rebuilds one from the current REDIS_URL."""

    global _client, _client_bound_url
    _client = None
    _client_bound_url = None


def build_cache_key(namespace: str, *parts: Any) -> str:
    """Stable, bounded-length Redis key from arbitrary cache-key parts.

    Hashing (rather than joining parts with a separator) means key length
    never depends on potentially large inputs (e.g. a long sorted tuple of
    player ids) and two different input tuples can never collide just
    because one part happened to contain the separator character.
    """

    digest = hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


# How often a caller blocked on someone else's single-flight lock re-checks
# whether the result is ready (or the lock has freed up) — short enough to
# not meaningfully add to perceived latency next to the ~150-300ms searches
# this guards (see modules.trade_hub_engine's cache comment), long enough
# to not hammer Redis with a busy-wait.
_LOCK_POLL_INTERVAL_SECONDS = 0.05

# Safe check-then-delete release, guarding the lock so a caller can never
# delete a lock it no longer owns (it expired and someone else already
# re-acquired it) — WATCH/MULTI/EXEC (optimistic locking) rather than a
# Lua EVAL script for this: functionally equivalent atomicity guarantee,
# but works against every real Redis deployment AND fakeredis (this repo's
# test double has no Lua scripting support at the pinned version — see
# tests), so one implementation serves both without a conditional.
def _release_lock(client: "redis.Redis", lock_key: str, token: bytes) -> None:
    try:
        with client.pipeline() as pipe:
            pipe.watch(lock_key)
            current = pipe.get(lock_key)
            pipe.multi()
            if current == token:
                pipe.delete(lock_key)
            else:
                pipe.unwatch()
            pipe.execute()
    except redis_exceptions.WatchError:
        # The key changed between our GET and DELETE (it expired and was
        # re-acquired by another caller) -- safe to do nothing: whoever
        # holds it now owns its lifecycle, not us.
        pass
    except redis_exceptions.RedisError:
        logger.warning(
            "Redis unreachable releasing single-flight lock %s; it will "
            "free on its own via the lock's own PX TTL.",
            lock_key,
            exc_info=True,
        )


def redis_single_flight_cache(
    *,
    cache_key: str,
    ttl_seconds: int,
    compute: Callable[[], T],
    lock_timeout_seconds: float = 15.0,
) -> T:
    """At most one caller, cluster-wide, actually runs `compute` for a given
    `cache_key` within its TTL window; every other concurrent caller for the
    same key either gets the cached result (once the first caller finishes
    and stores it) or -- if Redis itself is unreachable at any point, or
    this caller waits past `lock_timeout_seconds` for another worker's
    computation -- runs `compute` directly itself, uncached. That fallback
    is a deliberate fail-open: a Redis outage degrades this back to "every
    worker computes its own answer" (today's pre-Redis, per-process
    behavior), never a request failure.

    The cached result is pickled: all three current callers (Trade Hub
    idea records, league rankings frames/summaries, playoff odds) return
    plain dict/list structures or pandas DataFrames, none of which are
    uniformly JSON-safe (DataFrames aren't JSON at all; the dict/list
    shapes may carry numpy scalar types) -- pickle handles every one of
    those shapes transparently with one code path. This is safe here
    specifically because the only things that ever read/write this cache
    are this same trusted backend's own worker processes talking to a
    Redis instance that never receives untrusted input (`pickle.loads` of
    attacker-controlled data is the actual risk pickle carries, and that
    threat model doesn't apply to a private, same-stack cache).

    `lock_timeout_seconds` bounds both how long a lock is held (its Redis
    PX TTL) and how long a waiter blocks before giving up and computing its
    own answer -- so one wedged/crashed computation can only ever cost
    other callers this much extra latency once, not forever.
    """

    client = get_redis_client()

    def _read_cached() -> bytes | None:
        return client.get(cache_key)

    try:
        cached = _read_cached()
    except redis_exceptions.RedisError:
        logger.warning(
            "Redis unreachable reading cache %s; computing uncached (fail-open).",
            cache_key,
            exc_info=True,
        )
        return compute()

    if cached is not None:
        try:
            return pickle.loads(cached)
        except Exception:
            logger.exception("Corrupt cached entry for %s; recomputing.", cache_key)

    lock_key = f"lock:{cache_key}"
    token = uuid.uuid4().hex.encode("utf-8")
    lock_ttl_ms = max(1000, int(lock_timeout_seconds * 1000))
    deadline = time.monotonic() + lock_timeout_seconds

    while True:
        try:
            acquired = client.set(lock_key, token, nx=True, px=lock_ttl_ms)
        except redis_exceptions.RedisError:
            logger.warning(
                "Redis unreachable acquiring single-flight lock for %s; "
                "computing uncached (fail-open).",
                cache_key,
                exc_info=True,
            )
            return compute()

        if acquired:
            try:
                result = compute()
                # Cache write happens WHILE we still hold the lock, not
                # after releasing it: releasing first would open a window
                # where another waiter sees no lock AND no cached result
                # yet, re-acquires the lock, and redoes the computation —
                # exactly the double-run this whole mechanism exists to
                # prevent.
                try:
                    client.set(cache_key, pickle.dumps(result), ex=ttl_seconds)
                except redis_exceptions.RedisError:
                    logger.warning(
                        "Redis unreachable caching result for %s; result still "
                        "returned, just not shared with other workers this time.",
                        cache_key,
                        exc_info=True,
                    )
            finally:
                _release_lock(client, lock_key, token)
            return result

        if time.monotonic() >= deadline:
            logger.warning(
                "Timed out after %.1fs waiting for the single-flight lock on "
                "%s; computing uncached.",
                lock_timeout_seconds,
                cache_key,
            )
            return compute()

        time.sleep(_LOCK_POLL_INTERVAL_SECONDS)

        try:
            cached = _read_cached()
        except redis_exceptions.RedisError:
            logger.warning(
                "Redis unreachable polling cache for %s; computing uncached (fail-open).",
                cache_key,
                exc_info=True,
            )
            return compute()

        if cached is not None:
            try:
                return pickle.loads(cached)
            except Exception:
                logger.exception("Corrupt cached entry for %s; recomputing.", cache_key)
                # Fall through and retry lock acquisition on the next loop.
