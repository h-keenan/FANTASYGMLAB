"""Alerts / Activity timeline presentation."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, MutableMapping, Sequence
from urllib.parse import urlparse

import streamlit as st

from modules import alerts_activity
from modules import player_images
from modules import player_profile_ui
from modules.alerts_activity_styles import ALERTS_ACTIVITY_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment


def filter_widget_key(league_id: str = "") -> str:
    scope = str(league_id or "none").strip() or "none"
    return f"alerts_filter_{scope}"


def alerts_page_header_html() -> str:
    """Compressed secondary label — not a second page title."""

    return (
        "<section class='dg-alerts-masthead' aria-label='Activity timeline'>"
        "<p class='dg-alerts-kicker'>Activity</p>"
        "<p class='dg-alerts-lede'>Priority signals in one timeline.</p>"
        "</section>"
    )


def _safe_source_url(value: object) -> str:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


def timeline_row_html(row: Mapping[str, Any]) -> str:
    glyph = escape(str(row.get("glyph") or "NEWS")[:10])
    headline = escape(alerts_activity.humanize_headline(row))
    context = escape(str(row.get("context") or ""))
    freshness = escape(str(row.get("freshness") or ""))
    unread = bool(row.get("unread"))
    relationship = str(row.get("roster_relationship") or "").strip().upper()
    severity = str(row.get("severity") or "").strip().upper()
    event_type = str(row.get("event_type") or "").strip().upper()
    is_my_player = relationship in alerts_activity._MY_REL
    is_urgent = severity in {"CRITICAL", "HIGH"} and is_my_player
    row_classes = ["dg-alerts-row"]
    player_id = str(row.get("player_id") or "").strip()
    if player_id:
        row_classes.append("dg-alerts-row--player")
    if is_urgent:
        row_classes.extend(("dg-alerts-row--urgent", "dg-alerts-row--my-player"))
    elif str(row.get("category") or "").upper() == "NEWS":
        row_classes.append("dg-alerts-row--news")
    badges: list[str] = []
    if is_my_player:
        badges.append("<span class='dg-alerts-badge dg-alerts-badge--my'>MY PLAYER</span>")
    if event_type in {"INJURY", "INACTIVE", "IR_PUP_NFI", "INJURY_SEVERITY_UPDATE"}:
        event_label = (
            "POTENTIALLY SIGNIFICANT INJURY"
            if bool(row.get("significant_injury_event"))
            else "INJURY ALERT"
        )
        badges.append(f"<span class='dg-alerts-badge dg-alerts-badge--risk'>{event_label}</span>")
    badges_html = (
        "<div class='dg-alerts-badges'>" + "".join(badges) + "</div>"
        if badges
        else ""
    )
    unread_html = "<span class='dg-alerts-unread' aria-label='Unread'></span>" if unread else ""
    if is_my_player and event_type in {
        "INJURY",
        "INACTIVE",
        "IR_PUP_NFI",
        "INJURY_SEVERITY_UPDATE",
    }:
        relationship_label = {
            "MY_STARTER": "Starter",
            "MY_BENCH": "Bench",
            "MY_TAXI": "Taxi squad",
            "MY_IR": "IR",
        }.get(relationship, "My roster")
        status_label = "Status not yet confirmed" if bool(row.get("status_unconfirmed")) else ""
        context = escape(" · ".join(part for part in (relationship_label, status_label) if part))
    context_html = f"<p class='dg-alerts-context'>{context}</p>" if context else ""
    meta_parts = [part for part in (str(row.get("category") or ""), freshness) if part]
    meta = escape(" · ".join(meta_parts))
    source_url = _safe_source_url(row.get("source_url"))
    headline_html = (
        f"<a class='dg-alerts-headline dg-alerts-headline--link' href='{escape(source_url, quote=True)}' "
        f"target='_blank' rel='noopener noreferrer'>{headline}</a>"
        if source_url
        else f"<p class='dg-alerts-headline'>{headline}</p>"
    )
    player_name = str(row.get("player_name") or headline or "Player").strip()
    initials = "".join(part[:1] for part in player_name.split()[:2]).upper() or "?"
    visual_html = f"<div class='dg-alerts-glyph'>{glyph}</div>"
    if player_id:
        portrait = player_profile_ui.avatar_html(
            player_images.get_player_image_url(player_id),
            initials,
            css_class="dg-alerts-portrait",
        )
        visual_html = portrait
    article_open = f"<article class='{' '.join(row_classes)}'"
    article_open += " aria-label='Urgent player alert'>" if is_urgent else ">"
    return (
        article_open
        + visual_html
        + "<div>"
        f"{headline_html}"
        f"{badges_html}"
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
    open_player_quick_view=None,
) -> None:
    inject_global_styles(ALERTS_ACTIVITY_CSS)
    if render_section_header is not None:
        render_section_header(
            "Alerts",
            kicker="Activity",
            note="Priority signals in one timeline.",
        )
    render_html_fragment(alerts_page_header_html())
    rows = alerts_activity.compose_activity_timeline(
        session=session if session is not None else st.session_state,
        league_id=league_id,
        entitlement=entitlement,
    )
    try:
        from modules.news import schedule_news_cache_refresh

        schedule_news_cache_refresh()
    except Exception:
        # Cached rows remain useful even when deferred refresh cannot start.
        pass
    key = filter_widget_key(league_id)
    control_key = f"{key}_control"
    stored_filter = st.session_state.get(control_key, st.session_state.get(key))
    default = alerts_activity.normalize_filter(
        stored_filter,
        default=alerts_activity.FILTER_MY_PLAYERS,
    )
    if stored_filter == "Important":
        st.session_state[control_key] = default
    with st.container(key=key):
        selected = st.pills(
            "Timeline filter",
            list(alerts_activity.ALERT_FILTERS),
            default=default,
            key=control_key,
            label_visibility="collapsed",
        )
    selected_label = str(selected or default)
    visible = alerts_activity.filter_timeline(rows, selected_label)
    if not visible:
        copy = escape(alerts_activity.empty_copy(selected_label))
        render_html_fragment(f"<p class='dg-alerts-empty'>{copy}</p>")
        return
    with st.container(key=f"{key}_timeline"):
        for index, row in enumerate(visible):
            with st.container(key=f"alerts_item_{league_id}_{index}"):
                render_html_fragment(timeline_row_html(row))
                player_id = str(row.get("player_id") or "").strip()
                if player_id and open_player_quick_view is not None:
                    event_id = str(
                        row.get("id") or row.get("recommendation_id") or ""
                    ).strip()

                    def _open_alert_player(
                        selected_player_id=player_id,
                        selected_event_id=event_id,
                    ) -> None:
                        if isinstance(session, MutableMapping) and selected_event_id:
                            from modules import notification_center

                            notification_center.mark_notification_read(
                                session,
                                selected_event_id,
                                league_id=league_id,
                            )
                        open_player_quick_view(
                            selected_player_id,
                            source_label="Alerts",
                            event_id=selected_event_id,
                        )

                    st.button(
                        "Open player",
                        key=f"{key}_player_{index}_{player_id}",
                        on_click=_open_alert_player,
                    )
