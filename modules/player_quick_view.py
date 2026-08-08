"""Normalized, presentation-only models for the shared Player Quick View."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from html import escape
from typing import Mapping
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from modules import player_profile_ui
from modules.player_history import (
    CareerResume,
    HistoricalSeason,
    prioritize_milestones,
    summarize_career_resume,
)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_PRODUCTION_HOSTS = frozenset({"fantasygmlab.com", "www.fantasygmlab.com"})


@dataclass(frozen=True)
class StatItem:
    label: str
    value: str
    note: str
    tone: str


@dataclass(frozen=True)
class SeasonStatView:
    season: int | None
    season_type: str
    games: int | None
    complete: bool | None
    key_stats: tuple[StatItem, ...]
    fantasy: tuple[StatItem, ...]
    usage: tuple[StatItem, ...]

    @property
    def label(self) -> str:
        if self.season is None:
            return f"{self.season_type} (year unavailable)"
        return f"{self.season} {self.season_type}".strip()


@dataclass(frozen=True)
class PlayerQuickViewStats:
    seasons: tuple[SeasonStatView, ...]
    college: tuple[StatItem, ...]
    college_available: bool
    career_totals_available: bool = False


@dataclass(frozen=True)
class NewsItem:
    headline: str = ""
    source: str = ""
    freshness: str = ""
    snippet: str = ""
    url: str = ""
    summary: str = ""

    def display_headline(self) -> str:
        return self.headline or self.summary

    def display_snippet(self) -> str:
        return self.snippet


@dataclass(frozen=True)
class DossierSnapshot:
    dynasty_value: str
    rank: str
    tier: str
    recommendation: str
    trend: str
    recommendation_note: str
    position_rank: str = ""
    fantasy_ppg: str = ""
    recommendation_tone: str = "strategy"
    health: str = ""
    scoring_format: str = ""


@dataclass(frozen=True)
class CareerProfile:
    achievements: tuple[str, ...] = ()
    season_highlights: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return bool(self.achievements or self.season_highlights)


@dataclass(frozen=True)
class ExecutiveSnapshot:
    years_in_league: str = ""
    draft_capital: str = ""
    college: str = ""
    height: str = ""
    weight: str = ""
    bye_week: str = ""
    contract_status: str = ""


def build_executive_snapshot(
    row: Mapping[str, object],
    metadata: Mapping[str, object] | None = None,
) -> ExecutiveSnapshot:
    """Normalize verified profile metadata without inventing unavailable fields."""
    source = dict(metadata or {})
    source.update({key: value for key, value in row.items() if _text(value)})

    years_raw = pd.to_numeric(pd.Series([source.get("years_exp")]), errors="coerce").iloc[0]
    years = ""
    if pd.notna(years_raw) and float(years_raw) >= 0:
        seasons = int(float(years_raw))
        years = "Rookie" if seasons == 0 else f"{seasons} season{'s' if seasons != 1 else ''}"

    round_raw = pd.to_numeric(pd.Series([source.get("draft_round")]), errors="coerce").iloc[0]
    pick_raw = pd.to_numeric(
        pd.Series([source.get("draft_slot") or source.get("draft_pick")]),
        errors="coerce",
    ).iloc[0]
    year_raw = pd.to_numeric(pd.Series([source.get("draft_year")]), errors="coerce").iloc[0]
    draft_parts: list[str] = []
    if pd.notna(year_raw):
        draft_parts.append(str(int(float(year_raw))))
    if pd.notna(round_raw):
        draft_parts.append(f"Round {int(float(round_raw))}")
    if pd.notna(pick_raw):
        draft_parts.append(f"Pick {int(float(pick_raw))}")

    height = _text(source.get("height"))
    if height.isdigit():
        total_inches = int(height)
        height = f"{total_inches // 12}'{total_inches % 12}\""
    weight = _text(source.get("weight"))
    if weight and weight.replace(".", "", 1).isdigit():
        weight = f"{int(float(weight))} lb"

    return ExecutiveSnapshot(
        years_in_league=years,
        draft_capital=" / ".join(draft_parts),
        college=_text(source.get("college")),
        height=height,
        weight=weight,
        bye_week=_text(source.get("bye_week")),
        contract_status=_text(source.get("contract_status")),
    )


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _integer(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else int(numeric)


def _items(items: list[dict]) -> tuple[StatItem, ...]:
    return tuple(
        StatItem(
            label=_text(item.get("label")) or "Metric",
            value=_text(item.get("value")),
            note=_text(item.get("note")),
            tone=_text(item.get("tone")) or "reference",
        )
        for item in items
    )


def _group_items(row: pd.Series) -> dict[str, list[dict]]:
    return {
        label: list(items)
        for label, items in player_profile_ui.player_profile_stat_groups(row)
    }


def _key_stats(row: pd.Series, groups: Mapping[str, list[dict]]) -> list[dict]:
    by_label = {str(item.get("label")): item for item in groups.get("NFL Stats", [])}
    position = _text(row.get("position")).upper()
    order = {
        "QB": ["Games", "Pass Att", "Pass Yards", "Pass TDs", "Rush Yards", "Rush TDs"],
        "RB": ["Games", "Rush Att", "Rush Yards", "Rush TDs", "Targets", "Receptions", "Rec Yards", "Rec TDs"],
        "WR": ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Yards", "Rush TDs"],
        "TE": ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Yards", "Rush TDs"],
    }.get(
        position,
        ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Att", "Rush Yards", "Rush TDs", "Pass Yards", "Pass TDs"],
    )
    return [dict(by_label[label]) for label in order if label in by_label]


def _fantasy_stats(groups: Mapping[str, list[dict]], games: int | None) -> list[dict]:
    by_label = {str(item.get("label")): item for item in groups.get("Fantasy Stats", [])}
    formats = [
        ("Fantasy PPR", "PPR"),
        ("Half PPR", "Half PPR"),
        ("Fantasy Pts", "Standard"),
    ]
    present = [(source, label, by_label[source]) for source, label in formats if source in by_label]
    distinct_values = {str(item.get("value")) for _source, _label, item in present}
    suffix = f" across {games} games." if games is not None else "."
    if len(present) > 1 and len(distinct_values) == 1:
        source, _label, item = present[-1]
        collapsed = dict(item)
        collapsed["label"] = "Fantasy Points"
        collapsed["note"] = f"Scoring totals are identical across loaded formats{suffix}"
        output = [collapsed]
    else:
        output = []
        for _source, label, item in present:
            cloned = dict(item)
            cloned["label"] = label
            cloned["note"] = f"{label} season total{suffix}"
            output.append(cloned)
    if "PPG" in by_label:
        ppg = dict(by_label["PPG"])
        ppg["label"] = "PPR PPG"
        ppg["note"] = f"PPR points per game{suffix}"
        output.append(ppg)
    return output


def _usage_stats(groups: Mapping[str, list[dict]]) -> list[dict]:
    by_label = {str(item.get("label")): item for item in groups.get("Usage", [])}
    return [
        {**by_label[source], "label": label}
        for source, label in (
            ("Snap Share", "Snap %"),
            ("Route Part.", "Route %"),
            ("Target Share", "Target Share"),
            ("Rush Share", "Carry Share"),
            ("Opportunity Share", "Opportunity"),
        )
        if source in by_label
    ]


def build_stats_view(row: pd.Series) -> PlayerQuickViewStats:
    """Build the view from the one regular-season aggregate loaded today.

    The production loader joins exactly one ``stats_season`` record per player.
    It does not retain weekly rows or prior seasons, so this model deliberately
    exposes one season and never invents career totals.
    """

    groups = _group_items(row)
    games = _integer(row.get("games_played"))
    season = _integer(row.get("stats_season"))
    season_view = SeasonStatView(
        season=season,
        season_type="Regular Season",
        games=games,
        complete=None,
        key_stats=_items(_key_stats(row, groups)),
        fantasy=_items(_fantasy_stats(groups, games)),
        usage=_items(_usage_stats(groups)),
    )
    college = _items(groups.get("College Stats", []))
    has_professional_stats = bool(
        season_view.key_stats or season_view.fantasy or season_view.usage
    )
    return PlayerQuickViewStats(
        seasons=(season_view,) if has_professional_stats else (),
        college=college,
        college_available=bool(college),
    )


def dense_section_html(title: str, items: tuple[StatItem, ...] | list[StatItem]) -> str:
    rows = "".join(
        "<div class='player-quick-view-stat-row'>"
        f"<div class='player-quick-view-stat-label'>{escape(item.label)}</div>"
        "<div class='player-quick-view-stat-copy'>"
        f"<div class='player-quick-view-stat-value dg-stat-tone-{escape(item.tone)}'>{escape(item.value)}</div>"
        + (f"<div class='player-quick-view-stat-note'>{escape(item.note)}</div>" if item.note else "")
        + "</div></div>"
        for item in items
    )
    return (
        "<section class='player-quick-view-stat-section'>"
        f"<h3 class='player-quick-view-stat-heading'>{escape(title)}</h3>"
        f"<div class='player-quick-view-stat-grid'>{rows}</div></section>"
    )


def dossier_section_heading_html(title: str, subtitle: str = "") -> str:
    return (
        "<header class='player-dossier-section-heading'>"
        f"<h3>{escape(title)}</h3>"
        + (f"<p>{escape(subtitle)}</p>" if subtitle else "")
        + "</header>"
    )


def rank_strip_html(
    *,
    overall_display: str,
    position_display: str = "",
    scoring_format: str = "",
    dynasty_value: str = "",
) -> str:
    """Compact canonical rank line: OVR #16 · RB #6 · PPR."""

    parts: list[str] = []
    overall = _text(overall_display)
    if overall and overall.casefold() not in {"rank unavailable", "not available", "unavailable"}:
        parts.append(overall if overall.upper().startswith("OVR") else overall)
    position = _text(position_display)
    if position and position.casefold() not in {"not available", "unavailable", "unknown"}:
        parts.append(position)
    fmt = _text(scoring_format)
    if fmt:
        parts.append(fmt)
    if not parts and not _text(dynasty_value):
        return ""
    rank_line = " · ".join(parts) if parts else "Rank unavailable"
    value_html = (
        f"<span class='player-dossier-rank-strip-value'>Value {escape(_text(dynasty_value))}</span>"
        if _text(dynasty_value)
        else ""
    )
    return (
        "<div class='player-dossier-rank-strip' role='group' aria-label='Canonical rank'>"
        f"<strong>{escape(rank_line)}</strong>"
        + value_html
        + "</div>"
    )


