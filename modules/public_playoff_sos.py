"""Anonymous fantasy-playoff strength of schedule for the public SEO page.

A thin, public projection of ``external_ad_api.endpoint_playoff_sos`` (the Phase 2
advertising endpoint): same verified inputs (nflverse schedule + recency-weighted
points allowed by position), same ranking logic, no user, league or roster data.
Only the fields a public page needs are exposed; evidence rows and relevance
metadata stay on the authenticated endpoint.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from modules import external_ad_api

POSITIONS = external_ad_api.OFFENSE_POSITIONS
DEFAULT_WEEKS = external_ad_api.FANTASY_PLAYOFF_WEEKS
CACHE_TTL_SECONDS = 60 * 60

_lock = threading.Lock()
_cache: dict[tuple[int, int, int], tuple[float, dict[str, Any]]] = {}


def project(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce an ``endpoint_playoff_sos`` envelope to the public shape."""

    teams = []
    for it in payload.get("items") or []:
        by_pos = {}
        for pos, v in (it.get("by_position") or {}).items():
            if v.get("avg_points_allowed") is None:
                continue
            by_pos[pos] = {
                "avg_points_allowed": v["avg_points_allowed"],
                "vs_league_avg_pct": v["vs_league_avg_pct"],
                "rank_easiest": v.get("rank_easiest"),
                "of": v.get("of"),
            }
        teams.append(
            {
                "team": it["team"],
                "confidence": it.get("confidence"),
                "opponents": [
                    {"week": o["week"], "opponent": o.get("opponent"), "is_home": o.get("is_home")}
                    for o in it.get("opponents") or []
                ],
                "by_position": by_pos,
            }
        )
    return {
        "ok": True,
        "status": payload.get("status"),
        "unavailable_reason": payload.get("unavailable_reason"),
        "generated_at": payload.get("generated_at"),
        "season": payload.get("season"),
        "phase": payload.get("phase"),
        "week": payload.get("week"),
        "weeks": (payload.get("requested") or {}).get("weeks"),
        "methodology": payload.get("methodology"),
        "count": len(teams),
        "teams": teams,
    }


def get_public_playoff_sos(
    *, season: int | None = None, start_week: int = DEFAULT_WEEKS[0], end_week: int = DEFAULT_WEEKS[-1], now: datetime | None = None
) -> dict[str, Any]:
    """Cached for an hour per (season, weeks); raises ValueError on a bad week range."""

    clock = external_ad_api.clock_info()
    use_season = int(season) if season is not None else int(clock["season"])
    key = (use_season, start_week, end_week)
    mono = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and mono - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    raw = external_ad_api.endpoint_playoff_sos(
        season=use_season, start_week=start_week, end_week=end_week, position=None, limit=None, now=now or datetime.now(timezone.utc)
    )
    out = project(raw)
    if out["count"]:  # never cache an empty/unavailable answer
        with _lock:
            _cache[key] = (mono, out)
    return out
