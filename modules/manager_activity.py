"""Real per-manager transaction-activity count, derived entirely from
Sleeper's own transaction history — the "Most Active Manager" read the
mobile Dashboard's League Pulse tile needs.

Previously this needed "a full-season Sleeper transaction scan that doesn't
exist in modules/ yet" (see the comment this replaces in
services/mobile_api_service.py). That scan already exists: modules.sleeper's
`get_transactions(league_id, round_num)` returns real per-round transaction
data, and modules.league_history already knows how to walk every round of
the season and collect+normalize them (modules.team_trade_history reuses the
exact same pipeline for its own season-long buy/sell read). This module is
the missing, much simpler half: a pure activity *count*, not a value read,
so — unlike team_trade_history — it needs no player value lookup and never
touches the players table at all.

"Activity" here means every real completed transaction (trade, waiver claim,
or free-agent move) a roster was a party to, counted once per transaction
per involved roster — a trade between two rosters counts once for each side,
matching how each manager actually experiences "how many moves have I made
this season." This is deliberately simpler than app.py's own
`activity_totals`/`most_active` computation (which also tracks waiver-only
and roster-churn splits for a different, heavier weekly-recap surface) —
mobile's League Pulse tile only needs the single count.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Mapping

from modules import league_history, sleeper


def manager_activity_counts(
    league_id: str,
    *,
    profiles: Mapping[str, Any] | None = None,
) -> dict[int, int]:
    """roster_id -> number of real completed transactions (trades, waiver
    claims, free-agent moves) across every week of the current season that
    has occurred so far."""

    if not league_id:
        return {}
    payload = league_history.collect_season_transactions(
        league_id,
        fetch_league=sleeper.get_league,
        fetch_transactions=sleeper.get_transactions,
    )
    normalized = league_history.normalize_season_payload(
        payload,
        profiles=profiles if profiles is not None else sleeper.get_league_roster_profiles(league_id),
        # A pure move count needs no player value data — pass an empty
        # lookup rather than loading the real players table for a tally.
        player_lookup={},
    )
    counts: dict[int, int] = {}
    for tx in normalized:
        for roster_id in tx.get("roster_ids") or []:
            try:
                rid = int(roster_id)
            except (TypeError, ValueError):
                continue
            counts[rid] = counts.get(rid, 0) + 1
    return counts


# Same 30-minute cache idiom modules.team_trade_history uses for its own
# season-long transaction scan — real transaction history only changes when
# a real move happens, so re-scanning every request (Team Rankings, the
# Dashboard League Pulse tile) would be wasted work.
MANAGER_ACTIVITY_TTL_SECONDS = 30 * 60


def _manager_activity_cache_bucket() -> int:
    return int(time.time() // MANAGER_ACTIVITY_TTL_SECONDS)


@lru_cache(maxsize=64)
def _manager_activity_counts_cached(league_id: str, _bucket: int) -> dict[int, int]:
    return manager_activity_counts(league_id)


def manager_activity_counts_cached(league_id: str) -> dict[int, int]:
    """Cached front door for `manager_activity_counts` — shares one
    (league_id) cache key across callers within the same 30-minute window
    instead of each re-scanning the season's transactions."""

    return _manager_activity_counts_cached(league_id, _manager_activity_cache_bucket())


def clear_manager_activity_cache() -> None:
    """Test/refresh hook — mirrors team_trade_history's own cache-clear."""

    _manager_activity_counts_cached.cache_clear()
