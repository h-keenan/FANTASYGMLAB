"""Who a player (or a team) was and where he came from, derived from the event log.

Pure and replay-safe: a fold over the same ordered events that build ``GameState``, with no model change and nothing
stored. The state keeps only a capped transaction list and the current picks, so the full story of a player (the round
he was drafted in, each trade, claim and cut, the seasons he spent with each team) is read from the events, which are
never truncated. Events carry a week and the fold tracks the season, so a "date" here is a season and a week; there is
no wall clock in the game.

Both views take the frozen root snapshot (for names and settings) and the ascending event list.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules.sim.game_types import GameSnapshot
from modules.sim.season_label import season_label, season_label_for_year
from modules.sim.types import is_pick_id


class _Names:
    """Player and team names across dynasty seasons (a rookie exists only in a later season's pool)."""

    def __init__(self, root: GameSnapshot) -> None:
        self.root = root
        self._cache: dict[str, dict[str, Any]] = {}

    def player(self, pid: str) -> dict[str, Any]:
        hit = self._cache.get(pid)
        if hit is not None:
            return hit
        out: dict[str, Any] = {"id": pid, "name": pid, "pos": None}
        if is_pick_id(pid):
            out = {"id": pid, "name": _pick_label(pid, int(self.root.settings.start_year or 0)), "pos": None, "pick": True}
        else:
            for season in range(1, max(1, int(self.root.settings.seasons)) + 1):
                p = self.root.season_view(season).players.get(pid)
                if p is not None:
                    out = {"id": pid, "name": p.name, "pos": p.pos}
                    break
        self._cache[pid] = out
        return out

    def team(self, tid: str | None) -> str | None:
        if not tid:
            return None
        try:
            return self.root.team(tid).name
        except KeyError:
            return None


def _pick_label(pick_id: str, start_year: int = 0) -> str:
    parts = pick_id.split(":")
    try:
        return f"{season_label_for_year(int(parts[1]), start_year)} round {parts[2]} pick"
    except IndexError:
        return "Draft pick"


class _Clock:
    """Season and week as the events pass (``season_started`` opens season N+1; the rookie draft sits in the offseason)."""

    def __init__(self, root: GameSnapshot) -> None:
        self.season_no = 1
        self.start_year = int(root.settings.start_year or 0)
        self.offseason_year: int | None = None

    @property
    def year(self) -> int | None:
        return self.start_year + self.season_no - 1 if self.start_year else None

    def feed(self, ev: Mapping[str, Any]) -> None:
        kind, p = ev["type"], ev["payload"]
        if kind == "season_started":
            self.season_no = int(p["season_no"])
            self.offseason_year = None
        elif kind == "season_complete" and p.get("offseason"):
            self.offseason_year = int(p["year"]) if p.get("year") is not None else None


def _when(clock: _Clock, ev: Mapping[str, Any], *, offseason: bool = False) -> dict[str, Any]:
    return {"season": clock.season_no, "year": clock.year, "season_label": season_label(clock.season_no, clock.year), "week": int(ev.get("week") or 0), "offseason": offseason}


def _asset_names(names: _Names, pids: Iterable[str]) -> list[dict[str, Any]]:
    return [names.player(str(x)) for x in pids]


# ------------------------------------------------------------------ one player


def player_history(root: GameSnapshot, events: Iterable[Mapping[str, Any]], pid: str) -> dict[str, Any]:
    """Origin, every move, and a line per season for ``pid``. ``entries`` run oldest first."""

    names = _Names(root)
    clock = _Clock(root)
    entries: list[dict[str, Any]] = []
    holder: str | None = None
    seasons: dict[int, dict[str, Any]] = {}
    origin: dict[str, Any] | None = None
    # Every scored player's total per season (a position rank needs the whole field), read from the same week_scored events.
    field: dict[int, dict[str, float]] = {}

    def team_ref(tid: str | None) -> dict[str, Any]:
        return {"team_id": tid, "team_name": names.team(tid)}

    def add(kind: str, ev: Mapping[str, Any], tid: str | None, **extra: Any) -> dict[str, Any]:
        entry = {"kind": kind, **_when(clock, ev, offseason=bool(extra.pop("offseason", False))), **team_ref(tid), **extra}
        entries.append(entry)
        return entry

    for ev in events:
        kind, p = ev["type"], ev["payload"]
        if kind == "league_rosters":
            for tid in (t.tid for t in root.teams):
                if pid in (*root.start_rosters.get(tid, ()), *root.start_ir.get(tid, ()), *root.start_taxi.get(tid, ())):
                    holder = tid
                    origin = add("started", ev, tid)
        elif kind == "draft_pick" and p["pid"] == pid:
            holder = p["team"]
            origin = add("drafted", ev, holder, round=int(p["round"]), pick=int(p["n"]) + 1, auto=bool(p.get("auto")), draft="league")
        elif kind == "rookie_pick" and p["pid"] == pid:
            holder = p["team"]
            origin = add("drafted", ev, holder, offseason=True, round=int(p["round"]), pick=int(p["n"]) + 1, auto=bool(p.get("auto")), draft="rookie",
                         class_year=clock.offseason_year, class_season_label=season_label_for_year(clock.offseason_year, clock.start_year), via=team_ref(p.get("orig")) if p.get("orig") != holder else None)
        elif kind == "waiver_result" and p.get("ok"):
            if p.get("drop") == pid:
                add("dropped", ev, p["team"], reason="waiver_drop")
                holder = None
            if p.get("add") == pid:
                holder = p["team"]
                add("claimed", ev, holder, dropped=names.player(p["drop"])["name"] if p.get("drop") else None)
        elif kind in ("cut", "drop") and p.get("pid") == pid:
            add("cut" if p.get("reason", "cut") == "cut" else "dropped", ev, p["team"], reason=p.get("reason", "cut"))
            holder = None
        elif kind == "trade":
            for side_from, side_to, sent in ((p["team_a"], p["team_b"], p["give"]), (p["team_b"], p["team_a"], p["get"])):
                if pid in sent:
                    received = p["get"] if side_from == p["team_a"] else p["give"]
                    holder = side_to
                    add("traded", ev, side_to, from_team=team_ref(side_from), to_team=team_ref(side_to),
                        with_assets=_asset_names(names, received), sent_assets=_asset_names(names, [x for x in sent if x != pid]))
        elif kind == "season_complete":
            retired = {str(x) for x in p.get("retired", ())}
            if pid in retired:
                add("retired", ev, holder)
                holder = None
        elif kind == "week_scored":
            totals = field.setdefault(clock.season_no, {})
            for other, v in p["points"].items():
                if v is not None:
                    totals[other] = totals.get(other, 0.0) + float(v)
            pts = p["points"].get(pid)
            if pts is not None and holder is not None:
                line = seasons.setdefault(clock.season_no, {"season": clock.season_no, "year": clock.year, "season_label": season_label(clock.season_no, clock.year), "games": 0, "points": 0.0, "teams": {}, "weeks": []})
                line["weeks"].append({"week": int(ev.get("week") or 0), "points": round(float(pts), 1), "playoff": p.get("kind") != "regular"})
                line["games"] += 1
                line["points"] += float(pts)
                t = line["teams"].setdefault(holder, {"team_id": holder, "team_name": names.team(holder), "games": 0, "points": 0.0})
                t["games"] += 1
                t["points"] += float(pts)
        clock.feed(ev)

    season_rows = []
    for line in sorted(seasons.values(), key=lambda s: s["season"]):
        teams = [{**t, "points": round(t["points"], 1), "ppg": round(t["points"] / t["games"], 1)} for t in line["teams"].values()]
        pos, rank = _position_rank(root, field.get(line["season"], {}), line["season"], pid)
        best = max(line["weeks"], key=lambda w: (w["points"], -w["week"]), default=None)
        season_rows.append({"season": line["season"], "year": line["year"], "season_label": line["season_label"], "games": line["games"], "points": round(line["points"], 1),
                            "ppg": round(line["points"] / line["games"], 1) if line["games"] else None, "teams": teams,
                            # What the engine stores per player per game is his fantasy points (the component stats are not kept for the
                            # whole league), so a season is points / games / average / best week / position rank, never invented components.
                            "weeks": line["weeks"], "best_week": best, "pos": pos, "pos_rank": rank})
    return {"pid": pid, "name": names.player(pid)["name"], "origin": origin, "current_team": team_ref(holder) if holder else None,
            "entries": entries, "seasons": season_rows}


def _position_rank(root: GameSnapshot, totals: Mapping[str, float], season: int, pid: str) -> tuple[str | None, int | None]:
    """His position and where his season total ranked among that position's scored players (1 = best); (None, None) when unknown."""

    players = root.season_view(season).players
    me = players.get(pid)
    if me is None or pid not in totals:
        return None, None
    mine = totals[pid]
    return me.pos, 1 + sum(1 for other, v in totals.items() if v > mine and (q := players.get(other)) is not None and q.pos == me.pos)


# ------------------------------------------------------------------- one team


def team_history(root: GameSnapshot, events: Iterable[Mapping[str, Any]], tid: str) -> dict[str, Any]:
    """A team's draft classes, record by season and every move it made, newest first where a list is long."""

    names = _Names(root)
    clock = _Clock(root)
    draft: list[dict[str, Any]] = []
    rookie: dict[int, list[dict[str, Any]]] = {}
    records: dict[int, dict[str, Any]] = {}
    champions: dict[int, str] = {}
    moves: list[dict[str, Any]] = []

    def rec(season: int) -> dict[str, Any]:
        return records.setdefault(season, {"season": season, "year": None, "season_label": "", "wins": 0, "losses": 0, "ties": 0, "pf": 0.0, "pa": 0.0})

    for ev in events:
        kind, p = ev["type"], ev["payload"]
        w = _when(clock, ev)
        if kind == "draft_pick" and p["team"] == tid:
            draft.append({"round": int(p["round"]), "pick": int(p["n"]) + 1, "auto": bool(p.get("auto")), **names.player(p["pid"])})
        elif kind == "rookie_pick" and p["team"] == tid:
            year = clock.offseason_year or 0
            rookie.setdefault(year, []).append({"round": int(p["round"]), "pick": int(p["n"]) + 1, "auto": bool(p.get("auto")), **names.player(p["pid"]),
                                                "via": names.team(p["orig"]) if p.get("orig") != tid else None})
        elif kind == "week_scored" and p.get("kind") == "regular":
            for g in p["games"]:
                if tid not in (g["home"], g["away"]):
                    continue
                mine, theirs = (g["home_pts"], g["away_pts"]) if g["home"] == tid else (g["away_pts"], g["home_pts"])
                r = rec(clock.season_no)
                r["year"] = clock.year
                r["season_label"] = season_label(clock.season_no, clock.year)
                r["pf"] += float(mine)
                r["pa"] += float(theirs)
                r["wins" if mine > theirs else "losses" if mine < theirs else "ties"] += 1
        elif kind == "season_complete" and p.get("champion"):
            champions[clock.season_no] = str(p["champion"])
        elif kind == "trade" and tid in (p["team_a"], p["team_b"]):
            other = p["team_b"] if p["team_a"] == tid else p["team_a"]
            sent, got = (p["give"], p["get"]) if p["team_a"] == tid else (p["get"], p["give"])
            moves.append({"kind": "trade", **w, "with_team": {"team_id": other, "team_name": names.team(other)},
                          "sent": _asset_names(names, sent), "received": _asset_names(names, got)})
        elif kind == "waiver_result" and p.get("ok") and p["team"] == tid:
            moves.append({"kind": "claim", **w, "added": names.player(p["add"]), "dropped": names.player(p["drop"]) if p.get("drop") else None})
        elif kind in ("cut", "drop") and p.get("team") == tid:
            moves.append({"kind": "cut" if p.get("reason", "cut") == "cut" else "drop", **w, "player": names.player(p["pid"]), "reason": p.get("reason", "cut")})
        clock.feed(ev)

    seasons = []
    for s in sorted(records):
        r = records[s]
        seasons.append({**r, "pf": round(r["pf"], 1), "pa": round(r["pa"], 1), "champion": champions.get(s) == tid})
    classes = [{"year": y or None, "season_label": season_label_for_year(y, int(root.settings.start_year or 0)) if y else "", "picks": picks} for y, picks in sorted(rookie.items())]
    return {"team_id": tid, "team_name": names.team(tid), "draft": draft, "rookie_drafts": classes, "seasons": seasons, "moves": list(reversed(moves))}


__all__ = ["player_history", "team_history"]
