"""Stateless "Next Move" briefing tiles for a single roster.

This is a from-scratch, session-independent sibling to the web app's
render_home_dashboard (app.py) — it calls the exact same underlying engines
(modules.team_eval, modules.trade_analyzer_fit, modules.injury_ui,
modules.waivers_ui, modules.sleeper) so the mobile app's "Next Move" briefing
agrees with the web app's Dashboard, without importing from app.py (modules/
never imports app.py — app.py imports modules/). `select_need_headline` is
imported from modules.roster_needs, the single source of truth this module
and app.py's `team_need_display` both call — pure presentation selection
over an already-computed TeamNeedsAssessment.

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

from modules import (
    canonical_recommendation_narrative,
    daily_gm_briefing,
    dashboard_workflow,
    injury_ui,
    league_rankings,
    league_value_settings,
    news as news_cache,
    news_intelligence,
    rankings,
    record_signal,
    sleeper,
    sleeper_leagues,
    team_stance,
    trade_hub_ui,
    trade_hub_engine,
)
from modules.canonical_recommendation_narrative import build_waiver_narrative
from modules.compact_fantasy_assets import compact_package
from modules.league_value_settings import DEFAULT_LEAGUE_VALUE_SETTINGS
from modules.league_workspace_ui import _format_score
from modules.player_cards import recommendation_reason_text
from modules.rankings import injury_display_label, injury_level
from modules.player_state_authority import NFL_NON_ACTIONABLE_STATUSES
from modules.roster_needs import NEED_TIER_LABELS, TeamNeedsAssessment, select_need_headline
from modules.team_eval import refine_team_directions, suggest_optimal_lineup
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
        "route_player_position": alert.get("route_player_position") or "",
        "route_player_team": alert.get("route_player_team") or "",
        "route_player_tier": alert.get("route_player_tier") or "",
        "route_player_score": alert.get("route_player_score"),
        "route_player_injury_status": alert.get("route_player_injury_status") or "",
        "mentioned_players": alert.get("mentioned_players") or [],
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
        # Same row already backing every other field on this tile — not a
        # second valuation source.
        "route_player_name": _text(top_waiver.get("name")),
        "route_player_position": _text(top_waiver.get("position")),
        "route_player_team": _text(top_waiver.get("team")),
        "route_player_tier": _text(top_waiver.get("player_tier")),
        "route_player_score": top_waiver.get(score_field),
        "route_player_injury_status": _text(top_waiver.get("injury_status")),
        "recommendation_narrative": narrative.to_dict() if narrative else None,
        "recommendation_id": narrative.recommendation_id if narrative else "",
    }


def build_value_trend_tile(roster_df: pd.DataFrame, score_field: str) -> dict[str, Any] | None:
    """The single highest-value roster asset whose usage is trending down
    enough to narrate — the exact same gated read Live Draft/Player Compare
    already surface per player (``rankings.recency_trend_display``, see its
    docstring for the confidence/sample-size gate), just picking the one
    roster player it is most worth flagging at a glance instead of narrating
    whichever player a user already has open. No new valuation: the
    ``recency_trend``/``recency_confidence`` columns this reads are already
    on the same valued ``roster_df`` every other tile here reads from.

    Returns ``None`` when no roster player clears the display gate with a
    downward read — never fabricates a decline that isn't there.
    """

    if roster_df is None or roster_df.empty or score_field not in roster_df.columns:
        return None
    ordered = roster_df.sort_values(score_field, ascending=False)
    for _, row in ordered.iterrows():
        trend = rankings.recency_trend_display(row)
        if not trend or trend.get("direction") != "down":
            continue
        name = _text(row.get("name"), "A roster player")
        magnitude = trend.get("magnitude_pct")
        confidence_label = _text(trend.get("confidence_label"))
        note = (
            f"Usage down {magnitude}%"
            + (f" ({confidence_label})" if confidence_label else "")
            + " vs its earlier-season baseline."
            if magnitude is not None
            else "Usage trending down vs its earlier-season baseline."
        )
        return {
            "label": "Value Trend",
            "value": f"{name} trending down",
            "note": note,
            "tone": "risk",
            "route_key": "my_team",
            "route_player_id": _text(row.get("player_id")),
            "route_player_name": name,
            "route_player_position": _text(row.get("position")),
            "route_player_team": _text(row.get("team")),
            "route_player_tier": _text(row.get("player_tier")),
            "route_player_score": row.get(score_field),
            "route_player_injury_status": _text(row.get("injury_status")),
        }
    return None


# coridian_, 2026-10-18: "you might need to change your decision-making
# going through the rest of the season" — a team-level nudge when a user's
# own declared Team Situation stance meaningfully disagrees with the real,
# record-aware auto-computed posture modules.team_eval._classify_team_
# strategy already produces. Only the genuinely conflicting pairs are
# flagged — declared "competing" vs. auto "fringe_contender"/"retool" is
# close enough to not be worth a popup; this is for real divergence.
_STRATEGY_CHECK_CONFLICTS: dict[str, frozenset[str]] = {
    team_stance.STANCE_COMPETING: frozenset({"rebuild", "tank"}),
    team_stance.STANCE_REBUILDING: frozenset({"contender"}),
}

# Never flag this off a single early-season result — same noisy-sample-size
# reasoning modules.record_signal's own weight floor already applies to the
# auto-strategy math itself. "It's been six games" is coridian_'s own
# example phrasing, and six real results is also naturally at or past the
# halfway point of a normal dynasty regular season.
STRATEGY_CHECK_MIN_GAMES_PLAYED = 6
# Past this point in the season there's little left to meaningfully pivot
# on — stop nagging once the regular season is basically over.
STRATEGY_CHECK_MAX_SEASON_PROGRESS = 0.92


def build_strategy_check_tile(
    *,
    declared_team_stance: str,
    auto_strategy: str,
    auto_strategy_label: str,
    roster_record: Mapping[str, Any] | None,
    season_progress: float | None,
) -> dict[str, Any] | None:
    """A real season-record-vs-declared-stance mismatch tile, or None when
    there isn't one worth surfacing. Never fires without a declared stance
    (nothing to compare against), without enough real games played, or
    once the season's basically over — see the module-level constants
    above for the exact gates.
    """

    stance = str(declared_team_stance or "").strip().lower()
    conflicting_strategies = _STRATEGY_CHECK_CONFLICTS.get(stance)
    if not conflicting_strategies or str(auto_strategy or "") not in conflicting_strategies:
        return None
    if not isinstance(roster_record, Mapping):
        return None
    wins = record_signal.safe_int(roster_record.get("wins"), 0)
    losses = record_signal.safe_int(roster_record.get("losses"), 0)
    ties = record_signal.safe_int(roster_record.get("ties"), 0)
    games_played = wins + losses + ties
    if games_played < STRATEGY_CHECK_MIN_GAMES_PLAYED:
        return None
    progress = season_progress if season_progress is not None else 0.0
    if progress >= STRATEGY_CHECK_MAX_SEASON_PROGRESS:
        return None

    declared_label = team_stance.STANCE_LABELS.get(stance, stance.title())
    auto_label = _text(auto_strategy_label) or str(auto_strategy or "").replace("_", " ").title()
    record_text = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    advice = (
        "Worth reconsidering before the trade deadline."
        if stance == team_stance.STANCE_COMPETING
        else "This might be the year to push in instead of holding back."
    )
    note = (
        f"You're {record_text} through {games_played} games — your roster profile says "
        f"{auto_label}, not {declared_label}. {advice}"
    )
    return {
        "label": "Strategy Check",
        "value": f"{auto_label} outlook",
        "note": note,
        "tone": "risk",
        "route_key": "team_situation",
    }


def build_news_tiles(
    *,
    league_id: str,
    league_settings: Mapping[str, Any] | None,
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame,
    free_agents_df: pd.DataFrame,
    players_df: pd.DataFrame,
    max_tiles: int = 1,
) -> list[dict[str, Any]]:
    """Up to ``max_tiles`` "News Alert" tiles for players on THIS roster —
    the exact same roster-aware article matching/severity gate app.py's
    single-league Dashboard already runs
    (``news_intelligence.build_roster_news_alert_tiles``), reading only the
    disk-cached article pool (``modules.news.load_cached_news_pool`` — no
    live RSS fetch) so a many-league Portfolio fan-out never blocks on a
    network call. A plain throwaway ``session`` dict (never Streamlit's
    session state, which this session-independent module never touches) is
    enough for the dedupe/escalation bookkeeping that function expects — a
    quick-glance read of "is there a live story on one of my players right
    now" has no need for across-rerun escalation memory the way the
    single-league Dashboard's persistent session does.
    """

    try:
        articles = news_cache.load_cached_news_pool()
    except Exception:
        return []
    return news_intelligence.build_roster_news_alert_tiles(
        articles,
        session={},
        league_id=league_id,
        league_settings=league_settings or {},
        my_team_df=roster_df,
        starters_df=lineup_df,
        free_agents_df=free_agents_df,
        players_df=players_df,
        max_tiles=max_tiles,
        presentation=True,
    )


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
    # The headline ("value"/target_label below) already names whichever
    # receive-side PLAYER asset trade_ideas._first_player_asset picked for
    # `their_player`/`their_player_id` — this needs the same pick, not a
    # blind receive_assets[0] (a receive package with a pick listed first,
    # e.g. "2027 2nd + Tony Pollard", would otherwise point route_player at
    # the pick, which has no player_id, so the card silently showed no
    # identity at all for the player the headline actually names;
    # coridian_, 2026-10-17: "all players mentioned need to have the
    # player pfp").
    headline_player_asset = next(
        (asset for asset in receive_assets if _text(asset.get("player_id"))), None
    )
    route_player_id = _text(headline_player_asset.get("player_id")) if headline_player_asset else ""
    # Same raw asset dict compact_package/presentation_asset already reads
    # position/team/player_tier/score from (modules.trade_ideas._player_asset)
    # — not a second valuation source.
    route_player_name = _text(headline_player_asset.get("name")) if headline_player_asset else ""
    route_player_position = _text(headline_player_asset.get("position")) if headline_player_asset else ""
    route_player_team = _text(headline_player_asset.get("team")) if headline_player_asset else ""
    route_player_tier = _text(headline_player_asset.get("player_tier")) if headline_player_asset else ""
    route_player_score = headline_player_asset.get("score") if headline_player_asset else None
    package = compact_package(
        send_assets, receive_assets, value_edge=value_delta, confidence=confidence_label
    )
    # This tile's "value" is what the push-notification sweep sends verbatim
    # as the notification body (modules.push_triggers.run_push_trigger_sweep
    # uses item.headline, which traces straight back to this field — the
    # fuller injury-aware "note"/reason text is never included in the push).
    # A rebuild/tank buy-low trade idea is a legitimate recommendation (see
    # modules.trade_ideas' injury-discount scoring), so this never suppresses
    # the push — it just makes sure the headline-side player's non-actionable
    # status (the same canonical check waivers already gate on, see
    # modules.player_state_authority.NFL_NON_ACTIONABLE_STATUSES) is named
    # right in the short text a user actually sees, instead of reading as a
    # clean opportunity.
    trade_value = _text(narrative.target_label, _text(headline_idea.get("partner_team_name"), "Open Trade Hub"))
    if receive_assets:
        headline_status = str(receive_assets[0].get("status") or "").strip().casefold()
        if headline_status in NFL_NON_ACTIONABLE_STATUSES:
            injury_tag = injury_display_label(
                receive_assets[0].get("status"), receive_assets[0].get("injury_status")
            )
            if injury_tag:
                trade_value = f"{trade_value} ({injury_tag})"
    return {
        "label": "Top Trade Opportunity",
        "value": trade_value,
        "note": narrative.shorten("reason", 150),
        "tone": "trade",
        "route_key": "trade_hub",
        "route_player_id": route_player_id,
        "route_player_name": route_player_name,
        "route_player_position": route_player_position,
        "route_player_team": route_player_team,
        "route_player_tier": route_player_tier,
        "route_player_score": route_player_score,
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
    roster_record: Mapping[str, Any] | None = None,
    auto_strategy: str = "",
    auto_strategy_label: str = "",
    season_progress: float | None = None,
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

    `roster_record`/`auto_strategy`/`auto_strategy_label`/`season_progress`
    feed build_strategy_check_tile above — the caller's existing
    rankings_frame lookup and roster settings already have these for free,
    so this function never re-fetches league/rankings data itself to get
    them. All default to empty/None, which simply means that tile never
    fires (no stance comparison without the real inputs), not an error.
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
    # trade, waiver, need, injury) — see module docstring. Value Trend/News
    # Alert are appended last: quick-glance "watch" signals (see
    # daily_gm_briefing._WATCH_LABELS), never competing with an existing
    # trade/waiver/need tile for the single Top Priority headline.
    items = [roster_pressure_tile]
    if trade_tile is not None:
        items.append(trade_tile)
    if waiver_tile is not None:
        items.append(waiver_tile)
    items.extend([need_tile, injury_tile])

    value_trend_tile = build_value_trend_tile(roster_df, score_field)
    if value_trend_tile is not None:
        items.append(value_trend_tile)
    strategy_check_tile = build_strategy_check_tile(
        declared_team_stance=team_stance,
        auto_strategy=auto_strategy,
        auto_strategy_label=auto_strategy_label,
        roster_record=roster_record,
        season_progress=season_progress,
    )
    if strategy_check_tile is not None:
        items.append(strategy_check_tile)
    items.extend(
        build_news_tiles(
            league_id=league_id,
            league_settings=league_settings,
            roster_df=roster_df,
            lineup_df=lineup_df,
            free_agents_df=free_agents_df,
            players_df=players_df,
        )
    )

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


# Everyday, non-error outcomes a caller iterating many leagues should treat
# as "nothing to show for this one" rather than a bug — the same reasons
# _resolve_my_roster/get_league_dashboard (services/mobile_api_service.py)
# already surface for a single league.
# A Portfolio card is a quick glance across many leagues, not a second
# Dashboard — capped well under daily_gm_briefing.MAX_BRIEFING_ITEMS (5).
PORTFOLIO_MAX_SIGNALS = 3

LEAGUE_SUMMARY_SKIP_REASONS = frozenset(
    {
        "no_sleeper_username_linked",
        "sleeper_user_not_found",
        "league_not_found",
        "not_a_member_of_league",
        "empty_roster",
        "no_player_data",
        "league_season_ended",
    }
)


def build_league_summary(
    *,
    league_id: str,
    lens: str,
    sleeper_username: str,
    players_db_path: str,
    team_stance_value: str = "",
    gm_target_player_ids: tuple[str, ...] = (),
    gm_untouchable_player_ids: tuple[str, ...] = (),
    entitlement: str = "free",
) -> dict[str, Any]:
    """One league's compact standing/record/rank/top-need-or-opportunity
    summary — a cross-league "Portfolio" row.

    Built for the multi-league Portfolio view (mobile's GET /v1/portfolio
    and the web app's Portfolio page) so BOTH surfaces compute "my team in
    this league, at a glance" the exact same way, from the exact same
    engines `compose_next_move_briefing` above already uses for the
    single-league Dashboard (modules.league_value_settings for the lens,
    modules.trade_hub_engine for the trade tile, modules.league_rankings for
    power rank, modules.injury_ui for the health flag) — no new valuation or
    ranking math, just one more caller of what already exists, condensed to
    the handful of fields a league row needs instead of the full Dashboard's
    item list.

    Every field this function needs to resolve a user's roster in
    `league_id` (sleeper_username, declared team stance, GM Targets) is
    passed in rather than fetched here, so this stays a plain function any
    runtime can call — the FastAPI mobile API and the Streamlit web app
    fetch those from Supabase differently (bearer token vs. session state),
    and neither concern belongs in this module (see module docstring: this
    is a session-independent sibling to web's own dashboard, not a Supabase
    client).

    Returns `{"ok": False, "reason": "..."}` for any everyday non-member/
    no-data state (`LEAGUE_SUMMARY_SKIP_REASONS`) — never raises for those,
    matching `_resolve_my_roster`'s own non-error contract. A genuine
    failure (Sleeper unreachable, a malformed league payload, etc.) raises,
    same as the engines it calls — a caller iterating many leagues should
    catch that per league and report it, not swallow it here.
    """

    if not str(sleeper_username or "").strip():
        return {"ok": False, "reason": "no_sleeper_username_linked"}

    sleeper_user_id = sleeper_leagues.resolve_sleeper_user_id(sleeper_username)
    if not sleeper_user_id:
        return {"ok": False, "reason": "sleeper_user_not_found"}

    league = sleeper.get_league(league_id)
    if not league:
        return {"ok": False, "reason": "league_not_found"}

    # coridian_, 2026-10-19: "5 leauges saved maybe only 2 populate (thats
    # correct ... the other leauges didnt renew this year) and it takes
    # 8+ seconds" — a league that never got a follow-up created for the
    # new season still resolves fine from Sleeper (the old league_id and
    # its final roster persist indefinitely), so without this check it ran
    # the FULL valuation/lineup/trade-ideas pipeline for a stale roster
    # before failing somewhere downstream, paying the expensive path for
    # exactly the leagues that have nothing useful to show. Bail out here,
    # before any of that work starts, the same cheap way save_league
    # already verifies a league exists at all.
    if str(league.get("season") or "") != str(sleeper.default_player_stats_season()):
        return {"ok": False, "reason": "league_season_ended"}

    rosters = sleeper.get_rosters(league_id)
    my_roster = next(
        (r for r in rosters if str(r.get("owner_id") or "") == sleeper_user_id), None
    )
    if my_roster is None:
        return {"ok": False, "reason": "not_a_member_of_league"}

    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return {"ok": False, "reason": "empty_roster"}

    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    # Portfolio's real perf bug (coridian_, 2026-10-18: "~10s load"): this
    # used to re-run load -> filter -> apply_valuation_lens from scratch for
    # every saved league, every call — the full eligible-player-pool
    # valuation pass, not just this roster's slice of it. That's exactly
    # the shared "asker-independent, redone from scratch" cost
    # build_valued_players_frame_cached already exists to fix (same 30s
    # Redis-backed, single-flight cache modules.league_rankings/
    # modules.trade_hub_engine/modules.playoff_simulator/modules.waivers_ui
    # already use for their own downstream work) — this call site just
    # never used it, so every one of Portfolio's per-league fan-out threads
    # paid the full cost independently instead of sharing one cache entry
    # per (league_id, lens) across the whole 30s window.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if valued.empty:
        return {"ok": False, "reason": "no_player_data"}
    score_field = league_value_settings.valuation_score_field(lens)

    all_rostered_player_ids: set[str] = set()
    for roster in rosters:
        all_rostered_player_ids.update(str(pid) for pid in (roster.get("players") or []))

    roster_id = my_roster.get("roster_id")
    team_strategy = team_stance.team_strategy_for_stance(team_stance_value)

    trade_idea_records = None
    try:
        trade_idea_records = trade_hub_engine.generate_trade_idea_records_cached(
            league_id=league_id,
            roster_id=int(roster_id),
            strategy=team_strategy,
            lens=lens,
            players_db_path=players_db_path,
            untouchable_player_ids=gm_untouchable_player_ids,
            gm_target_player_ids=gm_target_player_ids,
            team_stance=team_stance_value,
        )
    except (TypeError, ValueError):
        pass

    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()
    lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)
    injury_context = roster_injury_context(roster_df, lineup_df, taxi_player_ids=my_roster.get("taxi"))

    # Moved ahead of compose_next_move_briefing below (this used to run
    # AFTER it, purely for this function's own power_rank/archetype return
    # fields) so build_strategy_check_tile's auto_strategy/auto_strategy_
    # label inputs are free — the exact same already-cached rankings_frame
    # row this function already needed for archetype_label, read once.
    power_rank = None
    power_rank_tied = False
    franchise_rank = None
    franchise_rank_tied = False
    roster_value_rank = None
    roster_value_rank_tied = False
    archetype = None
    archetype_label = None
    auto_strategy = ""
    auto_strategy_label = ""
    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if not rankings_frame.empty:
        # Archetype/strategy classification degrades gracefully without the
        # heavier per-roster injury-summary pass web's cached_league_intelligence_frame
        # builds (health/balance inputs just default to neutral — see
        # modules.team_eval._rank_strength's fallback), so it's safe to run
        # directly on the cheap, already-cached rankings_frame — same choice
        # services/mobile_api_service.py's get_league_team_rankings makes.
        # roster_value_rank is already present too: build_league_rankings_frame
        # (which build_league_rankings_frame_cached wraps) runs
        # add_league_detail_ranks before returning.
        rankings_frame = refine_team_directions(rankings_frame)
        match = rankings_frame[rankings_frame["roster_id"].astype(str) == str(roster_id or "")]
        if not match.empty:
            row = match.iloc[0]
            power_rank = row.get("power_rank")
            power_rank_tied = bool(row.get("power_rank_tied"))
            franchise_rank = row.get("franchise_rank")
            franchise_rank_tied = bool(row.get("franchise_rank_tied"))
            roster_value_rank = row.get("roster_value_rank")
            roster_value_rank_tied = bool(row.get("roster_value_rank_tied"))
            archetype = row.get("archetype")
            archetype_label = row.get("archetype_label")
            auto_strategy = _text(row.get("strategy"))
            auto_strategy_label = _text(row.get("strategy_label"))

    briefing = compose_next_move_briefing(
        league_id=league_id,
        roster_id=str(roster_id or ""),
        players_df=valued,
        roster_player_ids=roster_player_ids,
        all_rostered_player_ids=all_rostered_player_ids,
        league_settings=settings,
        score_field=score_field,
        entitlement=entitlement,
        rosters=rosters,
        team_strategy=team_strategy,
        trade_idea_records=trade_idea_records,
        roster_df=roster_df,
        lineup_df=lineup_df,
        injury_context=injury_context,
        team_stance=team_stance_value,
        roster_record=my_roster.get("settings"),
        auto_strategy=auto_strategy,
        auto_strategy_label=auto_strategy_label,
        season_progress=record_signal.season_progress_fraction(league),
    )

    injury_display_context = injury_ui.resolve_team_injury_context(injury_context)
    health_flag = (
        injury_ui.team_injury_display_label(injury_display_context, include_uncertainty=True)
        or "Stable"
    )

    team_profile = sleeper.get_league_roster_profiles(league_id).get(str(roster_id or ""), {})
    roster_settings = my_roster.get("settings") or {}

    # The single highest-value-score asset on this roster — just the top row
    # of the already-computed roster_df (the exact same valuation `valued`/
    # score_field every other tile on this summary reads), no new valuation
    # logic. None only for the (empty_roster already short-circuits above,
    # so this is just defensive) case where score_field itself is missing.
    top_asset = None
    if not roster_df.empty and score_field in roster_df.columns:
        top_row = roster_df.sort_values(score_field, ascending=False).iloc[0]
        top_player_id = _text(top_row.get("player_id"))
        if top_player_id:
            top_asset = {
                "player_id": top_player_id,
                "name": _text(top_row.get("name")) or None,
                "position": _text(top_row.get("position")) or None,
                "team": _text(top_row.get("team")) or None,
                "tier": _text(top_row.get("player_tier")) or None,
                "score": top_row.get(score_field),
            }

    return {
        "ok": True,
        "reason": "",
        "roster_id": str(roster_id or ""),
        "team_name": _text(team_profile.get("team_name")),
        # coridian_, 2026-10-18 (screenshot): Portfolio's league cards had no
        # team logo at all. Same Sleeper CDN avatar team_profile's own
        # team_name above already reads from (sleeper.get_league_roster_
        # profiles) — not a second fetch, not a new avatar source.
        "team_avatar_url": _text(team_profile.get("avatar_url")),
        "wins": roster_settings.get("wins"),
        "losses": roster_settings.get("losses"),
        "ties": roster_settings.get("ties"),
        "health_flag": health_flag,
        "power_rank": power_rank,
        "power_rank_tied": power_rank_tied,
        "franchise_rank": franchise_rank,
        "franchise_rank_tied": franchise_rank_tied,
        "roster_value_rank": roster_value_rank,
        "roster_value_rank_tied": roster_value_rank_tied,
        "archetype": archetype,
        "archetype_label": archetype_label,
        "top_asset": top_asset,
        # Priority-ordered by organize_dashboard_items/compose_daily_gm_briefing
        # above — items[0] is already "the one thing to do in this league",
        # the same headline the single-league Dashboard leads with. Portfolio
        # wants more than that single headline at a glance (coridian_: "a
        # quick synopsis of the whole team situation" — a player's value
        # trending down, an injury, a news story, actionable waiver info),
        # so `top_items` carries the next few already-ranked/deduped signals
        # too, capped well under compose_daily_gm_briefing's own
        # MAX_BRIEFING_ITEMS so a Portfolio card stays a quick glance, not a
        # second Dashboard. `top_item` stays exactly as it was (its own first
        # entry) for every existing caller.
        "top_item": briefing.items[0].to_dict() if briefing.items else None,
        "top_items": [item.to_dict() for item in briefing.items[:PORTFOLIO_MAX_SIGNALS]],
    }
