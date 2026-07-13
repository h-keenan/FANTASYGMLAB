from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd


FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
INELIGIBLE_STATUS_TERMS = {
    "retired",
    "inactive",
    "not active",
    "historical",
    "historical only",
    "deceased",
    "invalid",
}
CURRENT_STATUS_TERMS = {
    "active",
    "free agent",
    "free_agent",
    "unsigned",
    "practice squad",
    "injured reserve",
    "ir",
    "pup",
    "nfi",
    "out",
    "questionable",
    "doubtful",
}
FREE_AGENT_TEAM_MARKERS = {"", "FA", "FREE AGENT", "FREE_AGENT", "NONE", "N/A", "NA"}
NEWS_FRESHNESS_DAYS = 730


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "active"}:
        return True
    if text in {"0", "false", "no", "n", "inactive"}:
        return False
    try:
        return bool(int(float(text)))
    except (TypeError, ValueError):
        return None


def _safe_number(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _news_timestamp_seconds(value: Any) -> float | None:
    timestamp = _safe_number(value)
    if timestamp is None or timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000.0
    return timestamp


def _fantasy_positions(row: Mapping[str, Any]) -> set[str]:
    value = row.get("fantasy_positions")
    if isinstance(value, (list, tuple, set)):
        positions = {_safe_text(item).upper() for item in value}
    else:
        text = _safe_text(value)
        for separator in ("|", ",", ";"):
            text = text.replace(separator, " ")
        text = text.strip("[](){}").replace('"', "").replace("'", "")
        positions = {part.upper() for part in text.split() if part}
    position = _safe_text(row.get("position")).upper()
    if position:
        positions.add(position)
    return positions & FANTASY_POSITIONS


def player_eligibility(
    row: Mapping[str, Any] | pd.Series,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return current fantasy-pool eligibility from status plus corroborating current signals."""
    now = now or datetime.now(timezone.utc)
    status = _safe_text(row.get("status")).casefold()
    active = _optional_bool(row.get("active"))
    sport = _safe_text(row.get("sport")).casefold()
    positions = _fantasy_positions(row)

    if sport and sport != "nfl":
        return {"eligible": False, "reason": "non_nfl_record", "current_signal": False}
    if not positions:
        return {"eligible": False, "reason": "invalid_fantasy_position", "current_signal": False}
    if active is False:
        return {"eligible": False, "reason": "explicitly_inactive", "current_signal": False}
    if any(term in status for term in INELIGIBLE_STATUS_TERMS):
        return {"eligible": False, "reason": "retired_or_inactive_status", "current_signal": False}

    years_exp = _safe_number(row.get("years_exp"))
    rookie = active is True and years_exp is not None and years_exp <= 1

    news_timestamp = _news_timestamp_seconds(row.get("news_updated"))
    recent_news = bool(
        news_timestamp
        and (now.timestamp() - news_timestamp) <= NEWS_FRESHNESS_DAYS * 24 * 60 * 60
    )
    depth_order = _safe_number(row.get("depth_chart_order"), 0) or 0
    depth_position = _safe_text(row.get("depth_chart_position"))
    current_depth = bool(depth_position or depth_order > 0)

    stats_season = _safe_number(row.get("stats_season"))
    current_stats = bool(stats_season and stats_season >= now.year - 1)
    fantasycalc_value = _safe_number(row.get("fantasycalc_value"), 0) or 0
    current_market = fantasycalc_value > 0
    current_signal = bool(recent_news or current_depth or current_stats or current_market or rookie)

    status_is_current = status in CURRENT_STATUS_TERMS
    if active is True and current_signal:
        reason = "current_rookie" if rookie else "corroborated_current_player"
        return {"eligible": True, "reason": reason, "current_signal": True}
    if status_is_current and current_signal:
        return {"eligible": True, "reason": "corroborated_current_status", "current_signal": True}

    return {
        "eligible": False,
        "reason": "missing_current_player_corroboration",
        "current_signal": current_signal,
    }


def annotate_player_eligibility(
    players: pd.DataFrame,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    if players is None:
        return pd.DataFrame()
    annotated = players.copy()
    if annotated.empty:
        annotated["is_current_fantasy_eligible"] = pd.Series(dtype="bool")
        annotated["player_eligibility_reason"] = pd.Series(dtype="object")
        return annotated
    evaluations = [player_eligibility(row, now=now) for _, row in annotated.iterrows()]
    annotated["is_current_fantasy_eligible"] = [
        bool(evaluation["eligible"]) for evaluation in evaluations
    ]
    annotated["player_eligibility_reason"] = [
        str(evaluation["reason"]) for evaluation in evaluations
    ]
    return annotated


def eligibility_diagnostics(players: pd.DataFrame) -> dict[str, int]:
    if players is None or players.empty:
        return {
            "input_count": 0,
            "eligible_count": 0,
            "removed_retired_or_inactive": 0,
            "retained_current_free_agents": 0,
        }
    annotated = (
        players
        if "is_current_fantasy_eligible" in players.columns
        and "player_eligibility_reason" in players.columns
        else annotate_player_eligibility(players)
    )
    eligible = annotated["is_current_fantasy_eligible"].fillna(False).astype(bool)
    team = annotated.get(
        "team",
        pd.Series("", index=annotated.index, dtype="object"),
    ).fillna("").astype(str).str.strip().str.upper()
    reasons = annotated["player_eligibility_reason"].fillna("").astype(str)
    return {
        "input_count": int(len(annotated)),
        "eligible_count": int(eligible.sum()),
        "removed_retired_or_inactive": int(
            (
                ~eligible
                & reasons.isin(
                    {
                        "explicitly_inactive",
                        "retired_or_inactive_status",
                        "missing_current_player_corroboration",
                    }
                )
            ).sum()
        ),
        "retained_current_free_agents": int(
            (eligible & team.isin(FREE_AGENT_TEAM_MARKERS)).sum()
        ),
    }


def filter_current_fantasy_players(
    players: pd.DataFrame,
    *,
    surface: str = "",
    now: datetime | None = None,
) -> pd.DataFrame:
    """Filter before ranking while preserving the original order of eligible rows."""
    annotated = annotate_player_eligibility(players, now=now)
    diagnostics = eligibility_diagnostics(annotated)
    try:
        from modules import performance

        if performance.debug_enabled():
            payload = {
                "surface": str(surface or "decision_pool")[:64],
                **diagnostics,
            }
            print(
                "DYNASTYGM_PLAYER_ELIGIBILITY " + json.dumps(payload, sort_keys=True),
                flush=True,
            )
    except Exception:
        pass
    if annotated.empty:
        return annotated
    return annotated[
        annotated["is_current_fantasy_eligible"].fillna(False).astype(bool)
    ].copy()