def snapshot_html(snapshot: DossierSnapshot, *, include_recommendation: bool = True) -> str:
    tone = (
        snapshot.recommendation_tone
        if snapshot.recommendation_tone in {"strategy", "opportunity", "risk"}
        else "strategy"
    )
    metrics = (
        ("Dynasty Value", snapshot.dynasty_value),
        ("Overall Rank", snapshot.rank),
        ("Position Rank", snapshot.position_rank),
        ("Format", snapshot.scoring_format),
        ("Recent PPG", snapshot.fantasy_ppg),
        ("Health", snapshot.health),
        ("Trend", snapshot.trend),
    )

    metric_html = "".join(
        "<div class='player-dossier-snapshot-metric'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong>"
        "</div>"
        for label, value in metrics
        if value and value.casefold() not in {"not available", "unavailable", "unknown"}
    )
    recommendation_html = ""
    if include_recommendation:
        recommendation_html = (
            f"<div class='player-dossier-decision player-dossier-decision--{tone}'>"
            "<span>Recommendation</span>"
            f"<strong>{escape(snapshot.recommendation)}</strong>"
            f"<p>{escape(snapshot.recommendation_note)}</p>"
            "</div>"
        )
    return (
        "<section class='player-dossier-snapshot' aria-labelledby='player-dossier-snapshot-title'>"
        "<h3 class='player-dossier-snapshot-title' id='player-dossier-snapshot-title'>Value &amp; Health</h3>"
        f"<div class='player-dossier-snapshot-grid'>{metric_html}</div>"
        + recommendation_html
        + "</section>"
    )


