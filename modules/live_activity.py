"""Compact live-score snapshot for iOS Live Activities / widgets.

Pure shaping of the payload `_build_matchup` already produces (Sleeper's own
live `points`) into the few fields a lock-screen surface needs. Nothing is
estimated or invented: when either side has no live data yet the snapshot says
so (`available: False` + reason) instead of showing a fake 0-0.
"""

from __future__ import annotations

from typing import Any

_ACTIVE_STATES = {"live", "between_games"}


def _side(side: dict[str, Any] | None) -> dict[str, Any]:
    side = side or {}
    return {
        "team_name": str(side.get("team_name") or ""),
        "points": side.get("real_points") if side.get("has_live_data") else None,
    }


def build_live_activity_snapshot(matchup: dict[str, Any]) -> dict[str, Any]:
    comparison = matchup.get("real_comparison")
    game_state = matchup.get("game_state")
    reason = str(matchup.get("reason") or "")
    available = bool(matchup.get("my_team") and matchup.get("opponent") and comparison)
    if not available and not reason:
        reason = "no_live_data"
    win_prob = matchup.get("win_probability") or {}
    probability = win_prob.get("probability") if win_prob.get("available") else None
    return {
        "ok": True,
        "available": available,
        "reason": "" if available else reason,
        "week": matchup.get("week"),
        "game_state": game_state,
        # Only worth keeping a Live Activity on screen while games are running.
        "should_run": bool(available and game_state in _ACTIVE_STATES),
        "me": _side(matchup.get("my_team")),
        "opponent": _side(matchup.get("opponent")),
        "margin": comparison.get("margin") if comparison else None,
        "win_probability": probability,
    }
