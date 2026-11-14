"""Season and career achievements for the Fantasy Sim, derived at view time.

Pure, read-only and replay-safe: nothing here is stored, emitted or added to ``GameState`` (so every digest and every old
save is untouched). A *ledger* is one season's facts read off a ``GameState`` (its ``history``, ``recaps``, ``stand``,
``playoff`` and ``points``); ``fold_ledgers`` replays the event log through ``apply_event`` and snapshots a ledger just
before each season rolls over, and ``ledger_from_state`` reads the season in progress. ``evaluate`` turns the ordered
ledgers into the achievement list (unlocked and locked-with-progress); ``week_view`` slices out what a given week
unlocked plus the "WIN #10, still perfect" style milestones the recap banner shows.

Web + app twin (presentation only): ``web-next/src/lib/simAchievements.ts`` / ``mobile/src/lib/simAchievements.ts``.
Every item is plain JSON; a client only renders it.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from modules.sim.game_state import GameState, apply_event
from modules.sim.game_types import GameSnapshot
from modules.sim.season_label import season_label

_log = logging.getLogger(__name__)

EPS = 1e-9
# Streak, blowout, closest-win, bench and trade/waiver thresholds: (value, rarity), best tier last.
WIN_STREAK = ((5, "common"), (8, "rare"), (10, "epic"))
LOSS_STREAK = ((5, "common"), (8, "rare"), (10, "rare"))
BLOWOUT = ((30.0, "common"), (60.0, "rare"), (80.0, "epic"))
CLOSE_WIN = ((3.0, "common"), (1.0, "rare"), (0.1, "epic"))  # margin at or under
PERFECT_WEEKS = ((1, "common"), (3, "rare"), (5, "epic"))
TRADE_GAIN = ((40.0, "common"), (80.0, "rare"), (140.0, "epic"))
WAIVER_GAIN = ((60.0, "common"), (100.0, "rare"), (150.0, "epic"))
COMEBACK_WINS = ((4, "rare"), (6, "epic"))
FREE_FALL_WINS = 4
HEARTBREAK_MARGIN = 3.0
CAREER_WINS = ((10, "common"), (25, "common"), (50, "rare"), (100, "epic"))
CAREER_SEASONS = ((3, "common"), (5, "rare"), (10, "epic"))
CAREER_TITLES = ((3, "epic"), (5, "epic"))
PLAYOFF_STREAK = ((3, "common"), (5, "rare"), (8, "epic"))
MIN_RECORD_WEEKS = 4  # a "record week" needs at least this many earlier league weeks to beat
PERFECT_RUN_FROM = 3  # "still perfect" banners start at this many wins


def _r(value: float, places: int = 1) -> float:
    return round(float(value), places)


def _tier(table: Sequence[tuple[float, str]], value: float, *, below: bool = False) -> tuple[int, str] | None:
    """The best (index, rarity) a value reaches: ``>=`` the threshold, or ``<=`` when ``below``."""

    best = None
    for i, (threshold, rarity) in enumerate(table):
        if (value <= threshold + EPS) if below else (value >= threshold - EPS):
            best = (i, rarity)
    return best


# --------------------------------------------------------------------- ledger


def _sum_from(points: Mapping[str, Sequence[Any]], pid: str, week: int) -> float:
    return sum(v for v in (points.get(pid) or [])[max(0, week - 1):] if v is not None)


def _total(points: Mapping[str, Sequence[Any]], pid: str) -> float:
    return sum(v for v in (points.get(pid) or []) if v is not None)


def _reach(points: Mapping[str, Sequence[Any]], gain: Sequence[str], lose: Sequence[str], week: int, table: Sequence[tuple[float, str]]) -> list[int | None]:
    """For each tier, the first week the running net (points of ``gain`` minus ``lose`` from ``week`` on) reached it."""

    n = max([len(points.get(p) or []) for p in [*gain, *lose]] + [week])
    out: list[int | None] = [None] * len(table)
    net = 0.0
    for w in range(week, n + 1):
        net += sum((points.get(p) or [])[w - 1] or 0.0 for p in gain if len(points.get(p) or []) >= w)
        net -= sum((points.get(p) or [])[w - 1] or 0.0 for p in lose if len(points.get(p) or []) >= w)
        for i, (threshold, _) in enumerate(table):
            if out[i] is None and net >= threshold - EPS:
                out[i] = w
    return out


def _moves_from_transactions(state: GameState, user: str) -> list[dict[str, Any]]:
    out = []
    for t in state.transactions:
        if t.get("type") == "trade" and user in (t.get("team_a"), t.get("team_b")) and t.get("source") != "ai_ai":
            out.append({"type": "trade", "week": int(t["week"]), "team_a": t["team_a"], "give": list(t["give"]), "get": list(t["get"])})
        elif t.get("type") == "waiver" and t.get("team") == user:
            out.append({"type": "waiver", "week": int(t["week"]), "add": t["add"], "drop": t.get("drop")})
    return out


def event_move(ev: Mapping[str, Any], user: str) -> dict[str, Any] | None:
    """One user trade / won waiver claim read from an event, in the shape ``ledger_from_state`` takes."""

    kind, p = ev["type"], ev["payload"]
    week = int(ev.get("week") or 1)
    if kind == "trade" and user in (p.get("team_a"), p.get("team_b")) and p.get("source") != "ai_ai":
        return {"type": "trade", "week": week, "team_a": p["team_a"], "give": list(p["give"]), "get": list(p["get"])}
    if kind == "waiver_result" and p.get("team") == user and p.get("ok"):
        return {"type": "waiver", "week": week, "add": p["add"], "drop": p.get("drop")}
    return None


def ledger_from_state(root: GameSnapshot, state: GameState, moves: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """One season's facts, JSON-safe. ``state`` is the season in progress or just finished (before ``season_started``)."""

    from modules.sim.game_engine import standing_rows  # lazy: game_engine imports a lot

    snap = root.season_view(state.season_no)
    S = snap.settings
    user = snap.user_team.tid
    n = len(snap.tids)
    year = (int(S.start_year) + state.season_no - 1) if S.start_year else None
    seeds = list((state.playoff or {}).get("seeds") or [])
    weeks: list[dict[str, Any]] = []
    league_top: list[list[Any]] = []
    out_of_playoffs = user not in seeds if state.playoff else True
    lost_playoff = False
    for wk in state.history:
        week = int(wk["week"])
        best = max(((max(float(g["home_pts"]), float(g["away_pts"])), g["home"] if g["home_pts"] >= g["away_pts"] else g["away"]) for g in wk["games"]), default=None)
        if best:
            league_top.append([week, _r(best[0], 2), best[1]])
        mine = next((g for g in wk["games"] if user in (g["home"], g["away"])), None)
        if mine is None:
            if wk["kind"] == "playoff" and not out_of_playoffs and not lost_playoff:
                weeks.append({"week": week, "kind": "playoff", "round": wk.get("round"), "res": "bye", "pts": None, "opp_pts": None, "opp": None, "opp_name": None, "opp_seed": None})
            continue
        you_home = mine["home"] == user
        pts, opp_pts = (float(mine["home_pts"]), float(mine["away_pts"])) if you_home else (float(mine["away_pts"]), float(mine["home_pts"]))
        opp = mine["away"] if you_home else mine["home"]
        if wk["kind"] == "playoff" and mine.get("winner"):
            res = "w" if mine["winner"] == user else "l"
        else:
            res = "t" if abs(pts - opp_pts) < EPS else "w" if pts > opp_pts else "l"
        if wk["kind"] == "playoff" and res == "l":
            lost_playoff = True
        weeks.append({"week": week, "kind": wk["kind"], "round": wk.get("round"), "res": res, "pts": _r(pts, 2), "opp_pts": _r(opp_pts, 2),
                      "opp": opp, "opp_name": snap.team(opp).name, "opp_seed": (seeds.index(opp) + 1) if opp in seeds else None})
    left: dict[str, float] = {}
    for key, rc in state.recaps.items():
        g = (rc or {}).get("your_game")
        if g and "optimal_pts" in g and "your_pts" in g:
            left[key] = _r(max(0.0, float(g["optimal_pts"]) - float(g["your_pts"])), 2)
    rows = standing_rows(snap, state)
    me = next(r for r in rows if r["team_id"] == user)
    stand = state.stand[user]
    reg_played = sum(1 for wk in state.history if wk["kind"] == "regular")
    result = "champion" if state.champion == user else ((state.playoff or {}).get("results", {}).get(user, "missed") if state.playoff else None)
    ledger: dict[str, Any] = {
        "season_no": int(state.season_no), "year": year, "teams": n, "regular_weeks": int(S.regular_weeks),
        "playoff_teams": int(S.playoff_teams), "playoff_weeks": int(S.playoff_weeks),
        "reg_done": reg_played >= int(S.regular_weeks), "complete": bool(state.champion), "champion": state.champion or None,
        "weeks": weeks, "league_top": league_top, "bench_left": left,
        "w": int(stand["w"]), "l": int(stand["l"]), "t": int(stand["t"]), "pf": _r(stand["pf"]), "pa": _r(stand["pa"]),
        "rank": int(me["rank"]), "seed": me["seed"], "made_playoffs": user in seeds, "result": result,
        "standings": [{"tid": r["team_id"], "w": r["wins"], "l": r["losses"], "t": r["ties"], "pf": r["pf"], "rank": r["rank"]} for r in rows],
        "dynasty": bool(S.dynasty),
    }
    if state.champion:  # season-end facts (the points are final)
        sv = snap
        owners = state.owner_map()
        top = max(((_total(state.points, p), p) for p in snap.pids), key=lambda tp: (tp[0], tp[1]), default=None)
        if top and top[0] > 0:
            pl = sv.players[top[1]]
            ledger["mvp"] = {"pid": top[1], "name": pl.name, "pos": pl.pos, "pts": _r(top[0]), "is_you": owners.get(top[1]) == user}
        if S.dynasty and year:
            rookies = [(p_total, p) for p in snap.pids if sv.players[p].extra.get("draft_year") == float(year) and (p_total := _total(state.points, p)) > 0]
            mine = {x["pid"] for d in state.rookie_log if d.get("year") == year for x in d["picks"] if x["team"] == user}
            if rookies and mine:
                p_total, p = max(rookies, key=lambda tp: (tp[0], tp[1]))
                pl = sv.players[p]
                ledger["roy"] = {"pid": p, "name": pl.name, "pos": pl.pos, "pts": _r(p_total), "is_you": p in mine}
            nxt = next((d for d in state.rookie_log if d.get("year") == year + 1), None)
            if nxt is not None and nxt["picks"]:
                first = min(nxt["picks"], key=lambda x: x["n"])
                ledger["top_pick"] = {"is_you": first["team"] == user, "n": int(first["n"]) + 1}
            elif state.status == "offseason" and state.offseason and state.offseason.get("order"):
                slot = state.offseason["order"][0]
                holder = state.pick_owner.get(slot)
                ledger["top_pick"] = {"is_you": holder == user, "n": 1}
    trades, waivers = [], []
    for m in (moves if moves is not None else _moves_from_transactions(state, user)):
        week = int(m["week"])
        if m["type"] == "trade":
            sent, got = (m["give"], m["get"]) if m["team_a"] == user else (m["get"], m["give"])
            got_ids = [i for i in got if i in snap.players]
            if not got_ids:
                continue
            gp = sum(_sum_from(state.points, i, week) for i in got_ids)
            sp = sum(_sum_from(state.points, i, week) for i in sent if i in snap.players)
            best = max(got_ids, key=lambda i: (_sum_from(state.points, i, week), i))
            trades.append({"week": week, "got_pts": _r(gp), "sent_pts": _r(sp), "net": _r(gp - sp), "pid": best, "name": snap.players[best].name, "pos": snap.players[best].pos,
                           "reach": _reach(state.points, got_ids, [i for i in sent if i in snap.players], week, TRADE_GAIN)})
        elif m["type"] == "waiver" and m["add"] in snap.players:
            pts = _sum_from(state.points, m["add"], week)
            waivers.append({"week": week, "pts": _r(pts), "pid": m["add"], "name": snap.players[m["add"]].name, "pos": snap.players[m["add"]].pos,
                             "reach": _reach(state.points, [m["add"]], [], week, WAIVER_GAIN)})
    ledger["trades"], ledger["waivers"] = trades, waivers
    return ledger