def executive_snapshot_html(snapshot: ExecutiveSnapshot) -> str:
    metrics = (
        ("Experience", snapshot.years_in_league),
        ("Draft Capital", snapshot.draft_capital),
        ("College", snapshot.college),
        ("Height", snapshot.height),
        ("Weight", snapshot.weight),
        ("Bye Week", snapshot.bye_week),
        ("Contract", snapshot.contract_status),
    )
    content = "".join(
        "<div class='player-dossier-executive-metric'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in metrics
        if value and value.casefold() not in {"not available", "unavailable", "unknown"}
    )
    if not content:
        return ""
    heading = dossier_section_heading_html("Executive Summary").replace(
        "<h3>",
        "<h3 id='player-dossier-executive-title'>",
        1,
    )
    return (
        "<section class='player-dossier-executive' aria-labelledby='player-dossier-executive-title'>"
        + heading
        + f"<div class='player-dossier-executive-grid'>{content}</div></section>"
    )


def _achievement_html(achievement, *, show_current_label: bool = True) -> str:
    current_label = (
        "<span class='player-dossier-achievement-current'>Current season</span>"
        if show_current_label and achievement.current_season
        else ""
    )
    return (
        f"<li class='player-dossier-achievement player-dossier-achievement--{escape(achievement.level)}'>"
        f"<span class='player-dossier-achievement-icon' aria-hidden='true'>{escape(achievement.icon)}</span>"
        "<span class='player-dossier-achievement-copy'>"
        f"<strong>{escape(achievement.label)}</strong>"
        f"<small>{escape(str(achievement.season))} · {escape(achievement.detail)}</small>"
        f"{current_label}</span></li>"
    )


