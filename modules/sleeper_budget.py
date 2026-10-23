"""Sleeper call-rate budget, request priority, and last-known-good cache.

Sleeper's public API tolerates roughly 1000 calls/minute per IP. Every worker
on this box shares one IP, so the budget is counted cluster-wide in Redis
(``modules.redis_cache``, already used for the other shared caches) with a
process-local sliding window as the fail-open fallback.

Three small pieces, all fail-open (a failure here never blocks a request):

1. ``record_call()`` / ``calls_in_last_minute()``: the per-minute counter.
2. Priority: ``low_priority()`` marks background work (league warm-ups, the
   players-dump refresh) and ``set_request_tier()`` marks a request as coming
   from a free-tier user. ``should_defer()`` is True for that work only once
   the soft threshold (default 70% of 1000/min) is crossed. Paid-tier
   (Pro / Front Office) and untagged requests are never deferred.
3. ``remember()`` / ``last_known()``: the most recent *successful* payload per
   URL with its fetch time, so a 429/timeout (or a paused refresh) can serve
   real last-known data with an honest "as of" instead of an empty result.
   Nothing is ever synthesized.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import os
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any, Iterator

logger = logging.getLogger("fantasygm.sleeper_budget")

BUDGET_PER_MINUTE = int(os.environ.get("SLEEPER_CALLS_PER_MINUTE", "1000"))
SOFT_THRESHOLD_FRACTION = float(os.environ.get("SLEEPER_BUDGET_SOFT_FRACTION", "0.7"))
SOFT_THRESHOLD = int(BUDGET_PER_MINUTE * SOFT_THRESHOLD_FRACTION)
WINDOW_SECONDS = 60
LAST_KNOWN_MAX_ENTRIES = 1024

# "low" = background work; "free" = a free-tier user's request; "" = normal.
_priority: contextvars.ContextVar[str] = contextvars.ContextVar("sleeper_priority", default="")
# URLs served from last-known data during the current request, with fetch time.
_stale_served: contextvars.ContextVar[dict[str, float] | None] = contextvars.ContextVar(
    "sleeper_stale_served", default=None
)

_lock = threading.Lock()
_local_calls: deque[float] = deque()
_last_known: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()
_redis_count_cache: tuple[float, int] = (0.0, 0)
_deferred_total = 0
_stale_total = 0


# ------------------------------------------------------------------ counter
def _redis_key(now: float) -> str:
    return f"sleeper_budget:{int(now // WINDOW_SECONDS)}"


def record_call() -> None:
    """Count one outbound Sleeper request (cluster-wide when Redis is up)."""

    now = time.time()
    with _lock:
        _local_calls.append(now)
        cutoff = now - WINDOW_SECONDS
        while _local_calls and _local_calls[0] < cutoff:
            _local_calls.popleft()
    try:
        from modules import redis_cache

        client = redis_cache.get_redis_client()
        key = _redis_key(now)
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, WINDOW_SECONDS * 3)
        pipe.execute()
    except Exception:
        pass  # fail open to the local window


def _local_count(now: float) -> int:
    cutoff = now - WINDOW_SECONDS
    with _lock:
        while _local_calls and _local_calls[0] < cutoff:
            _local_calls.popleft()
        return len(_local_calls)


def calls_in_last_minute() -> int:
    """Best estimate of calls in the last minute: the larger of this process's
    sliding window and the shared Redis fixed-minute counters (current minute
    plus the previous one, weighted by how much of it still overlaps).
    Redis reads are cached for one second."""

    global _redis_count_cache
    now = time.time()
    local = _local_count(now)
    cached_at, cached = _redis_count_cache
    if now - cached_at < 1.0:
        return max(local, cached)
    shared = 0
    try:
        from modules import redis_cache

        client = redis_cache.get_redis_client()
        cur = int(client.get(_redis_key(now)) or 0)
        prev = int(client.get(_redis_key(now - WINDOW_SECONDS)) or 0)
        frac_prev = 1.0 - ((now % WINDOW_SECONDS) / WINDOW_SECONDS)
        shared = int(cur + prev * frac_prev)
    except Exception:
        shared = 0
    _redis_count_cache = (now, shared)
    return max(local, shared)


def over_soft_threshold() -> bool:
    return calls_in_last_minute() >= SOFT_THRESHOLD


# ----------------------------------------------------------------- priority
@contextlib.contextmanager
def low_priority() -> Iterator[None]:
    """Mark the enclosed work (warm-ups, background refresh) as pausable."""

    token = _priority.set("low")
    try:
        yield
    finally:
        _priority.reset(token)


def set_low_priority_for_thread() -> None:
    """Mark the rest of this (dedicated background) thread as low priority."""

    _priority.set("low")


def set_request_tier(entitlement: str | None) -> None:
    """Called once a request's entitlement is known. Only free tier is
    pausable; entitlement rules themselves are untouched."""

    if _priority.get() == "low":
        return
    tier = str(entitlement or "").strip().lower()
    _priority.set("free" if tier in ("", "free") else "paid")


def current_priority() -> str:
    return _priority.get()


def should_defer() -> bool:
    """True when pausable work should not spend Sleeper budget right now."""

    return _priority.get() in ("low", "free") and over_soft_threshold()


def should_skip_outright() -> bool:
    """Background work with no user waiting: skip entirely when over budget."""

    return _priority.get() == "low" and over_soft_threshold()


# -------------------------------------------------------- last-known cache
def remember(key: str, payload: Any) -> None:
    now = time.time()
    with _lock:
        _last_known[key] = (payload, now)
        _last_known.move_to_end(key)
        while len(_last_known) > LAST_KNOWN_MAX_ENTRIES:
            _last_known.popitem(last=False)


def last_known(key: str) -> tuple[Any, float] | None:
    with _lock:
        entry = _last_known.get(key)
    return entry


def note_stale_served(key: str, fetched_at: float) -> None:
    global _stale_total
    _stale_total += 1
    served = _stale_served.get()
    if served is None:
        served = {}
        _stale_served.set(served)
    served[key] = fetched_at


def note_deferred() -> None:
    global _deferred_total
    _deferred_total += 1


def begin_request() -> None:
    """Reset per-request state (call at the start of a request context)."""

    _stale_served.set({})


def stale_as_of() -> str | None:
    """ISO timestamp of the OLDEST last-known payload served during this
    request, or None when everything was live."""

    served = _stale_served.get()
    if not served:
        return None
    return datetime.fromtimestamp(min(served.values()), tz=timezone.utc).isoformat()


def snapshot() -> dict[str, Any]:
    return {
        "calls_last_minute": calls_in_last_minute(),
        "budget_per_minute": BUDGET_PER_MINUTE,
        "soft_threshold": SOFT_THRESHOLD,
        "over_soft_threshold": over_soft_threshold(),
        "deferred_total": _deferred_total,
        "stale_served_total": _stale_total,
    }


def reset_for_tests() -> None:
    global _redis_count_cache, _deferred_total, _stale_total
    with _lock:
        _local_calls.clear()
        _last_known.clear()
    _redis_count_cache = (0.0, 0)
    _deferred_total = _stale_total = 0
    _priority.set("")
    _stale_served.set(None)
