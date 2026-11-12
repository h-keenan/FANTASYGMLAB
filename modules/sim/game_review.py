"""The "Season in Review": awards, leaders and storylines read off a finished game.

Pure, read-only and deterministic: it folds the stored event log once (the same
fold resume uses) to know who was on the user's roster and lineup each week, and
reads everything else from the final state. It never replays the season, so it is
cheap next to the counterfactual replays in ``game_result``.

The payload is plain JSON (``review`` in the /result body). Every key is optional
for clients: an older stored result has no ``review`` at all.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from modules.sim.game_engine import _brief
from modules.sim.game_state import GameState, apply_event
from modules.sim.game_types import GameSnapshot

_log = logging.getLogger(__name__)

LEADER_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
LEADERS_PER_POSITION = 3
STAT_CATEGORIES = (
    ("pass_yd", "Passing yards", ("pass_yd",)),
    ("rush_yd", "Rushing yards", ("rush_yd",)),
    ("rec_yd", "Receiving yards", ("rec_yd",)),
    ("td", "Touchdowns", ("pass_td", "rush_td", "rec_td")),
)


def _sum_from(points: Mapping[str, Sequence[Any]], pid: str, week: int) -> float:
    """Points ``pid`` scored from ``week`` (1-based) to the end of the season."""

    return sum(v for v in (points.get(pid) or [])[max(0, week - 1):] if v is not None)


def _total(points: Mapping[str, Sequence[Any]], pid: str) -> tuple[float, int]:
    vals = [v for v in (points.get(pid) or []) if v is not None]
    return sum(vals), len(vals)


def _names(snap: GameSnapshot, pids: Sequence[str]) -> str:
    return ", ".join(snap.players[p].name for p in pids) or "nothing"


def _r(value: float, places: int = 1) -> float:
    return round(float(value), places)


def _team_name(snap: GameSnapshot, tid: str | None) -> str:
    try:
        return snap.team(tid).name if tid else ""
    except Exception:  # noqa: BLE001 - a missing team never breaks the review
        return ""


class _Replayer:
    """One cheap fold of the log that remembers the user's roster each week."""

    def __init__(self, snap: GameSnapshot, events: Sequence[Mapping[str, Any]]) -> None:
        self.snap = snap
        user = snap.user_team.tid
        state = GameState(snap)
        self.started: dict[str, float] = {}  # pid -> points scored in the user's lineup
        self.rostered: dict[str, float] = {}  # pid -> points scored while on the user's roster
        self.missed: dict[str, int] = {}  # pid -> weeks out while on the user's roster
        self.injuries: list[dict[str, Any]] = []  # the user's injuries, in order
        self.team_injuries: dict[str, int] = {t.tid: 0 for t in snap.teams}
        for ev in events:
            kind, p = ev["type"], ev["payload"]
            if kind == "week_scored":
                played = p["points"]
                for _, pid in state.lineups[user]:
                    if pid and pid in played:
                        self.started[pid] = self.started.get(pid, 0.0) + float(played[pid])
                for pid in state.rosters[user]:
                    if pid in played:
                        self.rostered[pid] = self.rostered.get(pid, 0.0) + float(played[pid])
                    if state.out.get(pid, 0) > 0:
                        self.missed[pid] = self.missed.get(pid, 0) + 1
            elif kind == "injury":
                owners = state.owner_map()
                for pid, weeks in p["items"]:
                    tid = owners.get(pid)
                    if tid:
                        self.team_injuries[tid] = self.team_injuries.get(tid, 0) + 1
                    if tid == user:
                        self.injuries.append({"pid": pid, "week": int(ev.get("week") or 0), "weeks": int(weeks)})
            apply_event(state, snap, ev)
        self.state = state


# ------------------------------------------------------------------- awards


def _award(key: str, kind: str, tone: str, label: str, headline: str, *, players=None, week=None,
           delta=None, detail: str = "", outcome=None) -> dict[str, Any]:
    return {"key": key, "kind": kind, "tone": tone, "label": label, "headline": headline,
            "players": players or [], "week": week, "delta": delta, "detail": detail, "outcome": outcome}


def _delta(value: float, unit: str) -> dict[str, Any]:
    return {"value": _r(value), "unit": unit}


