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
from typing import Any, Iterable, Mapping

import pandas as pd

from modules import league_history, redis_cache, sleeper


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


def activity_quartiles(counts: Iterable[int]) -> tuple[float, float]:
    """(tx_low, tx_high) = the league's 25th/75th percentile transaction
    count. Same quantile computation app.py's `_classify_manager_tendencies`
    uses for its own tx_low/tx_high (pandas `.quantile(0.25)`/`.quantile(0.75)`,
    falling back to min/max for a league of one), pulled out here so a
    caller with just a plain list of counts (mobile's
    transaction_activity_count across the league) doesn't need to re-derive
    the same quantile math."""

    series = pd.to_numeric(pd.Series(list(counts)), errors="coerce").fillna(0)
    if series.empty:
        return 0.0, 0.0
    if len(series) > 1:
        return float(series.quantile(0.25)), float(series.quantile(0.75))
    return float(series.min() or 0), float(series.max() or 0)


def classify_activity_level(
    *,
    transaction_count: int,
    tx_high: float,
    tx_low: float,
    waiver_moves: int = 0,
    trade_count: int = 0,
    roster_churn: int | None = None,
    churn_high: float | None = None,
) -> str | None:
    """"Highly Active" / "Quiet Manager" team badge off real transaction
    volume.

    Exact threshold logic app.py's `_classify_manager_tendencies` already
    used inline (~app.py 14420-14425: `transaction_count >= max(6,
    round(tx_high))` or `roster_churn >= max(12, round(churn_high))` ->
    Highly Active; `transaction_count <= max(1, round(tx_low)) and
    waiver_moves <= 1 and trade_count <= 1` -> Quiet Manager), pulled into
    this shared module so mobile can apply the same thresholds too.
    `roster_churn`/`churn_high` are optional — mobile doesn't have a
    roster-churn read piped through yet, so when they're omitted this is
    judged on transaction_count alone (web's app.py call site keeps passing
    both, so its own behavior is unchanged).
    """

    highly_active = transaction_count >= max(6, int(round(tx_high)))
    if roster_churn is not None and churn_high is not None:
        highly_active = highly_active or roster_churn >= max(12, int(round(churn_high)))
    if highly_active:
        return "Highly Active"
    if transaction_count <= max(1, int(round(tx_low))) and waiver_moves <= 1 and trade_count <= 1:
        return "Quiet Manager"
    return None


# Same 30-minute cache idiom modules.team_trade_history uses for its own
# season-long transaction scan — real transaction history only changes when
# a real move happens, so re-scanning every request (Team Rankings, the
# Dashboard League Pulse tile) would be wasted work.
MANAGER_ACTIVITY_TTL_SECONDS = 30 * 60


def _manager_activity_cache_bucket() -> int:
    return int(time.time() // MANAGER_ACTIVITY_TTL_SECONDS)


# Redis-backed single-flight + cache (modules.redis_cache.redis_single_flight_cache)
# — same pattern, and same reason, as modules.team_trade_history's/
# modules.player_projections's own caches: this used to be a per-process
# functools.lru_cache, which only protected ONE mobile-api worker. Under
# docker-compose.yml's multiple uvicorn workers, each worker has its own
# process memory, so that old cache would let the same season-long
# transaction scan run redundantly once per worker AND a cache hit in
# worker A would never help a request landing on worker B. Redis fixes
# both: the distributed lock makes only one worker, cluster-wide, actually
# run the scan for a given (league_id, bucket), and the cached result
# lives in Redis, not in any one worker's memory.
_MANAGER_ACTIVITY_LOCK_TIMEOUT_SECONDS = 15.0


def _manager_activity_counts_cached(league_id: str, _bucket: int) -> dict[int, int]:
    return manager_activity_counts(league_id)


def manager_activity_counts_cached(league_id: str) -> dict[int, int]:
    """Cached front door for `manager_activity_counts` — shares one
    (league_id) cache key across callers within the same 30-minute window
    instead of each re-scanning the season's transactions.

    Single-flight + cache, shared across every mobile-api worker via
    Redis: see modules.redis_cache.redis_single_flight_cache and this
    module's own comment above `_MANAGER_ACTIVITY_LOCK_TIMEOUT_SECONDS`."""

    key = (league_id, _manager_activity_cache_bucket())
    cache_key = redis_cache.build_cache_key("manager_activity_counts", *key)
    return redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=MANAGER_ACTIVITY_TTL_SECONDS,
        compute=lambda: _manager_activity_counts_cached(*key),
        lock_timeout_seconds=_MANAGER_ACTIVITY_LOCK_TIMEOUT_SECONDS,
    )
