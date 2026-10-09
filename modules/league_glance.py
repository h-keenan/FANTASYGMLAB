"""One league's compact "at a glance" card for the cross-league overview.

Backs mobile's GET /v1/leagues-glance (services/mobile_api_service.py), the
"All leagues at a glance" section on the My Leagues screen. Each card holds
exactly five trimmed data points for the signed-in manager's team in one
league:

  1. record     -- W-L-T, standings rank, playoff status
                   (modules.league_standings.build_league_standings_bundle)
  2. waiver     -- the single top-priority add + a one-line reason
                   (modules.waivers_ui.select_top_waiver_opportunity, projected
                   through modules.dashboard_engine.build_waiver_tile so the
                   reason text matches the Dashboard's own waiver tile)
  3. trade      -- the headline of the single top trade idea
                   (modules.trade_hub_engine.generate_trade_idea_records_cached,
                   ordered by modules.trade_hub_ui.order_trade_hub_visible_ideas
                   and projected through dashboard_engine.build_trade_tile)
  4. news       -- a roster news/injury count: the roster-relevant news items
                   the league's Alerts screen shows (modules.my_news, the same
                   filter/curation GET /v1/leagues/{id}/alerts uses, so the
                   badge count matches the screen it opens) plus how many
                   rostered players carry an injury designation
                   (modules.rankings.injury_level)
  5. need       -- the top team-need headline
                   (modules.roster_needs.assess_team_needs via
                   trade_analyzer_fit.build_team_needs_assessment, headlined by
                   roster_needs.select_need_headline)

Deliberately NOT the Dashboard pipeline: no Next Move briefing composition,
no league rankings frame, no roster-pressure tile, no full narrative item
list. The heavier shared inputs it does need (the valued players frame and
the trade-idea search) are read through their existing Redis-backed caches,
which the single-league Dashboard and Trade Hub also populate, so a user
who just opened a league's Dashboard pays almost nothing extra here.

Pure function: every Supabase-sourced input (sleeper username, declared
team stance, GM Targets) and the shared news pool are passed in, matching
dashboard_engine.build_league_summary's contract. Returns
`{"ok": False, "reason": ...}` for everyday non-member/no-data states
(dashboard_engine.LEAGUE_SUMMARY_SKIP_REASONS) and raises on genuine
failures so the caller can report that one league without blanking others.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from modules import (
    dashboard_engine,
    league_standings,
    league_value_settings,
    my_news,
    sleeper,
    sleeper_leagues,
    team_stance,
    trade_hub_engine,
    trade_hub_ui,
)
from modules.rankings import injury_level
from modules.roster_needs import select_need_headline
from modules.team_eval import suggest_optimal_lineup
from modules.trade_analyzer_fit import build_team_needs_assessment, get_needed_positions
from modules.waivers_ui import select_top_waiver_opportunity

# Same cap GET /v1/leagues/{id}/alerts defaults to, so the badge never
# promises more items than the Alerts screen it opens will list.
GLANCE_NEWS_ITEM_LIMIT = 12


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _int_or_none(value: object) -> int | None:
    try:
        if value is None or pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def build_glance_record(
    *,
    rosters: Sequence[Mapping[str, Any]],
    roster_profiles: Mapping[str, Any] | None,
    league: Mapping[str, Any] | None,
    roster_id: str,
) -> dict[str, Any]:
    """W-L-T + standings rank + playoff status for one roster.

    Falls back to the roster's own Sleeper W-L-T (rank/playoff blank) when
    standings aren't available yet, e.g. in the offseason before any games.
    """

    bundle = league_standings.build_league_standings_bundle(
        rosters=list(rosters or []), roster_profiles=roster_profiles, league=league
    )
    frame = bundle.get("frame")
    row: Mapping[str, Any] | None = None
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        match = frame[frame["roster_id"].astype(str) == str(roster_id)]
        if not match.empty:
            row = match.iloc[0].to_dict()

    team_count = len([r for r in rosters or [] if isinstance(r, Mapping)])
    if row is None:
        my_roster = next((r for r in rosters or [] if str(r.get("roster_id")) == str(roster_id)), {})
        settings = my_roster.get("settings") or {}
        wins = _int_or_none(settings.get("wins")) or 0
        losses = _int_or_none(settings.get("losses")) or 0
        ties = _int_or_none(settings.get("ties")) or 0
        return {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "record_label": league_standings.format_record(wins, losses, ties),
            "standing_rank": None,
            "team_count": team_count,
            "playoff_status": "",
            "standings_available": False,
        }

    available = bool(bundle.get("available"))
    return {
        "wins": _int_or_none(row.get("wins")) or 0,
        "losses": _int_or_none(row.get("losses")) or 0,
        "ties": _int_or_none(row.get("ties")) or 0,
        "record_label": _text(row.get("record_label")),
        # Before any games are played every team is 0-0, so a rank would be
        # an alphabetical artefact, not a standing: only expose it once the
        # bundle says standings are real.
        "standing_rank": _int_or_none(row.get("standing_rank")) if available else None,
        "team_count": team_count,
        "playoff_status": _text(row.get("playoff_status")) if available else "",
        "standings_available": available,
    }


def build_glance_news(
    *,
    news_pool: Sequence[Mapping[str, Any]] | None,
    roster_df: pd.DataFrame,
) -> dict[str, int]:
    """Roster news count (Alerts' own filter/curation) + injured-player count."""

    names = [_text(name) for name in roster_df.get("name", pd.Series(dtype="object"))]
    names = [name for name in names if name]
    teams = sorted({_text(team) for team in roster_df.get("team", pd.Series(dtype="object")) if _text(team)})

    news_count = 0
    if news_pool and names:
        filtered = my_news.filter_news_for_players(list(news_pool), names, teams)
        news_count = len(my_news.curate_player_news(filtered, max_items=GLANCE_NEWS_ITEM_LIMIT))

    injury_count = 0
    if not roster_df.empty:
        statuses = roster_df.get("status", pd.Series("", index=roster_df.index))
        injury_statuses = roster_df.get("injury_status", pd.Series("", index=roster_df.index))
        for status, injury_status in zip(statuses, injury_statuses):
            if injury_level(_text(status), _text(injury_status)) != "healthy":
                injury_count += 1

    return {"news_count": news_count, "injury_count": injury_count}


def project_waiver_tile(tile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not tile:
        return None
    name = _text(tile.get("route_player_name") or tile.get("value"))
    if not name:
        return None
    return {
        "player_id": _text(tile.get("route_player_id")),
        "name": name,
        "position": _text(tile.get("route_player_position")),
        "team": _text(tile.get("route_player_team")),
        "reason": _text(tile.get("note")),
    }


def project_trade_tile(tile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not tile:
        return None
    headline = _text(tile.get("value"))
    if not headline:
        return None
    presentation = tile.get("presentation") or {}
    return {
        "headline": headline,
        "partner_team_name": _text(presentation.get("partner_team_name")),
    }


def project_need_tile(tile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not tile:
        return None
    return {
        "category": _text(tile.get("category")),
        "label": _text(tile.get("label")),
        "value": _text(tile.get("value")),
        "tier_label": _text(tile.get("tier_label")),
    }


def build_league_glance(
    *,
    league_id: str,
    lens: str,
    sleeper_username: str,
    players_db_path: str,
    news_pool: Sequence[Mapping[str, Any]] | None = None,
    team_stance_value: str = "",
    gm_target_player_ids: tuple[str, ...] = (),
    gm_untouchable_player_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """The five trimmed glance fields for the caller's team in `league_id`."""

    if not _text(sleeper_username):
        return {"ok": False, "reason": "no_sleeper_username_linked"}

    sleeper_user_id = sleeper_leagues.resolve_sleeper_user_id(sleeper_username)
    if not sleeper_user_id:
        return {"ok": False, "reason": "sleeper_user_not_found"}

    league = sleeper.get_league(league_id)
    if not league:
        return {"ok": False, "reason": "league_not_found"}

    rosters = sleeper.get_rosters(league_id)
    my_roster = next((r for r in rosters if str(r.get("owner_id") or "") == sleeper_user_id), None)
    if my_roster is None:
        return {"ok": False, "reason": "not_a_member_of_league"}

    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return {"ok": False, "reason": "empty_roster"}

    roster_id = str(my_roster.get("roster_id") or "")
    roster_profiles = sleeper.get_league_roster_profiles(league_id)
    team_profile = roster_profiles.get(roster_id, {}) if isinstance(roster_profiles, Mapping) else {}

    record = build_glance_record(
        rosters=rosters, roster_profiles=roster_profiles, league=league, roster_id=roster_id
    )

    # Shared (league_id, lens) Redis cache -- the same frame Dashboard,
    # Rankings and Waivers read, never a fresh valuation build per visit.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if valued is None or valued.empty:
        return {"ok": False, "reason": "no_player_data"}

    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    score_field = league_value_settings.valuation_score_field(lens)
    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()

    lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)
    assessment = build_team_needs_assessment(
        roster_df, None, settings, lineup_df=lineup_df, score_field=score_field
    )
    need = project_need_tile(select_need_headline(assessment))

    all_rostered_player_ids: set[str] = set()
    for roster in rosters:
        all_rostered_player_ids.update(str(pid) for pid in (roster.get("players") or []))
    needed_positions = get_needed_positions(
        roster_df, None, settings, assessment=assessment, lineup_df=lineup_df
    )
    free_agents_df = valued[~valued["player_id"].astype(str).isin(all_rostered_player_ids)]
    top_waiver = select_top_waiver_opportunity(
        free_agents_df, roster_df, settings, score_field, needed_positions=needed_positions
    )
    waiver = project_waiver_tile(
        dashboard_engine.build_waiver_tile(
            top_waiver, league_id=league_id, roster_id=roster_id, score_field=score_field
        )
    )

    trade = None
    try:
        records = trade_hub_engine.generate_trade_idea_records_cached(
            league_id=league_id,
            roster_id=int(roster_id),
            strategy=team_stance.team_strategy_for_stance(team_stance_value),
            lens=lens,
            players_db_path=players_db_path,
            untouchable_player_ids=gm_untouchable_player_ids,
            gm_target_player_ids=gm_target_player_ids,
            team_stance=team_stance_value,
        )
    except (TypeError, ValueError):
        records = None
    if records:
        ranked = trade_hub_ui.order_trade_hub_visible_ideas(list(records))
        if ranked:
            trade = project_trade_tile(
                dashboard_engine.build_trade_tile(
                    ranked[0], league_id=league_id, roster_id=roster_id, score_field=score_field
                )
            )

    return {
        "ok": True,
        "reason": "",
        "roster_id": roster_id,
        "team_name": _text(team_profile.get("team_name")),
        "record": record,
        "waiver": waiver,
        "trade": trade,
        "news": build_glance_news(news_pool=news_pool, roster_df=roster_df),
        "need": need,
    }