def fold_ledgers(root: GameSnapshot, events: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every season's ledger from the event log: finished seasons snapshotted just before the next one starts, the last
    one as it stands, plus that season's user moves (so a caller can keep folding new events cheaply). A cheap fold (the
    same one resume uses); never replays dice."""

    state = GameState(root)
    user = root.user_team.tid
    out: list[dict[str, Any]] = []
    moves: list[dict[str, Any]] = []
    for ev in events:
        if ev["type"] == "season_started":
            out.append(ledger_from_state(root, state, moves))
            moves = []
        m = event_move(ev, user)
        if m:
            moves.append(m)
        apply_event(state, root, ev)
    out.append(ledger_from_state(root, state, moves))
    return out, moves


# ----------------------------------------------------------------- evaluation


def _item(key: str, scope: str, rarity: str, tone: str, icon: str, name: str, detail: str, ledger: Mapping[str, Any] | None, week: int | None, *,
          unlocked: bool = True, progress: Mapping[str, Any] | None = None, tier: int | None = None, player: Mapping[str, Any] | None = None,
          suffix: str = "", at_season: int | None = None) -> dict[str, Any]:
    season_no = int(ledger["season_no"]) if ledger else at_season
    year = ledger.get("year") if ledger else None
    return {
        "id": f"{key}{suffix}:{season_no}" if season_no and scope == "season" else f"{key}{suffix}", "key": key, "scope": scope, "rarity": rarity, "tone": tone,
        "icon": icon, "name": name, "detail": detail, "unlocked": unlocked,
        "season_no": season_no if season_no else None, "year": year, "season_label": season_label(season_no, year) if season_no else "",
        "week": week, "at": (int(season_no) * 100 + int(week or 0)) if (season_no and unlocked) else None,
        "progress": dict(progress) if progress else None, "tier": tier, "player": dict(player) if player else None,
    }


def _rec(w: int, l: int, t: int) -> str:
    return f"{w}-{l}" + (f"-{t}" if t else "")


def _streaks(weeks: Sequence[Mapping[str, Any]], res: str) -> tuple[int, int]:
    """(longest run of ``res`` in the regular season, the week it was reached)."""

    best = cur = 0
    at = 0
    for w in weeks:
        if w["kind"] != "regular":
            continue
        cur = cur + 1 if w["res"] == res else 0
        if cur > best:
            best, at = cur, w["week"]
    return best, at


def _last_week(ledger: Mapping[str, Any]) -> int:
    return int(ledger["weeks"][-1]["week"]) if ledger["weeks"] else int(ledger["regular_weeks"])


def _season_items(led: Mapping[str, Any], prev: Mapping[str, Any] | None, history: Sequence[Mapping[str, Any]], earlier_tops: Sequence[Sequence[Any]],
                  earlier_pf: float, streak_titles: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    weeks = led["weeks"]
    reg = [w for w in weeks if w["kind"] == "regular"]
    po = [w for w in weeks if w["kind"] == "playoff"]
    w_, l_, t_ = led["w"], led["l"], led["t"]
    games = w_ + l_ + t_
    reg_end = int(led["regular_weeks"])
    done = led["reg_done"]
    final = led["complete"]
    last = _last_week(led)
    # Records of the season
    if done and games and l_ == 0 and t_ == 0:
        po_clean = not any(x["res"] == "l" for x in po)
        if final and led["champion"] and led["result"] == "champion" and po_clean:
            out.append(_item("perfect_season", "season", "epic", "good", "crown", "Perfect Season",
                             f"{_rec(w_, l_, t_)} and the title, without a single loss.", led, last))
        else:
            out.append(_item("undefeated_regular", "season", "epic", "good", "flame", "Undefeated Regular Season",
                             f"{_rec(w_, l_, t_)}: not one loss in {games} games.", led, reg_end))
    elif done and games and l_ == 0 and t_ > 0:
        out.append(_item("unbeaten_regular", "season", "rare", "good", "flame", "Unbeaten Regular Season",
                         f"{_rec(w_, l_, t_)}: never lost, but {t_} tie{'s' if t_ != 1 else ''} kept it from perfect.", led, reg_end))
    if done and games and w_ == 0:
        pick = led.get("top_pick")
        tail = " The #1 pick is yours." if pick and pick["is_you"] else ""
        out.append(_item("winless", "season", "rare", "bad", "snow", "Winless Season", f"{_rec(w_, l_, t_)}: not a single win.{tail}", led, reg_end))
        if pick and pick["is_you"]:
            out.append(_item("tank_commander", "season", "rare", "neutral", "target", "Tank Commander", f"{_rec(w_, l_, t_)} and the #1 overall rookie pick.", led, last))
    # Championship ladder
    if final and led["result"] == "champion":
        out.append(_item("champion", "season", "rare", "good", "trophy", "League Champion", f"Won the title at {_rec(w_, l_, t_)}.", led, last))
        if streak_titles >= 3:
            out.append(_item("three_peat", "season", "epic", "good", "crown", "Three-peat", "Three league titles in a row.", led, last))
        elif streak_titles == 2:
            out.append(_item("back_to_back", "season", "epic", "good", "trophy", "Back-to-Back", "Champions in consecutive seasons.", led, last))
        if led.get("seed") and led["seed"] == led["playoff_teams"] and led["playoff_teams"] > 2:
            out.append(_item("underdog", "season", "epic", "good", "bolt", "Underdog", f"Squeaked in as the #{led['seed']} seed and won it all.", led, last))
    elif final and led["result"] == "runner_up":
        fin = next((x for x in reversed(po) if x["res"] == "l"), None)
        if fin and fin["pts"] is not None and fin["opp_pts"] is not None and fin["opp_pts"] - fin["pts"] < HEARTBREAK_MARGIN:
            out.append(_item("heartbreaker", "season", "rare", "bad", "heart", "Heartbreaker",
                             f"Lost the title game by {_r(fin['opp_pts'] - fin['pts'], 2)}.", led, fin["week"]))
    # Season-over-season swings
    if prev and done and prev.get("reg_done") and prev["teams"] == led["teams"]:
        if prev["rank"] == prev["teams"] and led["rank"] == 1:
            out.append(_item("worst_to_first", "season", "epic", "good", "rocket", "Worst to First", f"From last place to #1 ({_rec(w_, l_, t_)}).", led, reg_end))
        if prev["rank"] == 1 and led["rank"] == led["teams"]:
            out.append(_item("first_to_worst", "season", "rare", "bad", "fall", "First to Worst", f"From #1 to last place ({_rec(w_, l_, t_)}).", led, reg_end))
        gain = (w_ + 0.5 * t_) - (prev["w"] + 0.5 * prev["t"])
        hit = _tier(COMEBACK_WINS, gain)
        if hit:
            out.append(_item("comeback_year", "season", hit[1], "good", "rocket", "Comeback Year", f"{_r(gain, 1):g} more wins than last season ({_rec(w_, l_, t_)}).", led, reg_end, tier=hit[0]))
        if -gain >= FREE_FALL_WINS:
            out.append(_item("free_fall", "season", "common", "bad", "fall", "Free-fall", f"{_r(-gain, 1):g} fewer wins than last season ({_rec(w_, l_, t_)}).", led, reg_end))
    # Games
    wins = [x for x in weeks if x["res"] == "w" and x["pts"] is not None]
    if wins:
        big = max(wins, key=lambda x: (x["pts"] - x["opp_pts"], -x["week"]))
        margin = big["pts"] - big["opp_pts"]
        hit = _tier(BLOWOUT, margin)
        if hit:
            out.append(_item("blowout", "season", hit[1], "good", "bolt", "Blowout", f"Won by {_r(margin, 1)} over {big['opp_name']} in week {big['week']}.", led, big["week"], tier=hit[0]))
        close = min(wins, key=lambda x: (x["pts"] - x["opp_pts"], x["week"]))
        cm = close["pts"] - close["opp_pts"]
        hit = _tier(CLOSE_WIN, cm, below=True)
        if hit:
            out.append(_item("closest_win", "season", hit[1], "good", "target", "Nail-biter", f"Won by just {_r(cm, 2)} over {close['opp_name']} in week {close['week']}.", led, close["week"], tier=hit[0]))
    for res, table, key, name, tone, icon, verb in (("w", WIN_STREAK, "win_streak", "Win Streak", "good", "flame", "wins in a row"),
                                                    ("l", LOSS_STREAK, "loss_streak", "Losing Streak", "bad", "snow", "losses in a row")):
        run, at = _streaks(weeks, res)
        hit = _tier(table, run)
        if hit:
            out.append(_item(key, "season", hit[1], tone, icon, name, f"{run} {verb} (through week {at}).", led, at, tier=hit[0]))
    # Records
    if led["league_top"] and led["weeks"]:
        mine = [x for x in weeks if x["pts"] is not None]
        if mine:
            top = max(mine, key=lambda x: (x["pts"], -x["week"]))
            beat = [t[1] for t in earlier_tops] + [t[1] for t in led["league_top"] if t[0] != top["week"]]
            if len(beat) >= MIN_RECORD_WEEKS and top["pts"] > max(beat) + EPS:
                out.append(_item("record_week", "season", "epic", "good", "bolt", "League Record Week", f"{_r(top['pts'], 1)} points in week {top['week']}, the most any team has scored.", led, top["week"]))
    if final and led["pf"] > earlier_pf + EPS and earlier_pf > 0 and led["standings"] and led["pf"] >= max(s["pf"] for s in led["standings"]) - EPS:
        out.append(_item("record_season", "season", "epic", "good", "crown", "Highest-scoring Team Ever", f"{led['pf']} points, the most by any team in league history.", led, last))
    # Lineups
    perfect = sorted(int(k) for k, v in led["bench_left"].items() if v <= 0.05)
    mine_w = {x["week"]: x for x in weeks if x["pts"] is not None}
    perfect = [k for k in perfect if k in mine_w and mine_w[k]["pts"] > 0]
    hit = _tier(PERFECT_WEEKS, len(perfect))
    if hit:
        out.append(_item("perfect_lineup", "season", hit[1], "good", "check", "Perfect Lineup", f"Nothing left on the bench in {len(perfect)} week{'s' if len(perfect) != 1 else ''} (first: week {perfect[0]}).", led, perfect[0], tier=hit[0]))
    # Awards of the season
    mvp = led.get("mvp")
    if mvp and mvp["is_you"]:
        out.append(_item("mvp_season", "season", "rare", "good", "star", "League MVP", f"{mvp['name']} led the whole league with {mvp['pts']} points.", led, last, player={"id": mvp["pid"], "name": mvp["name"], "pos": mvp["pos"]}))
    roy = led.get("roy")
    if roy and roy["is_you"]:
        out.append(_item("roy", "season", "rare", "good", "star", "Rookie of the Year", f"You drafted {roy['name']}, the top-scoring rookie ({roy['pts']} points).", led, last, player={"id": roy["pid"], "name": roy["name"], "pos": roy["pos"]}))
    tr = max(led.get("trades") or [], key=lambda x: (x["net"], -x["week"]), default=None)
    hit = _tier(TRADE_GAIN, tr["net"]) if tr else None
    if hit:
        out.append(_item("trade_shark", "season", hit[1], "good", "swap", "Trade Shark", f"A week {tr['week']} trade brought in {tr['net']} more points than it sent out.", led, tr["reach"][hit[0]] or tr["week"], tier=hit[0], player={"id": tr["pid"], "name": tr["name"], "pos": tr["pos"]}))
    wv = max(led.get("waivers") or [], key=lambda x: (x["pts"], -x["week"]), default=None)
    hit = _tier(WAIVER_GAIN, wv["pts"]) if wv else None
    if hit:
        out.append(_item("waiver_wizard", "season", hit[1], "good", "wand", "Waiver Wizard", f"{wv['name']}, claimed in week {wv['week']}, scored {wv['pts']} points for you.", led, wv["reach"][hit[0]] or wv["week"], tier=hit[0], player={"id": wv["pid"], "name": wv["name"], "pos": wv["pos"]}))
    return out


def _in_progress(led: Mapping[str, Any], prev: Mapping[str, Any] | None, defending: int) -> list[dict[str, Any]]:
    """Locked items with progress for the season being played."""

    out: list[dict[str, Any]] = []
    if led["complete"]:
        return out
    reg_end = int(led["regular_weeks"])
    played = sum(1 for x in led["weeks"] if x["kind"] == "regular")
    left = reg_end - played
    w_, l_, t_ = led["w"], led["l"], led["t"]
    if l_ == 0 and t_ == 0 and played > 0 and not led["reg_done"]:
        out.append(_item("perfect_season", "season", "epic", "good", "crown", "Perfect Season", "Go undefeated and win the title.", led, None, unlocked=False,
                         progress={"current": played, "target": reg_end, "text": f"{_rec(w_, l_, t_)}, {left} game{'s' if left != 1 else ''} left"}))
    elif l_ == 0 and t_ == 0 and led["reg_done"] and led["result"] not in ("missed",) and not any(x["res"] == "l" for x in led["weeks"]):
        out.append(_item("perfect_season", "season", "epic", "good", "crown", "Perfect Season", "Win the title without a loss.", led, None, unlocked=False,
                         progress={"current": reg_end, "target": reg_end + int(led["playoff_weeks"]), "text": f"{_rec(w_, l_, t_)}, win the playoffs to finish perfect"}))
    if defending >= 1 and led["made_playoffs"] is False and not led["reg_done"]:
        nxt = "three_peat" if defending >= 2 else "back_to_back"
        out.append(_item(nxt, "season", "epic", "good", "trophy", "Three-peat" if defending >= 2 else "Back-to-Back", "Defend your title.", led, None, unlocked=False,
                         progress={"current": defending, "target": defending + 1, "text": f"Defending {defending} title{'s' if defending != 1 else ''}"}))
    if prev and prev.get("reg_done") and prev["rank"] == prev["teams"] and not led["reg_done"]:
        out.append(_item("worst_to_first", "season", "epic", "good", "rocket", "Worst to First", "Finish #1 after finishing last.", led, None, unlocked=False,
                         progress={"current": led["rank"], "target": 1, "text": f"Currently #{led['rank']} (was last)"}))
    return out


def _ladder(key: str, scope: str, name: str, icon: str, table: Sequence[tuple[int, str]], total: int, reached: Mapping[int, tuple[Mapping[str, Any] | None, int]],
            unit: str, detail: str, tone: str = "good") -> list[dict[str, Any]]:
    """A career ladder: every tier reached is an unlocked item (dated by ``reached[threshold]``), the next one is locked with progress."""

    out = []
    for i, (threshold, rarity) in enumerate(table):
        if total >= threshold and threshold in reached:
            led, week = reached[threshold]
            out.append(_item(key, "career", rarity, tone, icon, name.format(n=threshold), detail.format(n=threshold), led, week, tier=i, suffix=f"_{threshold}", at_season=led["season_no"] if led else None))
        elif total < threshold:
            out.append(_item(key, "career", rarity, tone, icon, name.format(n=threshold), detail.format(n=threshold), None, None, unlocked=False, tier=i, suffix=f"_{threshold}",
                             progress={"current": total, "target": threshold, "text": f"{total} of {threshold} {unit}"}))
            break
    return out


def evaluate(ledgers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Every achievement, unlocked then locked, newest unlock first within each group."""

    items: list[dict[str, Any]] = []
    prev: Mapping[str, Any] | None = None
    earlier_tops: list[list[Any]] = []
    earlier_pf = 0.0
    titles = streak = 0
    wins_at: dict[int, tuple[Mapping[str, Any], int]] = {}
    seasons_at: dict[int, tuple[Mapping[str, Any], int]] = {}
    title_at: dict[int, tuple[Mapping[str, Any], int]] = {}
    po_at: dict[int, tuple[Mapping[str, Any], int]] = {}
    total_wins = played = po_run = best_po_run = 0
    defending = 0
    for led in ledgers:
        if led["complete"]:
            streak = streak + 1 if led["result"] == "champion" else 0
        items += _season_items(led, prev, ledgers, earlier_tops, earlier_pf, streak)
        for x in led["weeks"]:  # career wins, dated to the week that reached each milestone
            if x["res"] == "w":
                total_wins += 1
                for threshold, _ in CAREER_WINS:
                    if total_wins == threshold:
                        wins_at[threshold] = (led, x["week"])
        if led["complete"]:
            played += 1
            for threshold, _ in CAREER_SEASONS:
                if played == threshold:
                    seasons_at[threshold] = (led, _last_week(led))
            if led["result"] == "champion":
                titles += 1
                for threshold, _ in CAREER_TITLES:
                    if titles == threshold:
                        title_at[threshold] = (led, _last_week(led))
            po_run = po_run + 1 if led["made_playoffs"] else 0
            for threshold, _ in PLAYOFF_STREAK:
                if po_run == threshold:
                    po_at[threshold] = (led, _last_week(led))
            best_po_run = max(best_po_run, po_run)
        earlier_tops += led["league_top"]
        earlier_pf = max([earlier_pf] + [s["pf"] for s in led["standings"]]) if led["complete"] else earlier_pf
        prev = led if led["reg_done"] else prev
    cur = ledgers[-1] if ledgers else None
    if cur and not cur["complete"]:
        before = ledgers[-2] if len(ledgers) > 1 else None
        defending = streak
        items += _in_progress(cur, before if before and before["reg_done"] else None, defending)
    items += _ladder("career_wins", "career", "{n} Career Wins", "flame", CAREER_WINS, total_wins, wins_at, "wins", "Reached {n} wins as a GM.")
    items += _ladder("career_seasons", "career", "{n} Seasons Played", "calendar", CAREER_SEASONS, played, seasons_at, "seasons", "Managed {n} full seasons.")
    items += _ladder("dynasty", "career", "Dynasty: {n} Titles", "crown", CAREER_TITLES, titles, title_at, "titles", "Won {n} league titles.")
    items += _ladder("playoff_streak", "career", "{n} Straight Playoffs", "shield", PLAYOFF_STREAK, max(po_run, best_po_run), po_at, "seasons in a row", "Made the playoffs {n} seasons running.")
    unlocked = sorted((i for i in items if i["unlocked"]), key=lambda i: (-(i["at"] or 0), i["id"]))
    locked = sorted((i for i in items if not i["unlocked"]), key=lambda i: (i["scope"], i["id"]))
    return unlocked + locked


