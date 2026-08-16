"""Presentation-only Dashboard briefing hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import streamlit as st

from modules import recommendation_lifecycle
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
POST_USEFUL_MOUNTED_KEY = "_dashboard_secondary_mounted"
POST_USEFUL_ARMED_KEY = "_dashboard_secondary_defer_armed"


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
    intelligence = recommendation_lifecycle.suppress_duplicate_intelligence(
        primary,
        intelligence,
    )
    additional = tuple(
        item
        for item in recommendations[1:]
        if str(item.get("label") or "") not in INTELLIGENCE_LABELS
    )
    additional = recommendation_lifecycle.dedupe_executive_items(
        additional,
        seen_ids={
            recommendation_lifecycle.item_recommendation_id(primary)
        }
        if primary is not None
        else set(),
    )
    return DashboardBriefing(
        immediate=immediate,
        primary=primary,
        additional=additional,
        intelligence=intelligence,
    )


def _log_dashboard_milestone(name: str) -> None:
    """Presentation milestones for #240 Python→browser boundary audit."""

    try:
        from modules import dashboard_visibility

        dashboard_visibility.log_python_render_milestone(
            st.session_state,
            name,
            once=True,
        )
    except Exception:
        pass


def render_dashboard_workflow(
    briefing: DashboardBriefing,
    *,
    snapshot_items: Sequence[Mapping],
    render_tiles: Callable[..., None],
    render_snapshot: Callable[[list[dict]], None],
    render_quick_actions: Callable[[list[tuple[str, str]]], None],
    render_league_pulse: Callable[[], None],
    render_orientation: Callable[[], None] | None = None,
    render_full_recommendations_lock: Callable[[], None] | None = None,
    render_league_pulse_lock: Callable[[], None] | None = None,
    render_todays_game_plan: Callable[[], None] | None = None,
    render_what_changed: Callable[[], None] | None = None,
    render_guest_continuity: Callable[[], None] | None = None,
    render_page_context: Callable[[], None] | None = None,
) -> None:
    """Render one executive briefing from precomputed inputs.

    When Today's Game Plan is present it owns current-action hierarchy
    (Top Priority + supporting plan items). Immediate Action / Your Next Move
    boards are omitted to prevent equal-weight duplicates. What Changed answers
    a different question (transitions). Supporting context stays collapsed.
    """

    with st.container(key="dashboard_workflow"):
        st.markdown(
            '<div class="dashboard-workflow-shell" aria-label="Dashboard executive briefing"></div>',
            unsafe_allow_html=True,
        )
        if render_page_context is not None:
            render_page_context()
        _log_dashboard_milestone("dashboard_header_complete")

        game_plan_present = render_todays_game_plan is not None
        if game_plan_present:
            render_todays_game_plan()
            if render_guest_continuity is not None:
                render_guest_continuity()

        def _render_post_useful_sections() -> None:
            if render_what_changed is not None:
                render_what_changed()

            if not game_plan_present:
                # Fallback board for paths that do not compose a Game Plan.
                ui_primitives.render_section_header("Immediate Action", weight="secondary")
                if briefing.immediate:
                    immediate_tiles = []
                    for index, item in enumerate(briefing.immediate):
                        tile = dict(item)
                        label = str(tile.get("label") or "").casefold()
                        if "injur" in label:
                            tile.setdefault("tone", "risk")
                        else:
                            tile.setdefault("tone", "need")
                        if index == 0:
                            tile["priority"] = "primary"
                        immediate_tiles.append(tile)
                    render_tiles(
                        immediate_tiles,
                        key_prefix="dashboard_immediate_action",
                    )
                else:
                    st.markdown(
                        '<div class="dashboard-clear-state" role="status">'
                        "<strong>No urgent action</strong>"
                        "<span>Your roster has no immediate limit or injury alert.</span>"
                        "</div>",
                        unsafe_allow_html=True,
                    )

                ui_primitives.render_section_header("Your Next Move", weight="primary")
                if briefing.primary is not None:
                    primary = dict(briefing.primary)
                    primary["wide"] = True
                    render_tiles([primary], key_prefix="dashboard_primary_move")
                elif briefing.immediate:
                    st.caption("Handle the urgent roster issue above first.")
                else:
                    st.caption("No new move to recommend right now.")

                if briefing.additional:
                    additional_tiles = [dict(item) for item in briefing.additional]
                    if len(additional_tiles) <= 2:
                        render_tiles(
                            additional_tiles,
                            key_prefix="dashboard_additional_moves",
                        )
                    else:
                        count = len(additional_tiles)
                        with st.expander(
                            f"View {count} more recommendations",
                            expanded=False,
                        ):
                            render_tiles(
                                additional_tiles,
                                key_prefix="dashboard_additional_moves",
                            )

            if render_full_recommendations_lock is not None:
                render_full_recommendations_lock()

            with st.container(key="dashboard_context_pair"):
                insight_col, snapshot_col = st.columns(2, gap="large")
                insight_count = len(briefing.intelligence)
                snapshot_count = len(snapshot_items)
                with insight_col:
                    with st.expander("League Insights", expanded=False):
                        st.caption(
                            "Market and league signals that may change your next move. "
                            "Uses already-computed tiles — not a new analysis pass."
                            + (
                                f" {insight_count} signal"
                                + ("s" if insight_count != 1 else "")
                                + " ready."
                                if insight_count
                                else " No extra market signal beyond Game Plan."
                            )
                        )
                        if briefing.intelligence:
                            render_tiles(
                                [dict(item) for item in briefing.intelligence],
                                key_prefix="dashboard_intelligence",
                            )
                        else:
                            st.caption(
                                "No separate market signal is stronger than your current Game Plan."
                            )
                with snapshot_col:
                    with st.expander("Team Snapshot", expanded=False):
                        st.caption(
                            "Record, health, and construction at a glance."
                            + (
                                f" {snapshot_count} snapshot tiles."
                                if snapshot_count
                                else ""
                            )
                        )
                        render_snapshot([dict(item) for item in snapshot_items])
            _log_dashboard_milestone("dashboard_summary_tiles_complete")

            if render_orientation is not None:
                render_orientation()

            ui_primitives.render_section_header(
                "Explore",
                weight="support",
                subtitle="Deeper tools when a recommendation isn't enough.",
            )
            render_quick_actions(
                [
                    ("League Overview", "rankings"),
                    ("My Team", "my_team"),
                    ("Trade Hub", "trade_hub"),
                    ("Draft Center", "draft_summary"),
                ]
            )
            _log_dashboard_milestone("dashboard_deep_analysis_complete")
            with st.expander("League Pulse and supporting trends", expanded=False):
                if render_league_pulse_lock is not None:
                    render_league_pulse_lock()
                else:
                    render_league_pulse()

        # Secondary Dashboard sections stay in this same script run as Game Plan.
        # A 250ms repeating fragment after first useful marked the rest of the
        # app stale (full-page gray/dim on iPhone). Do not reintroduce that timer.
        st.session_state[POST_USEFUL_MOUNTED_KEY] = True
        st.session_state.pop(POST_USEFUL_ARMED_KEY, None)
        st.session_state.pop("_dashboard_defer_secondary_once", None)
        try:
            from modules import hot_path_profile as _hot_path
        except Exception:
            _hot_path = None
        if _hot_path is not None:
            with _hot_path.span(
                "dashboard_post_useful_sections",
                mandatory_before_useful=False,
                kind="render",
                session_state=st.session_state,
            ):
                _render_post_useful_sections()
        else:
            _render_post_useful_sections()