def group_achievements_by_family_year(achievements: tuple) -> list[tuple[str, tuple]]:
    """Group achievements by season then family for expanded resume presentation."""

    buckets: dict[tuple[int, str], list] = {}
    order: list[tuple[int, str]] = []
    for item in achievements:
        key = (int(item.season), str(item.family))
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(item)
    return [
        (f"{season} · {family.replace('-', ' ').title()}", tuple(buckets[key]))
        for key in order
        for season, family in (key,)
    ]


def career_resume_html(
    resume: CareerResume,
    *,
    expanded: bool = False,
    position: str = "",
    years_exp: int | None = None,
) -> str:
    """Render factual Career Context résumé — no invented prestige system."""

    heading = dossier_section_heading_html("Career Context").replace(
        "<h3>",
        "<h3 id='player-dossier-resume-title'>",
        1,
    )
    normalized_position = str(position or "").upper()
    if not normalized_position and resume.seasons:
        # Infer only for presentation when callers omit position.
        normalized_position = "PLAYER"
    summary = summarize_career_resume(
        resume,
        position=normalized_position or "PLAYER",
        years_exp=years_exp,
    )
    metrics: list[tuple[str, str]] = []
    if summary.experience_label:
        metrics.append(("Experience", summary.experience_label))
    if summary.best_finish_label:
        finish_value = summary.best_finish_label
        if summary.best_finish_season:
            finish_value = f"{finish_value} · {summary.best_finish_season}"
        metrics.append(("Best finish", finish_value))
    if summary.best_production_label:
        metrics.append(("Best season", summary.best_production_label))
    if summary.consistency_label:
        metrics.append(("Consistency", summary.consistency_label))
    if summary.arc_label and (expanded or len(resume.seasons) >= 2):
        metrics.append(("Recent arc", summary.arc_label))

    if metrics:
        metric_html = "".join(
            "<div class='player-dossier-career-metric'>"
            f"<span>{escape(label)}</span><strong>{escape(value)}</strong>"
            "</div>"
            for label, value in metrics
        )
        body = f"<div class='player-dossier-career-summary'>{metric_html}</div>"
    elif summary.empty_state:
        body = (
            f"<p class='player-dossier-career-empty'>{escape(summary.empty_state)}</p>"
        )
    else:
        body = (
            "<p class='player-dossier-career-empty'>"
            "Limited NFL history available."
            "</p>"
        )

    milestones = prioritize_milestones(
        resume.achievements,
        limit=6 if expanded else 4,
    )
    if milestones and expanded:
        grouped = group_achievements_by_family_year(milestones)
        milestone_parts: list[str] = [
            "<div class='player-dossier-career-milestones'>"
            "<div class='player-dossier-career-milestones-title'>Career Milestones</div>"
        ]
        for group_label, group_items in grouped:
            milestone_parts.append(
                f"<div class='player-dossier-achievement-family'>{escape(group_label)}</div>"
            )
            milestone_parts.append(
                "<ol class='player-dossier-achievement-list'>"
                + "".join(_achievement_html(item) for item in group_items)
                + "</ol>"
            )
        milestone_parts.append("</div>")
        body += "".join(milestone_parts)
    elif milestones:
        labels = " · ".join(item.label for item in milestones)
        body += (
            "<div class='player-dossier-career-milestones'>"
            "<div class='player-dossier-career-milestones-title'>Career Milestones</div>"
            f"<p class='player-dossier-career-milestone-line'>{escape(labels)}</p>"
            "</div>"
        )

    basis = (
        f"<p class='player-dossier-career-basis'>{escape(summary.scoring_basis)}</p>"
        if expanded
        else ""
    )
    return (
        "<section class='player-dossier-career player-dossier-resume' aria-labelledby='player-dossier-resume-title'>"
        + heading
        + body
        + basis
        + "</section>"
    )


