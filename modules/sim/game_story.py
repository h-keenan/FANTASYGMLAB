"""A player's story, in plain language, derived from the game's event log (never stored).

"Why did he go from QB2 to not getting playing time?" is answered from what the log already holds: the ``depth_chart`` events
(``incumbent_v`` 1+: who took whose starting job and why), the ``injury`` events (with their type from ``injury_v`` 1+ and the weeks
missed), every trade / claim / cut / draft pick, and each season's scoring and depth-chart standing (his slot behind which players,
read from that season's player pool). The same pass folds the **injury history** (games missed per season, career, and the injury he
is serving now), shaped for the shared ``InjuryHistorySection``.

``player_view`` is the one entry point: ``player_history`` (origin, moves, seasons) plus ``story`` and ``injuries``. Pure and
replay-safe, like ``game_history``: a fold over the ordered events with no model change and nothing written to a save.

``depth_chart_view`` is the state-based twin for the Depth chart section: the player's NFL team and position in the sim's own
depth order right now.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules.sim import game_history as hist
from modules.sim import team_roles as tr
from modules.sim.game_history import _Clock, _Names
from modules.sim.game_types import GameSnapshot
from modules.sim.injuries import kinds_from_event, out_label
from modules.sim.season_label import season_label

SLOTTED = ("QB", "RB", "WR", "TE")  # the positions with a depth chart (team_roles.STARTER_SLOTS)
POS_NAMES = {"QB": "Quarterback", "RB": "Running back", "WR": "Wide receiver", "TE": "Tight end"}

WHY_LOST = {
    "outperformed_incumbent": "outperformed him",
    "rookie_won_job": "rookie won the job",
    "incumbent_aged": "age caught up with him",
    "incumbent_retired": "he retired",
    "incumbent_left": "he left the team",
    "filled_open_slot": "an open spot filled",
}
WHY_WON = {
    "outperformed_incumbent": "outperformed the incumbent",
    "rookie_won_job": "rookie won the job",
    "incumbent_aged": "the incumbent aged out",
    "incumbent_retired": "the incumbent retired",
    "incumbent_left": "the incumbent left",
    "filled_open_slot": "open spot",
}
BIG_RANK = 6  # a top-6 finish at his position is a big season
BUST_DROP = 0.6  # a season under 60 percent of last year's per-game scoring, after a top-12 year, is a bust
BUST_PRIOR_RANK = 12


def short_name(name: str) -> str:
    """"Rob Cole" -> "R. Cole" (a name with one word stays as it is)."""

    parts = str(name).split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else str(name)


def _games_label(n: int) -> str:
    return f"{n} game{'' if n == 1 else 's'}"


def _weeks_label(n: int) -> str:
    return f"{n} week{'' if n == 1 else 's'}"


def _role_label(players: Mapping[str, Any], book: tr.RoleBook, pid: str) -> tuple[str | None, list[str]]:
    """("QB2", [pids ahead of him on the chart]) for a player in a season's pool; (None, []) when he is not on a chart."""

    key = book.key(pid)
    if key is None:
        return None, []
    order = [m.pid for m in book.groups[key]]
    i = order.index(pid)
    return f"{key[1]}{i + 1}", order[:i]


def player_view(root: GameSnapshot, events: Iterable[Mapping[str, Any]], pid: str) -> dict[str, Any]:
    """``player_history`` plus the ``story`` timeline and the ``injuries`` record, in one pass over the events each."""

    evs = list(events)
    base = hist.player_history(root, evs, pid)
    return {**base, **_story(root, evs, pid)}


# ------------------------------------------------------------------ the fold


