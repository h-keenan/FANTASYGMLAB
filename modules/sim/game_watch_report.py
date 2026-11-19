"""The Draft & Watch report card: how the draft looked then against how it played out, read off the finished season.

Pure and read-only, like ``game_wrapped``. Two shapes come back together:

* the plain report (``draft`` then vs now, ``best_value``, ``bust`` with its why, ``standing``, ``moves``, ``what_ifs``), which the
  resting page shows, and
* ``cards``: the same story as a deck for the shared Wrapped story component (draft graded round by round, picks that paid off,
  picks that did not and why, the steal and the reach, the ones that stung, the final standing).

Every number comes from the real season (no replays, nothing invented). Player names in body copy are always "J. Surname".
"""

from __future__ import annotations

import statistics
from typing import Any, Mapping, Sequence

from modules.sim import game_wrapped_data as wd
from modules.sim.analysis import letter_for
from modules.sim.game_draft import _letter
from modules.sim.game_engine import _brief, standing_rows
from modules.sim.game_review import _total
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot

LOOKAHEAD = 12  # picks after yours a what-if compares against
SKIP_POS = ("K", "DEF")
ROUNDS_SHOWN = 5
LIST_SIZE = 3
_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def _short(name: str | None) -> str:
    parts = str(name or "").split()
    if len(parts) < 2:
        return parts[0] if parts else ""
    last = " ".join(parts[-2:]) if parts[-1].lower() in _SUFFIXES and len(parts) > 2 else parts[-1]
    return f"{parts[0][0].upper()}. {last}"


def _round(v: float) -> float:
    return round(float(v), 1)


def _pick_label(p: Mapping[str, Any]) -> str:
    return f"Round {p['round']}, pick {int(p['n']) + 1}"


def _short_pick(p: Mapping[str, Any]) -> str:
    return f"Rd {p['round']}, #{int(p['n']) + 1}"


def _pick_letter(delta: float) -> str:
    """A letter for a pick from its points against what was expected of it. Never below a D-: a pick is judged, not failed."""
    return letter_for(max(60.0, min(100.0, 78.0 + delta / 3.0)))