def _season_timeline_html(season: HistoricalSeason, *, include_achievements: bool = True) -> str:
    context = []
    if season.age is not None:
        context.append(f"Age {season.age}")
    if season.position_finish is not None:
        context.append(f"Position finish #{season.position_finish}")
    if season.games is not None:
        context.append(f"{season.games} games")
    metrics = []
    if season.fantasy_points is not None:
        metrics.append(f"{season.fantasy_points:.1f} PPR points")
    if season.fantasy_ppg is not None:
        metrics.append(f"{season.fantasy_ppg:.1f} PPG")
    metrics.extend(f"{label} {value}" for label, value in season.key_stats)
    achievement_labels = (
        ", ".join(item.label for item in season.achievements[:2])
        if include_achievements
        else ""
    )
    return (
        "<li class='player-dossier-timeline-season'>"
        f"<div class='player-dossier-timeline-year'><strong>{season.season}</strong>"
        + ("<span>Current</span>" if season.current_season else "")
        + "</div><div class='player-dossier-timeline-copy'>"
        + (f"<div class='player-dossier-timeline-context'>{escape(' · '.join(context))}</div>" if context else "")
        + (f"<p>{escape(' · '.join(metrics))}</p>" if metrics else "")
        + (f"<small>{escape(achievement_labels)}</small>" if achievement_labels else "")
        + "</div></li>"
    )


