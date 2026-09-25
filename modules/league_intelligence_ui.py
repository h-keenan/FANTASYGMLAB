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

# Only a true risk earns the danger-toned exception pill. Waiver Watch is an
# opportunity (a roster-relevant player is available), not a concern, so it
# must not share Injury Monitor's danger-red treatment (Magna Carta: semantic
# color discipline — red is reserved for actual risk).
_EXCEPTION_SIGNALS = frozenset({"Injury Monitor"})

# Recommendation-label tone for the primary-metric slot. Injury Monitor reads
# as risk (danger/red); Waiver Watch reads as an actionable opportunity
# (accent); routine Monitor stays untoned so real signals still stand out.
_SIGNAL_TONE_CLASS = {
    "Injury Monitor": "dg-intelligence-signal--danger",
    "Waiver Watch": "dg-intelligence-signal--opportunity",
}

# Decision-tier grouping (Magna Carta §4: organize by user decision, not backend
# taxonomy). Replaces the prior calendar-day section headers (Today/Yesterday/
# date) — per-item recency is unchanged and still shown via timestamp_label in
# the meta trail, so no information is lost, only reordered. Item order within
# a tier is exactly the existing chronological feed order; only bucketing
# changes here, mirroring the Alerts V2 restructure (Needs Your Attention ->
# My Players -> Around the League), with a Waiver Watch tier inserted per the
# Waiver UI rule (personalized/actionable before generic market context).
_TIER_ATTENTION = "attention"
_TIER_ROSTER = "roster"
_TIER_WAIVER = "waiver"
_TIER_LEAGUE = "league"
_TIER_ORDER = (_TIER_ATTENTION, _TIER_ROSTER, _TIER_WAIVER, _TIER_LEAGUE)
_TIER_LABELS = {
    _TIER_ATTENTION: "Needs Your Attention",
    _TIER_ROSTER: "Your Roster",
    _TIER_WAIVER: "Waiver Watch",
    _TIER_LEAGUE: "Around the League",
}


def _decision_tier(item: LeagueIntelligenceItem) -> str:
    """Presentation-only decision-priority bucket; never touches ranking/sort."""

    if item.league_relevance == "Owned by you":
        if item.recommendation_label == "Injury Monitor":
            return _TIER_ATTENTION
        return _TIER_ROSTER
    if item.recommendation_label == "Waiver Watch":
        return _TIER_WAIVER
    return _TIER_LEAGUE


def _unconfirmed_badge_html(item: LeagueIntelligenceItem) -> str:
    """Amber 'Unconfirmed' badge for speculative/rumor-sourced reports.

    Surfaces `item.speculative` (already computed upstream by
    modules.news_signal.enrich_news_item and passed through by
    build_league_intelligence_feed) so a rumor no longer reads with the same
    confidence as a confirmed report — matching the fix already applied to
    Alerts (PR #767).
    """

    if not item.speculative:
        return ""
    return " " + ui_primitives.status_badge_html("Unconfirmed", variant="caution")


def _recommendation_metric_html(recommendation_label: str) -> str:
    """Primary-metric slot for the recommendation, toned by urgency/opportunity."""

    text = recommendation_label or "Monitor"
    tone_class = _SIGNAL_TONE_CLASS.get(text, "")
    value_class = "dg-dense-metric__value" + (f" {tone_class}" if tone_class else "")
    return (
        "<div class='dg-dense-metric'>"
        f"<span class='{value_class}'>{escape(text)}</span>"
        "<span class='dg-dense-metric__label'>Signal</span>"
        "</div>"
    )


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
    headline_html += _unconfirmed_badge_html(item)
    identity = dense_list_primitives.dense_identity_html(
        primary=item.player_name or "League update",
        secondary_html=headline_html,
    )
    metric = _recommendation_metric_html(item.recommendation_label)
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

    grouped: dict[str, list[LeagueIntelligenceItem]] = {tier: [] for tier in _TIER_ORDER}
    for item in feed.items:
        grouped[_decision_tier(item)].append(item)

    rendered_index = 0
    for tier in _TIER_ORDER:
        tier_items = grouped[tier]
        if not tier_items:
            continue
        st.markdown(
            f"<div class='dg-intelligence-group dg-intelligence-group--{tier}'>"
            f"{escape(_TIER_LABELS[tier])}</div>",
            unsafe_allow_html=True,
        )
        for item in tier_items:
            item_html = intelligence_item_html(
                item,
                primary=rendered_index == 0,
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
            rendered_index += 1

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
