"""Streamlit presentation for GM Plan — a season-arc roadmap layer.

Standalone page (not embedded in Dashboard or My Team), matching mobile's
GmPlanScreen.tsx information architecture: a phase/stance hero, then three
focus-area sections (Where You Stand, Trade Opportunities, Roster
Construction).

This module assembles the ALREADY-COMPUTED signals modules.gm_plan.build_gm_plan
needs the same way services/mobile_api_service.py's get_gm_plan does for
mobile (modules.league_rankings for power/draft-capital/roster-construction
ranks, modules.trade_hub_engine for Trust-enforced trade ideas,
modules.playoff_simulator for the cached Monte Carlo playoff odds,
modules.trade_analyzer_fit for injury exposure) — just with web's
session/profile-based Team Situation, GM Targets, and team-strategy
plumbing instead of mobile's Supabase-backed equivalents. No new valuation
math lives here; modules.gm_plan itself does only pure aggregation/framing.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import pandas as pd
import streamlit as st

from modules import gm_plan
from modules import gm_targets
from modules import league_rankings
from modules import playoff_simulator
from modules import team_eval as team_eval_module
from modules import team_stance
from modules import trade_analyzer_fit
from modules import trade_hub_engine
from modules import ui_primitives
from modules.league_value_settings import VALUATION_LENS_TO_SCORE_FIELD
from modules.sleeper import get_league, get_rosters

_LENS_FOR_SCORE_FIELD: dict[str, str] = {
    score_field: lens for lens, score_field in VALUATION_LENS_TO_SCORE_FIELD.items()
}


def _lens_for_score_field(score_field: str) -> str:
    """The valuation lens whose score_field matches the app's active one.

    Reuses the app's already-active valuation lens rather than adding a new
    lens selector to this page — additive exposure, not new product surface.
    """

    return _LENS_FOR_SCORE_FIELD.get(str(score_field or "").strip(), "Dynasty")


# --- Per-item-type presentation (mirrors GmPlanScreen.tsx's FocusAreaSection
# type-discrimination switch — same fields, same honest "no signal" framing,
# just Streamlit cards instead of InsightRow). ----------------------------


def _rank_item_text(item: dict[str, Any]) -> tuple[str, str, bool]:
    tie_note = " (tied)" if item.get("tied") else ""
    total = item.get("total_teams")
    headline = f"{item.get('label')}: {item.get('rank')}"
    if total:
        headline += f" of {total}"
    headline += tie_note
    weak_spot = bool(item.get("relative_weak_spot"))
    detail = "Relative weak spot in this league." if weak_spot else ""
    return headline, detail, weak_spot


def _trade_item_text(item: dict[str, Any]) -> tuple[str, str, bool]:
    injury_display = str(item.get("their_player_injury_display") or "")
    their_player = str(item.get("their_player") or "")
    their_label = f"{their_player} ({injury_display})" if injury_display else their_player
    headline = (
        f"{item.get('my_player')} → {their_label} ({item.get('partner_team_name')})"
    )
    detail = str(item.get("rationale") or item.get("trade_confidence_label") or "")
    return headline, detail, bool(injury_display)


def _injury_item_text(item: dict[str, Any]) -> tuple[str, str, bool]:
    positions = ", ".join(item.get("injury_need_positions") or ())
    headline = f"{item.get('health_flag') or item.get('label')}: {positions}"
    detail = str(item.get("summary") or f"No healthy bench cover at {positions}.")
    return headline, detail, True


def _record_item_text(item: dict[str, Any]) -> tuple[str, str, bool]:
    wins = item.get("wins") or 0
    losses = item.get("losses") or 0
    ties = item.get("ties")
    record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    return f"Record: {record}", "", False


def _playoff_item_text(item: dict[str, Any]) -> tuple[str, str, bool]:
    try:
        probability = round(float(item.get("playoff_probability") or 0))
    except (TypeError, ValueError):
        probability = 0
    seed = item.get("median_seed")
    seed_note = f", projected {seed}-seed" if seed else ""
    status_note = (
        " · Clinched"
        if item.get("clinched")
        else " · Eliminated" if item.get("eliminated") else ""
    )
    headline = f"{probability}% to make the playoffs{seed_note}{status_note}"
    return headline, "", False


def _item_presentation(item: dict[str, Any]) -> tuple[str, str, bool]:
    """(headline, detail, is_risk) for one focus-area item.

    Dispatches on field presence exactly like the mobile screen's switch —
    these item shapes are modules.gm_plan's actual contract, not duplicated
    here, just read.
    """

    if "partner_team_name" in item:
        return _trade_item_text(item)
    if "injury_need_positions" in item:
        return _injury_item_text(item)
    if "rank" in item:
        return _rank_item_text(item)
    if "wins" in item:
        return _record_item_text(item)
    if "playoff_probability" in item:
        return _playoff_item_text(item)
    return str(item.get("label") or ""), "", False


def _render_focus_area(focus_area: dict[str, Any]) -> None:
    ui_primitives.render_section_header(
        focus_area.get("title", ""),
        subtitle=focus_area.get("framing", ""),
        weight="secondary",
    )
    if focus_area.get("status") == gm_plan.STATUS_NO_SIGNAL:
        ui_primitives.render_empty_state_panel(
            "Nothing to flag right now",
            focus_area.get("watch_for", ""),
            kind="no-data",
        )
        return
    for item in focus_area.get("items", []):
        if not isinstance(item, dict):
            continue
        headline, detail, is_risk = _item_presentation(item)
        ui_primitives.render_content_card(
            detail,
            title=headline,
            variant="warning" if is_risk else "elevated",
        )


def render_gm_plan_workspace(
    *,
    session: MutableMapping[str, Any],
    league_id: str,
    my_roster_id: Any,
    df_players: pd.DataFrame,
    score_field: str,
    league_value_settings: dict[str, Any] | None,
    team_strategy: str,
    players_db_path: str,
) -> None:
    league_key = str(league_id or "").strip()
    if (
        not league_key
        or my_roster_id is None
        or df_players is None
        or getattr(df_players, "empty", True)
    ):
        ui_primitives.render_empty_state_panel(
            "GM Plan isn't ready yet",
            "We don't have enough league data to build a GM Plan right now.",
            kind="unavailable",
        )
        return

    league = get_league(league_key) or {}
    raw_settings = league.get("settings") or {}
    # Same "leg"/"week" field modules.league_standings already reads off
    # Sleeper's raw league settings — reused, not recomputed (matches
    # services/mobile_api_service.py's get_gm_plan).
    current_week = raw_settings.get("leg") or raw_settings.get("week")
    playoff_week_start = raw_settings.get("playoff_week_start")
    season_phase = gm_plan.derive_season_phase(current_week, playoff_week_start)

    declared_stance = team_stance.fetch_stance_for_league(session, league_id=league_key)

    rosters = get_rosters(league_key) or []
    my_roster = next(
        (
            roster
            for roster in rosters
            if str(roster.get("roster_id") or "") == str(my_roster_id)
        ),
        None,
    )
    if my_roster is None:
        ui_primitives.render_empty_state_panel(
            "GM Plan isn't ready yet",
            "Your roster could not be matched in this league.",
            kind="unavailable",
        )
        return

    lens = _lens_for_score_field(score_field)

    injury_context: dict[str, Any] = {}
    roster_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if roster_ids and "player_id" in df_players.columns:
        roster_df = df_players[df_players["player_id"].astype(str).isin(roster_ids)].copy()
        if not roster_df.empty:
            lineup_df = team_eval_module.suggest_optimal_lineup(
                roster_df, league_value_settings, score_field=score_field
            )
            injury_context = trade_analyzer_fit.roster_injury_context(roster_df, lineup_df)

    rankings_row: dict[str, Any] | None = None
    total_teams: int | None = None
    try:
        rankings_frame = league_rankings.build_league_rankings_frame_cached(
            league_id=league_key, lens=lens, players_db_path=players_db_path
        )
    except Exception:
        rankings_frame = pd.DataFrame()
    if not rankings_frame.empty and "roster_id" in rankings_frame.columns:
        total_teams = int(len(rankings_frame))
        match = rankings_frame[rankings_frame["roster_id"].astype(str) == str(my_roster_id)]
        if not match.empty:
            rankings_row = match.iloc[0].to_dict()

    my_playoff_odds: dict[str, Any] | None = None
    try:
        playoff_odds_result = playoff_simulator.build_league_playoff_odds_cached(
            league_id=league_key, lens=lens, players_db_path=players_db_path
        )
    except Exception:
        playoff_odds_result = {}
    for team in (playoff_odds_result or {}).get("teams") or []:
        if str(team.get("roster_id") or "") == str(my_roster_id):
            my_playoff_odds = team
            break

    gm_targets.ensure_membership_cache(session, league_id=league_key)
    gm_target_ids = gm_targets.cached_target_ids(session, league_id=league_key)
    untouchable_ids = gm_targets.cached_untouchable_ids(session, league_id=league_key)

    trade_idea_records: list[dict[str, Any]] = []
    try:
        trade_idea_records = trade_hub_engine.generate_trade_idea_records_cached(
            league_id=league_key,
            roster_id=int(my_roster_id),
            strategy=str(team_strategy or "retool"),
            lens=lens,
            players_db_path=players_db_path,
            untouchable_player_ids=tuple(sorted(untouchable_ids)),
            gm_target_player_ids=tuple(sorted(gm_target_ids)),
            team_stance=declared_stance,
        )
    except (TypeError, ValueError):
        trade_idea_records = []

    roster_settings = my_roster.get("settings") or {}
    record = {
        "wins": roster_settings.get("wins"),
        "losses": roster_settings.get("losses"),
        "ties": roster_settings.get("ties"),
    }

    plan = gm_plan.build_gm_plan(
        team_stance=declared_stance,
        season_phase=season_phase,
        rankings_row=rankings_row,
        total_teams=total_teams,
        record=record,
        playoff_odds=my_playoff_odds,
        trade_ideas=trade_idea_records,
        injury_context=injury_context,
    )

    phase_label = str(plan.get("season_phase_label") or "").upper()
    stance_label = str(plan.get("team_stance_label") or "")
    badge_html = ""
    if phase_label:
        badge_html += ui_primitives.status_badge_html(phase_label, variant="information")
    if stance_label:
        badge_html += " " + ui_primitives.status_badge_html(stance_label, variant="premium")
    if badge_html:
        st.markdown(badge_html, unsafe_allow_html=True)
    st.subheader(str(plan.get("headline") or ""))

    focus_areas = plan.get("focus_areas") or []
    if not focus_areas:
        ui_primitives.render_empty_state_panel(
            "GM Plan isn't ready yet",
            "We don't have enough to build a GM Plan for this league yet.",
            kind="no-data",
        )
        return

    for focus_area in focus_areas:
        if isinstance(focus_area, dict):
            _render_focus_area(focus_area)
