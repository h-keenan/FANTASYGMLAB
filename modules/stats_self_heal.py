"""Weekly-stats backfill + boot-time self-heal.

``backfill_season`` is the one implementation of "rebuild a season's Sleeper weekly-stats
aggregate and report completeness" (``scripts/backfill_weekly_stats.py`` is a thin CLI over it).

``self_heal`` runs in a background thread when the API boots (never blocks startup or readiness):
for the current and previous season it checks the completeness manifest and, when the cache is
absent, partial, truncated or unverified, backfills it. A non-blocking file lock in the cache
directory makes exactly one worker do it; Sleeper calls are paced and a failing provider backs off
instead of being hammered. The outcome is logged and written to ``self_heal_status.json`` beside the
cache so ``/v1/public/data-freshness`` (and so ``ops_health_check``) can surface it from any worker.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List

from modules import sleeper
from modules.file_lock import ExclusiveFileLock

logger = logging.getLogger(__name__)

PACE_SECONDS = 5.0  # pause between seasons (each season is already one paced fan-out of weekly calls)
BACKOFF_SECONDS = (30.0, 120.0, 600.0)  # waits before attempts 2..4 for a season that stays incomplete/errors
STARTUP_DELAY_SECONDS = 30.0
STATUS_FILENAME = "self_heal_status.json"
LOCK_FILENAME = "self_heal.lock"


def backfill_season(season: int) -> Dict[str, Any]:
    """Refetch ``season`` (a worse rebuild never replaces a more complete cache); report before/after."""

    before = sleeper.season_stats_completeness(season)
    sleeper.get_season_player_stats(season, refresh=True, retain_weekly=True)
    after = sleeper.season_stats_completeness(season)
    return {"season": season, "before": before["status"], "before_missing": before["missing_weeks"], "after": after["status"], "after_missing": after["missing_weeks"], "suspect_weeks": after.get("suspect_weeks", [])}


def _cache_dir() -> str:
    return os.path.dirname(sleeper.PLAYER_STATS_CACHE_TEMPLATE) or "."


def status_path() -> str:
    return os.path.join(_cache_dir(), STATUS_FILENAME)


def read_status() -> Dict[str, Any] | None:
    try:
        with open(status_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_status(status: Dict[str, Any]) -> None:
    try:
        tmp = f"{status_path()}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(status, handle)
        os.replace(tmp, status_path())
    except Exception:
        logger.warning("stats self-heal: could not write status file", exc_info=True)


def seasons_to_check() -> List[int]:
    current = int(sleeper.default_player_stats_season())
    return [current - 1, current]


def needs_heal(season: int) -> bool:
    report = sleeper.season_stats_completeness(season)
    if report["expected_through"] <= 0:
        return False  # nothing is expected yet (e.g. a season that has not started)
    return report["status"] in ("absent", "incomplete", "unverified") or bool(report.get("suspect_weeks"))


def self_heal(
    seasons: List[int] | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
    pace_seconds: float = PACE_SECONDS,
    backoff_seconds: tuple = BACKOFF_SECONDS,
) -> Dict[str, Any]:
    """One heal pass. Never raises. Returns (and persists) ``{state, seasons, ...}``.

    ``state``: ``ok`` (nothing needed fixing or all fixed) | ``incomplete`` (still gaps after retries,
    provider erroring) | ``skipped_locked`` (another worker is on it) | ``error``.
    """

    started = time.time()
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        with ExclusiveFileLock(os.path.join(_cache_dir(), LOCK_FILENAME), wait_seconds=0) as lock:
            if not lock.acquired:
                logger.info("stats self-heal: another worker holds the lock; skipping")
                return {"state": "skipped_locked", "started_at": started}
            status: Dict[str, Any] = {"state": "running", "started_at": started, "seasons": []}
            _write_status(status)
            todo = seasons if seasons is not None else seasons_to_check()
            first = True
            for season in todo:
                entry: Dict[str, Any] = {"season": season, "attempts": 0}
                status["seasons"].append(entry)
                if not needs_heal(season):
                    entry["result"] = "complete"
                    continue
                if not first:
                    sleep(pace_seconds)
                first = False
                for attempt in range(len(backoff_seconds) + 1):
                    if attempt:
                        sleep(backoff_seconds[attempt - 1])
                    entry["attempts"] = attempt + 1
                    try:
                        outcome = backfill_season(season)
                    except Exception as exc:
                        entry["error"] = type(exc).__name__
                        logger.warning("stats self-heal: season %s attempt %s failed: %s", season, attempt + 1, type(exc).__name__)
                        continue
                    entry.pop("error", None)
                    entry["missing_weeks"] = outcome["after_missing"]
                    if outcome["after"] != "incomplete" and not outcome["suspect_weeks"]:
                        break
                entry["result"] = "healed" if not needs_heal(season) else "incomplete"
            bad = [e for e in status["seasons"] if e.get("result") == "incomplete"]
            status.update(state="incomplete" if bad else "ok", finished_at=time.time())
            _write_status(status)
            logger.info("stats self-heal: %s %s", status["state"], json.dumps(status["seasons"]))
            return status
    except Exception as exc:  # best-effort background task: must never take a worker down
        logger.warning("stats self-heal crashed: %s", type(exc).__name__, exc_info=True)
        return {"state": "error", "error": type(exc).__name__, "started_at": started}


def start_background(*, delay_seconds: float = STARTUP_DELAY_SECONDS) -> threading.Thread | None:
    """Fire-and-forget heal pass in a daemon thread; a no-op under tests."""

    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("DYNASTYGM_TEST_MODE"):
        return None
    if os.environ.get("DYNASTYGM_STATS_SELF_HEAL", "1").strip().lower() in ("0", "false", "off", "no"):
        return None

    def _run() -> None:
        time.sleep(delay_seconds)
        self_heal()

    thread = threading.Thread(target=_run, name="dgm-stats-self-heal", daemon=True)
    thread.start()
    return thread