# ------------------------------------------------------------------- recap


def _milestones(led: Mapping[str, Any], week: int) -> list[dict[str, Any]]:
    """Banners for the week just played: the streak of the record ("WIN #10, still perfect"), a winless-watch, the season's verdicts."""

    out: list[dict[str, Any]] = []
    mine = [x for x in led["weeks"] if x["kind"] == "regular" and x["week"] <= week]
    cur = next((x for x in led["weeks"] if x["week"] == week), None)
    if cur and cur["kind"] == "regular" and cur["res"] in ("w", "l", "t"):
        w_ = sum(1 for x in mine if x["res"] == "w")
        l_ = sum(1 for x in mine if x["res"] == "l")
        t_ = sum(1 for x in mine if x["res"] == "t")
        rec = _rec(w_, l_, t_)
        if cur["res"] == "w" and l_ == 0 and t_ == 0 and w_ >= PERFECT_RUN_FROM:
            out.append({"kind": "perfect_run", "tone": "good", "icon": "flame", "confetti": False,
                        "headline": f"WIN #{w_}, still perfect", "sub": f"{rec} and nobody has beaten you."})
        elif cur["res"] == "w" and w_ % 5 == 0:
            out.append({"kind": "win_number", "tone": "good", "icon": "flame", "confetti": False, "headline": f"WIN #{w_}", "sub": f"Now {rec}."})
        if cur["res"] != "w" and w_ == 0 and l_ >= 4 and not led["reg_done"]:
            out.append({"kind": "winless_watch", "tone": "bad", "icon": "snow", "confetti": False, "headline": f"Still hunting win #1 ({rec})",
                        "sub": "Every loss is a better draft slot."})
    return out


