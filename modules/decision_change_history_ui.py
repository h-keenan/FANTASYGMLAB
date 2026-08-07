"""Streamlit presentation for What Changed? decision history."""

from __future__ import annotations

from html import escape
from typing import Callable

import streamlit as st

from modules import decision_change_history as history
from modules import ui_primitives
from modules.html_rendering import inject_global_styles, render_html_fragment


# Scoped to Dashboard What Changed renders — keep off the global cold-path CSS budget.
DECISION_CHANGE_HISTORY_CSS = """
<style>
.dg-what-changed-quiet{align-items:baseline;background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-2xs);padding:var(--space-sm) var(--space-md)}
.dg-what-changed-quiet strong{color:var(--color-text-muted);font:var(--font-card-title)}
.dg-what-changed-quiet span{color:var(--color-text-secondary);font:var(--font-body);max-width:40rem}
.dg-what-changed-item{border-block-end:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-2xs);padding-block:var(--space-sm)}
.dg-what-changed-meta{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-what-changed-headline{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-what-changed-detail{color:var(--color-text-secondary);font:var(--type-caption-emphasis);max-width:40rem}
.dg-what-changed-why{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
@media (max-width:430px){.dg-what-changed-detail{-webkit-box-orient:vertical;-webkit-line-clamp:2;display:-webkit-box;overflow:hidden}}
</style>
"""


def _group_label(timestamp: float, *, now: float | None = None) -> str:
    from time import time as _time

    current = float(now if now is not None else _time())
    return "Today" if (current - float(timestamp)) < 86400 else "Earlier"


def render_what_changed_section(
    events: tuple[history.DecisionChangeEvent, ...],
    *,
    open_event: Callable[[history.DecisionChangeEvent], None] | None = None,
    key_prefix: str = "what_changed",
) -> None:
    """Compact Dashboard section — secondary to Today's Game Plan."""

    inject_global_styles(DECISION_CHANGE_HISTORY_CSS)
    ui_primitives.render_section_header("What Changed", weight="secondary")
    st.caption("How your decision picture changed.")

    if not events:
        render_html_fragment(
            "<div class='dg-what-changed-quiet' role='status'>"
            "<strong>No meaningful decision changes</strong>"
            "<span>No meaningful decision changes since your current session began.</span>"
            "</div>"
        )
        return

    for index, event in enumerate(events[: history.MAX_DASHBOARD_EVENTS]):
        age = history.age_label(event.timestamp)
        why_html = (
            f"<div class='dg-what-changed-why'>Why: {escape(event.why_label)}</div>"
            if event.why_label
            else ""
        )
        render_html_fragment(
            "<article class='dg-what-changed-item' "
            f"data-decision-event-id='{escape(event.event_id)}'>"
            f"<div class='dg-what-changed-meta'>{escape(event.summary_headline)} · {escape(age)}</div>"
            f"<div class='dg-what-changed-detail'>{escape(event.summary_detail)}</div>"
            f"{why_html}"
            "</article>"
        )
        if open_event is not None and history.destination_is_current(event):
            st.button(
                "Review →",
                key=f"{key_prefix}_open_{index}_{event.event_id[:16]}",
                use_container_width=True,
                on_click=open_event,
                args=(event,),
            )

    history_open_key = f"{key_prefix}_history_open"
    if st.button(
        "View decision history →",
        key=f"{key_prefix}_view_history",
        use_container_width=True,
    ):
        st.session_state[history_open_key] = True

    if st.session_state.get(history_open_key):
        _render_history_dialog(
            events=history.list_decision_events(
                st.session_state,
                league_id=events[0].league_id if events else "",
            )
            or events,
            open_event=open_event,
            key_prefix=key_prefix,
            close_key=history_open_key,
        )


def _render_history_dialog(
    *,
    events: tuple[history.DecisionChangeEvent, ...],
    open_event: Callable[[history.DecisionChangeEvent], None] | None,
    key_prefix: str,
    close_key: str,
) -> None:
    def _close() -> None:
        st.session_state[close_key] = False

    @st.dialog("Decision history", dismissible=True, on_dismiss=_close)
    def _dialog() -> None:
        inject_global_styles(DECISION_CHANGE_HISTORY_CSS)
        if not events:
            st.caption("No meaningful decision changes in this session.")
            st.button("Close", key=f"{key_prefix}_history_close_empty", on_click=_close)
            return

        current_group = ""
        for index, event in enumerate(events):
            group = _group_label(event.timestamp)
            if group != current_group:
                current_group = group
                st.caption(group)
            age = history.age_label(event.timestamp)
            why_html = (
                f"<div class='dg-what-changed-why'>Why: {escape(event.why_label)}</div>"
                if event.why_label
                else ""
            )
            render_html_fragment(
                "<article class='dg-what-changed-item' "
                f"data-decision-event-id='{escape(event.event_id)}'>"
                f"<div class='dg-what-changed-meta'>{escape(event.summary_headline)} · {escape(age)}</div>"
                f"<div class='dg-what-changed-headline'>{escape(event.target_label or event.category)}</div>"
                f"<div class='dg-what-changed-detail'>{escape(event.summary_detail)}</div>"
                f"{why_html}"
                "</article>"
            )
            if open_event is not None and history.destination_is_current(event):
                st.button(
                    "Open current context →",
                    key=f"{key_prefix}_hist_open_{index}_{event.event_id[:16]}",
                    use_container_width=True,
                    on_click=open_event,
                    args=(event,),
                )
        st.button(
            "Close history",
            key=f"{key_prefix}_history_close",
            use_container_width=True,
            on_click=_close,
        )

    _dialog()