def career_timeline_html(
    resume: CareerResume,
    *,
    expanded: bool = False,
    include_achievements: bool = False,
) -> str:
    heading = dossier_section_heading_html("Career Timeline").replace(
        "<h3>",
        "<h3 id='player-dossier-timeline-title'>",
        1,
    )
    seasons = resume.seasons if expanded else resume.seasons[:2]
    if seasons:
        body = "<ol class='player-dossier-timeline'>" + "".join(
            _season_timeline_html(season, include_achievements=include_achievements)
            for season in seasons
        ) + "</ol>"
    else:
        body = "<p class='player-dossier-career-empty'>Historical season data is not currently available for this player.</p>"
    return (
        "<section class='player-dossier-career player-dossier-career-timeline' aria-labelledby='player-dossier-timeline-title'>"
        + heading + body + "</section>"
    )
def recommendation_context_html(
    summary: str,
    context: str,
    *,
    action: str = "",
    active_recommendation: bool = True,
    recommendation_id: str = "",
) -> str:
    """Render PQV recommendation or neutral player context.

    When ``active_recommendation`` is false, this is general player analysis —
    not a synthesized recommendation.
    """

    title = "Recommendation" if active_recommendation else "Player Context"
    heading = dossier_section_heading_html(title).replace(
        "<h3>",
        "<h3 id='player-dossier-context-title'>",
        1,
    )
    action_html = (
        f"<p class='player-dossier-context-action'><strong>{escape(action)}</strong></p>"
        if action and active_recommendation
        else ""
    )
    provenance = (
        f"<p class='player-dossier-context-provenance' data-recommendation-id="
        f"'{escape(recommendation_id, quote=True)}'></p>"
        if recommendation_id
        else ""
    )
    mode_class = (
        "player-dossier-recommendation-context dg-info-weight-verdict"
        if active_recommendation
        else "player-dossier-recommendation-context player-dossier-neutral-context"
    )
    return (
        f"<section class='{mode_class}' "
        "aria-labelledby='player-dossier-context-title'>"
        + heading
        + action_html
        + f"<p class='player-dossier-context-summary'>{escape(summary)}</p>"
        + f"<p class='player-dossier-context-note'>{escape(context)}</p>"
        + provenance
        + "</section>"
    )


def current_season_summary_html(stats: pd.Series | PlayerQuickViewStats) -> str:
    """Compact executive season snapshot — full tables stay behind disclosure."""

    model = _stats_model(stats)
    if not model.seasons:
        return ""
    selected = model.seasons[0]
    fantasy_points = next(
        (
            item.value
            for item in selected.fantasy
            if item.label.casefold() in {"fantasy points", "ppr", "fantasy ppr"}
        ),
        "",
    )
    ppg = next(
        (item.value for item in selected.fantasy if "PPG" in item.label.upper()),
        "",
    )
    production = [
        (item.label, item.value)
        for item in selected.key_stats
        if item.label.casefold() != "games"
    ][:4]
    usage = [(item.label, item.value) for item in selected.usage[:2]]
    metrics: list[tuple[str, str]] = []
    if selected.games is not None:
        metrics.append(("Games", str(selected.games)))
    if ppg:
        metrics.append(("PPG", ppg))
    if fantasy_points:
        metrics.append(("Fantasy Pts", fantasy_points))
    metrics.extend(production)
    metrics.extend(usage)
    if not metrics:
        return ""
    metric_html = "".join(
        "<div class='player-dossier-snapshot-metric'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in metrics
        if value
    )
    heading = dossier_section_heading_html(
        "Current Snapshot",
        selected.label,
    ).replace("<h3>", "<h3 id='player-dossier-season-summary-title'>", 1)
    return (
        "<section class='player-dossier-season-summary player-dossier-snapshot' "
        "aria-labelledby='player-dossier-season-summary-title'>"
        + heading
        + f"<div class='player-dossier-snapshot-grid'>{metric_html}</div>"
        + "</section>"
    )


def college_unavailable_message() -> str:
    return "College production data is not currently available for this player."


