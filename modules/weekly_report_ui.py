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


# Plain-language "what this means" text for tiles whose label alone doesn't
# make the metric obvious, keyed by the tile's own label (casefolded). Wired
# through render_summary_tiles' existing detail/supporting_context fields —
# the same tap-to-detail affordance tests/test_workspace_ui.py already
# exercises for a non-comparison "detail" tile — so no new component or
# navigation is introduced, only an explanation of an already-rendered tile.
# Presentation only: never changes a tile's label/value/note/tone.
_HIGHLIGHT_TILE_CONTEXT: dict[str, tuple[str, str]] = {
    "highest score": (
        "The team that scored the most fantasy points among this week's completed matchups.",
        "",
    ),
    "lowest score": (
        "The team that scored the fewest fantasy points among this week's completed matchups.",
        "Check Team Notes below for injury or lineup context behind a quiet week.",
    ),
    "closest matchup": (
        "The week's matchup decided by the smallest point margin.",
        "",
    ),
    "largest blowout": (
        "The week's matchup decided by the largest point margin.",
        "",
    ),
    "biggest upset": (
        "The winning team was ranked lower in Power Rank than the team it beat this week.",
        "See Power Movement above for how this result may have shifted both teams' rank.",
    ),
    "team of the week": (
        "This week's single highest scorer — the same team as Highest Score above, using "
        "the app's own rank tiebreak. The two tiles will usually agree.",
        "",
    ),
    "disappointment": (
        "A team ranked well in Power Rank that scored well below its usual output this week.",
        "Check Team Notes below for what might be driving the dip.",
    ),
    "most active manager": (
        "The team with the most total completed transactions — trades plus waiver/free-agent "
        "claims — so far this season.",
        "",
    ),
    "most waiver moves": (
        "The team with the most completed waiver and free-agent claims so far this season.",
        "",
    ),
    "most trades": (
        "The team involved in the most completed trades so far this season.",
        "",
    ),
    "most roster churn": (
        "The team with the most total roster adds and drops combined so far this season.",
        "",
    ),
}

# Short next-step pointer appended to a League Trends card's own bullet list
# when the card has a real signal to point at (not a "no data yet" placeholder).
_TREND_TILE_FOLLOWUP: dict[str, str] = {
    "hottest team": "See Team Notes below for the roster story behind the streak.",
    "coldest team": "See Team Notes below for what might be behind the skid.",
}
_TREND_NO_SIGNAL_TITLES = {"", "No clear leader", "No clear skid"}


def _with_tile_context(items: list[dict]) -> list[dict]:
    """Attach a "what this means" explanation to tiles that don't already
    carry one, matched by the tile's own label. Every other field is passed
    through unchanged."""

    enriched: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        context = _HIGHLIGHT_TILE_CONTEXT.get(_safe_text(item.get("label")).strip().casefold())
        if context and not item.get("detail"):
            detail, supporting = context
            item["detail"] = detail
            if supporting and not item.get("supporting_context"):
                item["supporting_context"] = supporting
        enriched.append(item)
    return enriched


def _with_trend_followup(cards: list[dict]) -> list[dict]:
    """Append an on-page next-step bullet to a trend card that has a real
    signal to point at. Every other field is passed through unchanged."""

    enriched: list[dict] = []
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        card = dict(card)
        followup = _TREND_TILE_FOLLOWUP.get(_safe_text(card.get("label")).strip().casefold())
        if followup and _safe_text(card.get("title")) not in _TREND_NO_SIGNAL_TITLES:
            items = list(card.get("items") or [])
            if followup not in items:
                card["items"] = items + [followup]
        enriched.append(card)
    return enriched


def _movement_tile_context(*, scope: str, rising: bool) -> tuple[str, str]:
    """"What this means" + "what to check next" text for one Power/Franchise
    movement tile. ``scope`` is "power" or "franchise"."""

    if scope == "power":
        what = (
            "Power Rank is the app's read on which teams are currently strongest — "
            "who you'd expect to win on the field right now."
        )
    else:
        what = (
            "Franchise Rank is the app's read on total asset base — roster plus draft "
            "capital value — independent of this week's score."
        )
    direction = "climbed" if rising else "dropped"
    detail = f"{what} This team {direction} the most of anyone in the league this week."
    supporting = "See Transaction Summary and Team Notes below for what may be behind the move."
    return detail, supporting


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
        note="The clearest results from the latest week with matchup data. Tap a tile for what it means.",
        compact=True,
    )
    if weekly_report.get("highlights"):
        render_summary_tiles(_with_tile_context(weekly_report.get("highlights") or []))
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
        note=(
            "Power Rank tracks current strength. Franchise Rank tracks total asset base. Exact "
            "week-over-week movement starts once the app has saved at least one earlier weekly "
            "snapshot. Tap a tile for what moved and why."
        ),
        compact=True,
    )
    if movement.get("available"):
        power_riser = movement.get("power_riser") or {}
        power_faller = movement.get("power_faller") or {}
        franchise_riser = movement.get("franchise_riser") or {}
        franchise_faller = movement.get("franchise_faller") or {}
        power_rise_detail, power_rise_context = _movement_tile_context(scope="power", rising=True)
        power_fall_detail, power_fall_context = _movement_tile_context(scope="power", rising=False)
        franchise_rise_detail, franchise_rise_context = _movement_tile_context(scope="franchise", rising=True)
        franchise_fall_detail, franchise_fall_context = _movement_tile_context(scope="franchise", rising=False)
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
                    "detail": power_rise_detail,
                    "supporting_context": power_rise_context,
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
                    "detail": power_fall_detail,
                    "supporting_context": power_fall_context,
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
                    "detail": franchise_rise_detail,
                    "supporting_context": franchise_rise_context,
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
                    "detail": franchise_fall_detail,
                    "supporting_context": franchise_fall_context,
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
    render_analysis_cards(_with_trend_followup(weekly_report.get("trend_cards") or []))

    # Transaction Summary (this report week's specific moves) is rendered
    # ahead of Manager Activity (season-to-date totals): this page is a
    # per-week report, so the week-specific "what happened" belongs before
    # the cumulative reference leaderboard it contextualizes, per the
    # decision-importance hierarchy rule — not backend build order. See
    # tests/test_weekly_report_ui.py for the characterization test updated
    # alongside this reorder.
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
        "Manager Activity",
        kicker="Moves",
        note="Season-to-date context for the moves above. Tap a tile for what it counts.",
        compact=True,
    )
    render_summary_tiles(_with_tile_context(weekly_report.get("activity_tiles") or []))

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
