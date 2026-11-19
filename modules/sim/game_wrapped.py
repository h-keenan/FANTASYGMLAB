"""Season Wrapped for the Fantasy Sim: the card deck read off a finished (or in-progress, "so far") game.

Pure and read-only. It reads ``game_wrapped_data`` (expected wins, bench points, reason tags), the stored result's grade and the
event log (trades and waiver pickups), and returns plain JSON::

    {"kind": "sim", "partial": bool, "season_label": str, "team_name": str, "cards": [card, ...]}
    card = {"id", "eyebrow", "title", "sub", "pro": bool, "locked": bool, "data": {...} | None}

``locked`` cards (the Pro ones, for a free viewer) carry no data: the gate is here, not in the client. The personality card is free.
Every card the data cannot support is left out rather than invented, so a short or one-sided season simply has fewer cards.
"""

from __future__ import annotations

import statistics
from typing import Any, Mapping, Sequence

from modules.sim import game_wrapped_data as wd
from modules.sim.analysis import letter_for
from modules.sim.game_engine import _brief, standing_rows
from modules.sim.game_review import _sum_from, _total
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot

PRO_CARDS = ("steal", "trades")
MIN_WEEKS = 2  # fewer played weeks than this and there is nothing to wrap yet


_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def short_name(name: str | None) -> str:
    """"Jalen Pruitt" -> "J. Pruitt" (the same rule as the clients' wrappedShortName): body copy never carries a full player name."""

    parts = str(name or "").split()
    if len(parts) < 2:
        return parts[0] if parts else ""
    last = " ".join(parts[-2:]) if parts[-1].lower() in _SUFFIXES and len(parts) > 2 else parts[-1]
    return f"{parts[0][0].upper()}. {last}"


def _r(v: float, places: int = 1) -> float:
    return round(float(v), places)


def _pick_label(state: GameState, snap: GameSnapshot, pid: str) -> str | None:
    for p in state.picks:
        if p["pid"] == pid and p["team"] == snap.user_team.tid:
            return f"Round {p['round']}, pick {int(p['n']) + 1}"
    return None


def _games(state: GameState) -> list[tuple[int, dict[str, Any]]]:
    out = []
    for key in sorted(state.recaps, key=int):
        rc = state.recaps[key]
        g = rc.get("your_game") if isinstance(rc, dict) and rc.get("kind") == "regular" else None
        if g and "your_pts" in g:
            out.append((int(key), g))
    return out


def _grade_tone(letter: str) -> str:
    return "good" if letter[:1] in "AB" else "neutral"


def _net_letter(net: float) -> str:
    return letter_for(max(0.0, min(100.0, 70.0 + net / 4.0)))


