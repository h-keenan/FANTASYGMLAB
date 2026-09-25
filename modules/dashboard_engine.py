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

`build_trade_tile`'s Top Trade Opportunity is composed the same way app.py
builds its own `trade_item`: every reason/label/verdict piece is a real
modules/ function app.py itself calls (modules.trade_hub_ui.trade_target_reason
et al., modules.trade_analyzer_fit.trade_value_verdict,
modules.canonical_recommendation_narrative.build_trade_narrative) — app.py's
`_trade_target_reason` etc. are themselves just thin aliases to these same
functions (see app.py lines ~1658-1683), so nothing here is a duplicate or a
port. The one simplification: `route_player_id` links to the headline idea's
own first "receive" asset rather than replicating app.py's separate
`franchise_trade_summary` buy-low derivation across the full idea list —
equally correct for a single headline idea, and much simpler. Tile ordering
(roster pressure, trade, waiver, need, injury) matches app.py's default
dashboard-phase branch; the startup/playoff/early-season phase variants
aren't replicated here.
"""

from __future__ import annotations

from functools import partial
from typing import Any, Mapping

import pandas as pd

from modules import canonical_recommendation_narrative, daily_gm_briefing, dashboard_workflow, injury_ui, sleeper, trade_hub_ui, trade_hub_engine
from modules.canonical_recommendation_narrative import build_waiver_narrative
from modules.compact_fantasy_assets import compact_package
from modules.league_value_settings import DEFAULT_LEAGUE_VALUE_SETTINGS
from modules.league_workspace_ui import _format_score
from modules.player_cards import recommendation_reason_text
from modules.rankings import injury_level
from modules.roster_needs import TeamNeedsAssessment
from modules.team_eval import suggest_optimal_lineup
from modules.trade_analyzer_fit import (
    build_team_needs_assessment,
    get_needed_positions,
    roster_injury_context,
    trade_value_verdict,
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
        "route_player_id": alert.get("route_player_id") or "",
        "route_player_name": alert.get("route_player_name") or "",
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


_trade_asset_injury_context = partial(trade_hub_ui.trade_asset_injury_context, injury_level=injury_level)
_trade_idea_injury_display_context = partial(
    trade_hub_ui.trade_idea_injury_display_context, asset_injury_context=_trade_asset_injury_context
)


def build_trade_tile(
    headline_idea: Mapping[str, Any] | None,
    *,
    league_id: str,
    roster_id: str,
    score_field: str,
) -> dict[str, Any] | None:
    """The Top Trade Opportunity tile — see module docstring."""

    if not headline_idea:
        return None

    target_reason = trade_hub_ui.trade_target_reason(
        headline_idea, recommendation_reason_text=recommendation_reason_text
    )
    partner_reason = trade_hub_ui.trade_partner_reason(
        headline_idea, recommendation_reason_text=recommendation_reason_text
    )
    confidence_reason = trade_hub_ui.trade_confidence_reason(
        headline_idea,
        recommendation_reason_text=recommendation_reason_text,
        injury_display_context=_trade_idea_injury_display_context,
    )
    confidence_label = trade_hub_ui.trade_display_confidence_label(
        headline_idea, injury_display_context=_trade_idea_injury_display_context
    )
    gain = int(headline_idea.get("trade_gain") or 0)
    value_delta = (
        f"+{_format_score(gain)}"
        if gain > 0
        else (f"-{_format_score(abs(gain))}" if gain < 0 else "Even")
    )
    narrative = canonical_recommendation_narrative.build_trade_narrative(
        headline_idea,
        league_id=league_id,
        roster_id=roster_id,
        valuation_lens=score_field,
        source_surface="dashboard",
        target_reason=target_reason,
        partner_reason=partner_reason,
        confidence_reason=confidence_reason,
        confidence_label=confidence_label,
        value_verdict=trade_value_verdict(gain),
        value_delta=value_delta,
        health_context=_trade_idea_injury_display_context(headline_idea),
    )
    receive_assets = [
        asset for asset in (headline_idea.get("receive_assets") or []) if isinstance(asset, Mapping)
    ]
    send_assets = [
        asset for asset in (headline_idea.get("send_assets") or []) if isinstance(asset, Mapping)
    ]
    route_player_id = _text(receive_assets[0].get("player_id")) if receive_assets else ""
    package = compact_package(
        send_assets, receive_assets, value_edge=value_delta, confidence=confidence_label
    )
    return {
        "label": "Top Trade Opportunity",
        "value": _text(narrative.target_label, _text(headline_idea.get("partner_team_name"), "Open Trade Hub")),
        "note": narrative.shorten("reason", 150),
        "tone": "trade",
        "route_key": "trade_hub",
        "route_player_id": route_player_id,
        "route_focus_mode": "target_player",
        "recommendation_narrative": narrative.to_dict(),
        "recommendation_id": narrative.recommendation_id,
        # Mobile's rich "Top Priority" trade card renders this directly
        # rather than re-deriving it from narrative prose — same shape
        # Trade Hub's own cards already use (modules.compact_fantasy_assets).
        # Nested under "presentation" — daily_gm_briefing._presentation_from_tile
        # is the one field that survives tile -> DailyBriefingItem projection
        # verbatim; anything else here would be silently dropped.
        "presentation": {
            "trade_package": package,
            "trade_gain": gain,
            "trade_confidence_label": confidence_label,
            "trade_market_realism_label": _text(headline_idea.get("market_realism_label"), "Thin"),
            "partner_team_name": _text(headline_idea.get("partner_team_name"), "Trade partner"),
        },
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
    rosters: list[dict] | None = None,
    team_strategy: str = "retool",
    trade_idea_records: list[dict[str, Any]] | None = None,
    roster_df: pd.DataFrame | None = None,
    lineup_df: pd.DataFrame | None = None,
    injury_context: dict[str, Any] | None = None,
    team_stance: str = "",
) -> daily_gm_briefing.DailyGmBriefing:
    """The mobile "Next Move" briefing — same composition pipeline
    (organize_dashboard_items -> compose_daily_gm_briefing) app.py uses,
    fed by tiles computed fresh from this roster's live context.

    `trade_idea_records` is an optional pre-computed result of
    trade_hub_engine.generate_trade_idea_records for this exact
    (league_id, roster_id, team_strategy) — the mobile API passes its own
    cached copy (shared with the Trade Hub endpoint, since both ask the
    identical question) rather than letting this function recompute the
    same expensive search a second time. Omitting it (the default, and
    what every existing test/caller does) falls back to computing it fresh
    from the players_df/rosters already passed in, keeping this function
    pure and independently testable without needing to fake out live
    Sleeper/disk calls for a cache it doesn't otherwise know about.

    `roster_df`/`lineup_df`/`injury_context` are the same kind of optional
    override: the mobile API's dashboard endpoint needs this exact
    roster/lineup/injury pass a second time for its own team_snapshot
    display fields, and previously recomputed it from scratch (a second
    suggest_optimal_lineup call) rather than threading it through — this
    lets the caller compute it once and pass it to both. All three default
    to None and are computed fresh here when omitted, same purity
    guarantee as trade_idea_records above.
    """

    if roster_df is None:
        roster_df = players_df[players_df["player_id"].astype(str).isin(roster_player_ids)].copy()
    if lineup_df is None:
        lineup_df = suggest_optimal_lineup(roster_df, league_settings, score_field=score_field)
    if injury_context is None:
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

    trade_tile = None
    try:
        my_roster_id = int(roster_id)
    except (TypeError, ValueError):
        my_roster_id = None
    if my_roster_id is not None and rosters:
        records = (
            trade_idea_records
            if trade_idea_records is not None
            else trade_hub_engine.generate_trade_idea_records(
                league_id=league_id,
                my_roster_id=my_roster_id,
                players_df=players_df,
                rosters=rosters,
                league_settings=league_settings,
                score_field=score_field,
                team_strategy=team_strategy,
                team_stance=team_stance,
            )
        )
        ranked_records = trade_hub_ui.order_trade_hub_visible_ideas(list(records))
        headline_idea = ranked_records[0] if ranked_records else None
        trade_tile = build_trade_tile(
            headline_idea, league_id=league_id, roster_id=roster_id, score_field=score_field
        )

    # Order matches app.py's default dashboard-phase branch (roster_pressure,
    # trade, waiver, need, injury) — see module docstring.
    items = [roster_pressure_tile]
    if trade_tile is not None:
        items.append(trade_tile)
    if waiver_tile is not None:
        items.append(waiver_tile)
    items.extend([need_tile, injury_tile])

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
