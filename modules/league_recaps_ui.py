"""League Recaps presentation — editorial GM briefing over History facts."""

from __future__ import annotations

from html import escape
from typing import Any, Callable, Mapping, Sequence

import streamlit as st

from modules import deferred_rendering
from modules import league_history
from modules import league_history_ui
from modules import league_recaps
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.league_recaps_styles import LEAGUE_RECAPS_CSS
from modules.semantic_glyphs import glyph_html


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def recap_story_html(story: Mapping[str, Any]) -> str:
    glyph = _text(story.get("glyph"), "history")
    title = escape(_text(story.get("title"), "Story"))
    summary = escape(_text(story.get("summary")))
    team = escape(_text(story.get("primary_team")))
    secondary = escape(_text(story.get("secondary_team")))
    metric_label = escape(_text(story.get("metric_label")))
    metric_value = escape(_text(story.get("metric_value")))
    identity = team
    if secondary:
        identity = f"{team} vs {secondary}" if team else secondary
    metric = ""
    if metric_value:
        metric = (
            "<div class='dg-recap-metric'>"
            f"<span>{metric_label or 'Recorded'}</span>"
            f"<strong>{metric_value}</strong></div>"
        )
    players = "".join(
        f"<span class='dg-recap-player'>{escape(_text(name))}</span>"
        for name in story.get("players") or ()
        if _text(name)
    )
    lenses = ""
    for lens in story.get("value_lenses") or ():
        if not isinstance(lens, Mapping):
            continue
        lenses += (
            "<p class='dg-recap-lens'>"
            f"<strong>{escape(_text(lens.get('label')))}</strong> "
            f"{escape(_text(lens.get('note')))}</p>"
        )
    editorial = _text(story.get("editorial_label"))
    editorial_html = (
        f"<p class='dg-recap-editorial'>{escape(editorial)}</p>" if editorial else ""
    )
    return (
        f"<article class='dg-recap-story dg-recap-story--{escape(_text(story.get('story_type'), 'story'))}'>"
        "<div class='dg-recap-story-kicker'>"
        + glyph_html(glyph, size="kicker")
        + f"<h3>{title}</h3></div>"
        + (f"<p class='dg-recap-identity'>{identity}</p>" if identity else "")
        + f"<p class='dg-recap-summary'>{summary}</p>"
        + metric
        + (f"<div class='dg-recap-players'>{players}</div>" if players else "")
        + editorial_html
        + lenses
        + "</article>"
    )


def recap_edition_html(recap: Mapping[str, Any]) -> str:
    week = _text(recap.get("week") or recap.get("period_key"), "—")
    headline = escape(_text(recap.get("headline"), f"Week {week} recap"))
    stories = [recap_story_html(story) for story in recap.get("stories") or () if isinstance(story, Mapping)]
    body = "".join(stories) or (
        "<p class='dg-recap-empty'>Not enough historical data for a recap this week.</p>"
    )
    return (
        "<section class='dg-recap-edition' aria-label='Weekly recap'>"
        "<header class='dg-recap-masthead'>"
        f"<p class='dg-recap-kicker'>{glyph_html('history', size='kicker')}League Memory</p>"
        f"<h2>Week {escape(str(week))} recap</h2>"
        f"<p class='dg-recap-headline'>{headline}</p>"
        "</header>"
        f"<div class='dg-recap-board'>{body}</div>"
        "</section>"
    )


def dashboard_teaser_html(teaser: Mapping[str, str]) -> str:
    return (
        "<aside class='dg-recap-teaser' aria-label='League recap teaser'>"
        f"<p class='dg-recap-kicker'>{glyph_html('history', size='kicker')}"
        f"{escape(_text(teaser.get('kicker'), 'League Recap'))}</p>"
        f"<p class='dg-recap-teaser-title'>{escape(_text(teaser.get('title')))}</p>"
        f"<p class='dg-recap-teaser-note'>{escape(_text(teaser.get('note')))}</p>"
        "</aside>"
    )