def _story(root: GameSnapshot, events: list[Mapping[str, Any]], pid: str) -> dict[str, Any]:
    names = _Names(root)
    clock = _Clock(root)
    S = root.settings
    start_year = int(S.start_year or 0)
    regular = int(S.regular_weeks)
    items: list[dict[str, Any]] = []  # {season, week, order, ...} sorted at the end
    seq = 0
    completed: set[int] = set()
    totals: dict[int, dict[str, float]] = {}  # season -> pid -> points (every player: a position rank needs the field)
    games: dict[int, int] = {}  # season -> his games
    injuries: list[dict[str, Any]] = []  # his injuries: {season, year, week, weeks, games, kind}
    out_left = 0
    out_kind: str | None = None
    holder: str | None = None

    def year_of(season: int) -> int | None:
        return start_year + season - 1 if start_year else None

    def put(kind: str, season: int, week: int, text: str, tone: str = "neutral", **extra: Any) -> None:
        nonlocal seq
        seq += 1
        items.append({"kind": kind, "season": season, "year": year_of(season), "season_label": season_label(season, year_of(season)), "week": week, "text": text, "tone": tone, "_i": seq, **extra})

    def team(tid: str | None) -> str:
        return names.team(tid) or "a team"

    def when(ev: Mapping[str, Any]) -> tuple[int, int]:
        """(season, week) of an event; the offseason (after a season is complete, before the next starts) belongs to the next season at week 0."""
        if clock.offseason_year is not None:
            return clock.season_no + 1, 0
        return clock.season_no, int(ev.get("week") or 0)

    for ev in events:
        kind, p = ev["type"], ev["payload"]
        season, week = when(ev)
        if kind == "league_rosters":
            for tid in (t.tid for t in root.teams):
                if pid in (*root.start_rosters.get(tid, ()), *root.start_ir.get(tid, ()), *root.start_taxi.get(tid, ())):
                    holder = tid
                    put("started", 1, 0, f"Began the game on {team(tid)}")
        elif kind == "draft_pick" and p["pid"] == pid:
            holder = p["team"]
            put("drafted", season, week, f"Drafted by {team(holder)} in round {int(p['round'])} (pick {int(p['n']) + 1})")
        elif kind == "rookie_pick" and p["pid"] == pid:
            holder = p["team"]
            put("drafted", season, week, f"Picked by {team(holder)} in the rookie draft, round {int(p['round'])} (pick {int(p['n']) + 1})")
        elif kind == "waiver_result" and p.get("ok"):
            if p.get("drop") == pid:
                put("dropped", season, week, f"Dropped by {team(p['team'])}")
                holder = None
            if p.get("add") == pid:
                holder = p["team"]
                put("claimed", season, week, f"Claimed by {team(holder)}" + (f", dropping {names.player(p['drop'])['name']}" if p.get("drop") else ""))
        elif kind in ("cut", "drop") and p.get("pid") == pid:
            put("cut", season, week, f"Cut by {team(p['team'])}", "bad")
            holder = None
        elif kind == "trade":
            for src, dst, sent in ((p["team_a"], p["team_b"], p["give"]), (p["team_b"], p["team_a"], p["get"])):
                if pid in sent:
                    got = p["get"] if src == p["team_a"] else p["give"]
                    back = ", ".join(names.player(x)["name"] for x in got)
                    holder = dst
                    put("traded", season, week, f"Traded from {team(src)} to {team(dst)}" + (f" for {back}" if back else ""))
        elif kind == "season_complete":
            if pid in {str(x) for x in p.get("retired", ())}:
                put("retired", season, week, "Retired", "neutral")
            completed.add(clock.season_no)
        elif kind == "depth_chart":
            _depth(put, names, pid, p, season_of=int(p.get("season_no") or season), week=week if p.get("phase") == "in_season" else 0)
        elif kind == "injury":
            kinds = kinds_from_event(p)
            for it in p.get("items", ()):
                if it[0] != pid:
                    continue
                weeks = int(it[1])
                hurt_week = int(ev.get("week") or 0)
                missed = max(0, min(hurt_week + weeks, regular) - hurt_week)
                injuries.append({"season": clock.season_no, "week": hurt_week, "weeks": weeks, "games": missed, "kind": kinds.get(pid)})
                out_left, out_kind = weeks, kinds.get(pid)
                what = kinds.get(pid) or "Injured"
                put("injury", clock.season_no, hurt_week, f"{what} in Week {hurt_week}: out {_weeks_label(weeks)}" + (f", missed {_games_label(missed)}" if 0 < missed < weeks else ""), "bad", weeks=weeks, injury=kinds.get(pid))
        elif kind == "week_scored":
            tot = totals.setdefault(clock.season_no, {})
            for other, v in p["points"].items():
                if v is not None:
                    tot[other] = tot.get(other, 0.0) + float(v)
            if p["points"].get(pid) is not None:
                games[clock.season_no] = games.get(clock.season_no, 0) + 1
            out_left = max(0, out_left - 1)
        elif kind == "season_started":
            out_left, out_kind = 0, None
        clock.feed(ev)

    last_season = clock.season_no
    items.extend(_season_lines(root, pid, names, last_season, completed, totals, games, injuries, regular, year_of))
    items.extend(_team_moves(root, pid, last_season, year_of))
    items.sort(key=lambda e: (e["season"], e["week"], e["_i"] if "_i" in e else 0))
    for e in items:
        e.pop("_i", None)
    return {"story": items, "injuries": _injury_record(injuries, last_season, start_year, out_left, out_kind)}


