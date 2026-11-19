"""Season Wrapped data for real (Sleeper-shaped) leagues, from the weekly ``/matchups`` payloads already fetched.

Each week is a list of ``{roster_id, matchup_id, points, starters, players_points}``. From those alone (no new storage):

* expected wins: the all-play share of the league a roster outscored each week;
* bench points: points the roster's non-starters scored, and the best single bench score (the lineup call that cost the most);
* ``bench.available`` is False when the payload carried no per-player points (nothing is invented).

Projection history and reason tags need a per-week projection snapshot that real leagues do not store yet, so they are not here.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from modules.coerce import float_or_none


def roster_season(weeks: Sequence[Sequence[Mapping[str, Any]]], roster_id: int) -> dict[str, Any]:
    exp = actual = bench_total = 0.0
    played = 0
    best: dict[str, Any] | None = None
    have_bench = False
    for wk, rows in enumerate(weeks, start=1):
        pts = {r.get("roster_id"): float_or_none(r.get("points")) for r in rows}
        if not any(pts.values()):  # a week not yet played scores nothing for everyone
            continue
        mine = pts.get(roster_id)
        if mine is None:
            continue
        others = [v for k, v in pts.items() if k != roster_id and v is not None]
        if others:
            exp += (sum(1.0 for v in others if mine > v) + 0.5 * sum(1.0 for v in others if mine == v)) / len(others)
        row = next(r for r in rows if r.get("roster_id") == roster_id)
        opp = next((r for r in rows if r.get("matchup_id") == row.get("matchup_id") and r.get("roster_id") != roster_id), None)
        opp_pts = float_or_none(opp.get("points")) if opp is not None else None
        if opp_pts is not None:
            actual += 1.0 if mine > opp_pts else 0.5 if mine == opp_pts else 0.0
        played += 1
        pp = row.get("players_points")
        if isinstance(pp, Mapping) and pp:
            have_bench = True
            started = set(row.get("starters") or ())
            for pid, v in pp.items():
                if pid in started or float_or_none(v) is None:
                    continue
                bench_total += float(v)
                if best is None or float(v) > best["pts"]:
                    best = {"week": wk, "player_id": pid, "pts": round(float(v), 2)}
    return {
        "games": played, "actual_wins": actual, "expected_wins": round(exp, 2), "diff": round(actual - exp, 2),
        "bench": {"available": have_bench, "total": round(bench_total, 2) if have_bench else None, "best": best},
    }


__all__ = ["roster_season"]
