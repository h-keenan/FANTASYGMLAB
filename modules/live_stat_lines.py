"""Live per-player stat lines for the Matchup live feed.

Sleeper's matchups payload carries only points. The scoring events behind a
points change ("rushing TD, 4 yds") come from diffing consecutive stat lines,
which Sleeper serves for the whole league-wide week at
``/stats/nfl/regular/{season}/{week}`` (unofficial but the same endpoint the
season-stats builder in modules.sleeper already reads). One payload per
(season, week) is cached cluster-wide for the live TTL, so every league and
user shares a single fetch; per request this is a dict lookup per starter.

Best effort: any failure returns None and the feed falls back to points-only
events (labeled approximate). See docs/live-plays-research.md.
"""

from __future__ import annotations

import logging
from typing import Any

from modules import live_policy, sleeper, sleeper_cache

logger = logging.getLogger(__name__)

# Stat keys the feed describes (Sleeper's names). Everything else is dropped.
LIVE_STAT_KEYS: tuple[str, ...] = (
    "pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int", "pass_2pt",
    "rush_att", "rush_yd", "rush_td", "rush_2pt",
    "rec", "rec_tgt", "rec_yd", "rec_td", "rec_2pt",
    "fum_lost", "fgm", "fga", "xpm", "xpa",
    "def_td", "int", "fum_rec", "sack", "safe", "blk_kick", "pts_allow",
)


def week_payload(season: int, week: int) -> dict[str, Any] | None:
    """League-wide stats for the live week, cached for the live TTL; None when
    the week is not live or the fetch failed."""

    try:
        if live_policy.live_nfl_week() != int(week):
            return None
        url = f"{sleeper.SLEEPER_BASE}/stats/nfl/regular/{int(season)}/{int(week)}"
        ttl = float(live_policy.current_live_ttl())
        payload = sleeper_cache.shared_json(
            url,
            ttl=ttl,
            fetch=lambda: sleeper._request_json("sleeper_live_stats", url, timeout=8, allow_defer=False),
            large=True,
            store_ttl=max(ttl * 4, 600.0),
            max_age_on_error=max(ttl * 3, 90.0),
        )
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001 - best effort, never breaks the matchup
        logger.debug("live stat payload unavailable", exc_info=True)
        return None


def compact_line(payload: dict[str, Any] | None, player_id: Any) -> dict[str, float] | None:
    """The tracked stats for one player (non-zero only), or None when unknown."""

    if not payload:
        return None
    raw = payload.get(str(player_id or ""))
    if not isinstance(raw, dict):
        return None
    line: dict[str, float] = {}
    for key in LIVE_STAT_KEYS:
        value = raw.get(key)
        if isinstance(value, (int, float)) and value == value and value != 0:
            line[key] = round(float(value), 1)
    return line