def week_view(ledgers: Sequence[Mapping[str, Any]], items: Sequence[Mapping[str, Any]], week_from: int, week_to: int | None = None) -> dict[str, Any]:
    """What the weeks ``week_from..week_to`` of the season in progress unlocked, and the milestone banners of ``week_from``."""

    week_to = week_to or week_from
    cur = ledgers[-1] if ledgers else None
    if not cur:
        return {"new": [], "milestones": []}
    no = int(cur["season_no"])
    new = [i for i in items if i["unlocked"] and i["season_no"] == no and i["week"] is not None and week_from <= i["week"] <= week_to]
    new.sort(key=lambda i: (i["week"], {"epic": 0, "rare": 1, "common": 2}[i["rarity"]], i["id"]))
    banners = _milestones(cur, week_from)
    for i in new:
        if i["key"] in ("perfect_season", "champion", "three_peat", "back_to_back"):
            banners = [b for b in banners if b["kind"] != "perfect_run"]
    return {"new": new, "milestones": banners}


def build(root: GameSnapshot, ledgers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The payload every view carries: ``{"items", "counts"}``. Never raises (a failure yields an empty payload)."""

    try:
        items = evaluate(ledgers)
        unlocked = [i for i in items if i["unlocked"]]
        return {"items": items, "counts": {"unlocked": len(unlocked), "epic": sum(1 for i in unlocked if i["rarity"] == "epic"),
                                           "rare": sum(1 for i in unlocked if i["rarity"] == "rare"), "common": sum(1 for i in unlocked if i["rarity"] == "common"),
                                           "locked": len(items) - len(unlocked)}}
    except Exception:  # noqa: BLE001 - a view never breaks for a badge
        _log.exception("sim achievements failed")
        return {"items": [], "counts": {"unlocked": 0, "epic": 0, "rare": 0, "common": 0, "locked": 0}}


__all__ = ["ledger_from_state", "fold_ledgers", "event_move", "evaluate", "week_view", "build"]
