"""The data Season Wrapped and the Draft & Watch report card read (pure derivations; nothing here changes a game).

Everything is read from a played game's state:

* ``expected_wins``: the all-play record (each week, the share of the other teams a team outscored), the standard "you deserved
  better" number. Works on every save, old or new.
* ``bench_points``: points the user's bench scored (the ``bench_pts`` the recap carries from ``wrapped_v`` 1; older saves fall back to
  the recap's top-ten bench list and say so with ``complete: False``).
* ``player_lines`` / ``reason_tag``: per starter, points against the projection that was shown going into each week
  (``state.proj_hist``, ``wrapped_v`` 1+; the recap row's own ``proj`` on older saves) and a reason tag for a miss or a surge:
  ``injury`` (games missed and the injury type), ``lost_job`` (his team role shrank) or ``breakout`` (he beat his projection by a lot).
* ``rank_journey``: the user's league rank after each regular-season week.
"""

from __future__ import annotations

from typing import Any

from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot

TAG_INJURY, TAG_LOST_JOB, TAG_BREAKOUT, TAG_MISS = "injury", "lost_job", "breakout", "underperformed"
MIN_MISSED_FOR_INJURY = 2
LOST_JOB_ROLE_DROP = 0.25  # the role scale fell this much from the first to the last third of the season
BREAKOUT_RATIO = 1.25  # points vs projection
BREAKOUT_MIN_GAP = 3.0  # and at least this many points a game over it


def _regular(state: GameState) -> list[dict[str, Any]]:
    return [w for w in state.history if w.get("kind") == "regular"]


def weekly_scores(state: GameState, tid: str) -> list[dict[str, Any]]:
    """One row per regular-season week ``tid`` played: points, opponent points, result and the share of the league it outscored."""

    out: list[dict[str, Any]] = []
    for week in _regular(state):
        scores: dict[str, float] = {}
        for g in week["games"]:
            scores[g["home"]], scores[g["away"]] = float(g["home_pts"]), float(g["away_pts"])
        if tid not in scores:
            continue
        mine = scores[tid]
        opp = next((g["away_pts"] if g["home"] == tid else g["home_pts"] for g in week["games"] if tid in (g["home"], g["away"])), None)
        others = [v for t, v in scores.items() if t != tid]
        beat = (sum(1.0 for v in others if mine > v) + 0.5 * sum(1.0 for v in others if mine == v)) / len(others) if others else 0.0
        res = None if opp is None else ("w" if mine > opp else "l" if mine < opp else "t")
        out.append({"week": int(week["week"]), "pts": round(mine, 2), "opp_pts": None if opp is None else round(float(opp), 2),
                    "result": res, "all_play": round(beat, 4)})
    return out


def expected_wins(state: GameState, tid: str) -> float:
    return round(sum(r["all_play"] for r in weekly_scores(state, tid)), 2)


def luck(state: GameState, tid: str) -> dict[str, Any]:
    rows = weekly_scores(state, tid)
    actual = sum(1.0 if r["result"] == "w" else 0.5 if r["result"] == "t" else 0.0 for r in rows)
    exp = sum(r["all_play"] for r in rows)
    return {"actual_wins": actual, "expected_wins": round(exp, 2), "diff": round(actual - exp, 2), "games": len(rows)}


def best_worst_week(state: GameState, tid: str) -> dict[str, Any] | None:
    rows = weekly_scores(state, tid)
    if not rows:
        return None
    return {"best": max(rows, key=lambda r: (r["pts"], -r["week"])), "worst": min(rows, key=lambda r: (r["pts"], r["week"]))}


def bench_points(state: GameState) -> dict[str, Any]:
    """Bench points by week and the user's biggest bench miss. ``complete`` is False when only the recap's top-ten bench list was
    available (a save from before ``wrapped_v``)."""

    weeks: list[dict[str, Any]] = []
    complete = True
    biggest: dict[str, Any] | None = None
    for key in sorted(state.recaps, key=int):
        rc = state.recaps[key]
        g = rc.get("your_game") if isinstance(rc, dict) else None
        if not g or rc.get("kind") != "regular" or "your_pts" not in g:
            continue
        if "bench_pts" in g:
            total = float(g["bench_pts"])
        else:
            complete = False
            total = sum(float(r.get("pts") or 0.0) for r in g.get("bench", []))
        left = round(float(g.get("optimal_pts", g["your_pts"])) - float(g["your_pts"]), 2)
        weeks.append({"week": int(key), "bench_pts": round(total, 2), "left_on_bench": left, "result": g.get("result"),
                      "margin": round(float(g["your_pts"]) - float(g["opp_pts"]), 2)})
        top = next((r for r in g.get("bench", []) if r.get("player")), None)
        if top and (biggest is None or top["pts"] > biggest["pts"]):
            biggest = {"week": int(key), "player": top["player"], "pts": top["pts"], "proj": top.get("proj")}
    lost = [w["week"] for w in weeks if w["result"] == "loss" and w["left_on_bench"] > abs(w["margin"])]
    return {"total": round(sum(w["bench_pts"] for w in weeks), 2), "left_total": round(sum(w["left_on_bench"] for w in weeks), 2),
            "weeks": weeks, "biggest_miss": biggest, "lost_by_lineup": lost, "complete": complete}


