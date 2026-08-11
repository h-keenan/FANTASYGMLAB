"""Streamlit renderer for actionable league intelligence."""

from __future__ import annotations

from html import escape
from typing import Callable

import streamlit as st

from modules import dense_list_primitives
from modules import ui_primitives
from modules.league_intelligence import (
    LeagueIntelligenceFeed,
    LeagueIntelligenceItem,
    disclosure_state_key,
    toggle_disclosure,
)

# Material signals get exception emphasis; routine Monitor stays quiet.
_EXCEPTION_SIGNALS = frozenset({"Injury Monitor", "Waiver Watch"})


def intelligence_item_html(
    item: LeagueIntelligenceItem,
    *,
    player_html: str = "",
    primary: bool = False,
) -> str:
    """Dense news/event row — no article prose in the row shell."""

    del player_html  # Identity uses player_name; PQV tap uses data-player-id on the row.
    headline = escape(item.headline)
    headline_html = (
        f"<a href='{escape(item.external_url, quote=True)}' target='_blank' "
        f"rel='noopener noreferrer' aria-label='Open source report: {headline}'>{headline}</a>"
        if item.external_url
        else headline
    )
    identity = dense_list_primitives.dense_identity_html(
        primary=item.player_name or "League update",
        secondary_html=headline_html,
    )
    metric = dense_list_primitives.dense_metric_html(
        item.recommendation_label or "Monitor",
        "Signal",
        compact_label=False,
    )
    status = dense_list_primitives.dense_status_html(item.league_relevance or "")
    meta = dense_list_primitives.dense_meta_html(item.timestamp_label, item.source)
    exception = ""
    if item.recommendation_label in _EXCEPTION_SIGNALS:
        exception_body = item.relevance_reason or item.league_relevance or item.recommendation_label
        exception = dense_list_primitives.dense_exception_html(
            exception_body,
            label=item.recommendation_label,
        )
    trail = dense_list_primitives.dense_trail_html(
        status_html=status,
        meta_html=meta,
        exception_html=exception,
    )
    extra = ["dg-intelligence-item", "dg-ui-card"]
    if primary:
        extra.append("dg-intelligence-item--primary")
        extra.append("dg-dense-row--emphasis")
    aria = escape(
        f"{item.player_name or 'League update'}: {item.headline}".strip(": "),
        quote=True,
    )
    attrs = f"aria-label='{aria}' id='intelligence-{item.item_id}-title'"
    if item.player_id:
        attrs += (
            f" data-player-id='{escape(item.player_id, quote=True)}'"
            " role='button' tabindex='0'"
        )
        extra.append("player-card-tappable")
    return dense_list_primitives.dense_row_html(
        identity_html=identity,
        metric_html=metric,
        trail_html=trail,
        density="compact",
        extra_classes=extra,
        attrs=attrs,
        top=primary,
        no_lead=True,
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
            "No meaningful league updates yet",
            "No recent player news currently maps to a move that affects your league.",
            kind="no-data",
            recovery_guidance="Refresh after the next player-status or roster-news update.",
        )
        return

    # player_card_builder retained for call-site compatibility; dense rows use identity only.
    del score_field, score_label, player_card_builder

    current_group = ""
    for item_index, item in enumerate(feed.items):
        if item.timeline_group != current_group:
            current_group = item.timeline_group
            st.markdown(
                f"<div class='dg-intelligence-group'>{escape(current_group)}</div>",
                unsafe_allow_html=True,
            )

        item_html = intelligence_item_html(
            item,
            primary=item_index == 0,
        )
        clicked_player_id = render_tappable_player_html(
            html=item_html,
            key_prefix=f"league_intelligence_{item.item_id}",
        )
        if clicked_player_id and clicked_player_id == item.player_id:
            open_player_quick_view(
                clicked_player_id,
                source_label="News",
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
            prose = escape(item.summary)
            explanation = escape(item.explanation)
            st.markdown(
                f"<div class='dg-intelligence-explanation' role='note'>"
                f"<p class='dg-intelligence-explanation__summary'>{prose}</p>"
                f"<p>{explanation}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )
