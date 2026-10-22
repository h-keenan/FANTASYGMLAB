"""Percentile Explorer: the distribution behind one Player Quick View stat tile.

Numbers come from the exact pool and primitive the tiles use
(``player_quick_view._percentile_from_values`` over the
``filter_current_fantasy_players`` pool), so a player's percentile here always
equals his tile. The only extra scope is ``pool="all"``, which ranks the same
stat across every eligible position.

Only the single loaded regular season is supported: the player frame carries
no weekly or prior-season rows, so "Last 5" / "Career" are never offered.
"""

from __future__ import annotations

import threading
import time
from typing import Mapping

import pandas as pd

from modules import player_quick_view as pqv
from modules.player_eligibility import filter_current_fantasy_players

#: Stat key -> (tile display label, source label the tile percentiles use,
#: format kind). Keys mirror the tiles on the Stats tab.
_STATS: dict[str, tuple[str, str, str]] = {
    "ppr_ppg": ("PPR PPG", "PPG", "ppg"),
    "ppr": ("PPR", "Fantasy PPR", "points"),
    "half_ppr": ("Half PPR", "Half PPR", "points"),
    "standard": ("Standard", "Fantasy Pts", "points"),
    "fantasy_points": ("Fantasy Points", "Fantasy PPR", "points"),
    "targets": ("Targets", "Targets", "count"),
    "receptions": ("Receptions", "Receptions", "count"),
    "rec_yards": ("Rec Yards", "Rec Yards", "yards"),
    "rec_tds": ("Rec TDs", "Rec TDs", "td"),
    "rush_att": ("Rush Att", "Rush Att", "count"),
    "rush_yards": ("Rush Yards", "Rush Yards", "yards"),
    "rush_tds": ("Rush TDs", "Rush TDs", "td"),
    "pass_att": ("Pass Att", "Pass Att", "count"),
    "pass_yards": ("Pass Yards", "Pass Yards", "yards"),
    "pass_tds": ("Pass TDs", "Pass TDs", "td"),
    "snap": ("Snap %", "Snap Share", "share"),
    "route": ("Route %", "Route Part.", "share"),
    "target_share": ("Target Share", "Target Share", "share"),
    "carry_share": ("Carry Share", "Rush Share", "share"),
    "opportunity": ("Opportunity", "Opportunity Share", "share"),
    "targets_gm": ("Targets/Gm", "Targets/Gm", "rate"),
    "rec_gm": ("Rec/Gm", "Rec/Gm", "rate"),
    "yards_catch": ("Yards/Catch", "Yards/Catch", "rate"),
    "carries_gm": ("Carries/Gm", "Carries/Gm", "rate"),
    "yards_carry": ("Yards/Carry", "Yards/Carry", "rate"),
}

BIN_COUNT = 20
MAX_MARKERS = 7
_CACHE_TTL_S = 600.0
_CACHE_MAX = 256
_cache: dict[tuple, tuple[float, dict | None]] = {}
_cache_lock = threading.Lock()


def supported_stats() -> list[str]:
    return list(_STATS)


def _values_for(frame: pd.DataFrame, source_label: str) -> pd.Series | None:
    fields = pqv._PERCENTILE_STAT_FIELDS.get(source_label)
    if fields is not None:
        return pqv._coalesced_numeric_column(frame, fields)
    return pqv._ratio_stat_values_for_pool(frame).get(source_label)


def _display_value(value: float, format_kind: str) -> float:
    if format_kind == "share" and abs(value) <= 1.0:
        value *= 100.0
    return round(float(value), 1)


