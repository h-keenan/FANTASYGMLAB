"""League maturity and evidence gating.

This module is intentionally presentation-oriented.  It consumes league context that
has already been fetched and scored; it never calls Sleeper and never changes a
player, team, trade, waiver, or draft score.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

import pandas as pd


class LeagueMaturity(str, Enum):
    NEW_STARTUP = "NEW_STARTUP"
    STARTUP_IN_PROGRESS = "STARTUP_IN_PROGRESS"
    EARLY_SEASON = "EARLY_SEASON"
    ACTIVE_SEASON = "ACTIVE_SEASON"
    MATURE_DYNASTY = "MATURE_DYNASTY"


_MATURITY_LABELS = {
    LeagueMaturity.NEW_STARTUP: "New startup",
    LeagueMaturity.STARTUP_IN_PROGRESS: "Startup in progress",
    LeagueMaturity.EARLY_SEASON: "Early season",
    LeagueMaturity.ACTIVE_SEASON: "Active season",
    LeagueMaturity.MATURE_DYNASTY: "Mature dynasty",
}


INSIGHT_REQUIREMENTS: dict[str, dict[str, int]] = {
    "most_active_trader": {"completed_trades": 1},
    "likely_buyers": {"completed_trades": 3, "trade_participants": 2},
    "likely_sellers": {"completed_trades": 3, "trade_participants": 2},
    "trade_tendencies": {"completed_trades": 4, "trade_participants": 2},
    "waiver_tendencies": {"waiver_moves": 3},
    "league_trends": {"games_per_team": 3, "completed_transactions": 4},
}


_REQUIREMENT_LABELS = {
    "completed_trades": "completed trades",
    "trade_participants": "managers involved in trades",
    "waiver_moves": "waiver or free-agent moves",
    "games_per_team": "completed games per team",
    "completed_transactions": "completed transactions",
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _records(frame: Any) -> list[dict[str, Any]]:
    if isinstance(frame, pd.DataFrame):
        return frame.to_dict("records")
    if isinstance(frame, list):
        return [dict(row) for row in frame if isinstance(row, Mapping)]
    return []


def _analysis_totals(frame: Any) -> dict[str, int]:
    rows = _records(frame)
    trade_participations = sum(_safe_int(row.get("trade_count")) for row in rows)
    return {
        # A completed two-team trade appears on two manager rows.  Floor division
        # is deliberately conservative for multi-team or partially observed deals.
        "completed_trades": trade_participations // 2,
        "trade_participants": sum(
            1 for row in rows if _safe_int(row.get("trade_count")) > 0
        ),
        "waiver_moves": sum(_safe_int(row.get("waiver_moves")) for row in rows),
        "completed_transactions": sum(
            _safe_int(row.get("transaction_count")) for row in rows
        ),
    }


def build_league_evidence(
    *,
    startup_context: Mapping[str, Any] | None = None,
    league: Mapping[str, Any] | None = None,
    rosters: list[Mapping[str, Any]] | None = None,
    league_frame: Any = None,
) -> dict[str, Any]:
    """Build sanitized maturity evidence from already-loaded league inputs."""

    startup = dict(startup_context or {})
    league_data = dict(league or {})
    roster_rows = [dict(row) for row in (rosters or []) if isinstance(row, Mapping)]
    analysis = _analysis_totals(league_frame)

    roster_count = len(roster_rows)
    populated_rosters = sum(
        1 for roster in roster_rows if len(roster.get("players") or []) > 0
    )
    population_ratio = (
        populated_rosters / roster_count if roster_count else 0.0
    )

    games_by_team: list[int] = []
    standings_teams = 0
    for roster in roster_rows:
        settings = (
            roster.get("settings")
            if isinstance(roster.get("settings"), Mapping)
            else {}
        )
        games = sum(
            _safe_int(settings.get(key)) for key in ("wins", "losses", "ties")
        )
        games_by_team.append(games)
        if games > 0:
            standings_teams += 1
    games_per_team = max(games_by_team, default=0)
    completed_games = sum(games_by_team) // 2

    league_settings = (
        league_data.get("settings")
        if isinstance(league_data.get("settings"), Mapping)
        else {}
    )
    playoff_week_start = _safe_int(
        league_settings.get("playoff_week_start")
        or league_settings.get("playoff_week")
    )
    playoff_push = bool(
        playoff_week_start > 0
        and games_per_team >= max(1, playoff_week_start - 3)
    )

    draft_status = str(startup.get("draft_status") or "unknown").strip().lower()
    draft_in_progress = bool(startup.get("startup_mode")) or draft_status in {
        "pre_draft",
        "in_progress",
        "paused",
        "drafting",
    }
    draft_completed = bool(startup.get("draft_completed")) or draft_status in {
        "complete",
        "completed",
    }

    evidence: dict[str, Any] = {
        "draft_status": draft_status,
        "draft_in_progress": draft_in_progress,
        "draft_completed": draft_completed,
        "draft_available": bool(startup.get("draft_available")),
        "roster_count": roster_count,
        "populated_rosters": populated_rosters,
        "roster_population_ratio": round(population_ratio, 4),
        "completed_games": completed_games,
        "games_per_team": games_per_team,
        "standings_teams": standings_teams,
        "has_previous_season": bool(
            league_data.get("previous_league_id")
            or league_data.get("previous_league")
        ),
        "playoff_push": playoff_push,
        **analysis,
    }
    maturity = classify_league_maturity(evidence)
    evidence["maturity"] = maturity.value
    evidence["maturity_label"] = _MATURITY_LABELS[maturity]
    evidence["dashboard_phase"] = dashboard_phase(evidence)
    return evidence


def classify_league_maturity(evidence: Mapping[str, Any]) -> LeagueMaturity:
    if bool(evidence.get("draft_in_progress")):
        return LeagueMaturity.STARTUP_IN_PROGRESS

    roster_count = _safe_int(evidence.get("roster_count"))
    population_ratio = _safe_float(evidence.get("roster_population_ratio"))
    if roster_count and population_ratio < 0.5:
        return LeagueMaturity.STARTUP_IN_PROGRESS

    games_per_team = _safe_int(evidence.get("games_per_team"))
    completed_trades = _safe_int(evidence.get("completed_trades"))
    waiver_moves = _safe_int(evidence.get("waiver_moves"))
    completed_transactions = _safe_int(evidence.get("completed_transactions"))
    has_activity = any(
        (games_per_team, completed_trades, waiver_moves, completed_transactions)
    )

    if bool(evidence.get("has_previous_season")):
        return LeagueMaturity.MATURE_DYNASTY
    if roster_count and population_ratio >= 0.5 and not has_activity:
        return LeagueMaturity.NEW_STARTUP
    if games_per_team <= 3 and completed_transactions < 6:
        return LeagueMaturity.EARLY_SEASON
    return LeagueMaturity.ACTIVE_SEASON


def dashboard_phase(evidence: Mapping[str, Any]) -> str:
    maturity = str(evidence.get("maturity") or "")
    if maturity in {
        LeagueMaturity.NEW_STARTUP.value,
        LeagueMaturity.STARTUP_IN_PROGRESS.value,
    }:
        return "startup"
    if bool(evidence.get("playoff_push")):
        return "playoff_push"
    if maturity == LeagueMaturity.EARLY_SEASON.value:
        return "early_season"
    return "in_season"


def evidence_status(
    insight_key: str,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    requirements = INSIGHT_REQUIREMENTS.get(insight_key, {})
    observed = dict(evidence or {})
    missing: list[str] = []
    for field, minimum in requirements.items():
        if _safe_int(observed.get(field)) < minimum:
            missing.append(f"{minimum} {_REQUIREMENT_LABELS.get(field, field)}")

    if not missing:
        return {
            "available": True,
            "insight": insight_key,
            "requirements": dict(requirements),
            "message": "",
        }
    joined = ", ".join(missing)
    return {
        "available": False,
        "insight": insight_key,
        "requirements": dict(requirements),
        "message": (
            "Not enough league history yet. This insight appears after the "
            f"league records at least {joined}."
        ),
    }


def insight_is_available(
    insight_key: str,
    evidence: Mapping[str, Any] | None,
) -> bool:
    return bool(evidence_status(insight_key, evidence).get("available"))


def _strategy_key(row: Mapping[str, Any]) -> str:
    return str(row.get("strategy") or row.get("mode") or "").strip().lower()


def _pick_row(
    frame: pd.DataFrame,
    column: str,
    *,
    ascending: bool,
    mask: pd.Series | None = None,
) -> pd.Series | None:
    if frame.empty or column not in frame.columns:
        return None
    working = frame.loc[mask].copy() if mask is not None else frame.copy()
    if working.empty:
        return None
    working["_maturity_metric"] = pd.to_numeric(
        working[column], errors="coerce"
    )
    working = working.dropna(subset=["_maturity_metric"])
    if working.empty:
        return None
    sort_columns = ["_maturity_metric"]
    ascending_values = [ascending]
    if "team_name" in working.columns:
        sort_columns.append("team_name")
        ascending_values.append(True)
    return working.sort_values(
        sort_columns, ascending=ascending_values
    ).iloc[0]


def _startup_insight(
    label: str,
    row: pd.Series | None,
    metric: str,
    evidence: str,
    *,
    tone: str = "strength",
) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "label": label,
        "value": str(row.get("team_name") or "Team"),
        "note": evidence,
        "metric": metric,
        "tone": tone,
        "roster_id": str(row.get("roster_id") or ""),
        "evidence_basis": "current_roster_only",
    }


def build_startup_roster_insights(
    league_frame: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    """Create post-startup observations only from existing roster score fields."""

    if league_frame is None or league_frame.empty:
        return []
    frame = league_frame.copy()
    insights: list[dict[str, Any] | None] = []

    strongest_column = (
        "power_score" if "power_score" in frame.columns else "total_score"
    )
    strongest = _pick_row(frame, strongest_column, ascending=False)
    insights.append(
        _startup_insight(
            "Strongest Roster After the Draft",
            strongest,
            strongest_column,
            f"Highest existing {strongest_column.replace('_', ' ')}.",
        )
    )

    strategy = frame.apply(_strategy_key, axis=1)
    contender_mask = strategy.isin({"contender", "fringe_contender"})
    youngest = _pick_row(
        frame, "avg_age", ascending=True, mask=contender_mask
    )
    oldest = _pick_row(
        frame, "avg_age", ascending=False, mask=contender_mask
    )
    insights.extend(
        [
            _startup_insight(
                "Youngest Contender",
                youngest,
                "avg_age",
                f"Contender-tagged roster with the lowest current average age ({_safe_float(youngest.get('avg_age')):.1f})."
                if youngest is not None
                else "",
                tone="opportunity",
            ),
            _startup_insight(
                "Oldest Contender",
                oldest,
                "avg_age",
                f"Contender-tagged roster with the highest current average age ({_safe_float(oldest.get('avg_age')):.1f})."
                if oldest is not None
                else "",
                tone="risk",
            ),
        ]
    )

    specs = [
        ("Highest Future Draft Capital", "draft_capital", False, "opportunity"),
        ("Best QB Room", "qb_score", False, "strength"),
        ("Best RB Room", "rb_score", False, "strength"),
        ("Best WR Room", "wr_score", False, "strength"),
        ("Best TE Room", "te_score", False, "strength"),
        ("Deepest Bench", "bench_score", False, "strength"),
        ("Highest Upside Roster", "rebuild_index", False, "opportunity"),
        ("Most Win-Now Roster", "power_rank", True, "power"),
        ("Most Concentrated Roster Value", "top_heavy_ratio", False, "risk"),
        ("Biggest Sleeper Roster", "undervalued_gap", False, "opportunity"),
    ]
    for label, column, ascending, tone in specs:
        row = _pick_row(frame, column, ascending=ascending)
        insights.append(
            _startup_insight(
                label,
                row,
                column,
                (
                    f"Leads the league on the existing {column.replace('_', ' ')} "
                    "measure from current roster construction."
                ),
                tone=tone,
            )
        )

    position_columns = [
        column for column in ("qb_score", "rb_score", "wr_score", "te_score")
        if column in frame.columns
    ]
    if len(position_columns) >= 3:
        balance = frame[position_columns].apply(
            pd.to_numeric, errors="coerce"
        ).rank(pct=True)
        frame["_startup_balance_spread"] = balance.max(axis=1) - balance.min(axis=1)
        balanced = _pick_row(
            frame, "_startup_balance_spread", ascending=True
        )
        insights.append(
            _startup_insight(
                "Most Balanced Roster",
                balanced,
                "positional_score_spread",
                "Smallest percentile spread across the existing QB, RB, WR, and TE room scores.",
                tone="franchise",
            )
        )

    rebuild_mask = strategy.isin({"rebuild", "tank", "retool"})
    rebuild_column = (
        "rebuild_index" if "rebuild_index" in frame.columns else "franchise_score"
    )
    rebuild = _pick_row(
        frame, rebuild_column, ascending=False, mask=rebuild_mask
    )
    insights.append(
        _startup_insight(
            "Biggest Rebuild Candidate",
            rebuild,
            rebuild_column,
            (
                f"Highest existing {rebuild_column.replace('_', ' ')} among "
                "rosters already classified on a rebuild or retool timeline."
            ),
            tone="risk",
        )
    )

    return [insight for insight in insights if insight is not None]


def trade_partner_evidence(
    idea: Mapping[str, Any],
    *,
    historical_evidence_available: bool,
) -> dict[str, str]:
    """Choose a truthful partner explanation without changing idea selection."""

    current_reason = ""
    for field in (
        "hub_partner_reason",
        "reasoning_summary",
        "fit_summary",
        "market_realism_summary",
    ):
        value = str(idea.get(field) or "").strip()
        if value:
            current_reason = value
            break
    if not current_reason:
        current_reason = (
            "This partner owns the displayed return package; no stronger "
            "behavioral conclusion is available yet."
        )
    return {
        "reason": current_reason,
        "basis": (
            "Current roster construction and completed transaction history"
            if historical_evidence_available
            else "Current roster construction and package fit"
        ),
    }
