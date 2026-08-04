"""Verified, presentation-only career history for the canonical player dossier."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd


ACHIEVEMENT_LEVEL_ORDER = {
    "landmark": 0,
    "elite": 1,
    "standout": 2,
    "milestone": 3,
}
ACHIEVEMENT_ICONS = {
    "landmark": "◆",
    "elite": "▲",
    "standout": "■",
    "milestone": "●",
}


@dataclass(frozen=True)
class CareerAchievement:
    achievement_id: str
    family: str
    label: str
    detail: str
    season: int
    level: str
    current_season: bool = False

    @property
    def icon(self) -> str:
        return ACHIEVEMENT_ICONS.get(self.level, "●")


@dataclass(frozen=True)
class HistoricalSeason:
    season: int
    age: int | None
    games: int | None
    fantasy_points: float | None
    fantasy_ppg: float | None
    position_finish: int | None
    key_stats: tuple[tuple[str, str], ...]
    achievements: tuple[CareerAchievement, ...]
    current_season: bool = False


@dataclass(frozen=True)
class CareerResume:
    seasons: tuple[HistoricalSeason, ...]
    achievements: tuple[CareerAchievement, ...]
    source_note: str
    historical_cache_loaded: bool = False

    @property
    def available(self) -> bool:
        return bool(self.seasons or self.achievements)

    @property
    def prestige_level(self) -> str:
        return self.achievements[0].level if self.achievements else "milestone"


def _number(value: Any) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else float(numeric)


def _integer(value: Any) -> int | None:
    numeric = _number(value)
    return None if numeric is None else int(round(numeric))


def _metric(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in row:
            value = _number(row.get(key))
            if value is not None:
                return value
    return None


def _achievement(
    *,
    season: int,
    family: str,
    label: str,
    detail: str,
    level: str,
    current_season: bool,
) -> CareerAchievement:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{season}-{family}-{label}".casefold()).strip("-")
    return CareerAchievement(
        achievement_id=slug,
        family=family,
        label=label,
        detail=detail,
        season=season,
        level=level,
        current_season=current_season,
    )


def _season_achievements(
    row: Mapping[str, Any],
    *,
    season: int,
    position: str,
    position_finish: int | None,
    current_season: bool,
) -> tuple[CareerAchievement, ...]:
    achievements: list[CareerAchievement] = []

    if position_finish and position_finish <= 24:
        level = "landmark" if position_finish == 1 else "elite" if position_finish <= 5 else "standout" if position_finish <= 12 else "milestone"
        label = f"{position}{position_finish} fantasy finish"
        achievements.append(_achievement(
            season=season,
            family="fantasy-finish",
            label=label,
            detail=f"Finished {position_finish} among {position} players in verified PPR production.",
            level=level,
            current_season=current_season,
        ))

    passing_yards = _metric(row, "passing_yards", "pass_yards")
    passing_tds = _metric(row, "passing_tds", "pass_tds")
    rushing_yards = _metric(row, "rushing_yards", "rush_yards")
    rushing_tds = _metric(row, "rushing_tds", "rush_tds")
    receiving_yards = _metric(row, "receiving_yards", "receiving_yds")
    receiving_tds = _metric(row, "receiving_tds", "receiving_td")
    fantasy_points = _metric(row, "fantasy_points_ppr")
    ppg = _metric(row, "ppg", "fantasy_ppg", "fantasy_points_per_game")
    games = _integer(row.get("games_played"))

    objective_milestones = []
    if passing_yards is not None and passing_yards >= 4000:
        objective_milestones.append(("production", f"{int(passing_yards):,} passing yards", "elite" if passing_yards >= 5000 else "standout"))
    if passing_tds is not None and passing_tds >= 30:
        objective_milestones.append(("touchdowns", f"{int(passing_tds)} passing touchdowns", "elite" if passing_tds >= 40 else "standout"))
    if rushing_yards is not None and rushing_yards >= 1000:
        objective_milestones.append(("production", f"{int(rushing_yards):,} rushing yards", "elite" if rushing_yards >= 1500 else "standout"))
    if rushing_tds is not None and rushing_tds >= 10:
        objective_milestones.append(("touchdowns", f"{int(rushing_tds)} rushing touchdowns", "elite" if rushing_tds >= 15 else "standout"))
    if receiving_yards is not None and receiving_yards >= 1000:
        objective_milestones.append(("production", f"{int(receiving_yards):,} receiving yards", "elite" if receiving_yards >= 1500 else "standout"))
    if receiving_tds is not None and receiving_tds >= 10:
        objective_milestones.append(("touchdowns", f"{int(receiving_tds)} receiving touchdowns", "elite" if receiving_tds >= 12 else "standout"))
    if fantasy_points is not None and fantasy_points >= 250:
        objective_milestones.append(("fantasy-production", f"{fantasy_points:.1f} PPR points", "elite" if fantasy_points >= 300 else "standout"))
    if ppg is not None and ppg >= 15:
        objective_milestones.append(("fantasy-efficiency", f"{ppg:.1f} PPR points per game", "elite" if ppg >= 20 else "standout"))
    if games is not None and games >= 17:
        objective_milestones.append(("availability", "17-game season", "milestone"))

    for family, label, level in objective_milestones:
        achievements.append(_achievement(
            season=season,
            family=family,
            label=label,
            detail=f"Verified {season} regular-season production.",
            level=level,
            current_season=current_season,
        ))
    return tuple(sorted(
        achievements,
        key=lambda item: (ACHIEVEMENT_LEVEL_ORDER.get(item.level, 99), item.family, item.label),
    ))


def _key_stats(row: Mapping[str, Any], position: str) -> tuple[tuple[str, str], ...]:
    definitions = {
        "QB": (("Pass Yards", "passing_yards"), ("Pass TD", "passing_tds"), ("Rush Yards", "rushing_yards")),
        "RB": (("Rush Yards", "rushing_yards"), ("Rush TD", "rushing_tds"), ("Receptions", "receptions")),
        "WR": (("Receptions", "receptions"), ("Rec Yards", "receiving_yards"), ("Rec TD", "receiving_tds")),
        "TE": (("Receptions", "receptions"), ("Rec Yards", "receiving_yards"), ("Rec TD", "receiving_tds")),
    }.get(position, (("Fantasy Points", "fantasy_points_ppr"),))
    values = []
    for label, key in definitions:
        value = _metric(row, key)
        if value is not None:
            values.append((label, f"{int(value):,}" if float(value).is_integer() else f"{value:.1f}"))
    return tuple(values)


def build_career_resume(
    rows: Sequence[Mapping[str, Any]],
    *,
    position: str,
    current_season: int | None,
    source_note: str,
    historical_cache_loaded: bool = False,
) -> CareerResume:
    """Normalize verified season aggregates without inferring missing history."""

    normalized_position = str(position or "PLAYER").upper()
    by_season: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        season = _integer(row.get("stats_season") or row.get("season"))
        if season is not None:
            by_season[season] = row

    seasons: list[HistoricalSeason] = []
    for season in sorted(by_season, reverse=True):
        row = by_season[season]
        is_current = bool(current_season and season == current_season)
        position_finish = _integer(row.get("position_finish"))
        achievements = _season_achievements(
            row,
            season=season,
            position=normalized_position,
            position_finish=position_finish,
            current_season=is_current,
        )
        seasons.append(HistoricalSeason(
            season=season,
            age=_integer(row.get("age")),
            games=_integer(row.get("games_played")),
            fantasy_points=_metric(row, "fantasy_points_ppr"),
            fantasy_ppg=_metric(row, "ppg", "fantasy_ppg", "fantasy_points_per_game"),
            position_finish=position_finish,
            key_stats=_key_stats(row, normalized_position),
            achievements=achievements,
            current_season=is_current,
        ))

    achievements = tuple(sorted(
        (achievement for season in seasons for achievement in season.achievements),
        key=lambda item: (
            ACHIEVEMENT_LEVEL_ORDER.get(item.level, 99),
            -item.season,
            item.family,
            item.label,
        ),
    ))
    return CareerResume(
        seasons=tuple(seasons),
        achievements=achievements,
        source_note=source_note,
        historical_cache_loaded=historical_cache_loaded,
    )


def load_cached_career_resume(
    *,
    player_id: str,
    current_row: Mapping[str, Any],
    position_lookup: Mapping[str, str],
    cache_dir: str | Path = "data",
) -> CareerResume:
    """Read existing Sleeper season caches only; never fetch or mutate data."""

    selected_id = str(player_id)
    position = str(current_row.get("position") or position_lookup.get(selected_id) or "PLAYER").upper()
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(cache_dir).glob("sleeper_player_stats_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get(selected_id), dict):
            continue
        row = dict(payload[selected_id])
        season = _integer(row.get("stats_season"))
        if season is None:
            match = re.search(r"(\d{4})", path.stem)
            season = int(match.group(1)) if match else None
        if season is None:
            continue
        ranked = []
        for candidate_id, candidate in payload.items():
            if not isinstance(candidate, dict) or str(position_lookup.get(str(candidate_id), "")).upper() != position:
                continue
            points = _metric(candidate, "fantasy_points_ppr")
            if points is not None:
                ranked.append((str(candidate_id), points))
        ranked.sort(key=lambda item: (-item[1], item[0]))
        finish = next((index for index, item in enumerate(ranked, start=1) if item[0] == selected_id), None)
        row["stats_season"] = season
        row["position_finish"] = finish
        rows.append(row)

    current = dict(current_row)
    current_season = _integer(current.get("stats_season"))
    if current_season is not None:
        cached_current = next((row for row in rows if _integer(row.get("stats_season")) == current_season), {})
        merged = {**cached_current, **current, "position_finish": cached_current.get("position_finish")}
        rows = [row for row in rows if _integer(row.get("stats_season")) != current_season]
        rows.append(merged)

    return build_career_resume(
        rows,
        position=position,
        current_season=current_season,
        source_note="Verified regular-season aggregates already available in FantasyGM Lab's Sleeper cache.",
        historical_cache_loaded=True,
    )