def history_deep_link_label(story: Mapping[str, Any]) -> str:
    kind = _text(story.get("story_type"))
    if kind == league_recaps.STORY_TRADE:
        return "View Trade History"
    if kind == league_recaps.STORY_WAIVER:
        return "View waiver history"
    if kind in {league_recaps.STORY_ACTIVITY, league_recaps.STORY_PERFORMANCE, league_recaps.STORY_MATCHUP}:
        return "Open League History"
    return ""


def render_league_recaps_page(
    *,
    home_league_id: str,
    season: str,
    league: Mapping[str, Any] | None,
    player_lookup: Mapping[str, Mapping[str, Any]],
    current_profiles: Mapping[str, Any] | None,
    matchups: Sequence[Mapping[str, Any]],
    movement: Mapping[str, Any] | None,
    render_section_header: Callable[..., None],
    open_history: Callable[[str], None] | None = None,
    power_ranks: Mapping[int, int] | None = None,
) -> None:
    inject_global_styles(LEAGUE_RECAPS_CSS)
    render_section_header(
        "League Recaps",
        kicker="League Memory",
        note="Editorial briefing of completed weeks. History remains the source record.",
    )
    if not home_league_id:
        st.caption("Import a league to generate recaps from completed history.")
        return
    if not deferred_rendering.render_section_gate(
        st,
        st.session_state,
        f"league_recaps_{home_league_id}",
        button_label="Load league recaps",
        note="Recaps stay off until you open them. No extra provider pass on Dashboard.",
    ):
        return

    completed = league_recaps.completed_recap_week(league, matchups)
    named_matchups = []
    profile_map = current_profiles or {}
    for row in matchups:
        payload = dict(row)
        roster_id = str(payload.get("roster_id") or "")
        profile = profile_map.get(roster_id) or profile_map.get(str(payload.get("roster_id"))) or {}
        if isinstance(profile, Mapping) and not payload.get("team_name"):
            payload["team_name"] = _text(profile.get("team_name"))
        named_matchups.append(payload)
    matchups = named_matchups
    if completed <= 0:
        render_html_fragment(
            "<p class='dg-recap-empty'>A recap is not generated while the current week is incomplete.</p>"
        )
        return

    payload = league_history_ui.cached_season_history_payload(home_league_id)
    profiles = payload.get("profiles") or {}
    if current_profiles:
        profiles = current_profiles
    normalized = league_history.normalize_season_payload(
        payload,
        profiles=profiles,
        player_lookup=player_lookup or {},
    )
    available_weeks = sorted(
        {
            int(item.get("week") or 0)
            for item in normalized
            if int(item.get("week") or 0) > 0
        }
        | {
            int(row.get("week") or 0)
            for row in matchups
            if int(row.get("week") or 0) > 0
        }
    )
    available_weeks = [week for week in available_weeks if week <= completed]
    archive = league_recaps.archive_weeks(latest=completed, available=available_weeks)
    labels: list[str] = []
    label_to_week: dict[str, int] = {}
    if archive["this_week"]:
        label = f"This week · {completed}"
        labels.append(label)
        label_to_week[label] = completed
    for week in archive["previous_weeks"]:
        label = f"Week {week}"
        labels.append(label)
        label_to_week[label] = week
    if not labels:
        render_html_fragment(
            "<p class='dg-recap-empty'>Not enough historical data for a recap archive yet.</p>"
        )
        return
    selected_label = st.pills(
        "Recap archive",
        labels,
        default=labels[0],
        key=f"league_recaps_archive_{home_league_id}",
    ) or labels[0]
    selected_week = label_to_week.get(selected_label, completed)
    recap = league_recaps.get_or_build_weekly_recap(
        st.session_state,
        league_id=home_league_id,
        season=season or _text((league or {}).get("season") if isinstance(league, Mapping) else ""),
        week=selected_week,
        transactions=normalized,
        matchups=matchups,
        profiles=profiles,
        movement=movement if selected_week == completed else None,
        power_ranks=power_ranks,
    )
    render_html_fragment(recap_edition_html(recap))
    for index, story in enumerate(recap.get("stories") or ()):
        label = history_deep_link_label(story)
        if not label or open_history is None:
            continue
        if st.button(
            label,
            key=f"league_recap_history_{home_league_id}_{selected_week}_{index}",
            use_container_width=False,
        ):
            open_history(_text(story.get("history_filter")) or league_history.FILTER_ALL)
