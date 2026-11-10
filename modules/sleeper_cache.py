"""Shared, single-flight cache for live Sleeper GETs.

Before this module every uvicorn worker kept its own 30s ``lru_cache`` per
league endpoint, so N workers (and N concurrent first-openers of the same
league) each spent Sleeper budget on the same URL. The local load test
(docs/load-test-2026-10.md) measured 33-66 Sleeper calls per cold session
against a 1,000/min per-IP budget.

``shared_json`` fixes that with three layers, all fail-open:

1. Fresh hit: a JSON envelope ``{"ts", "p"}`` in Redis (cluster-wide) or, when
   Redis is unreachable, a bounded process-local store. Younger than ``ttl``
   means no upstream call at all.
2. Single-flight: on a miss exactly one caller per URL fetches. Threads in the
   same process coalesce on a per-key lock; workers coalesce on a Redis
   ``SET NX PX`` lock. Followers re-read the envelope instead of fetching, and
   only fetch themselves if the leader never publishes (timeout / Redis down).
3. Stale-while-error: envelopes live for ``STALE_TTL_SECONDS`` (far longer than
   ``ttl``). If the upstream fetch fails (429/5xx/timeout) the last real
   payload is served and recorded via ``sleeper_budget.note_stale_served`` so
   callers can show an honest "as of". Nothing is ever synthesized, and a
   stale or failed result is never written back as fresh.

``fetch`` returns the payload or ``None`` on failure (``modules.sleeper``'s
``_request_json`` contract). An empty list/dict is a valid, cacheable payload.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, Callable

from modules import sleeper_budget

logger = logging.getLogger("fantasygm.sleeper_cache")

STALE_TTL_SECONDS = 6 * 60 * 60
LOCAL_MAX_ENTRIES = 1024
# Short in-process negative cache: when Sleeper is failing and we hold nothing
# to serve, do not let every request re-hit it.
NEGATIVE_TTL_SECONDS = 3.0
# How long a follower waits for the leader before fetching itself.
FOLLOWER_WAIT_SECONDS = 8.0
LOCK_PX_MS = 15_000
_POLL_SECONDS = 0.03
# After a Redis error, skip Redis for this long (no per-call connect timeouts).
_REDIS_COOLDOWN_SECONDS = 5.0

_lock = threading.Lock()
_local: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()
_negative: dict[str, float] = {}
_key_locks: dict[str, list] = {}  # key -> [Lock, refcount]
_redis_down_until = 0.0
# Entries fetched before this instant are not 'fresh' in this process (an
# explicit refresh via clear_local); they remain usable as stale-on-error.
_fresh_floor = 0.0
_stats = {"hit": 0, "miss": 0, "coalesced": 0, "stale": 0, "fetch": 0, "fail": 0}


def _bump(name: str) -> None:
    with _lock:
        _stats[name] += 1


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_stats)


def reset_for_tests() -> None:
    global _redis_down_until, _fresh_floor
    _fresh_floor = 0.0
    with _lock:
        _local.clear()
        _negative.clear()
        _key_locks.clear()
        for k in _stats:
            _stats[k] = 0
    _redis_down_until = 0.0


def clear_local() -> None:
    """Explicit refresh: drop the local store and stop treating anything
    fetched so far (including shared Redis entries) as fresh in this process.
    Older entries still serve as stale-on-error."""

    global _fresh_floor
    _fresh_floor = time.time()
    with _lock:
        _local.clear()
        _negative.clear()


def _is_fresh(entry: tuple[Any, float] | None, ttl: float) -> bool:
    return entry is not None and entry[1] >= _fresh_floor and time.time() - entry[1] < ttl


def cache_key(url: str) -> str:
    return "sleeper_cache:v1:" + hashlib.sha256(url.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- storage
def _redis():
    global _redis_down_until
    if time.monotonic() < _redis_down_until:
        return None
    try:
        from modules import redis_cache

        return redis_cache.get_redis_client()
    except Exception:
        _redis_down_until = time.monotonic() + _REDIS_COOLDOWN_SECONDS
        return None


def _redis_failed() -> None:
    global _redis_down_until
    _redis_down_until = time.monotonic() + _REDIS_COOLDOWN_SECONDS


def _get_entry(key: str) -> tuple[Any, float] | None:
    """Newest known ``(payload, fetched_at)`` from Redis or the local store."""

    with _lock:
        best = _local.get(key)
    client = _redis()
    if client is not None:
        try:
            raw = client.get(key)
            if raw is not None:
                env = json.loads(raw)
                entry = (env["p"], float(env["ts"]))
                if best is None or entry[1] > best[1]:
                    best = entry
        except Exception:
            _redis_failed()
    return best


def _put_entry(key: str, payload: Any, ts: float) -> None:
    with _lock:
        _local[key] = (payload, ts)
        _local.move_to_end(key)
        while len(_local) > LOCAL_MAX_ENTRIES:
            _local.popitem(last=False)
        _negative.pop(key, None)
    client = _redis()
    if client is not None:
        try:
            client.set(key, json.dumps({"ts": ts, "p": payload}), ex=STALE_TTL_SECONDS)
        except Exception:
            _redis_failed()


def _acquire_key_lock(key: str) -> threading.Lock:
    with _lock:
        slot = _key_locks.get(key)
        if slot is None:
            slot = _key_locks[key] = [threading.Lock(), 0]
        slot[1] += 1
        return slot[0]


def _release_key_lock(key: str) -> None:
    with _lock:
        slot = _key_locks.get(key)
        if slot is not None:
            slot[1] -= 1
            if slot[1] <= 0:
                _key_locks.pop(key, None)


def _redis_unlock(client, lock_key: str, token: bytes) -> None:
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
    except Exception:
        pass  # the lock frees itself via its PX TTL


# --------------------------------------------------------------- main entry
def _fetch_and_store(key: str, url: str, fetch: Callable[[], Any]) -> tuple[Any, bool]:
    """Run ``fetch``. Returns ``(payload, is_fresh)``; fresh payloads are stored."""

    started = time.time()
    _bump("fetch")
    payload = fetch()
    if payload is None:
        return None, False
    # ``_request_json`` answers a failed call from sleeper_budget's last-known
    # store: that is stale data, not a fresh success. A real success calls
    # remember() after ``started``.
    known = sleeper_budget.last_known(url)
    if known is not None and known[1] < started - 0.001:
        return payload, False
    _put_entry(key, payload, time.time())
    return payload, True


def shared_json(
    url: str,
    *,
    ttl: float,
    fetch: Callable[[], Any],
    max_age_on_error: float = STALE_TTL_SECONDS,
) -> Any:
    """Return the JSON payload for ``url``, fetching at most once per ``ttl``
    cluster-wide. ``None`` only when there is neither a live nor a stale value."""

    key = cache_key(url)
    entry = _get_entry(key)
    if _is_fresh(entry, ttl):
        _bump("hit")
        return entry[0]

    with _lock:
        neg_until = _negative.get(key, 0.0)
    if neg_until > time.time() and entry is None:
        return None

    key_lock = _acquire_key_lock(key)
    try:
        with key_lock:
            # Another thread in this process may have just filled it.
            entry = _get_entry(key)
            if _is_fresh(entry, ttl):
                _bump("coalesced")
                return entry[0]

            _bump("miss")
            client = _redis()
            token = uuid.uuid4().hex.encode()
            lock_key = "lock:" + key
            leader = True
            if client is not None:
                try:
                    leader = bool(client.set(lock_key, token, nx=True, px=LOCK_PX_MS))
                except Exception:
                    _redis_failed()
                    client, leader = None, True
            if not leader:
                deadline = time.monotonic() + FOLLOWER_WAIT_SECONDS
                while time.monotonic() < deadline:
                    time.sleep(_POLL_SECONDS)
                    # Check the lock BEFORE reading the entry: the leader
                    # publishes, then unlocks, so "lock gone" guarantees the
                    # entry read below already sees its result.
                    try:
                        lock_gone = client.get(lock_key) is None
                    except Exception:
                        _redis_failed()
                        lock_gone = True
                    entry = _get_entry(key)
                    if _is_fresh(entry, ttl):
                        _bump("coalesced")
                        return entry[0]
                    if lock_gone:
                        break  # leader finished without a result: take over
            try:
                payload, fresh = _fetch_and_store(key, url, fetch)
            finally:
                if client is not None and leader:
                    _redis_unlock(client, lock_key, token)

            if fresh:
                return payload
            # Failure (or an already-stale answer): serve the newest real value
            # we hold, within the allowed staleness, and record it as stale.
            entry = _get_entry(key)
            if entry is not None and time.time() - entry[1] <= max_age_on_error:
                _bump("stale")
                sleeper_budget.note_stale_served(url, entry[1])
                return entry[0]
            if payload is None:
                _bump("fail")
                with _lock:
                    _negative[key] = time.time() + NEGATIVE_TTL_SECONDS
                    if len(_negative) > 4096:
                        now = time.time()
                        for k in [k for k, v in _negative.items() if v < now]:
                            _negative.pop(k, None)
            return payload
    finally:
        _release_key_lock(key)
