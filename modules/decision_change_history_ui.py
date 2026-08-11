"""Streamlit presentation for What Changed + Decision Memory."""

from __future__ import annotations

from html import escape
from time import time as _time
from typing import Callable

import streamlit as st

from modules import decision_change_history as history
from modules import decision_memory
from modules import premium
from modules import ui_primitives
from modules.html_rendering import inject_global_styles, render_html_fragment


# Quiet empty + CTA chrome only — row geometry owned by dense_list_styles.
DECISION_CHANGE_HISTORY_CSS = """
<style>
.dg-what-changed-quiet{align-items:baseline;display:flex;flex-direction:column}
.dg-what-changed-quiet strong{color:var(--color-text-muted);font:var(--font-card-title)}
.dg-what-changed-quiet span{color:var(--color-text-secondary);font:var(--font-body);max-width:40rem}
.dg-decision-memory-shell{display:flex;flex-direction:column;gap:var(--space-sm);max-width:36rem}
.dg-decision-history-cta{margin-block-start:var(--space-2xs);max-width:16rem}
.dg-decision-history-board{display:grid;gap:var(--space-xs);margin:0 0 var(--space-sm)}
@media (max-width:430px){.dg-decision-history-cta{max-width:none}}
</style>
"""


def _lifecycle_state_label(transition: str) -> str:
    text = " ".join(str(transition or "").split())
    if not text:
        return ""
    if "->" in text:
        return text.split("->", 1)[-1].strip().replace("_", " ").title()
    return text.replace("_", " ").title()


def decision_event_row_html(
    event: history.DecisionChangeEvent,
    *,
    include_detail: bool = True,
    rich: bool = False,
) -> str:
    """Canonical dense row for What Changed / Decision Memory events."""

    from modules import dense_list_primitives

    age = history.age_label(event.timestamp)
    identity_primary = event.target_label or event.category or event.summary_headline or "Decision"
    identity_secondary = event.summary_headline if event.target_label else event.category
    identity = dense_list_primitives.dense_identity_html(
        primary=identity_primary,
        secondary=identity_secondary if identity_secondary != identity_primary else "",
    )
    state_label = _lifecycle_state_label(event.lifecycle_transition) or event.summary_headline
    # Keep metric slot compact — long headlines belong in identity/meta.
    if len(state_label) > 14:
        state_label = state_label.split()[0][:14]
    metric = dense_list_primitives.dense_metric_html(
        state_label or "Updated",
        "State",
        compact_label=False,
    )
    status = dense_list_primitives.dense_status_html(
        (event.current_confidence_band or "").title() + (" confidence" if event.current_confidence_band else ""),
        event.category,
    )
    meta_parts = [age]
    if event.scoring_format:
        meta_parts.append(event.scoring_format)
    if include_detail and event.summary_detail:
        # Keep one short detail line in meta; do not render giant cards.
        detail = " ".join(str(event.summary_detail).split())
        if len(detail) > 96:
            detail = detail[:93].rstrip() + "…"
        meta_parts.append(detail)
    meta = dense_list_primitives.dense_meta_html(*meta_parts)
    exception = ""
    state_cf = (state_label or "").casefold()
    if any(token in state_cf for token in ("stale", "superseded", "resolved", "conflict")):
        exception = dense_list_primitives.dense_exception_html(
            event.why_label or state_label,
            label="Lifecycle",
        )
    elif event.why_label and rich:
        # Why stays supporting meta unless lifecycle is exceptional.
        meta = dense_list_primitives.dense_meta_html(*meta_parts, f"Why: {event.why_label}")
    elif event.why_label:
        meta = dense_list_primitives.dense_meta_html(*meta_parts, f"Why: {event.why_label}")
    trail = dense_list_primitives.dense_trail_html(
        status_html=status,
        meta_html=meta,
        exception_html=exception,
    )
    return dense_list_primitives.dense_row_html(
        identity_html=identity,
        metric_html=metric,
        trail_html=trail,
        density="compact",
        extra_classes=["dg-what-changed-item", "dg-ui-card"],
        attrs=f"data-decision-event-id='{escape(event.event_id)}'",
        no_lead=True,
    )


