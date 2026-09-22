"""Real per-team buy/sell trading-tendency signal, derived entirely from
Sleeper's own transaction history.

This is the data half of the "Decision Memory" concept coridian_ described:
a team with a real history of selling (shipping established value for
picks/future assets) should get flagged as such so the trade engine can
propose appropriate deals — not a user-declared stance, a pattern read off
real trade history. It reuses modules.league_history's existing transaction
scan/normalize pipeline (already built for the League History timeline)
rather than re-parsing Sleeper's raw transaction shape a second time.

Classification, per completed trade leg for a roster:
  - "sell" signal: gave up more established player value (sum of
    value_score across players in that leg) than received, AND received
    more draft picks than sent — the classic rebuild/sell-off shape.
  - "buy" signal: the reverse — paid draft picks/future value for more
    player value than sent, the classic win-now/buy shape.
  - otherwise: no signal (roughly even swaps, pure player-for-player
    trades with no picks involved, etc.) — most trades won't count toward
    either tendency, by design; this only tags the clear cases.

A roster's season tendency is "Seller"/"Buyer" only once it has at least
MIN_SIGNAL_TRADES legs of one signal and more of that signal than the
other; otherwise "Neutral" (including "not enough real signal yet").

Context only, by design (mirrors modules.nfl_schedule's own contract):
nothing here is wired into modules.trade_ideas's scoring — that's a
separate, deliberate follow-up so the signal can be reviewed on its own
before it starts shaping what deals get proposed.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Mapping

from modules import league_history, player_eligibility, rankings, sleeper

SELLER = "Seller"
BUYER = "Buyer"
NEUTRAL = "Neutral"

# A roster needs at least this many legs of the SAME signal, and more of
# that signal than the other, before it earns a Seller/Buyer label — one
# lopsided trade shouldn't brand a team all season.
MIN_SIGNAL_TRADES = 2


def _asset_value(asset: Mapping[str, Any], player_lookup: Mapping[str, Mapping[str, Any]]) -> float:
    row = player_lookup.get(str(asset.get("player_id")))
    if not isinstance(row, Mapping):
        return 0.0
    try:
        return float(row.get("value_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _leg_signal(
    *,
    roster_id: int,
    side: Mapping[str, Any],
    draft_picks: list[dict[str, Any]],
    player_lookup: Mapping[str, Mapping[str, Any]],
) -> str:
    received_value = sum(
        _asset_value(asset, player_lookup)
        for asset in (side.get("receives") or [])
        if isinstance(asset, Mapping) and asset.get("kind") == "player"
    )
    sent_value = sum(
        _asset_value(asset, player_lookup)
        for asset in (side.get("drops") or [])
        if isinstance(asset, Mapping) and asset.get("kind") == "player"
    )
    picks_received = sum(1 for pick in draft_picks if pick.get("to_roster_id") == roster_id)
    picks_sent = sum(1 for pick in draft_picks if pick.get("from_roster_id") == roster_id)
    if sent_value > received_value and picks_received > picks_sent:
        return "sell"
    if received_value > sent_value and picks_sent > picks_received:
        return "buy"
    return ""


def classify_trade_legs(
    transactions: list[Mapping[str, Any]],
    *,
    player_lookup: Mapping[str, Mapping[str, Any]],
) -> dict[int, dict[str, int]]:
    """roster_id -> {"sell": n, "buy": n} leg counts across every completed
    trade in `transactions` (already normalize_transaction'd). `player_lookup`
    must carry each player's `value_score` (modules.league_history.
    player_lookup_from_rows already includes it) — without real values every
    leg reads as a wash and nothing gets classified."""

    counts: dict[int, dict[str, int]] = {}
    for tx in transactions:
        if str(tx.get("type")) != "trade" or str(tx.get("status")) != "complete":
            continue
        draft_picks = list(tx.get("draft_picks") or [])
        for side in tx.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            try:
                roster_id = int(side.get("roster_id") or 0)
            except (TypeError, ValueError):
                roster_id = 0
            if not roster_id:
                continue
            signal = _leg_signal(
                roster_id=roster_id, side=side, draft_picks=draft_picks, player_lookup=player_lookup
            )
            if not signal:
                continue
            bucket = counts.setdefault(roster_id, {"sell": 0, "buy": 0})
            bucket[signal] += 1
    return counts


def tendency_from_counts(counts: Mapping[str, int]) -> str:
    sell = int(counts.get("sell") or 0)
    buy = int(counts.get("buy") or 0)
    if sell >= MIN_SIGNAL_TRADES and sell > buy:
        return SELLER
    if buy >= MIN_SIGNAL_TRADES and buy > sell:
        return BUYER
    return NEUTRAL


def league_trade_tendencies(
    league_id: str,
    *,
    player_lookup: Mapping[str, Mapping[str, Any]],
    profiles: Mapping[str, Any] | None = None,
) -> dict[int, dict[str, Any]]:
    """roster_id -> {tendency, sell_count, buy_count} for a whole league,
    scanning every week of the current season's real transaction history.

    `player_lookup` (modules.league_history.player_lookup_from_rows over the
    real players table) is required, not optional — an empty lookup means
    every asset resolves to 0 value and nothing gets classified."""

    payload = league_history.collect_season_transactions(
        league_id,
        fetch_league=sleeper.get_league,
        fetch_transactions=sleeper.get_transactions,
    )
    normalized = league_history.normalize_season_payload(
        payload,
        profiles=profiles or sleeper.get_league_roster_profiles(league_id),
        player_lookup=player_lookup,
    )
    counts = classify_trade_legs(normalized, player_lookup=player_lookup)
    return {
        roster_id: {
            "tendency": tendency_from_counts(bucket),
            "sell_count": bucket["sell"],
            "buy_count": bucket["buy"],
        }
        for roster_id, bucket in counts.items()
    }


# A season's real trade history changes only when a real trade happens —
# scanning every week fresh on every request (Trade Hub, Team Rankings)
# would be real, wasted work. Same live-time-bucket idiom
# modules.trade_hub_engine uses for idea generation, just a much longer
# window since this doesn't need to react within seconds.
TRADE_TENDENCY_TTL_SECONDS = 30 * 60


def _trade_tendency_cache_bucket() -> int:
    return int(time.time() // TRADE_TENDENCY_TTL_SECONDS)


@lru_cache(maxsize=64)
def _league_trade_tendencies_cached(league_id: str, players_db_path: str, _bucket: int) -> dict[int, dict[str, Any]]:
    players_df = rankings.load_players(players_db_path)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(players_db_path)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="team_trade_history_cache"
    )
    if players_df.empty:
        return {}
    player_lookup = league_history.player_lookup_from_rows(players_df.to_dict("records"))
    return league_trade_tendencies(league_id, player_lookup=player_lookup)


def league_trade_tendencies_cached(league_id: str, players_db_path: str) -> dict[int, dict[str, Any]]:
    """Cached front door for `league_trade_tendencies` — resolves its own
    player lookup from `players_db_path` rather than accepting one as an
    argument, so it's a single (league_id, players_db_path) cache key any
    caller (Trade Hub, Team Rankings) can share within the same 30-minute
    window instead of each re-scanning the season's transactions."""

    return _league_trade_tendencies_cached(league_id, players_db_path, _trade_tendency_cache_bucket())
