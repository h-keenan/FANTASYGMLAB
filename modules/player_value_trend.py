"""Player value history for the app: the chart series and the buy-low /
sell-high list, both derived only from real stored daily rating snapshots
(`modules.player_rating_history`) plus the current players table.

Honesty rules (docs/gap-analysis-best-app-2026-11-02.md, #6):
- Nothing is interpolated or backfilled. The chart is exactly the stored days;
  the response reports the real span so a short history reads as short.
- A change is only reported when a real snapshot at least `MIN_SIGNAL_SPAN_DAYS`
  old exists. Before that the list is "history building", never a guess.
- Buy-low / sell-high needs two independent things to disagree: how the
  market value rating MOVED (stored snapshots) and how the player is actually
  PRODUCING (this season's PPG percentile within position). One signal alone
  never qualifies. Thresholds are product choices, not fitted to outcomes.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Sequence

import pandas as pd

MIN_SIGNAL_SPAN_DAYS = 7
SIGNAL_WINDOW_DAYS = 30
# Rating points (0-99 badge) the value must have moved to count as a trend.
MIN_TREND_POINTS = 3
# Percentile points production must sit above/below the value percentile.
MIN_GAP_PERCENTILE = 15.0
# Games played before a PPG percentile means anything.
MIN_GAMES = 4
# Older players are legitimately priced down for age; not a buy-low.
BUY_LOW_MAX_AGE = 29
MIN_POSITION_POOL = 10
MAX_PER_LIST = 10
ELIGIBLE_POSITIONS = ("QB", "RB", "WR", "TE")
OUT_STATUSES = {"out", "ir", "pup", "sus", "suspended"}

METHOD_NOTE = (
    "Buy low: the value rating fell at least "
    f"{MIN_TREND_POINTS} points while this season's production sits at least "
    f"{int(MIN_GAP_PERCENTILE)} percentile points above where the value rating ranks them "
    f"(players {BUY_LOW_MAX_AGE + 1}+ are excluded: age already prices them). Sell high: the "
    "reverse. Needs "
    f"{MIN_GAMES}+ games played. Product thresholds, not fitted to outcomes."
)


def history_points(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Stored snapshot rows (any order) -> ascending [{date, rating}], one per
    date, malformed rows dropped."""

    by_date: dict[str, int] = {}
    for row in rows:
        day = str(row.get("snapshot_date") or "").strip()
        try:
            rating = int(row.get("overall_rating"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not day or not 0 <= rating <= 99:
            continue
        by_date[day] = rating
    return [{"date": day, "rating": by_date[day]} for day in sorted(by_date)]


def _parse(day: str) -> date | None:
    try:
        return date.fromisoformat(day)
    except ValueError:
        return None


def history_summary(points: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Status, real span and the changes that real data supports."""

    if len(points) < 2:
        return {
            "status": "insufficient_history",
            "points": list(points),
            "span_days": 0,
            "first_date": points[0]["date"] if points else None,
            "last_date": points[-1]["date"] if points else None,
            "current_rating": points[-1]["rating"] if points else None,
            "change": None,
            "changes": [],
        }
    first, last = points[0], points[-1]
    first_day, last_day = _parse(first["date"]), _parse(last["date"])
    span = (last_day - first_day).days if first_day and last_day else 0
    changes: list[dict[str, Any]] = []
    for window in (7, 30):
        if last_day is None or span < window:
            continue
        cutoff = last_day - timedelta(days=window)
        baseline = None
        for point in points:
            day = _parse(point["date"])
            if day is not None and day <= cutoff:
                baseline = point
        if baseline is not None:
            changes.append(
                {
                    "days": (last_day - _parse(baseline["date"])).days,  # type: ignore[operator]
                    "delta": last["rating"] - baseline["rating"],
                    "from_date": baseline["date"],
                }
            )
    return {
        "status": "ok",
        "points": list(points),
        "span_days": span,
        "first_date": first["date"],
        "last_date": last["date"],
        "current_rating": last["rating"],
        "change": {"days": span, "delta": last["rating"] - first["rating"]},
        "changes": changes,
    }


def _pct(series: pd.Series, groups: pd.Series) -> pd.Series:
    sizes = series.groupby(groups).transform(lambda s: int(s.notna().sum()))
    ranks = series.groupby(groups).rank(pct=True) * 100.0
    return ranks.where(sizes >= MIN_POSITION_POOL)


def compute_signals(
    frame: pd.DataFrame | None,
    latest: Mapping[str, int],
    baseline: Mapping[str, int],
    *,
    latest_date: str,
    baseline_date: str,
) -> dict[str, list[dict[str, Any]]]:
    """Buy-low and sell-high lists. `frame` is the current fantasy pool with
    `position`, `dynasty_score`/`score`, `ppg`, `games_played`, `age`."""

    empty: dict[str, list[dict[str, Any]]] = {"buy_low": [], "sell_high": []}
    if frame is None or frame.empty or "position" not in frame.columns or "player_id" not in frame.columns:
        return empty
    score_col = "dynasty_score" if "dynasty_score" in frame.columns else "score"
    if score_col not in frame.columns or "ppg" not in frame.columns:
        return empty
    df = frame[frame["position"].astype(str).str.upper().isin(ELIGIBLE_POSITIONS)].copy()
    if df.empty:
        return empty
    df["_pos"] = df["position"].astype(str).str.upper()
    df["_pid"] = df["player_id"].astype(str)
    games = pd.to_numeric(df.get("games_played"), errors="coerce")
    ppg = pd.to_numeric(df["ppg"], errors="coerce").where(games >= MIN_GAMES)
    df["_value_pct"] = _pct(pd.to_numeric(df[score_col], errors="coerce"), df["_pos"])
    df["_prod_pct"] = _pct(ppg, df["_pos"])

    span = (_parse(latest_date) - _parse(baseline_date)).days if _parse(latest_date) and _parse(baseline_date) else 0
    out: dict[str, list[dict[str, Any]]] = {"buy_low": [], "sell_high": []}
    for _, row in df.iterrows():
        pid = row["_pid"]
        if pid not in latest or pid not in baseline:
            continue
        if pd.isna(row["_value_pct"]) or pd.isna(row["_prod_pct"]):
            continue
        trend = latest[pid] - baseline[pid]
        gap = float(row["_prod_pct"]) - float(row["_value_pct"])
        age = pd.to_numeric(row.get("age"), errors="coerce")
        status = str(row.get("injury_status") or "").strip().lower()
        if status in OUT_STATUSES:
            continue
        if trend <= -MIN_TREND_POINTS and gap >= MIN_GAP_PERCENTILE:
            signal = "buy_low"
            if pd.notna(age) and age > BUY_LOW_MAX_AGE:
                continue
        elif trend >= MIN_TREND_POINTS and gap <= -MIN_GAP_PERCENTILE:
            signal = "sell_high"
        else:
            continue
        value_pct, prod_pct = int(round(float(row["_value_pct"]))), int(round(float(row["_prod_pct"])))
        factors = [
            {
                "label": "Value trend",
                "detail": f"{trend:+d} rating points over {span} days ({baseline[pid]} to {latest[pid]})",
            },
            {
                "label": "Production",
                "detail": f"{prod_pct}th percentile PPG at {row['_pos']} vs value ranked {value_pct}th",
            },
            {"label": "Sample", "detail": f"{int(games.loc[row.name])} games played this season"},
        ]
        if pd.notna(age):
            factors.append({"label": "Age", "detail": f"{int(age)}"})
        out[signal].append(
            {
                "player_id": pid,
                "name": str(row.get("name") or ""),
                "position": row["_pos"],
                "team": str(row.get("team") or ""),
                "age": int(age) if pd.notna(age) else None,
                "rating": latest[pid],
                "rating_change": trend,
                "ppg": round(float(row["ppg"]), 1) if pd.notna(row.get("ppg")) else None,
                "games_played": int(games.loc[row.name]),
                "production_percentile": prod_pct,
                "value_percentile": value_pct,
                "gap": round(abs(gap), 1),
                "injury_status": str(row.get("injury_status") or "") or None,
                "signal": signal,
                "factors": factors,
            }
        )
    for key in out:
        out[key].sort(key=lambda item: (-item["gap"], -abs(item["rating_change"]), item["name"]))
        out[key] = out[key][:MAX_PER_LIST]
    return out