def _group_label(timestamp: float, *, now: float | None = None) -> str:
    current = float(now if now is not None else _time())
    age = current - float(timestamp)
    if age < 86400:
        return "Today"
    if age < 7 * 86400:
        return "Earlier this week"
    return "Earlier"


def _open_flag(key: str) -> None:
    st.session_state[key] = True


def _close_flag(key: str) -> None:
    st.session_state[key] = False


def render_what_changed_section(
    events: tuple[history.DecisionChangeEvent, ...],
    *,
    open_event: Callable[[history.DecisionChangeEvent], None] | None = None,
    key_prefix: str = "what_changed",
    league_id: str = "",
    render_premium_lock: Callable[..., None] | None = None,
) -> None:
    """Compact Dashboard section — secondary to Today's Game Plan."""

    inject_global_styles(DECISION_CHANGE_HISTORY_CSS)
    ui_primitives.render_section_header("What Changed", weight="secondary")
    st.caption("How your priorities, opportunities, and roster decisions have changed.")

    experiment_on = decision_memory.experiment_enabled()
    premium_access = decision_memory.can_access_history(st.session_state)
    show_discovery = (
        experiment_on
        and decision_memory.can_show_discovery(st.session_state)
        and not premium_access
    )

    # Free users always keep session What Changed value. Decision Memory discovery
    # is a restrained teaser afterward — never replace Free history with a paywall.
    if not events:
        quiet_title, quiet_body = (
            ("No meaningful changes", "No meaningful changes since your last check.")
            if premium_access
            else (
                "No meaningful decision changes",
                "No meaningful decision changes since your current session began.",
            )
        )
        render_html_fragment(
            "<div class='dg-what-changed-quiet' role='status'>"
            f"<strong>{escape(quiet_title)}</strong>"
            f"<span>{escape(quiet_body)}</span>"
            "</div>"
        )
    else:
        for index, event in enumerate(events[: history.MAX_DASHBOARD_EVENTS]):
            render_html_fragment(decision_event_row_html(event, include_detail=True))
            if open_event is not None and history.destination_is_current(event):
                st.markdown("<div class='dg-decision-history-cta'>", unsafe_allow_html=True)
                st.button(
                    "Review →",
                    key=f"{key_prefix}_open_{index}_{event.event_id[:16]}",
                    use_container_width=True,
                    on_click=open_event,
                    args=(event,),
                )
                st.markdown("</div>", unsafe_allow_html=True)

    if show_discovery:
        _render_decision_memory_discovery(
            key_prefix=key_prefix,
            render_premium_lock=render_premium_lock,
        )
        return

    if experiment_on and premium_access:
        _render_memory_entry(
            key_prefix=key_prefix,
            league_id=league_id,
            open_event=open_event,
        )
        return

    history_open_key = f"{key_prefix}_history_open"
    st.button(
        "View decision history →",
        key=f"{key_prefix}_view_history",
        use_container_width=False,
        on_click=_open_flag,
        args=(history_open_key,),
    )

    if st.session_state.get(history_open_key):
        _render_history_dialog(
            events=history.list_decision_events(
                st.session_state,
                league_id=league_id or (events[0].league_id if events else ""),
            )
            or events,
            open_event=open_event,
            key_prefix=key_prefix,
            close_key=history_open_key,
            experimental=False,
        )


