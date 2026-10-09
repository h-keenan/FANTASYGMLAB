"""Real per-roster draft-pick flow (acquired vs. sent, with 1st-round picks
tracked separately), derived entirely from Sleeper's own transaction
history.

This is the missing data half of the "Pick Hoarder" / "Pick Seller" team
badge: app.py's own `cached_manager_behavior_summary` already computes an
equivalent read for the web Streamlit path, but it does so with its own
inline raw-transaction scan rather than modules.league_history's shared
collect+normalize pipeline. This module reuses that shared pipeline
instead (the same one modules.manager_activity and modules.team_trade_history
already use for their own season-long transaction scans) so mobile
(services/mobile_api_service.py) gets the same real signal without a third,
independent re-parse of Sleeper's raw transaction shape.

Counting rule, per normalized transaction's `draft_picks` entries (each
already carries `to_roster_id`/`from_roster_id`/`round` via
modules.league_history.normalize_transaction):
  - a pick counts as "acquired" for its `to_roster_id` and, when a
    `from_roster_id` is present (the pick changed hands rather than simply
    being the original owner's own pick listed on a trade), "sent" for
    that `from_roster_id`.
  - a pick with `round == 1` additionally counts toward that roster's
    `firsts_acquired`/`firsts_sent`.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Mapping

from modules import league_history, sleeper


def league_pick_flow_counts(
    league_id: str,
    *,
    profiles: Mapping[str, Any] | None = None,
) -> dict[int, dict[str, int]]:
    """roster_id -> {picks_acquired, picks_sent, firsts_acquired, firsts_sent}
    across every week of the current season that has occurred so far."""

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
        # Pick flow needs no player value data — pass an empty lookup rather
        # than loading the real players table for a tally (same contract
        # modules.manager_activity uses for its own pure-count read).
        player_lookup={},
    )

    counts: dict[int, dict[str, int]] = {}

    def bucket(roster_id: int) -> dict[str, int]:
        return counts.setdefault(
            roster_id,
            {"picks_acquired": 0, "picks_sent": 0, "firsts_acquired": 0, "firsts_sent": 0},
        )

    for tx in normalized:
        for pick in tx.get("draft_picks") or []:
            if not isinstance(pick, Mapping):
                continue
            try:
                to_roster_id = int(pick.get("to_roster_id") or 0)
            except (TypeError, ValueError):
                to_roster_id = 0
            try:
                from_roster_id = int(pick.get("from_roster_id") or 0)
            except (TypeError, ValueError):
                from_roster_id = 0
            is_first = pick.get("round") == 1

            if to_roster_id > 0:
                entry = bucket(to_roster_id)
                entry["picks_acquired"] += 1
                if is_first:
                    entry["firsts_acquired"] += 1
            if from_roster_id > 0:
                entry = bucket(from_roster_id)
                entry["picks_sent"] += 1
                if is_first:
                    entry["firsts_sent"] += 1

    return counts


def classify_pick_flow(firsts_acquired: int, firsts_sent: int) -> str | None:
    """"Pick Hoarder" / "Pick Seller" team badge off real future-1st flow.

    Mirrors the two rank-and-strategy-independent legs of app.py's
    `_classify_manager_tendencies` asset_behavior branch (~app.py
    14409-14412): `firsts_acquired - firsts_sent >= 1` -> Pick Hoarder,
    `firsts_sent > firsts_acquired` -> Pick Seller. The strategy/draft-rank
    OR-clauses in that function feed a different, broader
    "asset_behavior" classification (which also covers "Prospect Chaser"/
    "Consolidator") — this badge is deliberately narrower: just the real
    pick-flow signal, not a strategy-dependent inference.
    """

    if firsts_acquired - firsts_sent >= 1:
        return "Pick Hoarder"
    if firsts_sent > firsts_acquired:
        return "Pick Seller"
    return None


# Same 30-minute cache idiom modules.manager_activity/team_trade_history use
# for their own season-long transaction scans — real pick-flow history only
# changes when a real trade happens.
PICK_FLOW_TTL_SECONDS = 30 * 60


def _pick_flow_cache_bucket() -> int:
    return int(time.time() // PICK_FLOW_TTL_SECONDS)


@lru_cache(maxsize=64)
def _league_pick_flow_counts_cached(league_id: str, _bucket: int) -> dict[int, dict[str, int]]:
    return league_pick_flow_counts(league_id)


def league_pick_flow_counts_cached(league_id: str) -> dict[int, dict[str, int]]:
    """Cached front door for `league_pick_flow_counts` — shares one
    (league_id) cache key across callers within the same 30-minute window
    instead of each re-scanning the season's transactions."""

    return _league_pick_flow_counts_cached(league_id, _pick_flow_cache_bucket())


def clear_pick_flow_cache() -> None:
    """Test/refresh hook — mirrors manager_activity's own cache-clear."""

    _league_pick_flow_counts_cached.cache_clear()