def _depth(put, names: _Names, pid: str, p: Mapping[str, Any], *, season_of: int, week: int) -> None:
    for c in p.get("changes", ()):
        mine_gain, mine_lost = c.get("pid") == pid, c.get("replaced_pid") == pid
        if not (mine_gain or mine_lost):
            continue
        team, pos, slot, reason = c["nfl_team"], c["pos"], int(c.get("slot") or 1), c.get("reason")
        spot = f"{team} {pos}{slot}"
        other_id = c.get("replaced_pid") if mine_gain else c.get("pid")
        other = short_name(names.player(other_id)["name"]) if other_id else None
        if reason == "injury":
            text = (f"Stepped in at {spot} for hurt {other}" if mine_gain else f"Hurt: {other} stepped in at {spot}"
                    + (f" while he is out {_weeks_label(int(c['weeks']))}" if c.get("weeks") else ""))
            tone = "good" if mine_gain else "bad"
        elif reason == "returned_from_injury":
            text = f"Back from injury: retook the {spot} job from {other}" if mine_gain else f"Back to the bench: {other} returned from injury at {spot}"
            tone = "good" if mine_gain else "bad"
        elif mine_gain:
            text = f"Took the {spot} job" + (f" from {other}" if other else "") + f" ({WHY_WON.get(reason, 'depth chart change')})"
            tone = "good"
        else:
            text = f"Lost the {spot} starting job" + (f" to {other}" if other else "") + f" ({WHY_LOST.get(reason, 'depth chart change')})"
            tone = "bad"
        put("depth", season_of, week, text, tone, nfl_team=team, pos=pos, slot=slot, reason=reason)


