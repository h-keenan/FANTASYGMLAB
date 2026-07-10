from typing import Callable

import pandas as pd
import streamlit as st


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def render_weekly_report(
    weekly_report: dict,
    movement: dict,
    *,
    format_rank: Callable,
    render_section_header: Callable,
    render_summary_tiles: Callable,
    render_analysis_cards: Callable,
) -> None:
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
        st.info("No completed matchup week is available yet for weekly score highlights.")

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
                },
                {
                    "label": "Biggest Power Faller",
                    "value": _safe_text(power_faller.get("team_name"), "No movement"),
                    "note": (
                        f"{int(power_faller.get('power_delta') or 0)} spots | "
                        f"{format_rank(power_faller.get('power_before'))} to {format_rank(power_faller.get('power_after'))}"
                    ),
                    "tone": "risk",
                },
                {
                    "label": "Biggest Franchise Riser",
                    "value": _safe_text(franchise_riser.get("team_name"), "No movement"),
                    "note": (
                        f"+{int(franchise_riser.get('franchise_delta') or 0)} spots | "
                        f"{format_rank(franchise_riser.get('franchise_before'))} to {format_rank(franchise_riser.get('franchise_after'))}"
                    ),
                    "tone": "franchise",
                },
                {
                    "label": "Biggest Franchise Faller",
                    "value": _safe_text(franchise_faller.get("team_name"), "No movement"),
                    "note": (
                        f"{int(franchise_faller.get('franchise_delta') or 0)} spots | "
                        f"{format_rank(franchise_faller.get('franchise_before'))} to {format_rank(franchise_faller.get('franchise_after'))}"
                    ),
                    "tone": "risk",
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
        st.info(_safe_text(movement.get("note")))

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
        st.info("No completed weekly transactions were returned for the current report window.")

    render_section_header(
        "Team Notes",
        kicker="Storylines",
        note="Logic-based notes built from strategy, team needs, strength profiles, draft capital, injuries, and current rank context.",
        compact=True,
    )
    if weekly_report.get("team_note_cards"):
        render_analysis_cards(weekly_report.get("team_note_cards") or [])
    else:
        st.info("No standout team notes were generated from the current league state.")
