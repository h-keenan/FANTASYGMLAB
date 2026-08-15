"""Presentation-only league comparison models for tappable metric tiles."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ComparisonRow:
    roster_id: str
    team_name: str
    manager_name: str
    value: float
    rank: int
    active: bool
    avatar_url: str = ""


@dataclass(frozen=True)
class MetricComparison:
    metric_key: str
    title: str
    active_value: float
    active_rank: int
    league_baseline: float
    delta: float
    rows: tuple[ComparisonRow, ...]
    interpretation: str
    value_suffix: str = ""
    decimals: int = 1


def build_metric_comparison(
    frame: pd.DataFrame,
    *,
    metric_key: str,
    title: str,
    active_roster_id: object,
    ascending: bool,
    interpretation: str,
    value_suffix: str = "",
    decimals: int = 1,
    baseline: str = "median",
) -> MetricComparison | None:
    """Normalize existing league metrics without recalculating football inputs."""

    if frame is None or frame.empty or metric_key not in frame.columns:
        return None
    working = frame.copy()
    working["_comparison_value"] = pd.to_numeric(working[metric_key], errors="coerce")
    working = working[working["_comparison_value"].notna()].copy()
    if working.empty:
        return None
    working["_roster_id"] = working.get(
        "roster_id", pd.Series("", index=working.index)
    ).astype(str)
    active_id = str(active_roster_id)
    if not working["_roster_id"].eq(active_id).any():
        return None
    team_names = working.get("team_name", pd.Series("", index=working.index)).fillna("").astype(str)
    owner_names = working.get("owner_name", pd.Series("Team", index=working.index)).fillna("Team").astype(str)
    working["_team_name"] = team_names.where(team_names.str.strip().ne(""), owner_names)
    working = working.sort_values(
        ["_comparison_value", "_team_name", "_roster_id"],
        ascending=[ascending, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    working["_comparison_rank"] = range(1, len(working) + 1)
    baseline_value = (
        float(working["_comparison_value"].mean())
        if baseline == "average"
        else float(working["_comparison_value"].median())
    )
    rows = tuple(
        ComparisonRow(
            roster_id=str(row["_roster_id"]),
            team_name=str(row["_team_name"]),
            manager_name=str(row.get("owner_username") or row.get("owner_name") or "Manager"),
            value=float(row["_comparison_value"]),
            rank=int(row["_comparison_rank"]),
            active=str(row["_roster_id"]) == active_id,
            avatar_url=_row_avatar_url(row),
        )
        for _, row in working.iterrows()
    )
    active_row = next(row for row in rows if row.active)
    return MetricComparison(
        metric_key=metric_key,
        title=title,
        active_value=active_row.value,
        active_rank=active_row.rank,
        league_baseline=baseline_value,
        delta=active_row.value - baseline_value,
        rows=rows,
        interpretation=interpretation,
        value_suffix=value_suffix,
        decimals=decimals,
    )


def team_initials(name: str) -> str:
    parts = [part for part in str(name or "").replace("_", " ").split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "GM"


def _row_avatar_url(row) -> str:
    try:
        value = row.get("avatar_url")
    except Exception:
        value = ""
    return str(value or "").strip()


def _format(comparison: MetricComparison, value: float) -> str:
    return f"{value:,.{comparison.decimals}f}{comparison.value_suffix}"


def comparison_payload(comparison: MetricComparison | None) -> dict | None:
    if comparison is None or not comparison.rows:
        return None
    league_size = len(comparison.rows)
    return {
        "metric_key": comparison.metric_key,
        "active_value": _format(comparison, comparison.active_value),
        "active_rank": comparison.active_rank,
        "league_size": league_size,
        "rank_summary": f"Your rank: #{comparison.active_rank} of {league_size}",
        "league_baseline": _format(comparison, comparison.league_baseline),
        "delta": _format(comparison, comparison.delta),
        "interpretation": comparison.interpretation,
        "rows": [
            {
                "title": row.team_name,
                "kicker": "YOUR TEAM" if row.active else "",
                "value": _format(comparison, row.value),
                "note": (
                    f"#{row.rank} · My team"
                    if row.active
                    else f"#{row.rank} · {row.manager_name}"
                ),
                "current": row.active,
                "avatar_url": row.avatar_url,
                "avatar_initials": team_initials(row.team_name),
                "rank": row.rank,
            }
            for row in comparison.rows
        ],
        "youngest": comparison.rows[0].team_name if comparison.metric_key == "avg_age" else "",
        "oldest": comparison.rows[-1].team_name if comparison.metric_key == "avg_age" else "",
    }


def dashboard_comparison_payloads(
    frame: pd.DataFrame, active_roster_id: object
) -> dict[str, dict]:
    """Build comparisons only from league metrics already computed upstream."""

    specs = {
        "Average Age": {
            "metric_key": "avg_age",
            "ascending": True,
            "decimals": 1,
            "baseline": "average",
            "interpretation": "Age is roster direction context, not a standalone grade. Compare the gap with your current competitive window before moving core value.",
        },
        "Starter Strength": {
            "metric_key": "starter_score",
            "ascending": False,
            "decimals": 0,
            "interpretation": "Starter strength reflects the existing projected-lineup score. A lower league position points to a starting-slot upgrade before depth consolidation.",
        },
        "Bench Strength": {
            "metric_key": "bench_score",
            "ascending": False,
            "decimals": 0,
            "interpretation": "Bench strength compares usable depth under the current lineup model. Read it alongside starter strength before trading away insulation.",
        },
        "Health": {
            "metric_key": "injury_impact_score",
            "ascending": True,
            "decimals": 0,
            "interpretation": "Lower injury impact is better. This is current availability context and should not be treated as a change to long-term player value.",
        },
        "Power Rank": {
            "metric_key": "power_score",
            "ascending": False,
            "decimals": 0,
            "interpretation": "Power compares current lineup and depth strength using the existing league evaluation.",
        },
        "Franchise Rank": {
            "metric_key": "franchise_score",
            "ascending": False,
            "decimals": 0,
            "interpretation": "Franchise rank compares the existing total asset-base score across the league.",
        },
        "Draft Capital": {
            "metric_key": "draft_capital",
            "ascending": False,
            "decimals": 0,
            "interpretation": "Draft capital compares the existing value of owned future picks.",
        },
    }
    payloads: dict[str, dict] = {}
    for label, spec in specs.items():
        comparison = build_metric_comparison(
            frame,
            title=label,
            active_roster_id=active_roster_id,
            **spec,
        )
        payload = comparison_payload(comparison)
        if payload:
            payloads[label] = payload
    return payloads
