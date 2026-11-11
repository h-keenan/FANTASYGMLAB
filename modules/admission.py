"""Admission control / load shedding for the expensive API endpoints.

Why: one uvicorn worker is one GIL. The 50-cold-user load test
(docs/load-test-2026-10.md) showed that when more heavy requests arrive than a
worker can run, every one of them just gets slower together (dashboard p50 51s,
most 200-user requests hit the client's 60s timeout) and nobody is served. A
bounded concurrency gate turns that into: serve N at full speed, queue a
bounded few briefly, and answer the rest immediately with an honest, retryable
``503`` plus ``Retry-After`` that clients already know how to back off from.

Two lanes, each with its own pool (per worker process, since the constraint is
per-GIL), so cheap/cached reads never queue behind heavy engine work:

* ``heavy``: frame builds, trade engines, simulations (``ADMISSION_*``).
* ``light``: routes that are mostly served from the shared caches once warm
  (my-team, matchup, waivers, rankings, playoff-odds, ...) with a larger
  pool (``ADMISSION_LIGHT_*``). A cold light request still occupies a light
  slot while it builds, but it can neither be shed by nor delay heavy work.

Per lane:

* ``max_inflight`` requests run at once.
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
DEFAULT_LIGHT_MAX_INFLIGHT = 16
DEFAULT_LIGHT_MAX_QUEUE = 48
DEFAULT_LIGHT_MAX_WAIT_SECONDS = 10.0

# Engine-backed routes (frame builds, simulations, idea searches). Matched on
# the path only; method is irrelevant (POST trade-analyzer is as heavy as GET).
_HEAVY = re.compile(
    r"^/v1/leagues/[^/]+/(?:"
    r"dashboard|matchup/what-if|"
    r"trade-hub(?:/.*)?|trade-ideas/multi|trade-finder|trade-target|trade-analyzer(?:/multi)?|all-trades|"
    r"team-rankings|team-profiles|gm-plan|"
    r"games/season-sim(?:/what-if)?|trade-odds-effect|"
    r"recap|history|storylines|managers/.*"
    r")/?$"
)
# Cheap once the shared (league, lens) frame / response caches are warm.
_LIGHT = re.compile(
    r"^/v1/leagues/[^/]+/(?:"
    r"my-team|my-team-needs|matchup|waivers|rankings|playoff-odds|roundup|keepers|draft-center"
    r")/?$"
)


def lane_for(path: str) -> str | None:
    """``"heavy"`` / ``"light"`` for gated paths, ``None`` for ungated ones."""

    if not path.startswith("/v1/leagues/") or path.endswith(".png"):
        return None
    if _HEAVY.match(path):
        return "heavy"
    if _LIGHT.match(path):
        return "light"
    return None


def is_expensive(path: str) -> bool:
    return lane_for(path) is not None


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


class _Lane:
    """Concurrency state of one pool; rebuilt if the event loop changes."""

    def __init__(self) -> None:
        self.inflight = 0
        self.waiting = 0
        self.cond: asyncio.Condition | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    def condition(self) -> asyncio.Condition:
        loop = asyncio.get_running_loop()
        if self.cond is None or self.loop is not loop:
            self.cond, self.loop = asyncio.Condition(), loop
            self.inflight = self.waiting = 0
        return self.cond


class AdmissionControlMiddleware:
    """Per-lane bounded-concurrency gate with a short bounded queue (see module doc)."""

    def __init__(self, app: Any, *, enabled_in_tests: bool = False) -> None:
        self.app = app
        self._enabled_in_tests = enabled_in_tests
        self._lanes = {"heavy": _Lane(), "light": _Lane()}
        self.stats = {"admitted": 0, "queued": 0, "shed_full": 0, "shed_timeout": 0}
        self.lane_stats = {
            name: {"admitted": 0, "queued": 0, "shed_full": 0, "shed_timeout": 0} for name in self._lanes
        }

    # -- config is read per request so ops can retune via env + restart, and tests via monkeypatch
    @staticmethod
    def _limits(lane: str = "heavy") -> tuple[int, int, float]:
        if lane == "light":
            return (
                _env_int("ADMISSION_LIGHT_MAX_INFLIGHT", DEFAULT_LIGHT_MAX_INFLIGHT),
                _env_int("ADMISSION_LIGHT_MAX_QUEUE", DEFAULT_LIGHT_MAX_QUEUE),
                _env_float("ADMISSION_LIGHT_MAX_WAIT_SECONDS", DEFAULT_LIGHT_MAX_WAIT_SECONDS),
            )
        return (
            _env_int("ADMISSION_MAX_INFLIGHT", DEFAULT_MAX_INFLIGHT),
            _env_int("ADMISSION_MAX_QUEUE", DEFAULT_MAX_QUEUE),
            _env_float("ADMISSION_MAX_WAIT_SECONDS", DEFAULT_MAX_WAIT_SECONDS),
        )

    def snapshot(self) -> dict[str, Any]:
        lanes = {
            name: {**self.lane_stats[name], "inflight": lane.inflight, "waiting": lane.waiting}
            for name, lane in self._lanes.items()
        }
        return {
            **self.stats,
            "inflight": sum(lane.inflight for lane in self._lanes.values()),
            "waiting": sum(lane.waiting for lane in self._lanes.values()),
            "lanes": lanes,
        }

    def _count(self, lane: str, name: str) -> None:
        self.stats[name] += 1
        self.lane_stats[lane][name] += 1

    @staticmethod
    def _retry_after(waiting: int, max_inflight: int) -> int:
        return max(2, min(20, 2 + waiting // max(1, max_inflight)))

    async def _shed(self, scope, receive, send, *, reason: str, waiting: int, max_inflight: int, lane: str = "heavy") -> None:
        retry_after = self._retry_after(waiting, max_inflight)
        message = "FantasyDesk is busy right now. Your request is safe to retry in a few seconds."
        body = (
            b'{"ok":false,"code":"server_busy","error":"%s","detail":"%s","retry_after":%d}'
            % (message.encode(), message.encode(), retry_after)
        )
        logger.warning("Admission shed (%s/%s): %s waiting=%d", lane, reason, scope.get("path"), waiting)
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
        lane_name = lane_for(scope.get("path") or "") if scope.get("type") == "http" else None
        if lane_name is None or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if not self._enabled_in_tests and os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
            "DYNASTYGM_FORCE_ADMISSION"
        ):
            await self.app(scope, receive, send)
            return
        max_inflight, max_queue, max_wait = self._limits(lane_name)
        if max_inflight <= 0:
            await self.app(scope, receive, send)
            return

        lane = self._lanes[lane_name]
        cond = lane.condition()
        admitted = False
        reason, waiting = "", 0
        async with cond:
            if lane.inflight < max_inflight:
                lane.inflight += 1
                admitted = True
            elif lane.waiting >= max_queue:
                waiting, reason = lane.waiting, "queue_full"
                self._count(lane_name, "shed_full")
            else:
                lane.waiting += 1
                self._count(lane_name, "queued")
                deadline = time.monotonic() + max_wait
                try:
                    while lane.inflight >= max_inflight:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        try:
                            await asyncio.wait_for(cond.wait(), timeout=remaining)
                        except asyncio.TimeoutError:
                            break
                finally:
                    lane.waiting -= 1
                if lane.inflight < max_inflight:
                    lane.inflight += 1
                    admitted = True
                else:
                    waiting, reason = lane.waiting, "queue_timeout"
                    self._count(lane_name, "shed_timeout")

        if not admitted:
            await self._shed(scope, receive, send, reason=reason, waiting=waiting, max_inflight=max_inflight, lane=lane_name)
            return

        self._count(lane_name, "admitted")
        try:
            await self.app(scope, receive, send)
        finally:
            async with cond:
                lane.inflight -= 1
                cond.notify()
