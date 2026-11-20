"""League-wide matchups list: the pure presentation helpers.

The endpoint (services.mobile_api_service.get_league_matchups) reuses the
per-matchup computation GET /matchup already runs (real lineup + live points,
blended projected total, win probability); this module only shapes each pair for
the compact league card and formats the streak, so the formatting is testable
without Sleeper.
"""

from __future__ import annotations

from typing import Any

MAX_WEEK = 18


def streak_badge_label(current_streak: Any) -> str:
    """+3 -> "▲3W", -2 -> "▼2L", 0 / unknown -> "" (no streak to show)."""

    try:
        n = int(current_streak or 0)
    except (TypeError, ValueError):
        return ""
    if n > 0:
        return f"▲{n}W"
    if n < 0:
        return f"▼{abs(n)}L"
    return ""


def _points(value: Any) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def side_payload(
    roster_id: str,
    standing: dict[str, Any] | None,
    streaks: dict[int, dict[str, int]],
    *,
    real_points: Any,
    entry_points: Any,
    has_live_data: bool,
    projected_total: Any,
    win_probability: Any,
    is_mine: bool,
) -> dict[str, Any]:
    """One side of a pair: identity, record, streak, standing, live points, projection, win chance."""

    row = standing or {}
    try:
        streak = int((streaks.get(int(roster_id)) or {}).get("current_streak") or 0)
    except (TypeError, ValueError):
        streak = 0
    rank = row.get("standing_rank")
    points = _points(real_points) if has_live_data else None
    if points is None and has_live_data:
        points = _points(entry_points)
    return {
        "roster_id": str(roster_id),
        "team_name": row.get("team_name") or "Team",
        "owner_name": row.get("owner_username") or row.get("owner_name") or "",
        "avatar_url": row.get("avatar_url") or "",
        "record_label": row.get("record_label") or "",
        "streak": streak,
        "streak_label": streak_badge_label(streak),
        "standing_rank": int(rank) if rank is not None else None,
        "points": points,
        "projected_total": _points(projected_total),
        "win_probability": None if win_probability is None else round(float(win_probability), 4),
        "is_mine": is_mine,
    }
