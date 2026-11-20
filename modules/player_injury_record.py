"""Per-player injury record for the Player Quick View: the current injury
line plus a per-season history of stints and games missed.

Data (nothing new is fetched or stored): the official nflverse weekly injury
reports already committed under ``data/injury_history/nflverse_reports_<season>
.csv.gz`` (modules/nflverse_injury_reports.py), which carry each team/player/
week's FINAL game-status designation and the reported injury. A regular-season
week whose final designation is "Out" is a missed game. "Doubtful" and
"Questionable" are not counted: a designation is not a missed game, and we hold
no snap/game logs that could prove the player sat. A bye week is not a missed
game: it has no report, and a stint bridges exactly one such gap (a week where
the player's own team filed no report at all).

The per-season index is parsed once per file change (mtime + size) and shared
by every request in the process.

Pure functions below take rows/mappings and never touch the network, so the
derivation is tested from small fixtures.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from modules import nflverse_injury_reports as reports
from modules import player_availability

MISSED_STATUS = "out"
SOURCE_TEXT = "Official NFL injury reports (nflverse, CC BY 4.0)"
METHOD_NOTE = "Games missed = regular-season weeks the final report listed him Out. Doubtful and Questionable are not counted."

_PRACTICE_SHORT = {
    "did not participate in practice": "Did not practice",
    "limited participation in practice": "Limited in practice",
    "full participation in practice": "Full practice",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _week(row: Mapping[str, Any]) -> int | None:
    try:
        return int(str(row.get("week", "")).strip())
    except (TypeError, ValueError):
        return None


def _injury_label(row: Mapping[str, Any]) -> str:
    """The reported injury for one report row; "Not injury related" reasons
    (rest, coach's decision) are not an injury."""

    for key in ("report_primary_injury", "practice_primary_injury"):
        value = _text(row.get(key))
        if value and not value.lower().startswith("not injury related"):
            return value
    return ""


class SeasonReports:
    """One season's regular-season reports, indexed for lookups."""

    def __init__(self, season: int, rows: Iterable[Mapping[str, Any]]):
        self.season = season
        self.by_sleeper: dict[str, list[Mapping[str, Any]]] = {}
        self.by_gsis: dict[str, list[Mapping[str, Any]]] = {}
        self.team_weeks: dict[str, set[int]] = {}
        for row in rows:
            if _text(row.get("season_type")).upper() not in {"", "REG"}:
                continue
            week = _week(row)
            if week is None:
                continue
            team = _text(row.get("team")).upper()
            if team:
                self.team_weeks.setdefault(team, set()).add(week)
            sid, gsis = _text(row.get("sleeper_id")), _text(row.get("gsis_id"))
            if sid:
                self.by_sleeper.setdefault(sid, []).append(row)
            if gsis:
                self.by_gsis.setdefault(gsis, []).append(row)

    def player_rows(self, sleeper_id: str, gsis_id: str) -> list[Mapping[str, Any]]:
        merged: dict[int, Mapping[str, Any]] = {}
        # The same player can be reachable by both keys; one row per week wins.
        for row in (*self.by_sleeper.get(sleeper_id, ()), *(self.by_gsis.get(gsis_id, ()) if gsis_id else ())):
            week = _week(row)
            if week is not None:
                merged.setdefault(week, row)
        return [merged[w] for w in sorted(merged)]


_CACHE: dict[Path, tuple[tuple[int, int], SeasonReports]] = {}


def load_season(root: Path, season: int) -> SeasonReports | None:
    """The season's report index, cached per file version; None when absent."""

    path = reports.report_path(root, season)
    try:
        stat = path.stat()
    except OSError:
        return None
    version = (stat.st_mtime_ns, stat.st_size)
    cached = _CACHE.get(path)
    if cached and cached[0] == version:
        return cached[1]
    try:
        rows = reports.read_existing(path)
    except Exception:
        return None
    index = SeasonReports(season, rows)
    _CACHE[path] = (version, index)
    return index


def _stints(rows: Sequence[Mapping[str, Any]], team_weeks: Mapping[str, set[int]], through_week: int | None) -> list[dict[str, Any]]:
    """Group the player's Out weeks into stints (consecutive weeks, bridging
    exactly one team bye)."""

    out_rows = [
        r for r in rows
        if _text(r.get("report_status")).lower() == MISSED_STATUS
        and (through_week is None or (_week(r) or 0) <= through_week)
    ]
    groups: list[list[Mapping[str, Any]]] = []
    for row in out_rows:
        week = _week(row) or 0
        if groups:
            prev_week = _week(groups[-1][-1]) or 0
            gap = week - prev_week
            team = _text(row.get("team")).upper()
            bye_bridge = gap == 2 and (prev_week + 1) not in team_weeks.get(team, set())
            if gap == 1 or bye_bridge:
                groups[-1].append(row)
                continue
        groups.append([row])
    stints: list[dict[str, Any]] = []
    for group in groups:
        labels = Counter(label for label in (_injury_label(r) for r in group) if label)
        stints.append({
            "start_week": _week(group[0]),
            "end_week": _week(group[-1]),
            "games_missed": len(group),
            "injury": labels.most_common(1)[0][0] if labels else None,
        })
    return stints


def build_history(
    sleeper_id: str,
    gsis_id: str,
    seasons: Mapping[int, SeasonReports],
    *,
    current_season: int | None = None,
    through_week: int | None = None,
) -> dict[str, Any]:
    """Per-season stints and games missed, newest season first. For
    ``current_season`` only weeks up to ``through_week`` count (a week still
    being played has no final result)."""

    out: list[dict[str, Any]] = []
    career = 0
    for season in sorted(seasons, reverse=True):
        index = seasons[season]
        limit = through_week if season == current_season else None
        stints = _stints(index.player_rows(sleeper_id, gsis_id), index.team_weeks, limit)
        if not stints:
            continue
        missed = sum(s["games_missed"] for s in stints)
        career += missed
        out.append({"season": season, "games_missed": missed, "stints": stints})
    return {
        "seasons": out,
        "career_games_missed": career,
        "since_season": min(seasons) if seasons else None,
    }


def practice_line(row: Mapping[str, Any] | None) -> str | None:
    if not row:
        return None
    raw = _text(row.get("practice_status"))
    return _PRACTICE_SHORT.get(raw.lower(), raw) or None


def build_current(directory: Mapping[str, Any] | None, latest_report: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The current injury line ("Hamstring · Questionable") from Sleeper's
    directory (status, body part, notes, practice participation), with the
    latest official report's practice status as the fallback source. None
    when the player is healthy."""

    directory = directory or {}
    availability = player_availability.build_availability(
        directory.get("injury_status"), directory.get("injury_body_part"), directory.get("injury_notes")
    )
    if availability is None:
        return None
    body_part = availability["body_part"] or (_injury_label(latest_report or {}) or None)
    practice = (
        _text(directory.get("practice_description"))
        or _text(directory.get("practice_participation"))
        or practice_line(latest_report)
    )
    return {
        "label": availability["label"],
        "status": availability["status"],
        "severity": availability["severity"],
        "unavailable": availability["unavailable"],
        "body_part": body_part,
        "practice": practice or None,
        "report": availability["report"],
        "line": " · ".join(part for part in (body_part, availability["label"]) if part),
    }


def build_injury_record(
    player_id: str,
    directory: Mapping[str, Any] | None,
    *,
    root: Path,
    current_season: int,
    through_week: int | None,
    first_season: int = reports.FIRST_SEASON,
) -> dict[str, Any]:
    pid = str(player_id)
    gsis = _text((directory or {}).get("gsis_id"))
    loaded: dict[int, SeasonReports] = {}
    for season in range(first_season, current_season + 1):
        index = load_season(root, season)
        if index is not None:
            loaded[season] = index
    history = build_history(pid, gsis, loaded, current_season=current_season, through_week=through_week)
    latest = None
    season_rows: list[Mapping[str, Any]] = []
    if current_season in loaded:
        season_rows = loaded[current_season].player_rows(pid, gsis)
        latest = season_rows[-1] if season_rows else None
    current = build_current(directory, latest)
    # The official reports drop players on IR / PUP, so a player who is out with no row for this season has no countable
    # games here. Say it is untracked rather than letting "0 missed" stand (the client reads this flag).
    season_tracked = not (current and current["unavailable"] and not season_rows)
    return {
        "ok": True,
        "player_id": pid,
        "current_season": current_season,
        "current_season_tracked": season_tracked,
        "current": current,
        **history,
        "source": SOURCE_TEXT,
        "method": METHOD_NOTE,
    }