def _draft_then(events: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    for e in events:
        if e["type"] in ("draft_complete", "league_start", "midseason_start"):
            mine = ((e["payload"].get("recap") or {}).get("your_team")) or {}
            if mine.get("grade"):
                return {"grade": mine["grade"], "rank": mine.get("rank")}
    return None


def _draft_now(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    totals = {t.tid: 0.0 for t in snap.teams}
    for p in state.picks:
        totals[p["team"]] += _total(state.points, p["pid"])[0]
    order = sorted(snap.tids, key=lambda t: (-totals[t], t))
    rank = order.index(snap.user_team.tid) + 1
    return {"grade": _letter(rank - 1, len(order)), "rank": rank, "points": round(totals[snap.user_team.tid], 1)}


def _finish_rank(snap: GameSnapshot, state: GameState, pid: str) -> str:
    """"RB14": where the player finished in his position by season points."""
    pos = snap.players[pid].pos
    mine = _total(state.points, pid)[0]
    ahead = sum(1 for p in snap.pids if snap.players[p].pos == pos and _total(state.points, p)[0] > mine)
    return f"{pos}{ahead + 1}"


def _rounds(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    """The user's points per draft round against what the league's teams averaged in it."""
    user = snap.user_team.tid
    per: dict[int, dict[str, float]] = {}
    for p in state.picks:
        per.setdefault(int(p["round"]), {}).setdefault(p["team"], 0.0)
        per[int(p["round"])][p["team"]] += _total(state.points, p["pid"])[0]
    out = []
    for rnd in sorted(per)[:ROUNDS_SHOWN]:
        teams = per[rnd]
        out.append({"round": rnd, "actual": _round(teams.get(user, 0.0)), "expected": _round(statistics.mean(teams.values()))})
    return out


def build_watch_report(snap: GameSnapshot, state: GameState, events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    user = snap.user_team.tid
    teams = len(snap.tids)
    rows = standing_rows(snap, state)
    me = next(r for r in rows if r["team_id"] == user)
    outcome = (state.playoff or {}).get("results", {}).get(user, "missed")
    if state.champion == user:
        outcome = "champion"
    picks = list(state.picks)
    round_pts: dict[int, list[float]] = {}
    for p in picks:
        round_pts.setdefault(int(p["round"]), []).append(_total(state.points, p["pid"])[0])
    mine = []
    for p in picks:
        if p["team"] != user or p["pid"] not in snap.players or snap.players[p["pid"]].pos in SKIP_POS:
            continue
        pts, games = _total(state.points, p["pid"])
        proj = round(sum((state.proj_hist.get(p["pid"]) or {}).values()), 1)
        mine.append({"pick": p, "pts": pts, "games": games, "proj": proj, "vs_round": pts - statistics.mean(round_pts[int(p["round"])])})

    def why(m: Mapping[str, Any]) -> dict[str, Any]:
        proj = m["proj"] if m["proj"] > 0 else m["pts"]
        return wd.reason_tag(snap, state, m["pick"]["pid"], games=m["games"], proj=proj, pts=m["pts"])

    ranked = sorted(mine, key=lambda m: (-m["vs_round"], m["pick"]["pid"]))
    best = ranked[0] if ranked else None
    worst = ranked[-1] if ranked else None
    bust_rows = sorted((m for m in mine if m["proj"] > 0 and m["pts"] < m["proj"]), key=lambda m: (m["pts"] - m["proj"], m["pick"]["pid"]))
    bust = None
    if bust_rows:
        b = bust_rows[0]
        tag = why(b)
        bust = {
            "player": _brief(snap, b["pick"]["pid"]), "pick": _pick_label(b["pick"]), "projected": b["proj"], "actual": _round(b["pts"]),
            "gap": _round(b["pts"] - b["proj"]), "why": tag["text"] or "Fell short of his projection", "why_tag": tag["tag"], "games_missed": tag["games_missed"],
        }
    what_ifs = _what_ifs(snap, state, mine, picks)
    then, now = _draft_then(events), _draft_now(snap, state)
    standing = {"rank": me["rank"], "teams": teams, "record": f"{me['wins']}-{me['losses']}" + (f"-{me['ties']}" if me["ties"] else ""),
                "outcome": outcome, "champion": snap.team(state.champion).name if state.champion else None}
    report = {
        "sliders": {"waivers": snap.settings.watch_waivers, "trades": snap.settings.watch_trades},
        "standing": standing,
        "draft": {"then": then, "now": now, "teams": teams},
        "best_value": None if not best or best["vs_round"] <= 0 else {
            "player": _brief(snap, best["pick"]["pid"]), "pick": _pick_label(best["pick"]), "pts": _round(best["pts"]), "over_round": _round(best["vs_round"]),
        },
        "bust": bust,
        "moves": _moves(snap, events),
        "what_ifs": what_ifs[:3],
    }
    report["cards"] = _cards(snap, state, report, ranked, bust_rows, why, best, worst)
    return report


def _moves(snap: GameSnapshot, events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    user = snap.user_team.tid
    adds = sum(1 for e in events if e["type"] == "waiver_result" and e["payload"].get("team") == user and e["payload"].get("ok"))
    trades = sum(1 for e in events if e["type"] == "trade" and e["actor"] == "user")
    return {"waivers": adds, "trades": trades}


def _what_ifs(snap: GameSnapshot, state: GameState, mine: Sequence[Mapping[str, Any]], picks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Three what-ifs from the real season: the players taken just after your picks who out-scored them (distinct players), then the
    best player nobody held and the points the bench kept when fewer than three picks qualify."""

    user = snap.user_team.tid
    seen: set[str] = set()
    found = []
    for m in mine:
        n = int(m["pick"]["n"])
        for q in picks:
            if n < int(q["n"]) <= n + LOOKAHEAD and q["team"] != user and q["pid"] in snap.players and snap.players[q["pid"]].pos not in SKIP_POS:
                theirs = _total(state.points, q["pid"])[0]
                if theirs - m["pts"] > 0:
                    found.append((theirs - m["pts"], q["pid"], m, q, theirs))
    found.sort(key=lambda f: (-f[0], f[1]))
    out: list[dict[str, Any]] = []
    for gap, pid, m, q, theirs in found:
        if pid in seen or len(out) >= LIST_SIZE:
            continue
        seen.add(pid)
        out.append({
            "id": f"passed_on_{len(out) + 1}", "title": "The pick you passed on", "delta": _round(gap),
            "text": f"At {_pick_label(m['pick']).lower()} you took {_short(snap.players[m['pick']['pid']].name)} ({_round(m['pts'])} pts). "
                    f"{_short(snap.players[pid].name)} went {int(q['n']) - int(m['pick']['n'])} picks later and scored {_round(theirs)}.",
            "after": _short(snap.players[m["pick"]["pid"]].name), "players": [_brief(snap, pid)],
        })
    if len(out) < LIST_SIZE:
        wire = [(sum(v for v in (state.points.get(p) or [])[2:] if v is not None), p) for p in state.free_agents(snap) if snap.players[p].pos not in SKIP_POS]
        if wire:
            pts, pid = max(wire)
            if pts > 0:
                out.append({"id": "wire", "title": "The one left on the wire", "delta": _round(pts),
                            "text": f"{_short(snap.players[pid].name)} was never claimed by anyone and scored {_round(pts)} points from week 3 on.",
                            "after": "the waiver wire", "players": [_brief(snap, pid)]})
    if len(out) < LIST_SIZE:
        bench = wd.bench_points(state)
        if bench["weeks"]:
            flipped = len(bench["lost_by_lineup"])
            out.append({"id": "lineups", "title": "A perfect lineup every week", "delta": _round(bench["left_total"]),
                        "text": f"The auto-set lineups left {_round(bench['left_total'])} points on the bench"
                                + (f"; with hindsight that flips {flipped} loss{'es' if flipped != 1 else ''}." if flipped else ", but never cost you a game."),
                        "after": "your lineups", "players": []})
    return out


def _cards(snap, state, report, ranked, bust_rows, why, best, worst) -> list[dict[str, Any]]:
    """The report as Wrapped-style cards (same card shape as game_wrapped: id, eyebrow, title, sub, pro, locked, data)."""

    year = snap.settings.start_year + state.season_no - 1
    now = report["draft"]["now"]["grade"]
    standing = report["standing"]

    def card(cid: str, eyebrow: str, title: str, sub: str | None, data: dict[str, Any]) -> dict[str, Any]:
        return {"id": cid, "eyebrow": eyebrow, "title": title, "sub": sub, "pro": False, "locked": False, "data": data}

    def pick_row(m: Mapping[str, Any], delta: float, reason: str) -> dict[str, Any]:
        return {"player": _brief(snap, m["pick"]["pid"]), "text": " · ".join(x for x in (_short_pick(m["pick"]), reason) if x),
                "grade": _pick_letter(delta), "delta": _round(delta)}

    cards = [card("watch_draft", "DRAFT REPORT CARD", "Your draft, graded", f"Draft & Watch · {year} · actual vs expected, by round",
                  {"grade": now, "then": (report["draft"]["then"] or {}).get("grade"), "rounds": _rounds(snap, state)})]
    hits = [m for m in ranked if m["vs_round"] > 0][:LIST_SIZE]
    if hits:
        cards.append(card("watch_hits", "HITS", "Picks that paid off", "Points above the slot's expectation",
                          {"rows": [pick_row(m, m["vs_round"], (why(m)["text"] if why(m)["tag"] == wd.TAG_BREAKOUT else "")) for m in hits]}))
    busts = bust_rows[:LIST_SIZE]
    if busts:
        cards.append(card("watch_busts", "BUSTS", "Picks that did not", "And the reason, not just the number",
                          {"rows": [pick_row(m, m["pts"] - m["proj"], why(m)["text"] or "Fell short of his projection") for m in busts]}))
    if best and worst and best["vs_round"] > 0 and worst is not best:
        cards.append(card("watch_value", "STEAL AND REACH", "Your best and worst value", None, {"steal": {
            "player": _brief(snap, best["pick"]["pid"]), "text": f"{_pick_label(best['pick'])} · finished {_finish_rank(snap, state, best['pick']['pid'])}",
            "delta": _round(best["vs_round"]),
        }, "reach": {
            "player": _brief(snap, worst["pick"]["pid"]), "text": f"{_pick_label(worst['pick'])} · finished {_finish_rank(snap, state, worst['pick']['pid'])}",
            "delta": _round(worst["vs_round"]),
        }}))
    if report["what_ifs"]:
        cards.append(card("watch_whatif", "WHAT IF", "The ones that stung", "Who was on the board",
                          {"rows": [{"player": (w["players"][0] if w["players"] else None), "text": f"Went right after {w['after']}" if w["id"].startswith("passed_on") else w["title"],
                                     "delta": w["delta"], "grade": None} for w in report["what_ifs"]]}))
    best_name = _short(snap.players[best["pick"]["pid"]].name) if best else "-"
    worst_name = _short(snap.players[worst["pick"]["pid"]].name) if worst else "-"
    cards.append(card("watch_standing", "FINAL STANDING", {"champion": "Champions", "runner_up": "Lost in the final", "semifinal": "Lost in the semifinal", "missed": "Missed the playoffs"}.get(standing["outcome"], "Season complete"),
                      f"{standing['record']} · same draft, one season of luck",
                      {"grade": now, "rows": [{"label": "Record", "value": standing["record"]}, {"label": "Best pick", "value": best_name, "tone": "good"}, {"label": "Worst pick", "value": worst_name}]}))
    return cards


__all__ = ["build_watch_report"]