def player_lines(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    """The user's starters across the season: points, projection (what was shown going into each week he played), games and a reason tag."""

    agg: dict[str, dict[str, Any]] = {}
    for key in sorted(state.recaps, key=int):
        rc = state.recaps[key]
        g = rc.get("your_game") if isinstance(rc, dict) and rc.get("kind") == "regular" else None
        if not g:
            continue
        wk = int(key)
        for r in g.get("starters", []):
            pl = r.get("player")
            if not pl:
                continue
            pid = pl["id"]
            a = agg.setdefault(pid, {"pid": pid, "name": pl.get("name"), "pos": pl.get("pos"), "pts": 0.0, "proj": 0.0, "games": 0, "best": None})
            proj = (state.proj_hist.get(pid) or {}).get(str(wk))
            if proj is None:
                proj = r.get("proj")
            if r.get("flag") is None:  # he played
                a["pts"] += float(r["pts"])
                a["games"] += 1
                a["proj"] += float(proj or 0.0)
                if a["best"] is None or r["pts"] > a["best"]["pts"]:
                    a["best"] = {"week": wk, "pts": r["pts"]}
    out = []
    for a in agg.values():
        a["pts"], a["proj"] = round(a["pts"], 1), round(a["proj"], 1)
        a["over_proj"] = round(a["pts"] - a["proj"], 1)
        a["ppg"] = round(a["pts"] / a["games"], 1) if a["games"] else 0.0
        a["tag"] = reason_tag(snap, state, a["pid"], games=a["games"], proj=a["proj"], pts=a["pts"])
        out.append(a)
    out.sort(key=lambda a: (-a["pts"], a["pid"]))
    return out


def games_missed(state: GameState, pid: str) -> tuple[int, str | None]:
    """Games lost to injury this season and the longest injury's type, from the injury news (``weeks`` out each time)."""

    rows = [n for n in state.news if n.get("pid") == pid]
    if not rows:
        return 0, None
    return sum(int(n["weeks"]) for n in rows), max(rows, key=lambda n: int(n["weeks"])).get("kind")


def reason_tag(snap: GameSnapshot, state: GameState, pid: str, *, games: int, proj: float, pts: float) -> dict[str, Any]:
    """Why a player finished where he did against his projection. First rule that fits wins: injury, lost job, breakout."""

    missed, kind = games_missed(state, pid)
    missed = min(missed, snap.settings.regular_weeks)
    gap = pts - proj

    def tag(name: str | None, text: str) -> dict[str, Any]:
        return {"tag": name, "text": text, "games_missed": missed, "injury": kind}

    if missed >= MIN_MISSED_FOR_INJURY and gap < 0:
        return tag(TAG_INJURY, f"Missed {missed} games: {kind or 'injury'}")
    roles = state.role_hist.get(pid) or {}
    wks = sorted(int(w) for w in roles)
    if len(wks) >= 3:
        third = max(1, len(wks) // 3)
        first = sum(roles[str(w)][0] for w in wks[:third]) / third
        last = sum(roles[str(w)][0] for w in wks[-third:]) / third
        if gap < 0 and first - last >= LOST_JOB_ROLE_DROP:
            return tag(TAG_LOST_JOB, "Lost his role")
        if gap > 0 and last - first >= LOST_JOB_ROLE_DROP:
            return tag(TAG_BREAKOUT, "Took over a bigger role")
    if games and proj > 0 and pts / proj >= BREAKOUT_RATIO and gap / games >= BREAKOUT_MIN_GAP:
        return tag(TAG_BREAKOUT, "Breakout season")
    if gap < 0:
        return tag(TAG_MISS, "Underperformed his projection")
    return tag(None, "")


def rank_journey(state: GameState) -> list[dict[str, Any]]:
    """The user's league rank after each regular-season week, from the recaps' standings."""

    out = []
    for key in sorted(state.recaps, key=int):
        rc = state.recaps[key]
        if not isinstance(rc, dict) or rc.get("kind") != "regular":
            continue
        me = next((r for r in rc.get("standings", []) if r.get("is_you")), None)
        if me:
            out.append({"week": int(key), "rank": me["rank"], "wins": me["wins"], "losses": me["losses"]})
    return out


def season_data(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    """Everything the Wrapped cards read that the game did not already store, in one dict."""

    user = snap.user_team.tid
    lines = player_lines(snap, state)
    played = [a for a in lines if a["games"]]
    return {
        "wrapped_v": int(snap.settings.wrapped_v),
        "weekly": weekly_scores(state, user),
        "luck": luck(state, user),
        "best_worst_week": best_worst_week(state, user),
        "bench": bench_points(state),
        "rank_journey": rank_journey(state),
        "mvp": max(played, key=lambda a: (a["over_proj"], a["pid"])) if played else None,
        "bust": min(played, key=lambda a: (a["over_proj"], a["pid"])) if played else None,
        "players": lines,
    }


__all__ = ["weekly_scores", "expected_wins", "luck", "best_worst_week", "bench_points", "player_lines", "games_missed", "reason_tag",
           "rank_journey", "season_data"]
