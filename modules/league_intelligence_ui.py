"""Streamlit renderer for actionable league intelligence."""

from __future__ import annotations

from html import escape
from typing import Callable

import streamlit as st

from modules import ui_primitives
from modules.league_intelligence import (
    LeagueIntelligenceFeed,
    LeagueIntelligenceItem,
    disclosure_state_key,
    toggle_disclosure,
)


def intelligence_item_html(
    item: LeagueIntelligenceItem,
    *,
    player_html: str = "",
) -> str:
    metadata = " · ".join(
        part for part in (item.timestamp_label, item.source) if part
    )
    headline = escape(item.headline)
    headline_html = (
        f"<a href='{escape(item.external_url, quote=True)}' target='_blank' "
        f"rel='noopener noreferrer' aria-label='Open source report: {headline}'>{headline}</a>"
        if item.external_url
        else headline
    )
    recommendation = ui_primitives.status_badge_html(
        item.recommendation_label,
        variant=(
            "opportunity"
            if item.recommendation_label == "Waiver Watch"
            else "caution"
            if item.recommendation_label == "Injury Monitor"
            else "information"
        ),
    )
    relevance = (
        ui_primitives.status_badge_html(item.league_relevance, variant="neutral")
        if item.league_relevance
        else ""
    )
    return (
        f"<article class='dg-intelligence-item' aria-labelledby='intelligence-{item.item_id}-title'>"
        "<header class='dg-intelligence-item__header'>"
        f"<h3 class='dg-intelligence-item__headline' id='intelligence-{item.item_id}-title'>{headline_html}</h3>"
        "</header>"
        + (
            f"<div class='dg-intelligence-item__player'>{player_html}</div>"
            if player_html
            else ""
        )
        + f"<div class='dg-intelligence-item__meta'>{escape(metadata)}</div>"
        f"<p class='dg-intelligence-item__summary'>{escape(item.summary)}</p>"
        f"<div class='dg-intelligence-item__signals'>{recommendation}{relevance}</div>"
        + "</article>"
    )


def render_league_intelligence_feed(
    feed: LeagueIntelligenceFeed,
    *,
    score_field: str,
    score_label: str,
    player_card_builder: Callable,
    render_tappable_player_html: Callable,
    open_player_quick_view: Callable,
) -> None:
    if not feed.items:
        ui_primitives.render_empty_state_panel(
            "No meaningful league intelligence yet",
            "No recent player update currently maps to an actionable league context.",
            kind="no-data",
            recovery_guidance="Refresh after the next player-status or roster-news update.",
        )
        return

    current_group = ""
    for item in feed.items:
        if item.timeline_group != current_group:
            current_group = item.timeline_group
            st.markdown(
                f"<div class='dg-intelligence-group'>{escape(current_group)}</div>",
                unsafe_allow_html=True,
            )

        player_row = feed.player_rows_by_id.get(item.player_id)
        player_html = ""
        if player_row is not None:
            player_html = player_card_builder(
                player_row,
                score_field=score_field,
                score_label=score_label,
                note_text="",
                interactive=True,
                design_system=True,
            )
        item_html = intelligence_item_html(item, player_html=player_html)
        clicked_player_id = render_tappable_player_html(
            html=item_html,
            key_prefix=f"league_intelligence_{item.item_id}",
        )
        if clicked_player_id and clicked_player_id == item.player_id:
            open_player_quick_view(
                clicked_player_id,
                source_label="League Intelligence",
                source_note=item.summary,
                status_label=item.recommendation_label,
            )

        state_key = disclosure_state_key(item.item_id)
        expanded = bool(st.session_state.get(state_key, False))
        st.button(
            f"{'▾' if expanded else '▸'} Why this matters",
            key=f"league_intelligence_{item.item_id}_control",
            help=(
                "Collapse the league-specific explanation"
                if expanded
                else "Expand the league-specific explanation"
            ),
            on_click=toggle_disclosure,
            kwargs={"item_id": item.item_id, "state": st.session_state},
            type="tertiary",
            width="content",
        )
        if expanded:
            st.markdown(
                f"<div class='dg-intelligence-explanation' role='note'>{escape(item.explanation)}</div>",
                unsafe_allow_html=True,
            )
