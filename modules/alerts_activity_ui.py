"""Alerts / Activity timeline presentation."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

import streamlit as st

from modules import alerts_activity
from modules.alerts_activity_styles import ALERTS_ACTIVITY_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment


def filter_widget_key(league_id: str = "") -> str:
    scope = str(league_id or "none").strip() or "none"
    return f"alerts_filter_{scope}"


def alerts_page_header_html() -> str:
    return (
        "<section class='dg-alerts-masthead'>"
        "<p class='dg-alerts-kicker'>Signal intelligence</p>"
        "<h2>Alerts</h2>"
        "<p class='dg-alerts-lede'>"
        "Current roster-impacting signals, then the deeper activity timeline."
        "</p>"
        "</section>"
    )


def timeline_row_html(row: Mapping[str, Any]) -> str:
    glyph = escape(str(row.get("glyph") or "NEWS")[:10])
    headline = escape(str(row.get("headline") or "Update"))
    context = escape(str(row.get("context") or ""))
    freshness = escape(str(row.get("freshness") or ""))
    unread = bool(row.get("unread"))
    unread_html = "<span class='dg-alerts-unread' aria-label='Unread'></span>" if unread else ""
    context_html = f"<p class='dg-alerts-context'>{context}</p>" if context else ""
    meta_parts = [part for part in (str(row.get("category") or ""), freshness) if part]
    meta = escape(" · ".join(meta_parts))
    return (
        "<article class='dg-alerts-row'>"
        f"<div class='dg-alerts-glyph'>{glyph}</div>"
        "<div>"
        f"<p class='dg-alerts-headline'>{headline}</p>"
        f"{context_html}"
        f"<div class='dg-alerts-meta'>{unread_html}<span>{meta}</span></div>"
        "</div>"
        "</article>"
    )


def render_alerts_page(
    *,
    league_id: str = "",
    session: Mapping[str, Any] | None = None,
    entitlement: str = "free",
    render_section_header=None,
) -> None:
    inject_global_styles(ALERTS_ACTIVITY_CSS)
    if render_section_header is not None:
        render_section_header(
            "Alerts",
            kicker="Activity",
            note="Priority signals and a deeper timeline. Not a second History.",
        )
    render_html_fragment(alerts_page_header_html())
    rows = alerts_activity.compose_activity_timeline(
        session=session if session is not None else st.session_state,
        league_id=league_id,
        entitlement=entitlement,
    )
    key = filter_widget_key(league_id)
    default = st.session_state.get(key, alerts_activity.FILTER_IMPORTANT)
    if default not in alerts_activity.ALERT_FILTERS:
        default = alerts_activity.FILTER_IMPORTANT
    with st.container(key=key):
        selected = st.pills(
            "Timeline filter",
            list(alerts_activity.ALERT_FILTERS),
            default=default,
            key=f"{key}_control",
        )
    selected_label = str(selected or default)
    visible = alerts_activity.filter_timeline(rows, selected_label)
    if not visible:
        render_html_fragment(
            "<p class='dg-alerts-empty'>No activity in this filter yet.</p>"
        )
        return
    body = "".join(timeline_row_html(row) for row in visible)
    render_html_fragment(f"<div class='dg-alerts-shell'>{body}</div>")
