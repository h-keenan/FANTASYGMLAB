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
    recommendation_tone: str = "strategy"


@dataclass(frozen=True)
class CareerProfile:
    achievements: tuple[str, ...] = ()
    season_highlights: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return bool(self.achievements or self.season_highlights)


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


def snapshot_html(snapshot: DossierSnapshot) -> str:
    tone = (
        snapshot.recommendation_tone
        if snapshot.recommendation_tone in {"strategy", "opportunity", "risk"}
        else "strategy"
    )
    metrics = (
        ("Dynasty Value", snapshot.dynasty_value),
        ("Overall Rank", snapshot.rank),
        ("Prestige", snapshot.tier),
        ("Trend", snapshot.trend),
    )
    metric_html = "".join(
        "<div class='player-dossier-snapshot-metric'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong>"
        "</div>"
        for label, value in metrics
    )
    return (
        "<section class='player-dossier-snapshot' aria-labelledby='player-dossier-snapshot-title'>"
        "<h3 class='player-dossier-snapshot-title' id='player-dossier-snapshot-title'>Snapshot</h3>"
        f"<div class='player-dossier-snapshot-grid'>{metric_html}</div>"
        f"<div class='player-dossier-decision player-dossier-decision--{tone}'>"
        "<span>Immediate Recommendation</span>"
        f"<strong>{escape(snapshot.recommendation)}</strong>"
        f"<p>{escape(snapshot.recommendation_note)}</p>"
        "</div></section>"
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


def recommendation_context_html(summary: str, context: str) -> str:
    heading = dossier_section_heading_html(
        "Recommendation Context",
        "Why this player matters under the current league and roster lens.",
    ).replace("<h3>", "<h3 id='player-dossier-context-title'>", 1)
    return (
        "<section class='player-dossier-recommendation-context' "
        "aria-labelledby='player-dossier-context-title'>"
        + heading
        + f"<p class='player-dossier-context-summary'>{escape(summary)}</p>"
        + f"<p class='player-dossier-context-note'>{escape(context)}</p>"
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
) -> tuple[str, ...]:
    """Render the one proven regular-season aggregate loaded today."""
    model = _stats_model(stats)
    rendered: list[str] = []
    st.markdown(
        dossier_section_heading_html(
            "Current Season",
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


def render_news(news_items: list[NewsItem]) -> None:
    st.markdown(
        dossier_section_heading_html(
            "News",
            "Recent verified context, kept compact until you choose to expand it.",
        ),
        unsafe_allow_html=True,
    )
    with st.expander("Recent News", expanded=False):
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