def _pool_distribution(pool: pd.DataFrame, *, stat: str, scope: str, position: str) -> dict | None:
    """Percentiles + bins for one (stat, scope, position) pool, or None when
    the stat is missing or fewer than PERCENTILE_MIN_POOL players carry it."""

    _label, source_label, format_kind = _STATS[stat]
    if scope == "all":
        group = pool
    else:
        group = pool[pool["position"].astype(str).str.upper() == position]
    values = _values_for(group, source_label)
    if values is None or int(values.notna().sum()) < pqv.PERCENTILE_MIN_POOL:
        return None
    if scope == "all":
        positions = pd.Series("ALL", index=group.index)
    else:
        positions = group["position"].astype(str).str.upper()
    percentiles = pqv._percentile_from_values(values, positions)

    valid = values.notna() & percentiles.notna()
    ids = group["player_id"].astype(str)
    names = group["name"].astype(str) if "name" in group.columns else ids
    teams = group["team"].astype(str) if "team" in group.columns else pd.Series("", index=group.index)
    poss = group["position"].astype(str).str.upper()
    players = [
        {
            "player_id": ids[i],
            "name": names[i],
            "team": "" if teams[i].strip().lower() in {"nan", "none"} else teams[i],
            "position": poss[i],
            "value": _display_value(float(values[i]), format_kind),
            "percentile": int(percentiles[i]),
        }
        for i in group.index[valid]
    ]
    players.sort(key=lambda p: (-p["value"], -p["percentile"], p["player_id"]))

    raw = values[valid].astype(float).to_numpy()
    lo, hi = float(raw.min()), float(raw.max())
    n = len(raw)
    bins: list[dict] = []
    if hi > lo:
        width = (hi - lo) / BIN_COUNT
        for b in range(BIN_COUNT):
            start = lo + b * width
            last = b == BIN_COUNT - 1
            end = hi if last else start + width
            below_start = float((raw < start).sum())
            at_or_below_end = float((raw <= end).sum() if last else (raw < end).sum())
            bins.append(
                {
                    "count": int(at_or_below_end - below_start),
                    "pct_start": round(below_start / n * 100, 1),
                    "pct_end": round(at_or_below_end / n * 100, 1),
                    "value_start": _display_value(start, format_kind),
                    "value_end": _display_value(end, format_kind),
                }
            )
    return {"players": players, "bins": bins, "pool_size": n}


def _cached_distribution(pool, *, stat, scope, position, season, size) -> dict | None:
    key = (stat, scope, position if scope != "all" else "", season, size)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL_S:
            return hit[1]
    dist = _pool_distribution(pool, stat=stat, scope=scope, position=position)
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            _cache.clear()
        _cache[key] = (now, dist)
    return dist


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def select_nearby(players: list[dict], player_id: str, limit: int = MAX_MARKERS) -> list[dict]:
    """Up to `limit` real pool members around the player (sorted by value
    desc): always the nearest above and below him, then others spread across
    the percentile range. Returned in ascending percentile order."""

    me_idx = next((i for i, p in enumerate(players) if p["player_id"] == player_id), None)
    if me_idx is None:
        return []
    me = players[me_idx]
    chosen: list[dict] = []
    if me_idx > 0:
        chosen.append(players[me_idx - 1])
    if me_idx + 1 < len(players):
        chosen.append(players[me_idx + 1])
    for target in sorted((8, 25, 42, 58, 75, 92), key=lambda t: abs(t - me["percentile"]), reverse=True):
        if len(chosen) >= limit:
            break
        cands = [
            p
            for p in players
            if p["player_id"] != player_id
            and p not in chosen
            and abs(p["percentile"] - me["percentile"]) >= 4
            and all(abs(p["percentile"] - c["percentile"]) >= 4 for c in chosen)
        ]
        if cands:
            chosen.append(min(cands, key=lambda p: (abs(p["percentile"] - target), p["player_id"])))
    chosen.sort(key=lambda p: (p["percentile"], p["value"]))
    return chosen


def build_explorer(
    players_df: pd.DataFrame | None,
    row: Mapping[str, object],
    *,
    stat: str,
    pool: str = "position",
) -> dict:
    """The explorer payload. ``reason`` is "" on success, else one of
    ``unknown_stat`` / ``insufficient_pool`` / ``no_data``."""

    base: dict = {"stat": stat, "pool": pool, "season": None, "scopes": ["season"], "reason": ""}
    if stat not in _STATS:
        return {**base, "reason": "unknown_stat"}
    label, _src, fmt = _STATS[stat]
    position = pqv._text(row.get("position")).upper()
    player_id = pqv._text(row.get("player_id"))
    scope = "all" if pool == "all" else "position"
    base.update(
        {"label": label, "format": fmt, "position": position, "pool": scope, "season": pqv._integer(row.get("stats_season"))}
    )

    if players_df is None or players_df.empty or "position" not in players_df.columns:
        return {**base, "reason": "no_data"}
    try:
        eligible = filter_current_fantasy_players(players_df, surface="player_quick_view_percentiles")
    except Exception:
        return {**base, "reason": "no_data"}
    if eligible is None or eligible.empty:
        return {**base, "reason": "no_data"}

    dist = _cached_distribution(
        eligible, stat=stat, scope=scope, position=position, season=base["season"], size=len(eligible)
    )
    if dist is None:
        return {**base, "reason": "insufficient_pool"}
    me = next((p for p in dist["players"] if p["player_id"] == player_id), None)
    if me is None:
        return {**base, "reason": "no_data"}
    return {
        **base,
        "pool_size": dist["pool_size"],
        "bins": dist["bins"],
        "player": me,
        "nearby": select_nearby(dist["players"], player_id),
    }
