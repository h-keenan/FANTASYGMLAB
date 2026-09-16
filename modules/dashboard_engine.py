"""Stateless "Next Move" briefing tiles for a single roster.

This is a from-scratch, session-independent sibling to the web app's
render_home_dashboard (app.py) — it calls the exact same underlying engines
(modules.team_eval, modules.trade_analyzer_fit, modules.injury_ui,
modules.waivers_ui, modules.sleeper) so the mobile app's "Next Move" briefing
agrees with the web app's Dashboard, without importing from app.py (modules/
never imports app.py — app.py imports modules/). `select_need_headline` is a
deliberate, faithful duplicate of app.py's `team_need_display`: pure
presentation selection over an already-computed TeamNeedsAssessment, small
enough to keep in sync by inspection.

Composition (organize_dashboard_items -> compose_daily_gm_briefing) reuses
modules.dashboard_workflow and modules.daily_gm_briefing exactly as the web
app does — those two modules were already pure and session-independent.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from modules import daily_gm_briefing, dashboard_workflow, injury_ui, sleeper
from modules.canonical_recommendation_narrative import build_waiver_narrative
from modules.league_value_settings import DEFAULT_LEAGUE_VALUE_SETTINGS
from modules.roster_needs import TeamNeedsAssessment
from modules.team_eval import suggest_optimal_lineup
from modules.trade_analyzer_fit import (
    build_team_needs_assessment,
    get_needed_positions,
    roster_injury_context,
)
from modules.waivers_ui import select_top_waiver_opportunity, waiver_recommendation_label


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def select_need_headline(assessment: TeamNeedsAssessment) -> dict[str, str]:
    """Faithful copy of app.py's team_need_display — see module docstring."""

    position_items = {item.position: item for item in assessment.positions}
    current_needs = [
        position
        for position in assessment.true_needs
        if (
            position_items.get(position) is not None
            and position_items[position].classification == "short_term_need"
            and not position_items[position].temporary_injury_pressure
        )
    ]
    if current_needs:
        return {
            "label": "Biggest Team Need",
            "value": current_needs[0],
            "note": "Starter and depth coverage identify this as the clearest current roster deficiency.",
            "tone": "need",
        }
    if assessment.temporary_injury_pressures:
        return {
            "label": "Injury Pressure",
            "value": assessment.temporary_injury_pressures[0],
            "note": "Current availability is creating temporary pressure in this room.",
            "tone": "risk",
        }
    if assessment.future_risks:
        return {
            "label": "Future Roster Risk",
            "value": assessment.future_risks[0],
            "note": "Current coverage is playable, but future stability is limited.",
            "tone": "draft",
        }
    if assessment.upgrade_opportunities:
        return {
            "label": "Upgrade Opportunity",
            "value": assessment.upgrade_opportunities[0],
            "note": "This covered room trails the league baseline but is not a true roster need.",
            "tone": "need",
        }
    return {
        "label": "Balanced Roster",
        "value": "No urgent need",
        "note": "No current roster deficiency is standing out under the canonical coverage policy.",
        "tone": "draft",
    }


