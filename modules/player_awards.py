"""Canonical player awards from verified season aggregates.

Badges are deterministic fantasy-performance accomplishments. They are never
invented, never AI-generated, and never presented as official NFL honors.

This module does not fetch. It reads optional local Sleeper season cache files
already used by career résumé, or accepts in-memory season rows.

Thresholds (regular season, position-gated)
------------------------------------------
Fantasy finish (verified PPR rank among the player's position in the cache):
  Gold   positional rank <= 3
  Silver positional rank <= 5
  Bronze positional rank <= 10
  Same season: keep only the strongest finish.

Overall PPR finish (all skill players in the same season cache):
  Gold   overall rank <= 5
  Silver overall rank <= 10
  Same season: keep only the strongest overall finish.
  Skip when overall rank cannot be computed from the cache.

Yardage (strongest qualifying tier per family per season):
  QB  passing yards  Gold >= 5,000  Silver >= 4,000
  RB  rushing yards  Gold >= 1,500  Silver >= 1,000
  WR/TE receiving yards Gold >= 1,500  Silver >= 1,000

Touchdowns (strongest qualifying tier per family per season):
  QB  passing TD     Gold >= 40  Silver >= 30
  RB  rushing TD     Gold >= 15  Silver >= 10
  WR/TE receiving TD Gold >= 12  Silver >= 10

Usage (not every season is tiered — only elite volume):
  WR  targets >= 140   "Elite Target Volume"
  TE  targets >= 110   "Elite Target Volume"
  RB  rush attempts >= 280 or (rush attempts + targets) >= 320
      "Elite Workhorse Season"

Repeat seasons of the same family collapse into one badge with occurrence_count
and a compact "2×" label. The season shown is the most recent qualifying year.

Priority (lower number wins; then better tier; then more recent season):
  1 positional fantasy finish
  2 overall fantasy finish
  3 yardage milestone
  4 touchdown milestone
  5 usage / workload
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

TIER_GOLD = "gold"
TIER_SILVER = "silver"
TIER_BRONZE = "bronze"
TIER_RANK = {TIER_GOLD: 0, TIER_SILVER: 1, TIER_BRONZE: 2, None: 9}

DISPLAY_BADGE_LIMIT = 5
SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})

PRIORITY_POSITIONAL_FINISH = 1
PRIORITY_OVERALL_FINISH = 2
PRIORITY_YARDAGE = 3
PRIORITY_TOUCHDOWN = 4
PRIORITY_USAGE = 5


@dataclass(frozen=True)
class PlayerBadge:
    badge_id: str
    category: str
    title: str
    short_label: str
    tier: str | None
    season: int | None
    rank: int | None
    metric_value: float | None
    description: str
    priority: int
    family: str
    occurrence_count: int = 1

    def with_repeats(self, count: int, *, season: int | None) -> "PlayerBadge":
        if count <= 1:
            return self
        suffix = f"{count}×"
        short = self.short_label
        if "×" not in short:
            short = f"{short} {suffix}"
        return PlayerBadge(
            badge_id=self.badge_id,
            category=self.category,
            title=self.title,
            short_label=short,
            tier=self.tier,
            season=season if season is not None else self.season,
            rank=self.rank,
            metric_value=self.metric_value,
            description=self.description,
            priority=self.priority,
            family=self.family,
            occurrence_count=count,
        )


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


def _position(value: Any) -> str:
    return str(value or "").strip().upper()


def _badge(
    *,
    family: str,
    category: str,
    title: str,
    short_label: str,
    tier: str | None,
    season: int | None,
    rank: int | None,
    metric_value: float | None,
    description: str,
    priority: int,
) -> PlayerBadge:
    season_bit = str(season) if season is not None else "na"
    slug = re.sub(r"[^a-z0-9]+", "-", f"{family}-{season_bit}".casefold()).strip("-")
    return PlayerBadge(
        badge_id=slug,
        category=category,
        title=title,
        short_label=short_label,
        tier=tier,
        season=season,
        rank=rank,
        metric_value=metric_value,
        description=description,
        priority=priority,
        family=family,
    )


def _finish_tier(rank: int, *, gold: int, silver: int, bronze: int | None) -> str | None:
    if rank <= gold:
        return TIER_GOLD
    if rank <= silver:
        return TIER_SILVER
    if bronze is not None and rank <= bronze:
        return TIER_BRONZE
    return None


def _positional_finish_badge(position: str, season: int, rank: int) -> PlayerBadge | None:
    tier = _finish_tier(rank, gold=3, silver=5, bronze=10)
    if tier is None:
        return None
    cutoff = 3 if tier == TIER_GOLD else 5 if tier == TIER_SILVER else 10
    short = f"Top-{cutoff} {position}"
    return _badge(
        family="positional-finish",
        category="fantasy_finish",
        title=f"{short} PPR Finish",
        short_label=short,
        tier=tier,
        season=season,
        rank=rank,
        metric_value=float(rank),
        description=(
            f"Finished {position}{rank} in verified PPR among {position} players "
            f"in the {season} season cache. Historical finish, not a current ranking."
        ),
        priority=PRIORITY_POSITIONAL_FINISH,
    )


def _overall_finish_badge(season: int, rank: int) -> PlayerBadge | None:
    tier = _finish_tier(rank, gold=5, silver=10, bronze=None)
    if tier is None:
        return None
    cutoff = 5 if tier == TIER_GOLD else 10
    short = f"Overall Top {cutoff}"
    return _badge(
        family="overall-finish",
        category="fantasy_finish",
        title=f"{short} PPR Finish",
        short_label=short,
        tier=tier,
        season=season,
        rank=rank,
        metric_value=float(rank),
        description=(
            f"Finished overall PPR #{rank} in the {season} season cache. "
            "Historical finish, not a current ranking."
        ),
        priority=PRIORITY_OVERALL_FINISH,
    )


def _milestone_tier(value: float, *, gold: float, silver: float) -> str | None:
    if value >= gold:
        return TIER_GOLD
    if value >= silver:
        return TIER_SILVER
    return None


def _season_badges(row: Mapping[str, Any], *, position: str) -> list[PlayerBadge]:
    season = _integer(row.get("stats_season") or row.get("season"))
    if season is None:
        return []
    badges: list[PlayerBadge] = []
    pos_finish = _integer(row.get("position_finish"))
    if pos_finish:
        finish = _positional_finish_badge(position, season, pos_finish)
        if finish is not None:
            badges.append(finish)
    overall = _integer(row.get("overall_finish"))
    if overall:
        overall_badge = _overall_finish_badge(season, overall)
        if overall_badge is not None:
            badges.append(overall_badge)

    passing_yards = _metric(row, "passing_yards", "pass_yards")
    passing_tds = _metric(row, "passing_tds", "pass_tds")
    rushing_yards = _metric(row, "rushing_yards", "rush_yards")
    rushing_tds = _metric(row, "rushing_tds", "rush_tds")
    receiving_yards = _metric(row, "receiving_yards", "receiving_yds")
    receiving_tds = _metric(row, "receiving_tds", "receiving_td")
    targets = _metric(row, "targets")
    rush_att = _metric(row, "rush_attempts", "rushing_attempts", "carries")

    if position == "QB":
        if passing_yards is not None:
            tier = _milestone_tier(passing_yards, gold=5000, silver=4000)
            if tier is not None:
                cutoff = 5000 if tier == TIER_GOLD else 4000
                badges.append(
                    _badge(
                        family="pass-yards",
                        category="milestone",
                        title=f"{cutoff:,}+ Passing Yards",
                        short_label=f"{cutoff // 1000}k Pass Yds",
                        tier=tier,
                        season=season,
                        rank=None,
                        metric_value=passing_yards,
                        description=f"{int(passing_yards):,} passing yards in {season}.",
                        priority=PRIORITY_YARDAGE,
                    )
                )
        if passing_tds is not None:
            tier = _milestone_tier(passing_tds, gold=40, silver=30)
            if tier is not None:
                cutoff = 40 if tier == TIER_GOLD else 30
                badges.append(
                    _badge(
                        family="pass-td",
                        category="milestone",
                        title=f"{cutoff}+ Passing TDs",
                        short_label=f"{cutoff}+ Pass TD",
                        tier=tier,
                        season=season,
                        rank=None,
                        metric_value=passing_tds,
                        description=f"{int(passing_tds)} passing touchdowns in {season}.",
                        priority=PRIORITY_TOUCHDOWN,
                    )
                )
    elif position == "RB":
        if rushing_yards is not None:
            tier = _milestone_tier(rushing_yards, gold=1500, silver=1000)
            if tier is not None:
                cutoff = 1500 if tier == TIER_GOLD else 1000
                badges.append(
                    _badge(
                        family="rush-yards",
                        category="milestone",
                        title=f"{cutoff:,}+ Rushing Yards",
                        short_label=f"{cutoff:,}+ Rush Yds",
                        tier=tier,
                        season=season,
                        rank=None,
                        metric_value=rushing_yards,
                        description=f"{int(rushing_yards):,} rushing yards in {season}.",
                        priority=PRIORITY_YARDAGE,
                    )
                )
        if rushing_tds is not None:
            tier = _milestone_tier(rushing_tds, gold=15, silver=10)
            if tier is not None:
                cutoff = 15 if tier == TIER_GOLD else 10
                badges.append(
                    _badge(
                        family="rush-td",
                        category="milestone",
                        title=f"{cutoff}+ Rushing TDs",
                        short_label=f"{cutoff}+ Rush TD",
                        tier=tier,
                        season=season,
                        rank=None,
                        metric_value=rushing_tds,
                        description=f"{int(rushing_tds)} rushing touchdowns in {season}.",
                        priority=PRIORITY_TOUCHDOWN,
                    )
                )
        touches = None
        if rush_att is not None:
            touches = rush_att + (targets or 0.0)
        if (rush_att is not None and rush_att >= 280) or (
            touches is not None and touches >= 320
        ):
            metric = rush_att if rush_att is not None else touches
            badges.append(
                _badge(
                    family="workhorse",
                    category="usage",
                    title="Elite Workhorse Season",
                    short_label="Workhorse",
                    tier=None,
                    season=season,
                    rank=None,
                    metric_value=metric,
                    description=(
                        f"Elite rushing workload in {season} "
                        f"({int(rush_att or 0)} rush attempts"
                        + (f", {int(targets)} targets" if targets else "")
                        + ")."
                    ),
                    priority=PRIORITY_USAGE,
                )
            )
    elif position in {"WR", "TE"}:
        if receiving_yards is not None:
            tier = _milestone_tier(receiving_yards, gold=1500, silver=1000)
            if tier is not None:
                cutoff = 1500 if tier == TIER_GOLD else 1000
                badges.append(
                    _badge(
                        family="rec-yards",
                        category="milestone",
                        title=f"{cutoff:,}+ Receiving Yards",
                        short_label=f"{cutoff:,}+ Rec Yds",
                        tier=tier,
                        season=season,
                        rank=None,
                        metric_value=receiving_yards,
                        description=f"{int(receiving_yards):,} receiving yards in {season}.",
                        priority=PRIORITY_YARDAGE,
                    )
                )
        if receiving_tds is not None:
            tier = _milestone_tier(receiving_tds, gold=12, silver=10)
            if tier is not None:
                cutoff = 12 if tier == TIER_GOLD else 10
                badges.append(
                    _badge(
                        family="rec-td",
                        category="milestone",
                        title=f"{cutoff}+ Receiving TDs",
                        short_label=f"{cutoff}+ Rec TD",
                        tier=tier,
                        season=season,
                        rank=None,
                        metric_value=receiving_tds,
                        description=f"{int(receiving_tds)} receiving touchdowns in {season}.",
                        priority=PRIORITY_TOUCHDOWN,
                    )
                )
        target_floor = 140 if position == "WR" else 110
        if targets is not None and targets >= target_floor:
            badges.append(
                _badge(
                    family="targets",
                    category="usage",
                    title="Elite Target Volume",
                    short_label="Elite Targets",
                    tier=None,
                    season=season,
                    rank=None,
                    metric_value=targets,
                    description=f"{int(targets)} targets in {season}.",
                    priority=PRIORITY_USAGE,
                )
            )
    return badges


def _sort_key(badge: PlayerBadge) -> tuple:
    return (
        badge.priority,
        TIER_RANK.get(badge.tier, 9),
        -(badge.season or 0),
        badge.rank if badge.rank is not None else 10_000,
        badge.family,
        badge.badge_id,
    )


def collapse_repeat_badges(badges: Sequence[PlayerBadge]) -> tuple[PlayerBadge, ...]:
    """Keep one badge per family: strongest tier, most recent season, with count."""

    by_family: dict[str, list[PlayerBadge]] = {}
    for badge in badges:
        by_family.setdefault(badge.family, []).append(badge)
    collapsed: list[PlayerBadge] = []
    for family_badges in by_family.values():
        ordered = sorted(family_badges, key=_sort_key)
        best = ordered[0]
        seasons = {item.season for item in family_badges if item.season is not None}
        collapsed.append(best.with_repeats(len(seasons) or 1, season=best.season))
    return tuple(sorted(collapsed, key=_sort_key))


def build_player_awards(
    season_rows: Sequence[Mapping[str, Any]],
    *,
    position: str,
) -> tuple[PlayerBadge, ...]:
    """Build normalized awards from verified season rows. No network. No AI."""

    normalized = _position(position)
    if normalized not in SKILL_POSITIONS:
        return ()
    collected: list[PlayerBadge] = []
    for row in season_rows:
        collected.extend(_season_badges(row, position=normalized))
    return collapse_repeat_badges(collected)


def select_display_badges(
    badges: Sequence[PlayerBadge],
    *,
    limit: int = DISPLAY_BADGE_LIMIT,
) -> tuple[PlayerBadge, ...]:
    ordered = tuple(sorted(badges, key=_sort_key))
    if limit <= 0:
        return ()
    return ordered[:limit]


def remaining_badges(
    badges: Sequence[PlayerBadge],
    *,
    limit: int = DISPLAY_BADGE_LIMIT,
) -> tuple[PlayerBadge, ...]:
    ordered = tuple(sorted(badges, key=_sort_key))
    return ordered[max(0, limit) :]


def build_season_cache_index(
    cache_dir: str | Path = "data",
) -> tuple[dict[str, Any], ...]:
    """Load local Sleeper season JSON. Never fetches. Empty when files are absent."""

    seasons: list[dict[str, Any]] = []
    for path in sorted(Path(cache_dir).glob("sleeper_player_stats_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        match = re.search(r"(\d{4})", path.stem)
        file_season = int(match.group(1)) if match else None
        seasons.append({"path": str(path), "season": file_season, "payload": payload})
    return tuple(seasons)


def award_rows_for_player(
    index: Sequence[Mapping[str, Any]],
    *,
    player_id: str,
    current_row: Mapping[str, Any] | None = None,
    position: str,
    position_lookup: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Slice cached season files for one player and attach verified finishes."""

    selected_id = str(player_id or "").strip()
    if not selected_id:
        rows = []
        if current_row:
            rows.append(dict(current_row))
        return rows
    lookup = position_lookup or {}
    normalized = _position(position or lookup.get(selected_id))
    rows: list[dict[str, Any]] = []
    for entry in index:
        payload = entry.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get(selected_id), dict):
            continue
        row = dict(payload[selected_id])
        season = _integer(row.get("stats_season")) or _integer(entry.get("season"))
        if season is None:
            continue
        ranked_pos: list[tuple[str, float]] = []
        ranked_all: list[tuple[str, float]] = []
        for candidate_id, candidate in payload.items():
            if not isinstance(candidate, dict):
                continue
            points = _metric(candidate, "fantasy_points_ppr")
            if points is None:
                continue
            cid = str(candidate_id)
            ranked_all.append((cid, points))
            candidate_pos = _position(candidate.get("position") or lookup.get(cid))
            if candidate_pos == normalized:
                ranked_pos.append((cid, points))
        ranked_pos.sort(key=lambda item: (-item[1], item[0]))
        ranked_all.sort(key=lambda item: (-item[1], item[0]))
        pos_finish = next(
            (idx for idx, item in enumerate(ranked_pos, start=1) if item[0] == selected_id),
            None,
        )
        overall = next(
            (idx for idx, item in enumerate(ranked_all, start=1) if item[0] == selected_id),
            None,
        )
        row["stats_season"] = season
        row["position_finish"] = pos_finish
        row["overall_finish"] = overall
        rows.append(row)

    if current_row:
        current = dict(current_row)
        current_season = _integer(current.get("stats_season"))
        if current_season is not None:
            cached = next(
                (row for row in rows if _integer(row.get("stats_season")) == current_season),
                {},
            )
            merged = {
                **cached,
                **current,
                "position_finish": cached.get("position_finish")
                or _integer(current.get("position_finish")),
                "overall_finish": cached.get("overall_finish")
                or _integer(current.get("overall_finish")),
            }
            rows = [row for row in rows if _integer(row.get("stats_season")) != current_season]
            rows.append(merged)
        elif not rows:
            rows.append(current)
    return rows
