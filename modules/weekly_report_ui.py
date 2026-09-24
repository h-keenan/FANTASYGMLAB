from typing import Callable

import pandas as pd
import streamlit as st

from modules import ui_primitives
from modules.html_rendering import inject_global_styles
from modules.weekly_report_styles import WEEKLY_REPORT_CSS


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def _movement_direction_badge_html(delta: object) -> str:
    """Small colored up/down/flat glyph for one rank-movement tile.

    The tile's own tone identifies *which metric* moved (power/franchise) and
    a fall already resolves to the shared risk/danger tone, but a rise
    resolves to that same category tone rather than a positive one, so
    "Biggest Power Riser" and "Biggest Power Faller" read with no consistent
    up=positive/down=negative signal between them. This adds that signal
    through the tile's existing "graphic" slot (see workspace_ui.summary_tiles_html)
    without touching the shared tile tone classes any other surface relies on.
    """

    try:
        value = int(delta or 0)
    except (TypeError, ValueError):
        value = 0
    if value > 0:
        direction, arrow = "up", "&#9650;"
    elif value < 0:
        direction, arrow = "down", "&#9660;"
    else:
        direction, arrow = "flat", "&#8212;"
    return (
        f"<span class='wr-move-badge wr-move-badge--{direction}' aria-hidden='true'>"
        f"<span class='wr-move-badge__arrow'>{arrow}</span></span>"
    )


