"""Never-fetching freshness + completeness report for every scheduled dataset.

One answer to "is the data we serve current and complete?" that the external watchdog
(``scripts/ops_health_check.py``, run every 20 min by ``.github/workflows/ops-health-check.yml``)
reads from ``GET /v1/public/data-freshness``. A failing dataset opens/updates the
"Ops health check is failing" issue and posts to ``OPS_ALERT_WEBHOOK_URL`` when set - the
alert channel that already exists; nothing new is added.

Each dataset has a cadence (how often its job runs) and a ``max_age_hours`` threshold wider
than the cadence, because GitHub-hosted schedules lag by hours. Outside the regular season
nothing changes weekly, so the thresholds relax to ``OFFSEASON_MAX_AGE_HOURS``.

Statuses: ``ok`` | ``warn`` (unverifiable, or stale only off-season) | ``fail``.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

OFFSEASON_MAX_AGE_HOURS = 24 * 14


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    path: str  # file, or directory (newest file inside counts)
    cadence: str
    max_age_hours: float  # in season
    producer: str  # the workflow / code path that refreshes it


DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec("players_directory", "sleeper_players.json", "6h (Players DB Refresh) + 5 min app cache", 14, "players-db-refresh.yml / modules.sleeper.get_players"),
    DatasetSpec("players_db_and_injury_status", "players.db", "injury patch every 30 min, full rebuild every 6h", 4, "injury-status-sync.yml, players-db-refresh.yml"),
    DatasetSpec("values_fantasycalc", "fantasycalc_values.csv", "6h TTL, committed by the 6h refresh", 30, "modules.fantasycalc via players-db-refresh.yml"),
    DatasetSpec("depth_charts", "depth_chart_snapshots.json", "snapshot appended by the 6h refresh", 30, "scripts/refresh_and_commit_players_db.py"),
    DatasetSpec("injury_history", "injury_history", "Tue + Sat 15:30 UTC (nflverse)", 24 * 5, "injury-history-ingest.yml"),
    DatasetSpec("schedule_nflverse", "nfl_games.csv", "pulled on demand, long TTL", 24 * 8, "modules.nfl_schedule"),
    DatasetSpec("advanced_stats_nflverse", "nflverse_advanced_stats_2026.json", "hourly windows after games + 2x daily", 24 * 3, "advanced-stats-refresh.yml"),
)


def _newest_mtime(path: str) -> float | None:
    try:
        if os.path.isdir(path):
            times = [os.path.getmtime(os.path.join(root, f)) for root, _d, files in os.walk(path) for f in files]
            return max(times) if times else None
        return os.path.getmtime(path)
    except OSError:
        return None


def _age_status(age_hours: float, limit: float, in_season: bool) -> str:
    if in_season:
        return "ok" if age_hours <= limit else "fail"
    return "ok" if age_hours <= OFFSEASON_MAX_AGE_HOURS else "warn"


def _in_season() -> bool:
    try:
        from modules import season_clock

        return season_clock.season_clock().phase == season_clock.PHASE_REGULAR
    except Exception:
        return True  # unknown clock: judge strictly


def dataset_rows(now: float, data_dir: str, in_season: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in DATASETS:
        # advanced stats file is named per season; accept whichever season file is newest
        path = os.path.join(data_dir, spec.path)
        mtime = _newest_mtime(path)
        if mtime is None and spec.name == "advanced_stats_nflverse":
            candidates = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.startswith("nflverse_advanced_stats_")] if os.path.isdir(data_dir) else []
            mtime = max((m for m in map(_newest_mtime, candidates) if m is not None), default=None)
        row: dict[str, Any] = {"name": spec.name, "cadence": spec.cadence, "max_age_hours": spec.max_age_hours, "producer": spec.producer}
        if mtime is None:
            row.update(status="fail" if in_season else "warn", as_of=None, age_hours=None, detail="no data file found")
        else:
            age = max(0.0, (now - mtime) / 3600.0)
            row.update(status=_age_status(age, spec.max_age_hours, in_season), as_of=mtime, age_hours=round(age, 1), detail=f"{age:.1f}h old (limit {spec.max_age_hours:g}h in season)")
        rows.append(row)
    return rows


def weekly_stats_row(now: float, in_season: bool) -> dict[str, Any]:
    """Completeness of the Sleeper weekly-stats aggregate: every expected week obtained."""

    from modules import sleeper

    report = sleeper.season_stats_completeness()
    base = {"name": "weekly_stats", "cadence": "rebuilt on demand, 12h TTL in season; partial builds retried every 10 min", "producer": "modules.sleeper.get_season_player_stats", "season": report["season"], "expected_through": report["expected_through"], "missing_weeks": report["missing_weeks"], "suspect_weeks": report.get("suspect_weeks", [])}
    age = report["age_seconds"]
    base["age_hours"] = None if age is None else round(age / 3600.0, 1)
    base["as_of"] = None if age is None else now - age
    status = report["status"]
    if status == "absent":
        base.update(status="fail" if in_season and report["expected_through"] else "warn", detail="no weekly stats cache on disk")
    elif status == "incomplete":
        base.update(status="fail", detail=f"missing weeks {report['missing_weeks']} of 1..{report['expected_through']}")
    elif report.get("suspect_weeks"):
        base.update(status="fail", detail=f"weeks {report['suspect_weeks']} hold implausibly few player rows")
    elif status == "unverified":
        base.update(status="warn", detail="cache predates completeness manifest; run scripts/backfill_weekly_stats.py")
    elif in_season and age is not None and age / 3600.0 > 30:
        base.update(status="fail", detail=f"{age / 3600.0:.1f}h old (limit 30h in season)")
    else:
        base.update(status="ok", detail=f"all weeks 1..{report['expected_through']} present")
    return base


def build_report(now: float | None = None, data_dir: str = "data") -> dict[str, Any]:
    now = time.time() if now is None else now
    in_season = _in_season()
    rows = dataset_rows(now, data_dir, in_season)
    try:
        rows.append(weekly_stats_row(now, in_season))
    except Exception as exc:  # a broken check must itself be visible, not silent
        rows.append({"name": "weekly_stats", "status": "fail", "detail": f"completeness check errored: {type(exc).__name__}"})
    return {
        "checked_at": now,
        "in_season": in_season,
        "datasets": rows,
        "failing": [r["name"] for r in rows if r["status"] == "fail"],
        "warnings": [r["name"] for r in rows if r["status"] == "warn"],
    }
