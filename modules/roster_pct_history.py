"""Daily roster % snapshots (ESPN public ownership + Sleeper trending adds).

Same shape as modules/player_rating_history.py: own service-role Supabase
access, pure transforms separate from I/O, fail-soft. Table DDL lives in
docs/supabase_roster_pct_snapshots.sql. Trend = change in roster % over N
days; never fabricated -- None when history is insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import requests

from modules import app_config, public_roster_percentages, sleeper
from modules.player_rating_history import load_global_rating_pool

TABLE = "roster_pct_snapshots"
SOURCE = "espn"
RETENTION_DAYS = 400
# Baseline may be off the exact target day by this many days (gap tolerance).
BASELINE_TOLERANCE_DAYS = 1
_CHUNK = 500


@dataclass(frozen=True)
class Config:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_config(*, environ: dict | None = None, secrets: Any = None) -> Config:
    return Config(
        url=app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _headers(config: Config, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def build_rows(percentages: Mapping[str, Mapping[str, Any]], trending: Mapping[str, Mapping[str, Any]] | None = None,
               *, snapshot_date: str | None = None) -> list[dict[str, Any]]:
    """Pure: roster_percentages() output (+ optional Sleeper trending map) -> upsert rows."""
    day = snapshot_date or datetime.now(timezone.utc).date().isoformat()
    trending = trending or {}
    rows = []
    for pid, info in (percentages or {}).items():
        try:
            pct = float(info.get("percent"))
        except (TypeError, ValueError, AttributeError):
            continue
        if not pid or pct != pct or not 0 <= pct <= 100:
            continue
        adds = None
        entry = trending.get(str(pid))
        if entry is not None:
            try:
                adds = int(entry.get("count"))
            except (TypeError, ValueError):
                adds = None
        rows.append({"player_id": str(pid), "source": SOURCE, "snapshot_date": day,
                     "roster_pct": pct, "sleeper_trending_adds": adds})
    return rows


def store_daily_snapshot(config: Config, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Idempotent per day: upsert on (player_id, source, snapshot_date)."""
    stats: dict[str, Any] = {"ok": False, "rows_sent": 0, "errors": []}
    if not config.configured:
        stats["errors"].append("Supabase service-role is not configured.")
        return stats
    if not rows:
        stats["errors"].append("No roster percentages to store.")
        return stats
    computed_at = datetime.now(timezone.utc).isoformat()
    payload = [{**row, "computed_at": computed_at} for row in rows]
    for start in range(0, len(payload), _CHUNK):
        chunk = payload[start:start + _CHUNK]
        try:
            response = requests.post(
                f"{config.url}/rest/v1/{TABLE}",
                headers=_headers(config, prefer="resolution=merge-duplicates,return=minimal"),
                params={"on_conflict": "player_id,source,snapshot_date"},
                json=chunk, timeout=30,
            )
        except Exception as exc:
            stats["errors"].append(f"request failed: {exc}")
            continue
        if response.status_code >= 400:
            stats["errors"].append(f"status {response.status_code}")
            continue
        stats["rows_sent"] += len(chunk)
    stats["ok"] = stats["rows_sent"] > 0 and not stats["errors"]
    return stats


def prune_old_snapshots(config: Config, *, today: date | None = None, retention_days: int = RETENTION_DAYS) -> dict[str, Any]:
    """Delete rows older than the retention window."""
    cutoff = ((today or datetime.now(timezone.utc).date()) - timedelta(days=retention_days)).isoformat()
    stats: dict[str, Any] = {"ok": False, "cutoff": cutoff, "errors": []}
    if not config.configured:
        stats["errors"].append("Supabase service-role is not configured.")
        return stats
    try:
        response = requests.delete(
            f"{config.url}/rest/v1/{TABLE}", headers=_headers(config, prefer="return=minimal"),
            params={"snapshot_date": f"lt.{cutoff}"}, timeout=30,
        )
    except Exception as exc:
        stats["errors"].append(f"request failed: {exc}")
        return stats
    if response.status_code >= 400:
        stats["errors"].append(f"status {response.status_code}")
        return stats
    stats["ok"] = True
    return stats