def _render_decision_memory_discovery(
    *,
    key_prefix: str,
    render_premium_lock: Callable[..., None] | None = None,
) -> None:
    """Single restrained Free teaser — not a second Dashboard paywall wall."""

    title, body = decision_memory.empty_state_copy(
        has_baseline=False, premium_access=False
    )
    render_html_fragment(
        "<div class='dg-what-changed-quiet' role='status' "
        f"data-decision-memory-discovery='1'>"
        f"<strong>{escape(title)}</strong>"
        f"<span>{escape(body)}</span>"
        "</div>"
    )
    discovery_title = 'Decision Memory'
    discovery_body = (
        "See how your GM priorities evolve across sessions after you leave and come back. "
        "Premium keeps durable history beyond this session."
    )
    if render_premium_lock is not None:
        render_premium_lock(discovery_title, discovery_body, feature='Decision Memory')
    else:
        premium.render_premium_lock(
            discovery_title,
            discovery_body,
            feature='Decision Memory',
        )


def _render_memory_entry(
    *,
    key_prefix: str,
    league_id: str,
    open_event: Callable[[history.DecisionChangeEvent], None] | None,
) -> None:
    memory_open_key = f"{key_prefix}_memory_open"
    # Tertiary CTA key aligns Decision Memory entry with dg_cta_tertiary_* polish.
    with st.container(key=f"dg_cta_tertiary_{key_prefix}_view_memory"):
        st.button(
            "View Decision Memory →",
            key=f"{key_prefix}_view_memory",
            use_container_width=False,
            on_click=_open_flag,
            args=(memory_open_key,),
        )
    if st.session_state.get(memory_open_key):
        events = decision_memory.merged_history_events(
            st.session_state,
            league_id=league_id,
        )
        _render_history_dialog(
            events=events,
            open_event=open_event,
            key_prefix=f"{key_prefix}_memory",
            close_key=memory_open_key,
            experimental=True,
        )


def _render_history_dialog(
    *,
    events: tuple[history.DecisionChangeEvent, ...],
    open_event: Callable[[history.DecisionChangeEvent], None] | None,
    key_prefix: str,
    close_key: str,
    experimental: bool = False,
) -> None:
    def _close() -> None:
        _close_flag(close_key)

    def _open_current(event: history.DecisionChangeEvent) -> None:
        # Close first so the dialog does not remount over the destination.
        _close_flag(close_key)
        if open_event is not None:
            open_event(event)

    title = "Decision Memory" if experimental else "Decision history"

    @st.dialog(title, dismissible=True, on_dismiss=_close)
    def _dialog() -> None:
        inject_global_styles(DECISION_CHANGE_HISTORY_CSS)
        if experimental:
            render_html_fragment(
                "<div class='dg-decision-memory-shell'>"
                "<p class='dg-dense-meta'>"
                "See how your priorities, opportunities, and roster decisions "
                "have changed over time."
                "</p></div>"
            )
        if not events:
            if experimental:
                title_text, body = decision_memory.empty_state_copy(
                    has_baseline=bool(
                        st.session_state.get(
                            history.DECISION_HISTORY_PRIOR_SNAPSHOT_KEY
                        )
                    ),
                    premium_access=True,
                )
                st.caption(title_text)
                st.write(body)
            else:
                st.caption("No meaningful decision changes in this session.")
            st.button("Close", key=f"{key_prefix}_history_close_empty", on_click=_close)
            return

        current_group = ""
        for index, event in enumerate(events):
            group = _group_label(event.timestamp)
            if group != current_group:
                current_group = group
                st.caption(group)
            render_html_fragment(
                decision_event_row_html(event, include_detail=True, rich=True)
            )
            if open_event is not None and history.destination_is_current(event):
                label = (
                    decision_memory.cta_label_for_event(event)
                    if experimental
                    else "Open current context →"
                )
                st.markdown("<div class='dg-decision-history-cta'>", unsafe_allow_html=True)
                st.button(
                    label,
                    key=f"{key_prefix}_hist_open_{index}_{event.event_id[:16]}",
                    use_container_width=True,
                    on_click=_open_current,
                    args=(event,),
                )
                st.markdown("</div>", unsafe_allow_html=True)
        st.button(
            "Close",
            key=f"{key_prefix}_history_close",
            use_container_width=False,
            on_click=_close,
        )

    _dialog()
