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
    heal = _self_heal_summary()
    if heal:
        base["self_heal"] = heal
        base["detail"] = f"{base['detail']}; self-heal {heal['state']}"
    return base


def _self_heal_summary() -> dict[str, Any] | None:
    from modules import stats_self_heal

    status = stats_self_heal.read_status()
    if not status:
        return None
    return {k: status.get(k) for k in ("state", "started_at", "finished_at", "seasons") if k in status}


COLLEGE_PROSPECTS_STATUS_FILE = "college_prospects_ingest_status.json"
COLLEGE_PROSPECTS_MAX_AGE_HOURS = 24 * 9  # weekly Monday run + Actions lag


def college_prospects_row(now: float, data_dir: str, in_season: bool) -> dict[str, Any]:
    """Status of the Actions-only prospect ingest (college-prospect-ingest.yml).

    Reads the status file the job commits; fails if the job stopped or the
    class listing came back empty/errored."""

    import datetime as _dt
    import json

    base: dict[str, Any] = {"name": "college_prospects", "cadence": "weekly Mon + daily Apr-May (draft window)", "max_age_hours": COLLEGE_PROSPECTS_MAX_AGE_HOURS, "producer": "college-prospect-ingest.yml / modules.college_prospect_ingest"}
    path = os.path.join(data_dir, COLLEGE_PROSPECTS_STATUS_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            status = json.load(fh)
        as_of = _dt.datetime.fromisoformat(status["ran_at"]).timestamp()
    except (OSError, ValueError, KeyError, TypeError):
        base.update(status="warn", as_of=None, age_hours=None, detail="no ingest status file yet (job has not run)")
        return base
    age = max(0.0, (now - as_of) / 3600.0)
    base.update(as_of=as_of, age_hours=round(age, 1))
    classes = (status.get("classes") or {}).get("status")
    if classes in ("empty", "error") or status.get("ok") is False:
        base.update(status="fail", detail=f"last ingest unhealthy (classes={classes}, error={status.get('error')})")
    elif age > COLLEGE_PROSPECTS_MAX_AGE_HOURS:
        base.update(status=_age_status(age, COLLEGE_PROSPECTS_MAX_AGE_HOURS, in_season), detail=f"{age:.1f}h old (limit {COLLEGE_PROSPECTS_MAX_AGE_HOURS}h)")
    elif classes == "skipped_no_key":
        base.update(status="warn", detail="CFBD_API_KEY secret not set; class listing skipped")
    else:
        base.update(status="ok", detail=f"{age:.1f}h old; classes={classes}")
    return base


ADP_MAX_AGE_HOURS = 24 * 3


def adp_snapshot_row(now: float) -> dict[str, Any]:
    """Rookie/dynasty ADP feed (Supabase ``adp_snapshots``, GitHub Actions job).

    Never ``fail``: FFC only publishes ADP inside draft windows (rookie ADP is empty most of
    the year), so an old or empty feed is ``warn``; unreachable Supabase is ``warn``
    (unverifiable). One short query, fail-soft."""

    from datetime import datetime, timezone

    from modules import rookie_adp

    base = {"name": "adp_rookie_dynasty", "cadence": "daily 08:00 UTC; data only in FFC draft windows", "max_age_hours": ADP_MAX_AGE_HOURS, "producer": "rookie-adp-snapshot.yml / modules.rookie_adp"}
    try:
        newest = rookie_adp.newest_snapshot_date()
    except Exception:
        newest = None
    if not rookie_adp.load_config().configured:
        return {**base, "status": "warn", "as_of": None, "age_hours": None, "detail": "Supabase not configured here; unverifiable"}
    if not newest:
        return {**base, "status": "warn", "as_of": None, "age_hours": None, "detail": "no ADP snapshot stored (FFC window empty, or table not created)"}
    try:
        as_of = datetime.fromisoformat(newest).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return {**base, "status": "warn", "as_of": None, "age_hours": None, "detail": f"unreadable snapshot date {newest!r}"}
    age = max(0.0, (now - as_of) / 3600.0)
    status = "ok" if age <= ADP_MAX_AGE_HOURS + 24 else "warn"
    return {**base, "status": status, "as_of": as_of, "age_hours": round(age, 1), "detail": f"newest snapshot {newest} ({age:.0f}h old)"}


def build_report(now: float | None = None, data_dir: str = "data") -> dict[str, Any]:
    now = time.time() if now is None else now
    in_season = _in_season()
    rows = dataset_rows(now, data_dir, in_season)
    try:
        rows.append(weekly_stats_row(now, in_season))
    except Exception as exc:  # a broken check must itself be visible, not silent
        rows.append({"name": "weekly_stats", "status": "fail", "detail": f"completeness check errored: {type(exc).__name__}"})
    try:
        rows.append(college_prospects_row(now, data_dir, in_season))
    except Exception as exc:
        rows.append({"name": "college_prospects", "status": "fail", "detail": f"check errored: {type(exc).__name__}"})
    try:
        rows.append(adp_snapshot_row(now))
    except Exception as exc:
        rows.append({"name": "adp_rookie_dynasty", "status": "warn", "detail": f"check errored: {type(exc).__name__}"})
    return {
        "checked_at": now,
        "in_season": in_season,
        "datasets": rows,
        "failing": [r["name"] for r in rows if r["status"] == "fail"],
        "warnings": [r["name"] for r in rows if r["status"] == "warn"],
    }
