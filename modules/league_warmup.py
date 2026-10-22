"""Best-effort background warm-up for a freshly saved league.

After POST /v1/leagues/save the first Dashboard would otherwise compute the
shared, cached league work (rankings frame, trade-idea search) in the
caller's request. This module runs the same cached builders once in a
low-priority background thread so that first open finds them warm, and
records which stages finished in Redis so GET .../warmup-status can show
real progress. Everything here is fail-open: it never raises into callers.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from typing import Any, Callable

from modules import redis_cache, sleeper_budget

logger = logging.getLogger(__name__)

STAGES = ("roster", "values", "trades")
RATE_LIMIT_SECONDS = 180
STATE_TTL_SECONDS = 900
MAX_CONCURRENT_WARMUPS = 2

_slots = threading.BoundedSemaphore(MAX_CONCURRENT_WARMUPS)


def _state_key(user_id: str, league_id: str) -> str:
    return redis_cache.build_cache_key("league_warmup_state", user_id, league_id)


def _limit_key(user_id: str, league_id: str) -> str:
    return redis_cache.build_cache_key("league_warmup_limit", user_id, league_id)


def _write_state(user_id: str, league_id: str, state: str, done: list[str]) -> None:
    try:
        redis_cache.get_redis_client().set(
            _state_key(user_id, league_id),
            json.dumps({"state": state, "done": done}),
            ex=STATE_TTL_SECONDS,
        )
    except Exception:
        logger.debug("warm-up state write failed", exc_info=True)


def read_status(user_id: str, league_id: str) -> dict[str, Any]:
    """{"state": none|running|done|error, "stages": {stage: bool}}. "none"
    means no warm-up is known (never started, expired, or Redis down), which
    callers treat as nothing to wait for."""

    state, done = "none", []
    try:
        raw = redis_cache.get_redis_client().get(_state_key(user_id, league_id))
        if raw:
            parsed = json.loads(raw)
            state = str(parsed.get("state") or "none")
            done = [s for s in parsed.get("done", []) if s in STAGES]
    except Exception:
        state, done = "none", []
    return {"state": state, "stages": {stage: stage in done for stage in STAGES}}


def _lower_thread_priority() -> None:
    if not sys.platform.startswith("linux"):
        return
    try:
        current = os.getpriority(os.PRIO_PROCESS, threading.get_native_id())
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), min(19, current + 10))
    except Exception:
        pass


def start_warmup(
    *,
    user_id: str,
    league_id: str,
    steps: dict[str, Callable[[], None]],
) -> bool:
    """Start a warm-up thread. Returns True only if one was started. Skipped
    when rate-limited (one per user+league per RATE_LIMIT_SECONDS, which also
    covers "already in flight"), when Redis is unavailable, or when this
    process already runs MAX_CONCURRENT_WARMUPS. Never raises."""

    try:
        if not user_id or not league_id:
            return False
        if sleeper_budget.over_soft_threshold():
            # Warm-ups are pure pre-computation; skip them while Sleeper
            # budget is tight (the first real open computes on demand).
            sleeper_budget.note_deferred()
            return False
        client = redis_cache.get_redis_client()
        if not client.set(_limit_key(user_id, league_id), "1", nx=True, ex=RATE_LIMIT_SECONDS):
            return False
        if not _slots.acquire(blocking=False):
            return False
        _write_state(user_id, league_id, "running", [])
        thread = threading.Thread(
            target=_run, args=(user_id, league_id, steps), name="league-warmup", daemon=True
        )
        thread.start()
        return True
    except Exception:
        logger.debug("warm-up start failed", exc_info=True)
        return False


def _run(user_id: str, league_id: str, steps: dict[str, Callable[[], None]]) -> None:
    done: list[str] = []
    state = "done"
    try:
        _lower_thread_priority()
        sleeper_budget.set_low_priority_for_thread()
        for stage in STAGES:
            step = steps.get(stage)
            if step is not None:
                step()
            done.append(stage)
            _write_state(user_id, league_id, "running", list(done))
    except Exception:
        logger.warning("league warm-up failed for %s", league_id, exc_info=True)
        state = "error"
    finally:
        _write_state(user_id, league_id, state, done)
        _slots.release()