def run_roster_pct_snapshot(*, environ: dict | None = None, secrets: Any = None) -> dict[str, Any]:
    config = load_config(environ=environ, secrets=secrets)
    stats: dict[str, Any] = {"ok": False, "configured": config.configured, "players_matched": 0,
                             "rows_sent": 0, "pruned": False, "errors": []}
    if not config.configured:
        stats["errors"].append("Supabase service-role is not configured.")
        return stats
    try:
        pool = load_global_rating_pool()
        percentages = public_roster_percentages.roster_percentages(pool) if pool is not None and not pool.empty else {}
    except Exception as exc:
        stats["errors"].append(f"roster % build failed: {exc}")
        return stats
    try:
        trending = sleeper.trending_add_rank_map(limit=200)
    except Exception:
        trending = {}
    rows = build_rows(percentages, trending)
    stats["players_matched"] = len(rows)
    stored = store_daily_snapshot(config, rows)
    stats["rows_sent"] = stored["rows_sent"]
    stats["errors"].extend(stored["errors"])
    if stored["ok"]:
        pruned = prune_old_snapshots(config)
        stats["pruned"] = pruned["ok"]
        stats["errors"].extend(pruned["errors"])
    stats["ok"] = bool(stored["ok"])
    return stats


def _parse_day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def compute_trend(rows: Sequence[Mapping[str, Any]], *, days: int = 7, today: date | None = None) -> dict[str, Any] | None:
    """Pure: one player's snapshot rows -> {current, previous, delta, ...} or None.

    Current must be from today or yesterday; the baseline must be within
    BASELINE_TOLERANCE_DAYS of (current date - days). Otherwise None.
    """
    today = today or datetime.now(timezone.utc).date()
    points: dict[date, float] = {}
    for row in rows or []:
        day = _parse_day(row.get("snapshot_date"))
        try:
            pct = float(row.get("roster_pct"))
        except (TypeError, ValueError):
            continue
        if day is not None and pct == pct:
            points[day] = pct
    if not points:
        return None
    current_day = max(points)
    if (today - current_day).days > BASELINE_TOLERANCE_DAYS or current_day > today:
        return None
    target = current_day - timedelta(days=days)
    baseline_day = None
    for offset in range(BASELINE_TOLERANCE_DAYS + 1):
        for candidate in (target - timedelta(days=offset), target + timedelta(days=offset)):
            if candidate in points and candidate < current_day:
                baseline_day = candidate
                break
        if baseline_day:
            break
    if baseline_day is None:
        return None
    current, previous = points[current_day], points[baseline_day]
    return {"current": current, "previous": previous, "delta": round(current - previous, 4),
            "current_date": current_day.isoformat(), "previous_date": baseline_day.isoformat()}


def get_roster_pct_trend(player_ids: Sequence[str], days: int = 7, *, config: Config | None = None,
                         today: date | None = None) -> dict[str, dict[str, Any] | None]:
    """player_id -> {current, previous, delta, ...} or None (insufficient history / any I/O problem)."""
    ids = [str(p) for p in player_ids if str(p).strip()]
    result: dict[str, dict[str, Any] | None] = {pid: None for pid in ids}
    config = config or load_config()
    if not ids or not config.configured:
        return result
    today = today or datetime.now(timezone.utc).date()
    since = (today - timedelta(days=days + BASELINE_TOLERANCE_DAYS + 1)).isoformat()
    for start in range(0, len(ids), 100):
        chunk = ids[start:start + 100]
        try:
            response = requests.get(
                f"{config.url}/rest/v1/{TABLE}", headers=_headers(config), timeout=15,
                params={"select": "player_id,snapshot_date,roster_pct", "source": f"eq.{SOURCE}",
                        "snapshot_date": f"gte.{since}", "player_id": "in.(" + ",".join(chunk) + ")",
                        "limit": str(len(chunk) * (days + 5))},
            )
            if response.status_code >= 400:
                continue
            data = response.json()
        except Exception:
            continue
        grouped: dict[str, list] = {}
        for row in data if isinstance(data, list) else []:
            if isinstance(row, Mapping):
                grouped.setdefault(str(row.get("player_id")), []).append(row)
        for pid, rows in grouped.items():
            if pid in result:
                result[pid] = compute_trend(rows, days=days, today=today)
    return result
