"""Real per-roster current win/loss streak, derived entirely from actual
weekly Sleeper matchup results.

Extracted from app.py's inline `season_results`/streak computation (built
for the weekly Streamlit recap's "Hottest Team" / "Coldest Team" / "Win
Streaks" / "Losing Streaks" callouts, ~app.py 14792-14821) into a shared
module so mobile (services/mobile_api_service.py) can surface the same real
signal as a Teams-screen badge without re-deriving the week-by-week
matchup-pairing logic a second time. Reuses modules.league_recaps' existing
history-window and matchup-flattening helpers (`league_history_window`,
`build_matchup_history_rows` — already extracted from app.py's own
`cached_matchup_history_frame`) rather than re-scanning Sleeper's raw
matchup shape again.

app.py's own inline computation is left as-is (not switched over to call
this module) — this is additive, not a refactor of the Streamlit recap
path, to keep this change's blast radius limited to "give mobile the same
signal."
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from modules import league_recaps, sleeper


def _safe_positive_int(value: Any, default: int = 0) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def league_current_streaks(league_id: str) -> dict[int, dict[str, int]]:
    """roster_id -> {current_streak, wins_last_three, losses_last_three}.

    `current_streak` is positive for an active win streak, negative for an
    active losing streak, 0 with no streak (including when the most recent
    result was a tie). Same pairing/streak algorithm as app.py's
    `season_results` computation: within each week, matchup rows sharing a
    `matchup_id` are paired off (ties never start or extend a streak).
    """

    if not league_id:
        return {}
    league = sleeper.get_league(league_id)
    if not league:
        return {}

    _, _, max_history_week = league_recaps.league_history_window(league)
    rows = league_recaps.build_matchup_history_rows(
        league_id, max_history_week, fetch_matchups=sleeper.get_matchups
    )

    by_week: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for row in rows:
        week = _safe_positive_int(row.get("week"), 0)
        matchup_id = _safe_positive_int(row.get("matchup_id"), 0)
        if week <= 0 or matchup_id <= 0:
            continue
        by_week.setdefault(week, {}).setdefault(matchup_id, []).append(row)

    season_results: dict[int, list[dict[str, Any]]] = {}
    for week in sorted(by_week):
        for matchup_rows in by_week[week].values():
            if len(matchup_rows) < 2:
                continue
            ordered = sorted(
                matchup_rows,
                key=lambda r: (-_safe_float(r.get("points"), 0.0), _safe_positive_int(r.get("roster_id"), 0)),
            )[:2]
            team_a, team_b = ordered[0], ordered[1]
            score_a = _safe_float(team_a.get("points"), 0.0)
            score_b = _safe_float(team_b.get("points"), 0.0)
            roster_a = _safe_positive_int(team_a.get("roster_id"), 0)
            roster_b = _safe_positive_int(team_b.get("roster_id"), 0)
            if roster_a <= 0 or roster_b <= 0:
                continue
            if score_a > score_b:
                result_a, result_b = "W", "L"
            elif score_b > score_a:
                result_a, result_b = "L", "W"
            else:
                result_a = result_b = "T"
            season_results.setdefault(roster_a, []).append({"week": week, "result": result_a})
            season_results.setdefault(roster_b, []).append({"week": week, "result": result_b})

    streaks: dict[int, dict[str, int]] = {}
    for roster_id, results in season_results.items():
        ordered_results = sorted(results, key=lambda item: int(item.get("week") or 0))
        wins_last_three = sum(1 for item in ordered_results[-3:] if item.get("result") == "W")
        losses_last_three = sum(1 for item in ordered_results[-3:] if item.get("result") == "L")
        streak = 0
        if ordered_results:
            last_result = ordered_results[-1].get("result")
            if last_result in {"W", "L"}:
                streak = 1 if last_result == "W" else -1
                for item in reversed(ordered_results[:-1]):
                    if item.get("result") != last_result:
                        break
                    streak += 1 if last_result == "W" else -1
        streaks[roster_id] = {
            "current_streak": streak,
            "wins_last_three": wins_last_three,
            "losses_last_three": losses_last_three,
        }
    return streaks


# A judgment call, documented per the audit's instructions: the weekly
# Streamlit recap highlights ANY active streak (even a single win/loss) as
# "hottest"/"coldest" because that's a one-week highlight reel. A Teams-
# screen badge is persistent (shown every time the screen loads, not just
# in a weekly recap), so a single result isn't enough signal to brand a
# team all week — this requires at least 2 consecutive results.
MIN_STREAK_FOR_BADGE = 2


def classify_streak_badge(current_streak: int, *, min_streak: int = MIN_STREAK_FOR_BADGE) -> str | None:
    """"Hot Streak" / "Cold Streak" team badge off a real current win/loss
    streak. See MIN_STREAK_FOR_BADGE's comment for the threshold's
    rationale."""

    if current_streak >= min_streak:
        return "Hot Streak"
    if current_streak <= -min_streak:
        return "Cold Streak"
    return None


# Same 30-minute cache idiom modules.manager_activity/team_trade_history use
# — real matchup results only change once games finish for the week.
TEAM_STREAKS_TTL_SECONDS = 30 * 60


def _team_streaks_cache_bucket() -> int:
    return int(time.time() // TEAM_STREAKS_TTL_SECONDS)


@lru_cache(maxsize=64)
def _league_current_streaks_cached(league_id: str, _bucket: int) -> dict[int, dict[str, int]]:
    return league_current_streaks(league_id)


def league_current_streaks_cached(league_id: str) -> dict[int, dict[str, int]]:
    """Cached front door for `league_current_streaks` — shares one
    (league_id) cache key across callers within the same 30-minute window
    instead of each re-scanning the season's matchups."""

    return _league_current_streaks_cached(league_id, _team_streaks_cache_bucket())


def clear_team_streaks_cache() -> None:
    """Test/refresh hook — mirrors manager_activity's own cache-clear."""

    _league_current_streaks_cached.cache_clear()
