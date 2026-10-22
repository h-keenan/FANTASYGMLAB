"""Keeper-league support: who is kept, at what round, and the surplus value.

Only uses what Sleeper actually exposes:
  * ``roster["keepers"]``      - the player ids a team has declared as keepers.
  * draft picks ``is_keeper``  - the draft round a keeper was assigned to.
  * previous-season draft      - the round a player was originally drafted in.
  * ``settings.max_keepers``   - the keeper count (checked against the data).

Sleeper has no machine-readable keeper *cost rule* (round penalties live in the
league description text), so the cost round is an estimate: the player's last
draft round, shifted by an optional user-chosen ``round_penalty``. Surplus is
player value minus the typical value of a player taken at that round, derived
from the league's own value ranking. Both are estimates and labelled as such.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

MAX_ROUND_PENALTY = 3


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def slot_value(sorted_values: list[float], round_no: int, num_teams: int) -> float:
    """Typical value of the player taken mid-round ``round_no`` (1-based)."""
    if not sorted_values or round_no < 1 or num_teams < 1:
        return 0.0
    idx = min((round_no - 1) * num_teams + num_teams // 2, len(sorted_values) - 1)
    return float(sorted_values[idx])


def latest_draft_picks(drafts: list[Mapping[str, Any]], fetch_picks) -> list[dict[str, Any]]:
    """Picks of the most recent draft that has any (drafts are newest-first by season)."""
    ordered = sorted(drafts or [], key=lambda d: str(d.get("season") or ""), reverse=True)
    for draft in ordered:
        picks = fetch_picks(str(draft.get("draft_id") or ""))
        if picks:
            return list(picks)
    return []


def _observed_keeper_count(picks: list[Mapping[str, Any]]) -> int:
    per_roster: dict[str, int] = {}
    for pick in picks:
        if pick.get("is_keeper"):
            key = str(pick.get("roster_id"))
            per_roster[key] = per_roster.get(key, 0) + 1
    return max(per_roster.values(), default=0)


def resolve_keep_count(
    max_keepers: Any, previous_picks: list[Mapping[str, Any]], declared: int
) -> tuple[int, str]:
    """Baseline number of keepers and where it came from."""
    setting = _int(max_keepers)
    observed = _observed_keeper_count(previous_picks)
    if observed and setting != observed and (setting <= 0 or setting < observed):
        return observed, "previous_draft"
    if setting > 0:
        return setting, "league_setting"
    if declared:
        return declared, "declared_keepers"
    return 0, "unknown"


def build_keeper_report(
    *,
    roster: Mapping[str, Any],
    valued: pd.DataFrame,
    score_field: str,
    num_teams: int,
    max_keepers: Any,
    current_picks: list[Mapping[str, Any]],
    previous_picks: list[Mapping[str, Any]],
    round_penalty: int = 0,
) -> dict[str, Any]:
    round_penalty = max(0, min(MAX_ROUND_PENALTY, _int(round_penalty)))
    declared = [str(p) for p in (roster.get("keepers") or []) if p]
    roster_id = str(roster.get("roster_id") or "")
    roster_ids = {str(p) for p in (roster.get("players") or []) if p}

    if valued is None or valued.empty or score_field not in valued.columns:
        return {"players": {}, "candidates": [], "recommended_ids": [], "keep_count": 0}
    frame = valued.copy()
    frame["_pid"] = frame["player_id"].astype(str)
    frame["_val"] = pd.to_numeric(frame[score_field], errors="coerce").fillna(0.0)
    sorted_values = sorted(frame["_val"].tolist(), reverse=True)
    by_id = {row["_pid"]: row for _, row in frame.iterrows()}

    kept_round_now = {
        str(p.get("player_id")): _int(p.get("round"))
        for p in current_picks
        if p.get("is_keeper") and str(p.get("roster_id")) == roster_id
    }
    last_round = {str(p.get("player_id")): _int(p.get("round")) for p in previous_picks if p.get("player_id")}

    keep_count, basis = resolve_keep_count(max_keepers, previous_picks, len(declared))

    players: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    for pid in sorted(roster_ids | set(declared)):
        row = by_id.get(pid)
        value = float(row["_val"]) if row is not None else None
        kept_round = kept_round_now.get(pid) or None
        drafted_round = last_round.get(pid) or None
        cost_round, source = None, None
        if kept_round:
            cost_round, source = kept_round, "keeper_pick"
        elif drafted_round:
            cost_round, source = max(1, drafted_round - round_penalty), "last_draft_round"
        surplus = None
        if value is not None and cost_round:
            surplus = int(round(value - slot_value(sorted_values, cost_round, num_teams)))
        info = {
            "is_keeper": pid in declared or pid in kept_round_now,
            "kept_round": kept_round,
            "cost_round": cost_round,
            "cost_source": source,
            "surplus": surplus,
        }
        players[pid] = info
        if row is not None and pid in roster_ids and surplus is not None:
            candidates.append(
                {
                    "player_id": pid,
                    "name": str(row.get("name") or pid),
                    "position": str(row.get("position") or ""),
                    "team": str(row.get("team") or ""),
                    "value": int(round(value)),
                    "cost_round": cost_round,
                    "cost_source": source,
                    "surplus": surplus,
                    "is_keeper": info["is_keeper"],
                    "reason": _reason(cost_round, source, surplus, round_penalty),
                }
            )
    candidates.sort(key=lambda c: c["surplus"], reverse=True)
    recommended = [c["player_id"] for c in candidates[:keep_count] if c["surplus"] > 0]
    return {
        "players": players,
        "candidates": candidates[:12],
        "recommended_ids": recommended,
        "keep_count": keep_count,
        "keep_count_basis": basis,
        "round_penalty": round_penalty,
        "unpriced_count": len([p for p in roster_ids if players[p]["cost_round"] is None]),
    }


def _reason(cost_round: int, source: str, surplus: int, penalty: int) -> str:
    where = f"kept at round {cost_round}" if source == "keeper_pick" else (
        f"est. cost round {cost_round} (drafted there last year" + (f", -{penalty}" if penalty else "") + ")"
    )
    verdict = "worth more than a pick there" if surplus > 0 else "a pick there is worth more"
    return f"{where}; {verdict} ({surplus:+d})"
