"""Official weekly NFL injury reports from nflverse (CC BY 4.0).

The only point-in-time, *official* injury source we can get for free: the
practice-status reports (Wed/Thu/Fri participation) and the final game-status
designation per team/player/week, published by nflverse-data as one CSV per
season (https://github.com/nflverse/nflverse-data/releases/tag/injuries).
Sleeper's live feed (modules/injury_history.py) tells us WHEN a status changed
as we observed it; this tells us what the league officially reported for each
game week, going back to 2021, and carries the report's own injury/body part.
Together they let a later model separate injuries from benching/rest
("Not injury related - resting player" is a practice-report reason).

Storage: ``data/injury_history/nflverse_reports_<season>.csv.gz`` (all
positions, ~6k rows/season, ~100 KB gzipped), rewritten whole per season only
when the content changed, deterministic bytes (no gzip timestamp) so an
unchanged download produces an empty git diff. Rows carry both ``gsis_id``
(nflverse key) and ``sleeper_id`` (resolved through the GSIS ids in Sleeper's
own player dump, modules/gsis_crosswalk.py; blank when unmapped or ambiguous).

Attribution: nflverse (nflverse.com), CC BY 4.0.
"""

from __future__ import annotations

import csv
import gzip
import io
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ATTRIBUTION_TEXT = "Injury reports: nflverse (nflverse.com), CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
RELEASE_URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"

FIRST_SEASON = 2021
FETCH_TIMEOUT_SECONDS = 60
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_SECONDS = 4
MAX_BYTES = 20 * 1024 * 1024

# Source columns we require / keep. date_modified exists only in some seasons.
REQUIRED_SOURCE_COLUMNS = ("season", "week", "team", "gsis_id", "position", "report_status", "practice_status")
OUTPUT_COLUMNS = (
    "season", "season_type", "week", "team", "gsis_id", "sleeper_id", "position", "full_name",
    "report_status", "report_primary_injury", "report_secondary_injury",
    "practice_status", "practice_primary_injury", "practice_secondary_injury", "date_modified",
)
# A finished season with fewer rows than this is a truncated/bad download.
MIN_ROWS_COMPLETED_SEASON = 2000
# Refuse to replace a committed file with one this much smaller.
MAX_SHRINK_FRACTION = 0.2


class InjuryReportError(RuntimeError):
    """Upstream data could not be fetched or failed validation."""


class NotPublished(InjuryReportError):
    """The season file does not exist upstream (HTTP 404)."""


def report_path(root: Path, season: int) -> Path:
    return root / "data" / "injury_history" / f"nflverse_reports_{season}.csv.gz"


def fetch_season_csv(season: int, *, session: Any = None) -> str:
    import requests

    http = session or requests
    url = RELEASE_URL.format(season=season)
    last: Exception | None = None
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            response = http.get(url, timeout=FETCH_TIMEOUT_SECONDS)
            if response.status_code == 404:
                raise NotPublished(f"{url} not published")
            response.raise_for_status()
            content = response.content
            if len(content) > MAX_BYTES:
                raise InjuryReportError(f"{url} exceeded {MAX_BYTES} bytes")
            return content.decode("utf-8")
        except InjuryReportError:
            raise
        except Exception as exc:  # network/HTTP: retried, then surfaced
            last = exc
            if attempt < FETCH_ATTEMPTS:
                time.sleep(FETCH_BACKOFF_SECONDS * attempt)
    raise InjuryReportError(f"could not fetch {url}: {last}")


def _week_sort(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_reports(text: str, season: int, *, sleeper_id_for_gsis: Callable[..., str | None] | None = None) -> list[dict[str, str]]:
    """Validate + normalise one season's CSV. Pure; raises InjuryReportError."""

    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    missing = [c for c in REQUIRED_SOURCE_COLUMNS if c not in columns]
    if missing:
        raise InjuryReportError(f"season {season}: missing columns {missing}")
    rows: list[dict[str, str]] = []
    for raw in reader:
        if str(raw.get("season", "")).strip() != str(season):
            continue
        gsis = (raw.get("gsis_id") or "").strip()
        out = {c: (raw.get(c) or "").strip() for c in OUTPUT_COLUMNS if c != "sleeper_id"}
        out["sleeper_id"] = (
            sleeper_id_for_gsis(gsis, out["full_name"], out["team"], out["position"]) or ""
        ) if (sleeper_id_for_gsis and gsis) else ""
        out["season"] = str(season)
        rows.append(out)
    rows.sort(key=lambda r: (r["season_type"], _week_sort(r["week"]), r["team"], r["gsis_id"], r["full_name"], r["practice_status"], r["report_status"]))
    return rows


def serialize(rows: Sequence[Mapping[str, str]]) -> bytes:
    """Deterministic gzip CSV (fixed mtime, fixed filename) for stable diffs."""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(OUTPUT_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in OUTPUT_COLUMNS})
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as handle:
        handle.write(buffer.getvalue().encode("utf-8"))
    return raw.getvalue()


def read_existing(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def seasons_to_sync(root: Path, current_season: int, *, first_season: int = FIRST_SEASON) -> list[int]:
    """The in-progress season (always re-checked) plus every earlier season
    from ``first_season`` whose file is missing (one-time backfill)."""

    seasons = [s for s in range(first_season, current_season) if not report_path(root, s).exists()]
    seasons.append(current_season)
    return seasons


def sync_season(
    root: Path,
    season: int,
    *,
    current_season: int,
    fetch: Callable[[int], str] = fetch_season_csv,
    sleeper_id_for_gsis: Callable[..., str | None] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Fetch, validate and (when changed) write one season. Returns stats;
    raises InjuryReportError for a bad/missing completed season. A missing
    CURRENT season (not yet published, e.g. before week 1) is a quiet skip."""

    stats: dict[str, Any] = {"season": season, "rows": 0, "changed": False, "status": "ok"}
    try:
        text = fetch(season)
    except NotPublished:
        if season >= current_season:
            stats["status"] = "not_published_yet"
            return stats
        raise
    rows = parse_reports(text, season, sleeper_id_for_gsis=sleeper_id_for_gsis)
    stats["rows"] = len(rows)
    if season < current_season and len(rows) < MIN_ROWS_COMPLETED_SEASON:
        raise InjuryReportError(f"season {season}: only {len(rows)} rows, expected a full season")
    if not rows:
        stats["status"] = "empty"
        return stats

    path = report_path(root, season)
    existing = read_existing(path)
    if existing and len(rows) < len(existing) * (1 - MAX_SHRINK_FRACTION):
        raise InjuryReportError(
            f"season {season}: new file has {len(rows)} rows vs {len(existing)} committed; refusing to shrink"
        )
    payload = serialize(rows)
    if path.exists() and path.read_bytes() == payload:
        return stats
    stats["changed"] = True
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return stats


def current_season_now() -> int:
    from modules import season_clock

    return season_clock.season_clock().season


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
