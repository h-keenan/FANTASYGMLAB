"""Admission control / load shedding for the expensive API endpoints.

Why: one uvicorn worker is one GIL. The 50-cold-user load test
(docs/load-test-2026-10.md) showed that when more heavy requests arrive than a
worker can run, every one of them just gets slower together (dashboard p50 51s,
most 200-user requests hit the client's 60s timeout) and nobody is served. A
bounded concurrency gate turns that into: serve N at full speed, queue a
bounded few briefly, and answer the rest immediately with an honest, retryable
``503`` plus ``Retry-After`` that clients already know how to back off from.

Shape (per worker process, since the constraint is per-GIL):

* ``max_inflight`` expensive requests run at once.
* Up to ``max_queue`` more wait, each for at most ``max_wait_seconds``.
* Anything beyond that, or any waiter that times out, is shed with 503
  ``{"code": "server_busy", ...}`` and ``Retry-After`` scaled to queue depth.

Only the paths matched by ``is_expensive`` are gated; auth, health, analytics,
settings and every cheap route are never queued behind heavy work. Fail-open:
any internal error admits the request. Pure ASGI (no BaseHTTPMiddleware) so
gated requests are not re-buffered.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any

logger = logging.getLogger("fantasygm.admission")

DEFAULT_MAX_INFLIGHT = 8
DEFAULT_MAX_QUEUE = 24
DEFAULT_MAX_WAIT_SECONDS = 10.0

# Engine-backed routes (frame builds, simulations, idea searches). Matched on
# the path only; method is irrelevant (POST trade-analyzer is as heavy as GET).
_EXPENSIVE = re.compile(
    r"^/v1/leagues/[^/]+/(?:"
    r"dashboard|my-team|my-team-needs|matchup(?:/what-if)?|waivers|"
    r"trade-hub(?:/.*)?|trade-finder|trade-target|trade-analyzer|all-trades|"
    r"playoff-odds|team-rankings|team-profiles|rankings|gm-plan|"
    r"games/season-sim(?:/what-if)?|trade-odds-effect|"
    r"recap|roundup|history|storylines|managers/.*|keepers|draft-center"
    r")/?$"
)


def is_expensive(path: str) -> bool:
    if not path.startswith("/v1/leagues/"):
        return False
    if path.endswith(".png"):
        return False
    return _EXPENSIVE.match(path) is not None


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


class AdmissionControlMiddleware:
    """Bounded-concurrency gate with a short bounded queue (see module doc)."""

    def __init__(self, app: Any, *, enabled_in_tests: bool = False) -> None:
        self.app = app
        self._enabled_in_tests = enabled_in_tests
        self._inflight = 0
        self._waiting = 0
        self._cond: asyncio.Condition | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.stats = {"admitted": 0, "queued": 0, "shed_full": 0, "shed_timeout": 0}

    # -- config is read per request so ops can retune via env + restart, and tests via monkeypatch
    @staticmethod
    def _limits() -> tuple[int, int, float]:
        return (
            _env_int("ADMISSION_MAX_INFLIGHT", DEFAULT_MAX_INFLIGHT),
            _env_int("ADMISSION_MAX_QUEUE", DEFAULT_MAX_QUEUE),
            _env_float("ADMISSION_MAX_WAIT_SECONDS", DEFAULT_MAX_WAIT_SECONDS),
        )

    def snapshot(self) -> dict[str, int]:
        return {**self.stats, "inflight": self._inflight, "waiting": self._waiting}

    def _condition(self) -> asyncio.Condition:
        loop = asyncio.get_running_loop()
        if self._cond is None or self._loop is not loop:
            self._cond, self._loop = asyncio.Condition(), loop
            self._inflight = self._waiting = 0
        return self._cond

    @staticmethod
    def _retry_after(waiting: int, max_inflight: int) -> int:
        return max(2, min(20, 2 + waiting // max(1, max_inflight)))

    async def _shed(self, scope, receive, send, *, reason: str, waiting: int, max_inflight: int) -> None:
        retry_after = self._retry_after(waiting, max_inflight)
        message = "FantasyDesk is busy right now. Your request is safe to retry in a few seconds."
        body = (
            b'{"ok":false,"code":"server_busy","error":"%s","detail":"%s","retry_after":%d}'
            % (message.encode(), message.encode(), retry_after)
        )
        logger.warning("Admission shed (%s): %s waiting=%d", reason, scope.get("path"), waiting)
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(retry_after).encode()),
                    (b"cache-control", b"no-store"),
                    (b"x-admission", reason.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or scope.get("method") == "OPTIONS" or not is_expensive(scope.get("path") or ""):
            await self.app(scope, receive, send)
            return
        if not self._enabled_in_tests and os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
            "DYNASTYGM_FORCE_ADMISSION"
        ):
            await self.app(scope, receive, send)
            return
        max_inflight, max_queue, max_wait = self._limits()
        if max_inflight <= 0:
            await self.app(scope, receive, send)
            return

        cond = self._condition()
        admitted = False
        reason, waiting = "", 0
        async with cond:
            if self._inflight < max_inflight:
                self._inflight += 1
                admitted = True
            elif self._waiting >= max_queue:
                waiting, reason = self._waiting, "queue_full"
                self.stats["shed_full"] += 1
            else:
                self._waiting += 1
                self.stats["queued"] += 1
                deadline = time.monotonic() + max_wait
                try:
                    while self._inflight >= max_inflight:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        try:
                            await asyncio.wait_for(cond.wait(), timeout=remaining)
                        except asyncio.TimeoutError:
                            break
                finally:
                    self._waiting -= 1
                if self._inflight < max_inflight:
                    self._inflight += 1
                    admitted = True
                else:
                    waiting, reason = self._waiting, "queue_timeout"
                    self.stats["shed_timeout"] += 1

        if not admitted:
            await self._shed(scope, receive, send, reason=reason, waiting=waiting, max_inflight=max_inflight)
            return

        self.stats["admitted"] += 1
        try:
            await self.app(scope, receive, send)
        finally:
            async with cond:
                self._inflight -= 1
                cond.notify()
