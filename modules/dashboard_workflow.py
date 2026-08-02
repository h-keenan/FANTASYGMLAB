"""Presentation-only Dashboard briefing hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import streamlit as st

from modules import ui_primitives


INTELLIGENCE_LABELS = frozenset(
    {"Top Trade Opportunity", "Top Waiver Opportunity"}
)
STATUS_ONLY_LABELS = frozenset(
    {
        "Roster Pressure",
        "Injury Alert",
        "Roster Quality",
        "Lineup Construction",
        "Startup Observation",
    }
)


@dataclass(frozen=True)
class DashboardBriefing:
    immediate: tuple[Mapping, ...]
    primary: Mapping | None
    additional: tuple[Mapping, ...]
    intelligence: tuple[Mapping, ...]


def organize_dashboard_items(
    items: Sequence[Mapping],
    *,
    immediate_labels: frozenset[str] = frozenset(),
) -> DashboardBriefing:
    """Assign existing recommendation items to presentation zones only."""

    normalized = tuple(items)
    immediate = tuple(
        item for item in normalized if str(item.get("label") or "") in immediate_labels
    )
    remaining = tuple(
        item
        for item in normalized
        if str(item.get("label") or "") not in immediate_labels
    )
    recommendations = tuple(
        item
        for item in remaining
        if str(item.get("label") or "") not in STATUS_ONLY_LABELS
    )
    primary = recommendations[0] if recommendations else None
    intelligence = tuple(
        item
        for item in recommendations[1:]
        if str(item.get("label") or "") in INTELLIGENCE_LABELS
    )
    additional = tuple(
        item
        for item in recommendations[1:]
        if str(item.get("label") or "") not in INTELLIGENCE_LABELS
    )
    return DashboardBriefing(
        immediate=immediate,
        primary=primary,
        additional=additional,
        intelligence=intelligence,
    )


def render_dashboard_workflow(
    briefing: DashboardBriefing,
    *,
    snapshot_items: Sequence[Mapping],
    render_tiles: Callable[[list[dict]], None],
    render_snapshot: Callable[[list[dict]], None],
    render_quick_actions: Callable[[list[tuple[str, str]]], None],
    render_league_pulse: Callable[[], None],
    render_orientation: Callable[[], None] | None = None,
    render_full_recommendations_lock: Callable[[], None] | None = None,
    render_league_pulse_lock: Callable[[], None] | None = None,
) -> None:
    """Render one five-zone executive briefing from precomputed inputs."""

    with st.container(key="dashboard_workflow"):
        st.markdown(
            '<div class="dashboard-workflow-shell" aria-label="Dashboard executive briefing"></div>',
            unsafe_allow_html=True,
        )

        ui_primitives.render_section_header(
            "Immediate Action",
            eyebrow="Needs Attention",
            subtitle="Only issues that require a decision now.",
        )
        if briefing.immediate:
            render_tiles([dict(item) for item in briefing.immediate])
        else:
            st.markdown(
                '<div class="dashboard-clear-state" role="status">'
                '<strong>No urgent action</strong><span>Your roster has no immediate limit or injury alert.</span>'
                "</div>",
                unsafe_allow_html=True,
            )

        ui_primitives.render_section_header(
            "Your Next Move",
            eyebrow="Recommended",
            subtitle="The highest-priority non-urgent recommendation for this franchise.",
        )
        if briefing.primary is not None:
            primary = dict(briefing.primary)
            primary["wide"] = True
            render_tiles([primary])
        elif briefing.immediate:
            st.caption("Resolve the urgent action above before opening another workflow.")
        else:
            st.caption("No additional recommendation is available right now.")

        if briefing.additional:
            count = len(briefing.additional)
            with st.expander(
                f"View {count} more recommendation{'s' if count != 1 else ''} →",
                expanded=False,
            ):
                render_tiles([dict(item) for item in briefing.additional])
        if render_full_recommendations_lock is not None:
            render_full_recommendations_lock()

        ui_primitives.render_section_header(
            "Team Snapshot",
            eyebrow="Franchise Health",
            subtitle="The compact operating read for this roster.",
        )
        render_snapshot([dict(item) for item in snapshot_items])

        if render_orientation is not None:
            render_orientation()

        ui_primitives.render_section_header(
            "League Intelligence",
            eyebrow="Market Watch",
            subtitle="Trade and waiver signals worth monitoring now.",
        )
        if briefing.intelligence:
            render_tiles([dict(item) for item in briefing.intelligence])
        else:
            st.caption("No separate market signal is stronger than your current next move.")

        ui_primitives.render_section_header(
            "Deep Analysis",
            eyebrow="When You Need Context",
            subtitle="League-wide detail stays available without competing with today's decision.",
        )
        render_quick_actions(
            [
                ("League Overview", "rankings"),
                ("My Team", "my_team"),
                ("Trade Hub", "trade_hub"),
                ("Draft Center", "draft_summary"),
            ]
        )
        with st.expander("League Pulse and supporting trends", expanded=False):
            if render_league_pulse_lock is not None:
                render_league_pulse_lock()
            else:
                render_league_pulse()
