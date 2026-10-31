"""Fetches the real Sleeper inputs for modules.league_integrity and caches the
finished report. All reads are public Sleeper endpoints plus the shared valued
players frame; nothing here writes to the players database."""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable

from modules import (
    league_history,
    league_integrity,
    league_value_settings,
    nfl_schedule,
    redis_cache,
    sleeper,
)

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


def _build(league_id: str, draft_rule: str, players_db_path: str, _bucket: int) -> dict[str, Any]:
    league = sleeper.get_league(league_id) or {}
    settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    status = str(league.get("status") or "")
    leg = int(settings.get("leg") or 0)
    if status not in {"in_season", "complete"} or (status == "in_season" and leg <= 0):
        return {"ok": True, "reason": "offseason", "teams": [], "collusion": [], "inactive": [],
                "limits": league_integrity.LIMITS, "draft_order_rule": draft_rule}
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