def render_weekly_report(
    weekly_report: dict,
    movement: dict,
    *,
    format_rank: Callable,
    render_section_header: Callable,
    render_summary_tiles: Callable,
    render_analysis_cards: Callable,
) -> None:
    inject_global_styles(WEEKLY_REPORT_CSS)
    st.caption(
        f"Report week: {_safe_text(weekly_report.get('report_label'), 'No completed week yet')}. "
        "The page refreshes off the same cached league data used by the rest of the app."
    )
    if not weekly_report.get("matchup_history_available"):
        st.info("Sleeper matchup history did not return completed weekly scores yet. Transaction and team-context sections will still render when possible.")

    render_section_header(
        "Weekly Highlights",
        kicker="Scoreboard",
        note="The clearest results from the latest week with matchup data.",
        compact=True,
    )
    if weekly_report.get("highlights"):
        render_summary_tiles(weekly_report.get("highlights") or [])
    else:
        ui_primitives.render_empty_state_panel(
            "No weekly score highlights yet",
            "No completed matchup week is available yet for weekly score highlights.",
            kind="no-data",
            recovery_guidance="Check back after this week's matchups finish.",
        )

    render_section_header(
        "Power Movement",
        kicker="Rank Drift",
        note="Power Rank tracks current strength. Franchise Rank tracks total asset base. Exact week-over-week movement starts once the app has saved at least one earlier weekly snapshot.",
        compact=True,
    )
    if movement.get("available"):
        power_riser = movement.get("power_riser") or {}
        power_faller = movement.get("power_faller") or {}
        franchise_riser = movement.get("franchise_riser") or {}
        franchise_faller = movement.get("franchise_faller") or {}
        render_summary_tiles(
            [
                {
                    "label": "Biggest Power Riser",
                    "value": _safe_text(power_riser.get("team_name"), "No movement"),
                    "note": (
                        f"+{int(power_riser.get('power_delta') or 0)} spots | "
                        f"{format_rank(power_riser.get('power_before'))} to {format_rank(power_riser.get('power_after'))}"
                    ),
                    "tone": "power",
                    "graphic": _movement_direction_badge_html(power_riser.get("power_delta")),
                },
                {
                    "label": "Biggest Power Faller",
                    "value": _safe_text(power_faller.get("team_name"), "No movement"),
                    "note": (
                        f"{int(power_faller.get('power_delta') or 0)} spots | "
                        f"{format_rank(power_faller.get('power_before'))} to {format_rank(power_faller.get('power_after'))}"
                    ),
                    "tone": "risk",
                    "graphic": _movement_direction_badge_html(power_faller.get("power_delta")),
                },
                {
                    "label": "Biggest Franchise Riser",
                    "value": _safe_text(franchise_riser.get("team_name"), "No movement"),
                    "note": (
                        f"+{int(franchise_riser.get('franchise_delta') or 0)} spots | "
                        f"{format_rank(franchise_riser.get('franchise_before'))} to {format_rank(franchise_riser.get('franchise_after'))}"
                    ),
                    "tone": "franchise",
                    "graphic": _movement_direction_badge_html(franchise_riser.get("franchise_delta")),
                },
                {
                    "label": "Biggest Franchise Faller",
                    "value": _safe_text(franchise_faller.get("team_name"), "No movement"),
                    "note": (
                        f"{int(franchise_faller.get('franchise_delta') or 0)} spots | "
                        f"{format_rank(franchise_faller.get('franchise_before'))} to {format_rank(franchise_faller.get('franchise_after'))}"
                    ),
                    "tone": "risk",
                    "graphic": _movement_direction_badge_html(franchise_faller.get("franchise_delta")),
                },
            ]
        )
        st.caption(_safe_text(movement.get("note")))
        with st.expander("Detailed rank movement", expanded=False):
            movement_rows = movement.get("rows") or []
            if movement_rows:
                st.dataframe(
                    pd.DataFrame(movement_rows)
                    .rename(
                        columns={
                            "team_name": "Team",
                            "power_before": "Power Before",
                            "power_after": "Power After",
                            "power_delta": "Power Change",
                            "franchise_before": "Franchise Before",
                            "franchise_after": "Franchise After",
                            "franchise_delta": "Franchise Change",
                        }
                    )
                    .reset_index(drop=True),
                    width="stretch",
                    hide_index=True,
                )
    else:
        ui_primitives.render_empty_state_panel(
            "No rank movement yet",
            _safe_text(movement.get("note"), "Rank movement is not available yet."),
            kind="no-data",
            recovery_guidance="Movement appears automatically once the app has saved a second weekly snapshot.",
        )

    render_section_header(
        "League Trends",
        kicker="Momentum",
        note="Recent streaks and current temperature, using weekly results where Sleeper exposes them.",
        compact=True,
    )
    render_analysis_cards(weekly_report.get("trend_cards") or [])

    render_section_header(
        "Manager Activity",
        kicker="Moves",
        note="Season-to-date transaction volume through the report week.",
        compact=True,
    )
    render_summary_tiles(weekly_report.get("activity_tiles") or [])

    render_section_header(
        "Transaction Summary",
        kicker="This Week's Moves",
        note="Completed trades, priority waiver adds, and the heaviest roster churn from the report week.",
        compact=True,
    )
    transaction_cards = []
    transaction_cards.extend(weekly_report.get("trade_cards") or [])
    transaction_cards.extend(weekly_report.get("waiver_cards") or [])
    transaction_cards.extend(weekly_report.get("move_cards") or [])
    if transaction_cards:
        render_analysis_cards(transaction_cards)
    else:
        ui_primitives.render_empty_state_panel(
            "No transactions yet",
            "No completed weekly transactions were returned for the current report window.",
            kind="no-data",
            recovery_guidance="Check back once trades, waiver adds, or roster moves are completed for the report week.",
        )

    render_section_header(
        "Team Notes",
        kicker="Storylines",
        note="Logic-based notes built from strategy, team needs, strength profiles, draft capital, injuries, and current rank context.",
        compact=True,
    )
    if weekly_report.get("team_note_cards"):
        render_analysis_cards(weekly_report.get("team_note_cards") or [])
    else:
        ui_primitives.render_empty_state_panel(
            "No standout team notes yet",
            "No standout team notes were generated from the current league state.",
            kind="no-data",
            recovery_guidance="Notes regenerate automatically as strategy, needs, and rank context change.",
        )