def _moves(snap: GameSnapshot, state: GameState, events: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    user = snap.user_team.tid
    trades, waivers = [], []
    for e in events:
        p = e["payload"]
        week = int(e.get("week") or 1)
        if e["type"] == "trade" and e["actor"] == "user" and user in (p["team_a"], p["team_b"]):
            sent, got = (p["give"], p["get"]) if p["team_a"] == user else (p["get"], p["give"])
            got_pts = sum(_sum_from(state.points, i, week) for i in got)
            sent_pts = sum(_sum_from(state.points, i, week) for i in sent)
            trades.append({"week": week, "sent": list(sent), "got": list(got), "net": got_pts - sent_pts})
        elif e["type"] == "waiver_result" and p.get("team") == user and p.get("ok"):
            added = _sum_from(state.points, p["add"], week)
            dropped = _sum_from(state.points, p["drop"], week) if p.get("drop") else 0.0
            waivers.append({"week": week, "add": p["add"], "drop": p.get("drop"), "pts": added, "net": added - dropped})
    return trades, waivers


def _assets(snap: GameSnapshot, pids: Sequence[str]) -> list[dict[str, Any]]:
    return [b for b in (_brief(snap, i) for i in pids if i in snap.players) if b]


def _persona(adds: int, trades: int, efficiency: float, draft_rank: int, teams: int, started_adds: int) -> dict[str, Any]:
    scores = {
        "waiver_hawk": adds + 0.5 * started_adds,
        "trade_shark": trades * 3.0,
        "lineup_perfectionist": max(0.0, (efficiency - 0.85) * 60.0),
        "draft_day_sharp": max(0.0, (teams / 2 - draft_rank) * 1.2) if adds + trades <= 6 else 0.0,
        "set_and_forget": max(0.0, 6.0 - adds - trades),
    }
    names = {
        "waiver_hawk": ("The Waiver Hawk", "swap"), "trade_shark": ("The Trade Shark", "swap"),
        "lineup_perfectionist": ("The Lineup Perfectionist", "check"), "draft_day_sharp": ("The Draft Day Sharp", "target"),
        "set_and_forget": ("The Set-and-Forget Manager", "clock"),
    }
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top, second = ranked[0][0], ranked[1][0]
    return {"key": top, "name": names[top][0], "glyph": names[top][1], "runner_up": names[second][0]}


def build_wrapped(
    snap: GameSnapshot, state: GameState, events: Sequence[Mapping[str, Any]], result: Mapping[str, Any] | None, *, is_pro: bool,
) -> dict[str, Any]:
    """The Wrapped deck. ``result`` is the stored end-of-season result (None while the season is still being played)."""

    partial = state.status != "complete"
    user = snap.user_team.tid
    team_name = snap.user_team.name
    teams = len(snap.tids)
    games = _games(state)
    year = snap.settings.start_year + state.season_no - 1
    label = f"Sim Season {state.season_no} · {year}" if year else f"Sim Season {state.season_no}"
    deck: dict[str, Any] = {"kind": "sim", "partial": partial, "season_label": label, "team_name": team_name, "cards": []}
    if len(games) < MIN_WEEKS:
        return deck
    data = wd.season_data(snap, state)
    rows = standing_rows(snap, state)
    me = next(r for r in rows if r["team_id"] == user)
    cards: list[dict[str, Any]] = []
    so_far = "Through the week so far" if partial else None

    def add(cid: str, eyebrow: str, title: str, sub: str | None, body: dict[str, Any] | None) -> None:
        if body is None:
            return
        pro = cid in PRO_CARDS
        locked = pro and not is_pro
        cards.append({"id": cid, "eyebrow": eyebrow, "title": title, "sub": sub, "pro": pro, "locked": locked, "data": None if locked else body})

    # 1. intro
    outcome = (state.playoff or {}).get("results", {}).get(user) if state.playoff else None
    outcome_text = {"champion": "Champions", "runner_up": "Lost in the final", "semifinal": "Lost in the semifinal", "missed": "Missed the playoffs"}.get(outcome or "")
    record = f"{me['wins']}-{me['losses']}" + (f"-{me['ties']}" if me["ties"] else "")
    add("intro", label.upper() if not partial else "SEASON SO FAR", "Your season, wrapped", team_name,
        {"record": record, "outcome": outcome_text if not partial else f"Rank {me['rank']} of {teams}", "rank": me["rank"], "weeks": len(games)})

    # 2. MVP and 3. bust
    lines = [a for a in data["players"] if a["games"]]
    if lines:
        mvp = max(lines, key=lambda a: (a["over_proj"], a["pid"]))
        total_pts = sum(a["pts"] for a in lines) or 1.0
        add("mvp", "MVP", "Your most valuable player", so_far or "Points above projection",
            {"player": _brief(snap, mvp["pid"]), "pts": mvp["pts"], "over_proj": mvp["over_proj"], "ppg": mvp["ppg"],
             "best": mvp["best"], "share": _r(100.0 * mvp["pts"] / total_pts, 0)})
        bust = min(lines, key=lambda a: (a["over_proj"], a["pid"]))
        if bust["over_proj"] < 0 and bust["pid"] != mvp["pid"]:
            add("bust", "BIGGEST BUST", "The one that got away", _pick_label(state, snap, bust["pid"]),
                {"player": _brief(snap, bust["pid"]), "projected": bust["proj"], "actual": bust["pts"], "over_proj": bust["over_proj"],
                 "why": bust["tag"]["text"] or "Fell short of his projection", "why_tag": bust["tag"]["tag"]})

    # 4. best and worst week
    bw = data["best_worst_week"]
    if bw:
        opp = {wk: g["opponent_name"] for wk, g in games}
        add("weeks", "BEST AND WORST WEEK", "Peak and valley", so_far,
            {"best": {**bw["best"], "opponent": opp.get(bw["best"]["week"])}, "worst": {**bw["worst"], "opponent": opp.get(bw["worst"]["week"])}})

    # 5. the steal (Pro): the user's pick that out-scored its round the most
    round_pts: dict[int, list[float]] = {}
    for p in state.picks:
        round_pts.setdefault(int(p["round"]), []).append(_total(state.points, p["pid"])[0])
    mine = []
    for p in state.picks:
        if p["team"] != user or p["pid"] not in snap.players or snap.players[p["pid"]].pos in ("K", "DEF"):
            continue
        pts = _total(state.points, p["pid"])[0]
        base = statistics.mean(round_pts[int(p["round"])])
        mine.append((pts - base, p, pts))
    if mine:
        gain, pick, pts = max(mine, key=lambda m: (m[0], m[1]["pid"]))
        if gain > 0:
            add("steal", "THE STEAL", "Best value on your roster", "Points against what it cost you",
                {"player": _brief(snap, pick["pid"]), "over_cost": _r(gain), "round": int(pick["round"]), "pick": int(pick["n"]) + 1, "pts": _r(pts)})

    # 6. Mr. Consistent vs Rollercoaster (needs 5+ starts)
    per: dict[str, list[tuple[float, float]]] = {}
    for wk, g in games:
        for r in g["starters"]:
            pl = r.get("player")
            if pl and r.get("flag") is None:
                proj = (state.proj_hist.get(pl["id"]) or {}).get(str(wk), r.get("proj"))
                per.setdefault(pl["id"], []).append((float(r["pts"]), float(proj or 0.0)))
    steady = [(pid, v) for pid, v in per.items() if len(v) >= 5]
    if len(steady) >= 2:
        def spread(v: list[tuple[float, float]]) -> float:
            return statistics.pstdev([a for a, _ in v])
        cons = min(steady, key=lambda kv: (spread(kv[1]) / max(1.0, statistics.mean(a for a, _ in kv[1])), kv[0]))
        roll = max((s for s in steady if s[0] != cons[0]), key=lambda kv: (spread(kv[1]), kv[0]))

        def pack(entry: tuple[str, list[tuple[float, float]]]) -> dict[str, Any]:
            pid, v = entry
            beat = [a >= b for a, b in v]
            return {"player": _brief(snap, pid), "beat": beat[-14:], "beat_count": sum(beat), "games": len(beat), "swing": _r(spread(v))}
        add("consistency", "CONSISTENCY", "Mr. Consistent vs Rollercoaster", "Weeks over projection", {"consistent": pack(cons), "rollercoaster": pack(roll)})

    # 7. trades (Pro) and 8. best pickup
    trades, waivers = _moves(snap, state, events)
    if trades:
        best = max(trades, key=lambda t: (t["net"], -t["week"]))
        worst = min(trades, key=lambda t: (t["net"], t["week"]))

        def tpack(t: dict[str, Any]) -> dict[str, Any]:
            return {"week": t["week"], "grade": _net_letter(t["net"]), "got": _assets(snap, t["got"]), "sent": _assets(snap, t["sent"]), "net": _r(t["net"])}
        add("trades", "TRADES", "Best and worst trade", "Graded on what happened next",
            {"best": tpack(best), "worst": tpack(worst) if worst is not best else None})
    if waivers:
        bw_ = max(waivers, key=lambda w: (w["net"], -w["week"]))
        add("waiver", "WAIVER WIRE", "Best pickup", f"Added in week {bw_['week']}",
            {"player": _brief(snap, bw_["add"]), "net": _r(bw_["net"]), "pts": _r(bw_["pts"]), "week": bw_["week"],
             "dropped": _brief(snap, bw_["drop"]) if bw_["drop"] in snap.players else None})

    # 9. points left on the table
    bench = data["bench"]
    close_lost = [(g["opp_pts"] - g["your_pts"], wk) for wk, g in games if g["result"] == "loss"]
    close_won = [(g["your_pts"] - g["opp_pts"], wk) for wk, g in games if g["result"] == "win"]
    if bench["weeks"]:
        lost = min(close_lost) if close_lost else None
        won = min(close_won) if close_won else None
        big = bench["biggest_miss"]
        add("close", "CLOSE CALLS", "Points left on the table", so_far,
            {"lost_by": None if lost is None else {"margin": _r(lost[0]), "week": lost[1]},
             "won_by": None if won is None else {"margin": _r(won[0]), "week": won[1]},
             "bench_pts": bench["total"], "left_on_bench": bench["left_total"], "complete": bench["complete"],
             "miss": None if not big else {"player": big["player"], "week": big["week"], "pts": big["pts"], "proj": big.get("proj")}})

    # 10. luck
    luck = data["luck"]
    add("luck", "LUCK", "You deserved better" if luck["diff"] < -0.4 else "How the season fell", f"All-play record {_allplay(state, user, teams)}",
        {"actual_wins": luck["actual_wins"], "expected_wins": luck["expected_wins"], "diff": luck["diff"], "games": luck["games"]})

    # 11. rank journey
    journey = data["rank_journey"]
    if len(journey) >= MIN_WEEKS:
        ranks = [j["rank"] for j in journey]
        add("journey", "RANK JOURNEY", f"{_ord(ranks[0])} to {_ord(ranks[-1])}", f"Peaked at {_ord(min(ranks))}",
            {"ranks": ranks, "weeks": [j["week"] for j in journey], "teams": teams})

    # 12. grade with sub-grades
    efficiency, _ = _eff(state)
    draft = (result or {}).get("draft") or _draft_grade(snap, state)
    t_net = sum(t["net"] for t in trades)
    w_net = sum(w["net"] for w in waivers)
    subs = [
        {"key": "draft", "label": "Draft", "letter": draft["grade"] if isinstance(draft.get("grade"), str) else letter_for(70)},
        {"key": "lineups", "label": "Lineups", "letter": letter_for(max(0.0, min(100.0, (efficiency - 0.8) / 0.2 * 100.0)))},
        {"key": "waivers", "label": "Waivers", "letter": _net_letter(w_net) if waivers else "-"},
        {"key": "trades", "label": "Trades", "letter": _net_letter(t_net) if trades else "-"},
    ]
    overall = ((result or {}).get("grade") or {}).get("letter")
    if not overall:
        pts = [_LETTER_PTS.get(s["letter"]) for s in subs if s["letter"] != "-"]
        pts = [p for p in pts if p is not None]
        overall = letter_for(sum(pts) / len(pts)) if pts else "C"
    add("grade", "GRADE SO FAR" if partial else "FINAL GRADE", "How you managed it", team_name, {"overall": overall, "subs": subs})

    # 13. personality (free)
    adds = len(waivers)
    started = {pl["id"] for _, g in games for r in g["starters"] for pl in [r.get("player")] if pl}
    draft_rank = int(((result or {}).get("draft") or {}).get("rank") or _draft_rank(snap, state, user))
    persona = _persona(adds, len(trades), efficiency, draft_rank, teams, sum(1 for w in waivers if w["add"] in started))
    best_w = max(waivers, key=lambda w: w["net"]) if waivers else None
    lines_ = []
    if adds:
        lines_.append(f"{adds} waiver pickups, {sum(1 for w in waivers if w['add'] in started)} of them starters")
    if best_w and best_w["add"] in snap.players:
        lines_.append(f"{short_name(snap.players[best_w['add']].name)} alone was worth {_r(best_w['net'])} pts")
    if trades:
        lines_.append(f"{len(trades)} trade{'s' if len(trades) != 1 else ''}")
    lines_.append(f"Lineups at {int(round(efficiency * 100))}% of the best you could have set")
    add("persona", "YOUR MANAGER TYPE", "Who you were this season" if not partial else "Who you are so far", None,
        {**persona, "lines": lines_[:3]})

    deck["cards"] = cards
    return deck


_LETTER_PTS = {"A": 95, "A-": 91, "B+": 88, "B": 85, "B-": 81, "C+": 78, "C": 75, "C-": 71, "D+": 68, "D": 65, "D-": 61, "F": 50}


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _eff(state: GameState) -> tuple[float, list[dict[str, Any]]]:
    from modules.sim.game_result import _efficiency

    return _efficiency(state)


def _draft_grade(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    from modules.sim.game_result import _draft_from_state

    try:
        d = _draft_from_state(snap, state)["your_team"]
        return {"grade": d["grade"], "rank": d["rank"]}
    except Exception:  # noqa: BLE001 - a missing draft grade only drops that sub-grade to neutral
        return {"grade": letter_for(70), "rank": max(1, len(snap.tids) // 2)}


def _draft_rank(snap: GameSnapshot, state: GameState, user: str) -> int:
    return int(_draft_grade(snap, state).get("rank") or max(1, len(snap.tids) // 2))


def _allplay(state: GameState, tid: str, teams: int) -> str:
    rows = wd.weekly_scores(state, tid)
    per = max(1, teams - 1)
    wins = round(sum(r["all_play"] for r in rows) * per)
    return f"{wins}-{len(rows) * per - wins}"


__all__ = ["build_wrapped", "PRO_CARDS"]
