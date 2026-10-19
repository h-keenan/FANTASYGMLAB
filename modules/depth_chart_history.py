"""Week-over-week depth-chart-order snapshots.

coridian_, 2026-10-19: "was there any way for us to predict (scenario)
something like cam skattebo having 0 snaps and relaying that to USERS?" A
pure coaching-decision role change (a healthy scratch, a benching) has no
injury signal at all, so nothing in modules.rankings' injury/status reads
can catch it. But Sleeper's own depth_chart_order field often moves days
before that kind of change becomes visible any other way -- and nothing in
this app tracked that value over time before this; it was read live
(modules.rankings.normalize_player_record) and overwritten every 6 hours
with zero history (modules.rankings.build_players_table).

Modeled directly on app.py's own _load_weekly_rank_snapshots /
_write_weekly_rank_snapshots / build_weekly_rank_movement pattern -- the
existing week-over-week snapshot mechanism for roster power rank -- but
player-keyed instead of league/roster-keyed, since depth chart position has
no fantasy-league scope at all.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import pandas as pd

DEPTH_CHART_SNAPSHOT_PATH = os.path.join("data", "depth_chart_snapshots.json")

# How many most-recent week buckets to keep -- enough for a real
# week-over-week comparison without the file growing unbounded.
RETAINED_WEEKS = 8


def _current_week_key(now: time.struct_time | None = None) -> str:
    current = now or time.gmtime()
    return time.strftime("%Y-W%W", current)


def load_depth_chart_snapshots(path: str = DEPTH_CHART_SNAPSHOT_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_depth_chart_snapshots(data: dict, path: str = DEPTH_CHART_SNAPSHOT_PATH) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=True, indent=2, sort_keys=True)
    except Exception:
        return


def record_depth_chart_snapshot(
    players_df: pd.DataFrame,
    *,
    path: str = DEPTH_CHART_SNAPSHOT_PATH,
    week_key: str | None = None,
) -> pd.DataFrame:
    """Diff this run's depth_chart_order against the most recent PRIOR
    week's snapshot, add 'depth_chart_order_delta' (positive = moved up
    the depth chart, e.g. 2 -> 1; 0 when no prior data exists for a
    player, including the very first run ever), then persist this week's
    values for the next comparison.

    Fails soft on a corrupt/unreadable snapshot file (treated as empty
    history) -- never raises, always returns players_df with the new
    column added.
    """

    out = players_df.copy()
    if out.empty or "player_id" not in out.columns:
        out["depth_chart_order_delta"] = pd.Series(dtype="int64")
        return out

    current_week = week_key or _current_week_key()
    snapshots = load_depth_chart_snapshots(path)

    previous_week = None
    for candidate in snapshots.keys():
        if candidate < current_week and (previous_week is None or candidate > previous_week):
            previous_week = candidate
    previous_snapshot = snapshots.get(previous_week, {}) if previous_week else {}
    if not isinstance(previous_snapshot, dict):
        previous_snapshot = {}

    order_series = pd.to_numeric(out.get("depth_chart_order"), errors="coerce")
    player_ids = out["player_id"].astype(str)

    deltas: list[int] = []
    current_snapshot: dict[str, Any] = {}
    for player_id, order in zip(player_ids, order_series):
        has_order = pd.notna(order) and order > 0
        if has_order:
            current_snapshot[player_id] = int(order)
        prior = previous_snapshot.get(player_id)
        if has_order and prior is not None:
            deltas.append(int(prior) - int(order))
        else:
            deltas.append(0)

    out["depth_chart_order_delta"] = deltas

    snapshots[current_week] = current_snapshot
    recent_weeks = sorted(snapshots.keys())[-RETAINED_WEEKS:]
    _write_depth_chart_snapshots({week: snapshots[week] for week in recent_weeks}, path)

    return out