def _trade_awards(snap: GameSnapshot, state: GameState, events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    user = snap.user_team.tid
    rows = []
    for e in events:
        p = e["payload"]
        if e["type"] != "trade" or e["actor"] != "user" or user not in (p["team_a"], p["team_b"]):
            continue
        sent, got = (p["give"], p["get"]) if p["team_a"] == user else (p["get"], p["give"])
        week = int(e.get("week") or 1)
        got_pts = sum(_sum_from(state.points, i, week) for i in got)
        sent_pts = sum(_sum_from(state.points, i, week) for i in sent)
        rows.append({"week": week, "sent": sent, "got": got, "net": got_pts - sent_pts,
                     "got_pts": got_pts, "sent_pts": sent_pts})
    if not rows:
        return []
    best = max(rows, key=lambda r: (r["net"], -r["week"]))
    worst = min(rows, key=lambda r: (r["net"], r["week"]))

    def make(r: dict[str, Any], key: str, label: str) -> dict[str, Any]:
        players = ([{**_brief(snap, i), "role": "get"} for i in r["got"]]
                   + [{**_brief(snap, i), "role": "give"} for i in r["sent"]])
        detail = (f"Got {_names(snap, r['got'])} ({_r(r['got_pts'])} pts after the deal) for "
                  f"{_names(snap, r['sent'])} ({_r(r['sent_pts'])} pts).")
        return _award(key, "trade", "good" if r["net"] >= 0 else "bad", label,
                      f"Week {r['week']} trade", players=players, week=r["week"],
                      delta=_delta(r["net"], "pts"), detail=detail,
                      outcome="Won the deal" if r["net"] >= 0 else "Lost the deal")

    out = [make(best, "best_trade", "Best trade")]
    if len(rows) > 1 and worst is not best:
        out.append(make(worst, "worst_trade", "Worst trade"))
    return out


def _waiver_awards(snap: GameSnapshot, state: GameState, events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    user = snap.user_team.tid
    rows = []
    for e in events:
        p = e["payload"]
        if e["type"] != "waiver_result" or p.get("team") != user or not p.get("ok"):
            continue
        week = int(e.get("week") or 1)
        added = _sum_from(state.points, p["add"], week)
        dropped = _sum_from(state.points, p["drop"], week) if p.get("drop") else 0.0
        rows.append({"week": week, "add": p["add"], "drop": p.get("drop"), "pts": added, "net": added - dropped})
    if not rows:
        return []
    best = max(rows, key=lambda r: (r["net"], -r["week"]))
    players = [{**_brief(snap, best["add"]), "role": "add"}]
    detail = f"Scored {_r(best['pts'])} points from week {best['week']} on."
    if best["drop"]:
        players.append({**_brief(snap, best["drop"]), "role": "drop"})
        detail += f" The dropped {snap.players[best['drop']].name} scored {_r(best['pts'] - best['net'])}."
    return [_award("best_waiver", "waiver", "good" if best["net"] >= 0 else "bad", "Best waiver pickup",
                   f"Week {best['week']} pickup", players=players, week=best["week"],
                   delta=_delta(best["net"], "pts"), detail=detail, outcome="Great find")]


def _draft_awards(snap: GameSnapshot, state: GameState, draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Best pick by value over ADP; worst pick is a real reach (negative value over ADP)
    or, when none, the early pick that produced the least."""

    mine = draft.get("your_team") or {}
    out = []

    def make(pick: Mapping[str, Any], key: str, label: str, good: bool, delta: dict[str, Any], outcome: str):
        pid = pick["player_id"]
        total, games = _total(state.points, pid)
        detail = (f"Pick {pick['pick_no']} (round {pick['round']}), ADP {_r(pick.get('adp') or 0)}. "
                  f"Scored {_r(total)} points over {games} games.")
        return _award(key, "draft", "good" if good else "bad", label, f"Round {pick['round']} pick",
                      players=[{**_brief(snap, pid), "role": "pick"}], delta=delta, detail=detail, outcome=outcome)

    best = mine.get("best_pick")
    if best:
        out.append(make(best, "best_pick", "Best draft pick", True, _delta(best.get("value_over_adp") or 0.0, "adp"), "Steal"))
    worst = mine.get("worst_pick")
    if worst and float(worst.get("value_over_adp") or 0.0) < 0:
        out.append(make(worst, "worst_pick", "Worst draft pick", False, _delta(worst["value_over_adp"], "adp"), "Reach"))
    else:
        early = [p for p in draft.get("picks_value") or []
                 if p["team_id"] == snap.user_team.tid and int(p["round"]) <= 6 and p["pos"] not in ("K", "DEF")]
        if early:
            def ppg(p):
                total, games = _total(state.points, p["player_id"])
                return total / games if games else 0.0
            low = min(early, key=lambda p: (ppg(p), p["pick_no"]))
            if not best or low["player_id"] != best["player_id"]:
                out.append(make(low, "worst_pick", "Worst draft pick", False,
                                _delta(ppg(low), "ppg"), "Underperformed"))
    return out


def _injury_awards(snap: GameSnapshot, state: GameState, rep: _Replayer) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    for pid, weeks in rep.missed.items():
        total, games = _total(state.points, pid)
        ppg = total / games if games else 0.0
        rows.append({"pid": pid, "weeks_missed": weeks, "points_lost": _r(ppg * weeks), "ppg": _r(ppg)})
    rows.sort(key=lambda r: (-r["points_lost"], -r["weeks_missed"], r["pid"]))
    by_weeks = sorted(rows, key=lambda r: (-r["weeks_missed"], -r["points_lost"], r["pid"]))
    lost_total = _r(sum(r["points_lost"] for r in rows))
    team_counts = sorted(rep.team_injuries.items(), key=lambda kv: (-kv[1], kv[0]))
    summary = {
        "your_injuries": len(rep.injuries), "weeks_missed": sum(r["weeks_missed"] for r in rows),
        "points_lost": lost_total,
        "most_injured_team": ({"team_id": team_counts[0][0], "name": _team_name(snap, team_counts[0][0]),
                               "count": team_counts[0][1], "is_you": team_counts[0][0] == snap.user_team.tid}
                              if team_counts and team_counts[0][1] > 0 else None),
        "rows": [{**r, "player": _brief(snap, r["pid"])} for r in rows[:5]],
    }
    out = []
    if rows and rows[0]["points_lost"] > 0:
        top = rows[0]
        out.append(_award("injury_cost", "injury", "bad", "Injury that cost the most",
                          f"Missed {top['weeks_missed']} week{'s' if top['weeks_missed'] != 1 else ''}",
                          players=[{**_brief(snap, top["pid"]), "role": "hurt"}],
                          delta=_delta(-top["points_lost"], "pts"),
                          detail=f"Averaging {top['ppg']} points a game, that is about {top['points_lost']} points left on the sideline.",
                          outcome="Injured"))
    if by_weeks and by_weeks[0]["weeks_missed"] > 0 and (not rows or by_weeks[0]["pid"] != rows[0]["pid"]):
        top = by_weeks[0]
        out.append(_award("injury_longest", "injury", "bad", "Hurt the longest",
                          f"Missed {top['weeks_missed']} weeks", players=[{**_brief(snap, top["pid"]), "role": "hurt"}],
                          delta=_delta(-top["points_lost"], "pts"),
                          detail=f"Out {top['weeks_missed']} weeks while on your roster.", outcome="Injured"))
    return out, summary


def _boom_bust(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    boom = bust = None
    for key in sorted(state.recaps, key=int):
        g = state.recaps[key].get("your_game")
        if not g or "your_pts" not in g:
            continue
        mvp, b = g.get("mvp"), g.get("bust")
        if mvp and (boom is None or mvp["pts"] > boom[1]["pts"]):
            boom = (int(key), mvp)
        if b:
            gap = float(b["expected"]) - float(b["pts"])
            if bust is None or gap > bust[2]:
                bust = (int(key), b, gap)
    out = []
    if boom:
        week, m = boom
        out.append(_award("boom", "boom", "good", "Biggest boom", f"Week {week}", players=[{**m["player"], "role": "boom"}],
                          week=week, delta=_delta(m["pts"], "pts"), detail=f"Your top single-game score of the season: {_r(m['pts'])} points.",
                          outcome="Boom"))
    if bust:
        week, b, gap = bust
        out.append(_award("bust", "bust", "bad", "Biggest bust", f"Week {week}", players=[{**b["player"], "role": "bust"}],
                          week=week, delta=_delta(-gap, "pts"),
                          detail=f"Projected for about {_r(b['expected'])}, scored {_r(b['pts'])}.", outcome="Bust"))
    return out


# ------------------------------------------------------------------ sections


def _stat_leaders(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    user = snap.user_team.tid
    owners = state.owner_map()
    league = []
    for pos in LEADER_POSITIONS:
        rows = []
        for pid in snap.pids:
            if snap.players[pid].pos != pos:
                continue
            total, games = _total(state.points, pid)
            if games == 0 or total <= 0:
                continue
            tid = owners.get(pid)
            rows.append((total, pid, games, tid))
        rows.sort(key=lambda r: (-r[0], r[1]))
        if rows:
            league.append({"pos": pos, "rows": [
                {"player": _brief(snap, pid), "pts": _r(total), "games": games, "ppg": _r(total / games),
                 "team_id": tid, "team_name": _team_name(snap, tid), "is_you": tid == user}
                for total, pid, games, tid in rows[:LEADERS_PER_POSITION]]})
    totals: dict[str, dict[str, float]] = {}
    brief: dict[str, Any] = {}
    for key in state.recaps:
        g = state.recaps[key].get("your_game")
        if not g or "starters" not in g:
            continue
        for row in list(g["starters"]) + list(g.get("bench") or []):
            pl, stats = row.get("player"), row.get("stats")
            if not pl or not stats:
                continue
            brief[pl["id"]] = pl
            acc = totals.setdefault(pl["id"], {})
            for k, v in stats.items():
                acc[k] = acc.get(k, 0.0) + float(v)
    yours = []
    for key, label, fields in STAT_CATEGORIES:
        rows = sorted(((sum(t.get(f, 0.0) for f in fields), pid) for pid, t in totals.items()), key=lambda r: (-r[0], r[1]))
        rows = [r for r in rows if r[0] > 0][:LEADERS_PER_POSITION]
        if rows:
            yours.append({"key": key, "label": label, "rows": [{"player": brief[pid], "value": int(round(v))} for v, pid in rows]})
    return {"league": league, "yours": yours}


def _games(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    user = snap.user_team.tid
    flat = []
    for wk in state.history:
        for g in wk["games"]:
            hp, ap = float(g["home_pts"]), float(g["away_pts"])
            flat.append({
                "week": int(wk["week"]), "kind": wk["kind"], "home_id": g["home"], "away_id": g["away"],
                "home": _team_name(snap, g["home"]), "away": _team_name(snap, g["away"]),
                "home_pts": _r(hp, 2), "away_pts": _r(ap, 2), "margin": _r(abs(hp - ap), 2),
                "is_yours": user in (g["home"], g["away"]),
                "you_won": ((hp > ap) == (g["home"] == user)) if user in (g["home"], g["away"]) and hp != ap else None,
            })
    by_margin = sorted(flat, key=lambda g: (g["margin"], g["week"], g["home_id"]))
    return {
        "closest_yours": [g for g in by_margin if g["is_yours"]][:3],
        "closest_league": by_margin[:3],
        "blowout": max(flat, key=lambda g: (g["margin"], -g["week"]), default=None),
    }


def _rank_journey(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    out = []
    for key in sorted(state.recaps, key=int):
        rec = state.recaps[key]
        if rec.get("kind") != "regular":
            continue
        me = next((r for r in rec.get("standings") or [] if r.get("is_you")), None)
        if me:
            out.append({"week": int(key), "rank": me["rank"], "wins": me["wins"], "losses": me["losses"], "ties": me.get("ties", 0)})
    return out


def _path(snap: GameSnapshot, state: GameState, tid: str) -> dict[str, Any] | None:
    pl = state.playoff
    if not pl or tid not in pl["seeds"]:
        return None
    rounds = []
    for rd in pl["rounds"]:
        game = next((g for g in rd["games"] if tid in (g["home"], g["away"])), None)
        if game is None:
            if any(tid == t for t in (pl["slots"] if rd["round"] == 1 else [])) or rd["round"] == 1:
                rounds.append({"round": rd["round"], "week": rd["week"], "bye": True})
            continue
        mine = game["home_pts"] if game["home"] == tid else game["away_pts"]
        theirs = game["away_pts"] if game["home"] == tid else game["home_pts"]
        opp = game["away"] if game["home"] == tid else game["home"]
        rounds.append({"round": rd["round"], "week": rd["week"], "bye": False, "opponent": _team_name(snap, opp),
                       "opponent_seed": pl["seeds"].index(opp) + 1 if opp in pl["seeds"] else None,
                       "pts": _r(mine, 2), "opp_pts": _r(theirs, 2), "won": game.get("winner") == tid})
        if game.get("winner") != tid:
            break
    return {"team_id": tid, "name": _team_name(snap, tid), "seed": pl["seeds"].index(tid) + 1,
            "is_you": tid == snap.user_team.tid, "total_rounds": snap.settings.playoff_weeks, "rounds": rounds}


def _season_stats(snap: GameSnapshot, state: GameState, rep: _Replayer) -> list[dict[str, Any]]:
    user = snap.user_team.tid
    weeks = []
    left = 0.0
    longest = cur = 0
    for key in sorted(state.recaps, key=int):
        g = state.recaps[key].get("your_game")
        if not g or "your_pts" not in g:
            continue
        weeks.append((int(key), float(g["your_pts"]), g["result"], state.recaps[key].get("kind")))
        left += max(0.0, float(g.get("optimal_pts", g["your_pts"])) - float(g["your_pts"]))
        cur = cur + 1 if g["result"] == "win" and state.recaps[key].get("kind") == "regular" else 0
        longest = max(longest, cur)
    out: list[dict[str, Any]] = []
    reg = [w for w in weeks if w[3] == "regular"]
    if reg:
        hi = max(reg, key=lambda w: (w[1], -w[0]))
        lo = min(reg, key=lambda w: (w[1], w[0]))
        out += [
            {"key": "ppg", "label": "Points per game", "value": f"{_r(sum(w[1] for w in reg) / len(reg))}"},
            {"key": "high", "label": "Best week", "value": f"{_r(hi[1])}", "sub": f"Week {hi[0]}", "tone": "good"},
            {"key": "low", "label": "Worst week", "value": f"{_r(lo[1])}", "sub": f"Week {lo[0]}", "tone": "bad"},
            {"key": "streak", "label": "Longest win streak", "value": str(longest), "tone": "good" if longest >= 3 else None},
        ]
    out.append({"key": "bench", "label": "Points left on bench", "value": f"{_r(left)}", "tone": "bad" if left >= 60 else None})
    out.append({"key": "injuries", "label": "Injuries to your players", "value": str(len(rep.injuries)),
                "tone": "bad" if len(rep.injuries) >= 4 else None})
    best_scorer = max(rep.started.items(), key=lambda kv: (kv[1], kv[0]), default=None)
    if best_scorer:
        out.append({"key": "mvp", "label": "Season MVP", "value": f"{_r(best_scorer[1])}", "sub": "pts in your lineup",
                    "player": _brief(snap, best_scorer[0]), "tone": "good"})
    return out


# --------------------------------------------------------------------- entry


def build_review(
    snap: GameSnapshot, events: Sequence[Mapping[str, Any]], final: GameState, draft: Mapping[str, Any],
) -> dict[str, Any]:
    """The whole review payload. Never raises: a failure yields ``{}`` so the
    grade still ships."""

    try:
        rep = _Replayer(snap, events)
        injury_awards, injuries = _injury_awards(snap, final, rep)
        awards = (_trade_awards(snap, final, events) + _waiver_awards(snap, final, events)
                  + _draft_awards(snap, final, draft) + _boom_bust(snap, final) + injury_awards)
        champion = final.champion or None
        user = snap.user_team.tid
        return {
            "awards": awards,
            "season_stats": _season_stats(snap, final, rep),
            "injuries": injuries,
            "leaders": _stat_leaders(snap, final),
            "games": _games(snap, final),
            "rank_journey": _rank_journey(snap, final),
            "team_count": len(snap.tids),
            "champion_path": _path(snap, final, champion) if champion else None,
            "your_path": _path(snap, final, user) if champion != user else None,
        }
    except Exception:  # noqa: BLE001 - the grade must still ship
        _log.exception("sim season review failed")
        return {}


__all__ = ["build_review"]