def developer_diagnostics_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    enabled = _text(env.get("DYNASTYGM_DEBUG_UI")).casefold() in _TRUE_VALUES
    host = _text(env.get("APP_BASE_URL")).casefold().removeprefix("https://").removeprefix("http://").split("/")[0]
    return enabled and host not in _PRODUCTION_HOSTS


def developer_diagnostics(row: pd.Series) -> dict[str, list[str]]:
    return player_profile_ui.player_stat_field_debug(row)


def safe_news_url(value: object) -> str:
    url = _text(value)
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


_KNOWN_NEWS_HOSTS = {
    "rotowire.com": "RotoWire",
    "espn.com": "ESPN",
    "cbssports.com": "CBS Sports",
    "sports.yahoo.com": "Yahoo Sports",
    "yahoo.com": "Yahoo Sports",
    "nbcsports.com": "NBC Sports",
    "nfl.com": "NFL.com",
    "theathletic.com": "The Athletic",
    "profootballtalk.nbcsports.com": "PFT",
    "pff.com": "PFF",
    "si.com": "Sports Illustrated",
    "bleacherreport.com": "Bleacher Report",
}

_KNOWN_NEWS_NAMES = {
    "espn": "ESPN",
    "espn nfl": "ESPN",
    "cbs": "CBS Sports",
    "cbs sports": "CBS Sports",
    "cbssports": "CBS Sports",
    "rotowire": "RotoWire",
    "roto wire": "RotoWire",
    "yahoo": "Yahoo Sports",
    "yahoo sports": "Yahoo Sports",
    "nbc": "NBC Sports",
    "nbc sports": "NBC Sports",
    "nfl": "NFL.com",
    "the athletic": "The Athletic",
    "profootballtalk": "PFT",
    "pft": "PFT",
    "pff": "PFF",
}


def normalize_news_source(value: object) -> str:
    """Return a publisher label; never invent a false brand for unknown hosts."""

    text = _text(value)
    if not text:
        return ""
    lower = text.casefold().strip()
    if lower in _KNOWN_NEWS_NAMES:
        return _KNOWN_NEWS_NAMES[lower]
    looks_like_url = any(token in text for token in ("://", "/", "?", "&", "www."))
    if not looks_like_url:
        return text
    candidate = text if "://" in text else f"https://{text.lstrip('/')}"
    parsed = urlparse(candidate)
    host = (parsed.netloc or "").casefold()
    if not host:
        return text
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host in _KNOWN_NEWS_HOSTS:
        return _KNOWN_NEWS_HOSTS[host]
    for known_host, label in _KNOWN_NEWS_HOSTS.items():
        if host.endswith(f".{known_host}"):
            return label
    # Clean domain label only — do not invent a publisher name.
    return host


def news_card_html(item: NewsItem) -> str:
    headline = escape(item.display_headline())
    if not headline:
        return ""
    meta_parts = [part for part in (item.source, item.freshness) if part]
    meta = escape(" · ".join(meta_parts)) if meta_parts else ""
    snippet = escape(item.display_snippet()) if item.display_snippet() else ""
    return (
        "<article class='player-dossier-news-card'>"
        + (f"<p class='player-dossier-news-meta'>{meta}</p>" if meta else "")
        + f"<h4 class='player-dossier-news-headline'>{headline}</h4>"
        + (f"<p class='player-dossier-news-snippet'>{snippet}</p>" if snippet else "")
        + "</article>"
    )


def news_unavailable_html() -> str:
    return (
        "<p class='player-dossier-news-quiet'>"
        "Recent news is temporarily unavailable."
        "</p>"
    )


def news_empty_html() -> str:
    return (
        "<p class='player-dossier-news-quiet'>"
        "No recent player news is available."
        "</p>"
    )


def _stats_model(value: pd.Series | PlayerQuickViewStats) -> PlayerQuickViewStats:
    return value if isinstance(value, PlayerQuickViewStats) else build_stats_view(value)