def _season_lines(root, pid, names, last_season, completed, totals, games, injuries, regular, year_of) -> list[dict[str, Any]]:
    """One line per season he was in the pool: his depth slot, points, rank, and when he did not play, why (behind whom, or hurt)."""

    out: list[dict[str, Any]] = []
    prev: dict[str, Any] | None = None
    for season in range(1, last_season + 1):
        view = root.season_view(season)
        me = view.players.get(pid)
        if me is None:
            prev = None
            continue
        role, ahead = _role_label(view.players, tr.RoleBook(view.players), pid)
        g = games.get(season, 0)
        pts = totals.get(season, {}).get(pid)
        rank = None
        if pts is not None:
            rank = 1 + sum(1 for o, v in totals[season].items() if v > pts and (q := view.players.get(o)) is not None and q.pos == me.pos)
        missed = sum(i["games"] for i in injuries if i["season"] == season)
        in_progress = season not in completed
        label = role or me.pos
        parts = [label]
        tone = "neutral"
        ppg = round(pts / g, 1) if pts is not None and g else None
        if g:
            parts.append(f"{round(pts, 1)} pts" + (" so far" if in_progress else ""))
            parts.append(_games_label(g))
            if rank is not None and rank <= BIG_RANK and g >= 4:
                parts.append(f"big season: {me.pos}{rank}")
                tone = "good"
            if prev and prev.get("ppg") and ppg is not None and g >= 4 and (prev.get("rank") or 99) <= BUST_PRIOR_RANK and ppg < BUST_DROP * prev["ppg"]:
                parts.append(f"bust: down from {prev['ppg']} to {ppg} ppg")
                tone = "bad"
        elif not in_progress or season < last_season:
            reasons = []
            if missed >= max(1, regular // 2):
                kinds = sorted({i["kind"] for i in injuries if i["season"] == season and i["kind"]})
                reasons.append("missed the year hurt" + (f" ({', '.join(kinds)})" if kinds else ""))
            if ahead:
                reasons.append("behind " + ", ".join(short_name(names.player(a)["name"]) for a in ahead[:3]))
            parts.append("did not play" + (f": {'; '.join(reasons)}" if reasons else ""))
            tone = "bad"
        else:
            if ahead:
                parts.append("behind " + ", ".join(short_name(names.player(a)["name"]) for a in ahead[:3]))
            elif role:
                parts.append("starting")
        out.append({"kind": "season", "season": season, "year": year_of(season), "season_label": season_label(season, year_of(season)), "week": 99,
                    "text": " · ".join(parts), "tone": tone, "role": role, "team": me.nfl_team, "games": g, "points": round(pts, 1) if pts is not None else None, "ppg": ppg, "pos_rank": rank, "_i": 10_000 + season})
        prev = {"ppg": ppg, "rank": rank}
    return out


def _team_moves(root, pid, last_season, year_of) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    prev_team: str | None = None
    for season in range(1, last_season + 1):
        me = root.season_view(season).players.get(pid)
        if me is None:
            prev_team = None
            continue
        cur = str(me.nfl_team or "")
        if prev_team and cur and cur != prev_team:
            out.append({"kind": "nfl_team", "season": season, "year": year_of(season), "season_label": season_label(season, year_of(season)), "week": 0,
                        "text": f"Moved from {prev_team} to {cur}", "tone": "neutral", "_i": 20_000 + season})
        prev_team = cur or prev_team
    return out


def _injury_record(injuries: list[dict[str, Any]], last_season: int, start_year: int, out_left: int, out_kind: str | None) -> dict[str, Any]:
    """The shape the shared InjuryHistorySection reads (web-next/src/lib/playerDepthInjury.ts ``InjuryRecordData``)."""

    def year_of(season: int) -> int:
        return start_year + season - 1 if start_year else season

    by_season: dict[int, list[dict[str, Any]]] = {}
    for i in injuries:
        if i["games"] <= 0:
            continue
        by_season.setdefault(i["season"], []).append({
            "start_week": i["week"] + 1, "end_week": i["week"] + i["games"], "games_missed": i["games"], "injury": i["kind"],
        })
    seasons = [{"season": year_of(s), "season_label": season_label(s, year_of(s)), "games_missed": sum(x["games_missed"] for x in stints), "stints": stints}
               for s, stints in sorted(by_season.items())]
    current = None
    if out_left > 0:
        label = out_label(out_kind, out_left)
        current = {"label": out_kind or "Injury", "status": "Out", "severity": "out", "unavailable": True, "body_part": out_kind, "practice": None,
                   "report": f"Out {_weeks_label(out_left)} more.", "line": label}
    return {"ok": True, "current_season": year_of(last_season), "current": current, "seasons": seasons,
            "career_games_missed": sum(s["games_missed"] for s in seasons), "since_season": year_of(1) if seasons else None, "source": "sim", "method": "game log"}


# ------------------------------------------------------------ the depth chart


def depth_chart_view(snap: GameSnapshot, state: Any, ev: Any, pid: str) -> dict[str, Any] | None:
    """The player's NFL team at his position, in the sim's own depth order right now (``DepthChartData``); None off a chart."""

    book = getattr(ev, "book", None)
    if book is None:
        return None
    key = book.key(pid)
    if key is None:
        return None
    team, pos = key
    order = [m.pid for m in book.groups[key]]
    entries = []
    for i, other in enumerate(order, 1):
        p = snap.players[other]
        left = state.out.get(other, 0)
        kind = state.out_kind.get(other) if left else None
        entries.append({
            "player_id": other, "name": p.name, "position": p.pos, "team": p.nfl_team, "order": i, "status": "out" if left else "healthy",
            "injury_status": out_label(kind, left) if left else None, "is_self": other == pid, "change": None,
        })
    return {"ok": True, "player_id": pid, "team": team, "slot": pos, "slot_label": POS_NAMES.get(pos, pos), "self_order": order.index(pid) + 1,
            "entries": entries, "total": len(entries)}


__all__ = ["player_view", "depth_chart_view", "short_name"]