def build_roster_pressure_tile(
    *,
    league_id: str,
    roster_id: str,
    roster_df: pd.DataFrame,
    league_settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Roster size vs. league limit — mirrors app.py's roster_limit_status
    slot-counting formula exactly, without its much larger drop/trade/keep
    candidate-building tail (not needed for a single summary tile)."""

    league = sleeper.get_league(league_id) or {}
    settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    positions = tuple(str(pos or "").upper() for pos in (league.get("roster_positions") or []))
    bench_positions = {"BN", "BE", "BENCH"}

    starter_slots = len([pos for pos in positions if pos and pos not in {"IR", "TAXI", *bench_positions}])
    bench_slots = sum(1 for pos in positions if pos in bench_positions)
    taxi_slots = max(sum(1 for pos in positions if pos == "TAXI"), int(settings.get("taxi_slots") or 0))
    ir_slots = max(sum(1 for pos in positions if pos == "IR"), int(settings.get("reserve_slots") or 0))
    max_roster_size = starter_slots + bench_slots
    if max_roster_size <= 0:
        resolved_settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
        resolved_settings.update(league_settings or {})
        starter_slots = int(resolved_settings.get("starter_count") or 9)
        bench_slots = int(resolved_settings.get("bench_count") or 0)
        taxi_slots = int(resolved_settings.get("taxi_count") or 0)
        ir_slots = int(resolved_settings.get("ir_count") or 0)
        max_roster_size = starter_slots + bench_slots

    roster_payload = next(
        (r for r in (sleeper.get_rosters(league_id) or []) if str(r.get("roster_id")) == str(roster_id)),
        {},
    )
    live_player_ids = {str(pid) for pid in (roster_payload.get("players") or []) if pid is not None}
    taxi_ids = {str(pid) for pid in (roster_payload.get("taxi") or []) if pid is not None}
    reserve_ids = {str(pid) for pid in (roster_payload.get("reserve") or []) if pid is not None}
    total_rostered = len(live_player_ids) or len(roster_df)
    taxi_count = len(live_player_ids & taxi_ids)
    reserve_count = len(live_player_ids & reserve_ids)
    exempt = min(taxi_count, taxi_slots) + min(reserve_count, ir_slots)
    active_roster_size = max(0, total_rostered - exempt)
    over_by = max(0, active_roster_size - max_roster_size)

    return {
        "label": "Roster Pressure",
        "value": f"{over_by} Over" if over_by > 0 else "Within Limit",
        "note": (
            f"{active_roster_size} active vs {max_roster_size} limit"
            if max_roster_size
            else "Sleeper roster limit unavailable."
        ),
        "tone": "risk" if over_by > 0 else "draft",
        "route_key": "my_team",
        "over_limit": over_by > 0,
    }


def build_injury_tile(injury_display_context: Mapping[str, Any]) -> dict[str, Any]:
    alert = injury_ui.my_team_injury_alert(injury_display_context)
    return {
        "label": "Injury Alert",
        "value": alert.get("value"),
        "note": alert.get("note"),
        "tone": "risk",
        "route_key": "my_team",
    }


def build_waiver_tile(
    top_waiver: pd.Series,
    *,
    league_id: str,
    roster_id: str,
    score_field: str,
) -> dict[str, Any] | None:
    if top_waiver is None or getattr(top_waiver, "empty", True):
        return None
    action, _ = waiver_recommendation_label(
        top_waiver, int(top_waiver.get("position_rank") or 99) or 99
    )
    waiver_note = _text(
        top_waiver.get("injury_replacement_note"),
        _text(top_waiver.get("opportunity_label"), "Open Waivers for the best live add."),
    )
    narrative = build_waiver_narrative(
        top_waiver,
        action=action,
        reason=waiver_note,
        league_id=league_id,
        roster_id=roster_id,
        valuation_lens=score_field,
        source_surface="dashboard",
    )
    return {
        "label": "Top Waiver Opportunity",
        "value": _text(top_waiver.get("name"), "Open Waivers"),
        "note": narrative.shorten("reason", 150) if narrative else waiver_note,
        "tone": "waiver",
        "route_key": "waivers",
        "route_player_id": _text(top_waiver.get("player_id")),
        "recommendation_narrative": narrative.to_dict() if narrative else None,
        "recommendation_id": narrative.recommendation_id if narrative else "",
    }


def compose_next_move_briefing(
    *,
    league_id: str,
    roster_id: str,
    players_df: pd.DataFrame,
    roster_player_ids: set[str],
    all_rostered_player_ids: set[str],
    league_settings: Mapping[str, Any] | None,
    score_field: str,
    entitlement: str = "free",
) -> daily_gm_briefing.DailyGmBriefing:
    """The mobile "Next Move" briefing — same composition pipeline
    (organize_dashboard_items -> compose_daily_gm_briefing) app.py uses,
    fed by tiles computed fresh from this roster's live context."""

    roster_df = players_df[players_df["player_id"].astype(str).isin(roster_player_ids)].copy()
    lineup_df = suggest_optimal_lineup(roster_df, league_settings, score_field=score_field)
    injury_context = roster_injury_context(roster_df, lineup_df)
    injury_display_context = injury_ui.resolve_team_injury_context(injury_context)
    team_needs_assessment = build_team_needs_assessment(
        roster_df, None, league_settings, lineup_df=lineup_df, score_field=score_field
    )
    needed_positions = get_needed_positions(
        roster_df, None, league_settings, assessment=team_needs_assessment, lineup_df=lineup_df
    )

    free_agents_df = players_df[~players_df["player_id"].astype(str).isin(all_rostered_player_ids)]
    top_waiver = select_top_waiver_opportunity(
        free_agents_df, roster_df, league_settings, score_field, needed_positions=needed_positions
    )

    need_tile = select_need_headline(team_needs_assessment)
    need_tile["route_key"] = "my_team"
    injury_tile = build_injury_tile(injury_display_context)
    roster_pressure_tile = build_roster_pressure_tile(
        league_id=league_id, roster_id=roster_id, roster_df=roster_df, league_settings=league_settings
    )
    waiver_tile = build_waiver_tile(
        top_waiver, league_id=league_id, roster_id=roster_id, score_field=score_field
    )

    items = [roster_pressure_tile, need_tile, injury_tile]
    if waiver_tile is not None:
        items.append(waiver_tile)

    immediate_labels = frozenset(
        label
        for label, active in (
            ("Roster Pressure", bool(roster_pressure_tile.get("over_limit"))),
            ("Injury Alert", int(injury_display_context.get("injured_starters") or 0) > 0),
        )
        if active
    )
    briefing = dashboard_workflow.organize_dashboard_items(items, immediate_labels=immediate_labels)
    return daily_gm_briefing.compose_daily_gm_briefing(
        briefing,
        league_id=league_id,
        roster_id=roster_id,
        valuation_lens=score_field,
        entitlement=entitlement,
    )
