"""Fetches the real Sleeper inputs for modules.league_integrity and caches the
finished report. All reads are public Sleeper endpoints plus the shared valued
players frame; nothing here writes to the players database."""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable

from modules import (
    league_calendar,
    league_history,
    league_integrity,
    league_value_settings,
    nfl_schedule,
    redis_cache,
    sleeper,
)

class SleeperUnavailable(RuntimeError):
    """Sleeper returned nothing for data this report cannot be built without.

    Raised instead of returning an "offseason" / short report so a Sleeper
    blip is never cached for 30 minutes as if it were the league's real state.
    """


INTEGRITY_TTL_SECONDS = 30 * 60
_LOCK_TIMEOUT_SECONDS = 20.0


def _bye_checker(season: int) -> Callable[[str, int], bool]:
    cache: dict[str, int | None] = {}

    def on_bye(team: str, week: int) -> bool:
        if not team:
            return False
        if team not in cache:
            try:
                cache[team] = nfl_schedule.team_bye_week(team, season)
            except Exception:
                cache[team] = None
        return cache[team] == week

    return on_bye


def calendar_payload(league: dict[str, Any]) -> dict[str, Any]:
    """The league's trade deadline and season calendar (modules.league_calendar
    plus the playoff start week), so the page can show it next to the report."""

    settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    playoff_start = league_calendar._int_or_none(settings.get("playoff_week_start"))
    playoff_start = playoff_start if playoff_start and playoff_start > 1 else None
    return {
        **league_calendar.trade_window(league),
        "playoff_week_start": playoff_start,
        "regular_season_weeks": (playoff_start - 1) if playoff_start else None,
        "in_season": league_calendar.is_in_season(league),
    }


def _build(league_id: str, draft_rule: str, players_db_path: str, _bucket: int) -> dict[str, Any]:
    league = sleeper.get_league(league_id) or {}
    if not league:
        raise SleeperUnavailable("league")
    settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    status = str(league.get("status") or "")
    leg = int(settings.get("leg") or 0)
    if status not in {"in_season", "complete"} or (status == "in_season" and leg <= 0):
        return {"ok": True, "reason": "offseason", "teams": [], "collusion": [], "inactive": [],
                "limits": league_integrity.LIMITS, "draft_order_rule": draft_rule,
                "calendar": calendar_payload(league)}
    playoff_start = int(settings.get("playoff_week_start") or 0)
    last = max(1, (playoff_start - 1) if playoff_start > 1 else leg)
    if status == "in_season":
        last = min(last, leg)
    rosters = sleeper.get_rosters(league_id) or []
    profiles = sleeper.get_league_roster_profiles(league_id)
    weeks = list(range(1, last + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(weeks)), thread_name_prefix="dgm-integrity") as ex:
        fetched = list(ex.map(lambda w: sleeper.get_matchups(league_id, w) or [], weeks))
    weekly = {w: rows for w, rows in zip(weeks, fetched) if rows}
    # A played week with no rows before a later week that has rows is a failed
    # fetch, not a real gap: scoring around it would corrupt every team's
    # lineup history (and could flag people).
    if weekly and any(w not in weekly for w in range(1, max(weekly))):
        raise SleeperUnavailable("matchups")

    players = sleeper.get_players() or {}
    meta: dict[str, dict[str, Any]] = {}
    for rows in weekly.values():
        for entry in rows:
            for pid in entry.get("players") or []:
                p = players.get(str(pid))
                if p and str(pid) not in meta:
                    meta[str(pid)] = {
                        "name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                        "position": p.get("position") or "",
                        "team": p.get("team") or "",
                    }

    values: dict[str, dict[str, Any]] = {}
    try:
        frame = league_value_settings.build_valued_players_frame_cached(
            league_id=league_id, lens="Dynasty", players_db_path=players_db_path
        )
        if frame is not None and not frame.empty:
            values = league_history.player_lookup_from_rows(frame.to_dict("records"))
    except Exception:
        values = {}

    payload = league_history.collect_season_transactions(
        league_id, fetch_league=sleeper.get_league, fetch_transactions=sleeper.get_transactions
    )
    transactions = league_history.normalize_season_payload(payload, profiles=profiles, player_lookup=values)

    try:
        season = int(league.get("season") or 0)
    except (TypeError, ValueError):
        season = 0
    report = league_integrity.build_league_integrity(
        league=league, rosters=rosters, weekly=weekly, player_meta=meta, profiles=profiles,
        transactions=transactions, values=values, on_bye=_bye_checker(season) if season else None,
        draft_rule=draft_rule, current_week=leg if status == "in_season" else None,
    )
    report["week"] = leg if status == "in_season" else None
    report["calendar"] = calendar_payload(league)
    report["trades_valued"] = bool(values)
    return report


def build_cached(league_id: str, draft_rule: str, players_db_path: str) -> dict[str, Any]:
    draft_rule = draft_rule if draft_rule in league_integrity.DRAFT_RULES else league_integrity.DRAFT_RULE_UNKNOWN
    key = (league_id, draft_rule, players_db_path, int(time.time() // INTEGRITY_TTL_SECONDS))
    return redis_cache.redis_single_flight_cache(
        cache_key=redis_cache.build_cache_key("league_integrity", *key),
        ttl_seconds=INTEGRITY_TTL_SECONDS,
        compute=lambda: _build(*key),
        lock_timeout_seconds=_LOCK_TIMEOUT_SECONDS,
    )
