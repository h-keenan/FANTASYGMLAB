"""Normalized, presentation-only models for the shared Player Quick View."""

from __future__ import annotations

import os
from dataclasses import dataclass
from html import escape
from typing import Mapping
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from modules import player_profile_ui
from modules.player_history import CareerResume, HistoricalSeason

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
    summary: str
    url: str = ""


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
        "<h3 class='player-dossier-snapshot-title' id='player-dossier-snapshot-title'>Current Value</h3>"
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


def career_resume_html(resume: CareerResume, *, expanded: bool = False) -> str:
    heading = dossier_section_heading_html("Career Resume").replace(
        "<h3>",
        "<h3 id='player-dossier-resume-title'>",
        1,
    )
    if expanded:
        achievements = tuple(
            sorted(
                resume.achievements,
                key=lambda item: (
                    -item.season,
                    item.family,
                    item.label,
                ),
            )
        )
    else:
        # Highest-value only; source order already prioritizes significance.
        achievements = resume.achievements[:3]
    if achievements and expanded:
        grouped = group_achievements_by_family_year(achievements)
        body_parts: list[str] = []
        for group_label, group_items in grouped:
            body_parts.append(
                f"<div class='player-dossier-achievement-family'>{escape(group_label)}</div>"
            )
            body_parts.append(
                "<ol class='player-dossier-achievement-list'>"
                + "".join(_achievement_html(item) for item in group_items)
                + "</ol>"
            )
        body = "".join(body_parts)
    elif achievements:
        body = "<ol class='player-dossier-achievement-list'>" + "".join(
            # Suppress repeated "Current season" badges in the default viewport.
            _achievement_html(item, show_current_label=False)
            for item in achievements
        ) + "</ol>"
    else:
        body = (
            "<p class='player-dossier-career-empty'>"
            "No verified achievement threshold has been reached in the loaded season data."
            "</p>"
        )
    mode = "Full verified history" if expanded else "Highest-value achievements"
    return (
        "<section class='player-dossier-career player-dossier-resume' aria-labelledby='player-dossier-resume-title'>"
        + heading
        + f"<div class='player-dossier-resume-meta'><span>Prestige</span><strong>{escape(resume.prestige_level.title())}</strong><small>{escape(mode)}</small></div>"
        + body
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
def career_profile_html(profile: CareerProfile) -> str:
    if not profile.available:
        body = (
            "<p class='player-dossier-career-empty'>"
            "Career credentials will appear here when verified achievement data is available."
            "</p>"
        )
    else:
        groups: list[str] = []
        for label, values in (
            ("Major Achievements", profile.achievements),
            ("Season Highlights", profile.season_highlights),
        ):
            if values:
                groups.append(
                    "<div class='player-dossier-career-group'>"
                    f"<h4>{escape(label)}</h4><ul>"
                    + "".join(f"<li>{escape(value)}</li>" for value in values)
                    + "</ul></div>"
                )
        body = "".join(groups)
    heading = dossier_section_heading_html(
        "Career Profile",
        "Verified production achievements and season credentials.",
    ).replace("<h3>", "<h3 id='player-dossier-career-title'>", 1)
    return (
        "<section class='player-dossier-career' aria-labelledby='player-dossier-career-title'>"
        + heading
        + body
        + "</section>"
    )


def recommendation_context_html(
    summary: str,
    context: str,
    *,
    action: str = "",
) -> str:
    heading = dossier_section_heading_html("Recommendation").replace(
        "<h3>",
        "<h3 id='player-dossier-context-title'>",
        1,
    )
    action_html = (
        f"<p class='player-dossier-context-action'><strong>{escape(action)}</strong></p>"
        if action
        else ""
    )
    return (
        "<section class='player-dossier-recommendation-context dg-info-weight-verdict' "
        "aria-labelledby='player-dossier-context-title'>"
        + heading
        + action_html
        + f"<p class='player-dossier-context-summary'>{escape(summary)}</p>"
        + f"<p class='player-dossier-context-note'>{escape(context)}</p>"
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
        "<div class='player-dossier-season-summary-metric'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in metrics
        if value
    )
    heading = dossier_section_heading_html(
        "Current Season",
        selected.label,
    ).replace("<h3>", "<h3 id='player-dossier-season-summary-title'>", 1)
    return (
        "<section class='player-dossier-season-summary' "
        "aria-labelledby='player-dossier-season-summary-title'>"
        + heading
        + f"<div class='player-dossier-season-summary-grid'>{metric_html}</div>"
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


def render_news(news_items: list[NewsItem], *, include_shell: bool = True) -> None:
    if include_shell:
        st.markdown(
            dossier_section_heading_html(
                "News",
                "Recent verified context, kept compact until you choose to expand it.",
            ),
            unsafe_allow_html=True,
        )
        news_container = st.expander("Recent News", expanded=False)
    else:
        news_container = st.container()
    with news_container:
        if news_items:
            st.markdown(
                "<div class='player-quick-view-note'>Recent news: "
                f"{escape(news_items[0].summary)}</div>",
                unsafe_allow_html=True,
            )
            if news_items[0].url:
                st.link_button(
                    "Read source",
                    news_items[0].url,
                    use_container_width=True,
                )
        else:
            st.caption("No recent player news is available.")


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
