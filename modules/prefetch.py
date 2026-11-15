"""Run independent, idempotent cache-warming reads concurrently.

A request often needs several Sleeper reads that do not depend on each other (a roster list, a user lookup, a league's users and
traded picks) and used to issue them one after another, paying one network round trip each. ``warm_parallel`` runs them at the same
time and returns when all have finished; the caller then makes the SAME calls it always made, which now hit the in-process
caches those reads populate. It changes nothing a caller can observe: a warm-up that fails is swallowed (the real call runs
again and raises or recovers exactly as before), and nothing is returned or shared except through the callee's own cache."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Callable

logger = logging.getLogger("fantasygm.prefetch")

_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="prefetch")


def warm_parallel(*calls: Callable[[], object], timeout: float = 20.0) -> None:
    """Run ``calls`` concurrently (a single call just runs inline) and wait for them; never raises."""

    live = [c for c in calls if c is not None]
    if len(live) < 2:
        for call in live:
            _safely(call)
        return
    try:
        futures = [_POOL.submit(_safely, call) for call in live]
        wait(futures, timeout=timeout)
    except RuntimeError:  # interpreter shutting down: the caller's own sequential calls still work
        return


def _safely(call: Callable[[], object]) -> None:
    try:
        call()
    except Exception:  # the caller repeats the real call and handles/raises it itself
        logger.debug("prefetch warm-up failed", exc_info=True)