def render_current_season(
    stats: pd.Series | PlayerQuickViewStats,
    *,
    show_heading: bool = True,
) -> tuple[str, ...]:
    """Render the one proven regular-season aggregate loaded today."""
    model = _stats_model(stats)
    rendered: list[str] = []
    if show_heading:
        st.markdown(
            dossier_section_heading_html(
                "Complete Season Stats",
                "Professional production, fantasy output, and usage from one consistent season.",
            ),
            unsafe_allow_html=True,
        )
    if model.seasons:
        selected = model.seasons[0]
        context = selected.label
        if selected.games is not None:
            context += f" | {selected.games} games"
        st.markdown(
            f"<div class='player-quick-view-season-context'>{escape(context)}</div>",
            unsafe_allow_html=True,
        )
        for title, items in (
            ("Professional Production", selected.key_stats),
            ("Fantasy Production", selected.fantasy),
            ("Usage", selected.usage),
        ):
            if items:
                rendered.append(title)
                st.markdown(dense_section_html(title, items), unsafe_allow_html=True)

    if not rendered:
        st.markdown(
            "<div class='player-detail-empty player-quick-view-stats-empty'>"
            "No professional statistics are available for the loaded season."
            "</div>",
            unsafe_allow_html=True,
        )

    return tuple(rendered)


def render_news(
    news_items: list[NewsItem],
    *,
    include_shell: bool = True,
    status: str = "ok",
    default_limit: int = 3,
) -> None:
    """Render polished recent-news cards. Never exposes raw URLs as primary copy."""

    if include_shell:
        st.markdown(
            dossier_section_heading_html(
                "Recent News",
                "Automatically loaded player headlines.",
            ),
            unsafe_allow_html=True,
        )

    if status == "error":
        st.markdown(news_unavailable_html(), unsafe_allow_html=True)
        return
    if status == "loading":
        st.caption("Loading recent news…")
        return
    if not news_items:
        st.markdown(news_empty_html(), unsafe_allow_html=True)
        return

    visible = list(news_items[: max(1, int(default_limit))])
    overflow = list(news_items[len(visible) :])

    def _paint(items: list[NewsItem]) -> None:
        for index, item in enumerate(items):
            card = news_card_html(item)
            if card:
                st.markdown(card, unsafe_allow_html=True)
            if item.url:
                digest = hashlib.sha1(
                    f"{item.url}|{item.display_headline()}|{index}".encode("utf-8")
                ).hexdigest()[:12]
                st.link_button(
                    "Read article →",
                    item.url,
                    key=f"pqv_news_read_{digest}",
                    use_container_width=False,
                )

    _paint(visible)
    if overflow:
        overflow_parts: list[str] = []
        for item in overflow:
            card = news_card_html(item)
            if card:
                overflow_parts.append(card)
            if item.url:
                overflow_parts.append(
                    "<p class='player-dossier-news-link'>"
                    f"<a href='{escape(item.url, quote=True)}' target='_blank' "
                    "rel='noopener noreferrer'>Read article →</a></p>"
                )
        details = (
            f"<details class='dg-info-disclosure dg-client-disclosure "
            f"player-dossier-more-news'>"
            f"<summary>More news ({len(overflow)})</summary>"
            f"<div class='dg-client-disclosure-body'>{''.join(overflow_parts)}</div>"
            "</details>"
        )
        st.markdown(details, unsafe_allow_html=True)


def render_college_production(stats: pd.Series | PlayerQuickViewStats) -> None:
    model = _stats_model(stats)
    if model.college_available:
        st.markdown(
            dense_section_html("College Production", model.college),
            unsafe_allow_html=True,
        )
    else:
        st.caption(college_unavailable_message())


def render_developer_diagnostics(row: pd.Series) -> None:
    if developer_diagnostics_enabled():
        st.caption("Developer Information — field availability diagnostics.")
        st.json(developer_diagnostics(row))
