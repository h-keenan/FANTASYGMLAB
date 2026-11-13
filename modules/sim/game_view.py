"""JSON views of a game for the API: player rows, lineup, draft board, league.

Read-only over (snapshot, state). Nothing here changes state.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules.sim.game_actions import lineup_warnings
from modules.sim.game_ai import trade_window
from modules.sim.game_draft import DraftContext, best_for_user
from modules.sim.game_engine import rank_teams, standing_rows
from modules.sim.game_eval import Evaluator
from modules.sim.game_state import GameState
from modules.sim.game_types import PREVIEW_PAYWALL_WEEK, GameSnapshot, headshot_id
from modules.sim.personas import PERSONAS
from modules.sim.types import is_pick_id

PAGE_MAX = 60
SORTS = ("projection", "value", "adp", "age", "name", "last_week", "season")


def preview_block(is_pro: bool, state: GameState | None) -> dict[str, Any] | None:
    """Free-preview status. None for Pro."""

    if is_pro:
        return None
    if state is None or state.status == "drafting":
        left = PREVIEW_PAYWALL_WEEK - 1
    elif state.status == "complete":
        left = 0
    else:
        left = max(0, PREVIEW_PAYWALL_WEEK - state.week)
    return {"weeks_left": left, "paywall_week": PREVIEW_PAYWALL_WEEK, "paywalled": left == 0 and bool(state) and state.status in ("in_season", "playoffs")}


def paywalled(is_pro: bool, state: GameState) -> bool:
    """Would a mutating call be refused for this caller right now?"""

    if is_pro:
        return False
    return state.status in ("in_season", "playoffs") and state.week >= PREVIEW_PAYWALL_WEEK


# ------------------------------------------------------------------ players


def _owner(snap: GameSnapshot, state: GameState, owners: Mapping[str, str], pid: str) -> dict[str, Any]:
    tid = owners.get(pid)
    if tid is None:
        return {"type": "free_agent", "team_id": None, "name": None}
    team = snap.team(tid)
    return {"type": "you" if team.is_user else "ai", "team_id": tid, "name": team.name}


def player_row(
    snap: GameSnapshot, state: GameState, ev: Evaluator, pid: str, owners: Mapping[str, str], *, week: int | None = None
) -> dict[str, Any]:
    if is_pick_id(pid):
        return pick_asset(snap, state, ev, pid)
    p = snap.players[pid]
    w = week if week is not None else max(state.week, 1)
    games = state.games_played(pid) if state.status != "offseason" else []
    floor, ceiling = ev.band(pid)
    return {
        "id": pid, "headshot_id": headshot_id(pid), "name": p.name, "pos": p.pos, "team": p.nfl_team,
        "age": p.age, "adp": p.adp, "value": p.value, "projection": round(ev.proj(pid, w), 1), "ros_mean": round(ev.ros_mean(pid), 1),
        "floor": round(floor, 1), "ceiling": round(ceiling, 1), "status": ev.status(pid, w),
        "out_weeks": state.out.get(pid, 0), "bye_week": snap.bye_of(pid) or None,
        "owner": _owner(snap, state, owners, pid), "kind": "player",
        "squad": state.where(owners[pid], pid) if pid in owners else None,
        "taxi_eligible": taxi_ok(snap, pid), "rookie": bool(p.extra.get("is_rookie")), "generated": bool(p.extra.get("draft_year")),
        "last_week": state.last_points(pid), "season_points": round(sum(games), 1), "games": len(games),
        "ppg": round(sum(games) / len(games), 1) if games else None,
    }


def taxi_ok(snap: GameSnapshot, pid: str) -> bool:
    from modules.sim.game_actions import taxi_eligible

    return bool(snap.settings.reserves and snap.settings.taxi_slots and taxi_eligible(snap, pid))


def pick_asset(snap: GameSnapshot, state: GameState, ev: Evaluator, pid: str) -> dict[str, Any]:
    """A draft pick shaped like a player row (the trade builder, the inbox and
    counters treat both as assets) with ``kind: "pick"``."""

    season, rnd, orig = ev.pick_parts(pid)
    holder = state.pick_owner.get(pid)
    frac = ev.pick_slot_frac(orig) if season <= ev.draft_year_now() else None
    hint = None if frac is None else ("early" if frac < 0.34 else "mid" if frac < 0.67 else "late")
    team = snap.team(holder) if holder else None
    return {
        "id": pid, "kind": "pick", "headshot_id": None, "name": f"{season} Round {rnd}", "pos": "PICK", "team": "",
        "season": season, "round": rnd, "orig_team_id": orig, "orig_team_name": snap.team(orig).name,
        "slot_hint": hint, "label": ev.pick_name(pid), "age": None, "adp": None, "value": round(ev.pick_value(pid), 1),
        "projection": 0.0, "ros_mean": 0.0, "floor": 0.0, "ceiling": 0.0, "status": "healthy", "out_weeks": 0,
        "bye_week": None, "owner": ({"type": "you" if team.is_user else "ai", "team_id": holder, "name": team.name}
                                      if team else {"type": "free_agent", "team_id": None, "name": None}),
        "squad": "picks", "last_week": None, "season_points": 0.0, "games": 0, "ppg": None,
    }


def players_page(
    snap: GameSnapshot, state: GameState, *, q: str = "", pos: str = "", status: str = "", team: str = "",
    sort: str = "projection", page: int = 1, page_size: int = 25,
) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    user = snap.user_team.tid
    w = max(state.week, 1)
    needle = q.strip().lower()
    pids = []
    for pid in snap.pids:
        p = snap.players[pid]
        if pos and p.pos != pos:
            continue
        if needle and needle not in p.name.lower() and needle != p.nfl_team.lower():
            continue
        owner = owners.get(pid)
        if status == "available" and owner is not None:
            continue
        if status == "rostered" and owner is None:
            continue
        if status == "mine" and owner != user:
            continue
        if status == "injured" and ev.status(pid, w) != "out":
            continue
        if status == "bye" and ev.status(pid, w) != "bye":
            continue
        if team and owner != team:
            continue
        pids.append(pid)

    def key(pid: str):
        p = snap.players[pid]
        if sort == "value":
            return (-p.value, pid)
        if sort == "adp":
            return (p.adp, pid)
        if sort == "age":
            return (p.age, pid)
        if sort == "name":
            return (p.name.lower(), pid)
        if sort == "last_week":
            return (-(state.last_points(pid) or 0.0), pid)
        if sort == "season":
            return (-sum(state.games_played(pid)), pid)
        return (-ev.proj(pid, w), -ev.ros_mean(pid), pid)

    pids.sort(key=key)
    page_size = max(1, min(PAGE_MAX, page_size))
    page = max(1, page)
    chunk = pids[(page - 1) * page_size: page * page_size]
    return {
        "items": [player_row(snap, state, ev, pid, owners) for pid in chunk],
        "total": len(pids), "page": page, "page_size": page_size,
    }


def player_detail(snap: GameSnapshot, state: GameState, pid: str) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    first = max(state.week, 1)
    last = snap.settings.regular_weeks if state.status != "complete" else 0
    floor, ceiling = ev.band(pid)
    weeks = []
    for w in range(first, last + 1):
        healthy = ev.status(pid, w) == "healthy"
        weeks.append({
            "week": w, "projection": round(ev.proj(pid, w), 1),
            "floor": round(floor, 1) if healthy else 0.0, "ceiling": round(ceiling, 1) if healthy else 0.0,
            "bye": ev.on_bye(pid, w), "out": ev.out_in(pid, w),
        })
    history = []
    for i, pts in enumerate(state.points.get(pid, [])):
        history.append({"week": i + 1, "points": pts, "stats": _stats_for(state, pid, i + 1)})
    news = [{"week": n["week"], "text": f"Injured in Week {n['week']}; expected to miss {n['weeks']} week(s)."}
            for n in state.news if n["pid"] == pid]
    if state.out.get(pid) and not news:
        news.append({"week": 0, "text": f"Listed out for {state.out[pid]} week(s) to start the season."})
    return {"player": player_row(snap, state, ev, pid, owners), "weeks": weeks, "history": history, "news": news}


def _stats_for(state: GameState, pid: str, week: int) -> dict[str, float] | None:
    g = state.recaps.get(str(week), {}).get("your_game") or {}
    for r in [*g.get("starters", []), *g.get("bench", []), *g.get("opp_starters", [])]:
        if r.get("player") and r["player"]["id"] == pid:
            return r.get("stats")
    return None


# -------------------------------------------------------------------- lineup


def lineup_view(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    user = snap.user_team.tid
    week = max(state.week, 1)
    lineup = state.lineups[user]
    started = {pid for _, pid in lineup if pid}
    slots = [
        {"slot": slot, "player": player_row(snap, state, ev, pid, owners, week=week) if pid else None}
        for slot, pid in lineup
    ]
    bench = [
        player_row(snap, state, ev, pid, owners, week=week)
        for pid in sorted(state.rosters[user], key=lambda p: (-ev.ros_mean(p), p)) if pid not in started
    ]
    return {
        "week": week, "slots": slots, "bench": bench,
        "projected_total": round(ev.lineup_projection(lineup, week), 1),
        "warnings": lineup_warnings(ev, lineup, week) if state.status in ("in_season", "playoffs") else [],
        "roster_size": len(state.rosters[user]), "roster_limit": snap.settings.roster_limit,
        "opponent": _opponent(snap, state, ev, week), "locked": state.status in ("complete", "offseason"),
        **reserve_block(snap, state, ev, user, owners, week),
    }


def reserve_block(snap: GameSnapshot, state: GameState, ev: Evaluator, tid: str, owners: Mapping[str, str], week: int) -> dict[str, Any]:
    """The IR and taxi squads of a team (empty lists and zero slots for a save from before them)."""

    S = snap.settings
    rows = lambda pids: [player_row(snap, state, ev, p, owners, week=week) for p in sorted(pids, key=lambda p: (-ev.ros_mean(p), p))]
    return {
        "ir": rows(state.ir.get(tid, ())), "taxi": rows(state.taxi.get(tid, ())),
        "reserves": {"enabled": S.reserves, "ir_slots": S.ir_slots, "taxi_slots": S.taxi_slots if S.reserves else 0,
                     "taxi_years": S.taxi_years, "ir_used": len(state.ir.get(tid, ())), "taxi_used": len(state.taxi.get(tid, ()))},
    }


def _opponent(snap: GameSnapshot, state: GameState, ev: Evaluator, week: int) -> dict[str, Any] | None:
    user = snap.user_team.tid
    opp = None
    if state.status == "in_season" and 1 <= week <= snap.settings.regular_weeks:
        for home, away in snap.schedule[week - 1]:
            if user in (home, away):
                opp = away if home == user else home
    elif state.status == "playoffs" and state.playoff:
        alive = state.playoff["alive"]
        for i in range(0, len(alive), 2):
            if user in (alive[i], alive[i + 1]):
                opp = alive[i + 1] if alive[i] == user else alive[i]
    if not opp:
        return None
    team = snap.team(opp)
    return {
        "team_id": opp, "name": team.name, "persona_id": team.persona_id,
        "projection": round(ev.lineup_projection(state.lineups[opp], week), 1),
    }


# ---------------------------------------------------------------------- game


def dynasty_block(snap: GameSnapshot, state: GameState) -> dict[str, Any] | None:
    S = snap.settings
    if not S.dynasty:
        return None
    user = snap.user_team.tid
    return {
        "season_no": state.season_no, "seasons": S.seasons, "year": S.start_year + state.season_no - 1,
        "stage": (state.offseason or {}).get("stage") if state.status == "offseason" else None,
        "picks_held": len(state.picks_of(user)), "titles": sum(1 for a in state.seasons if a["champion"] and a["champion"]["is_you"]),
        "last_season": state.season_no >= S.seasons,
    }


def game_view(
    row: Mapping[str, Any], snap: GameSnapshot, state: GameState, *, is_pro: bool
) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    user = snap.user_team.tid
    standings = standing_rows(snap, state) if state.status != "drafting" else []
    me = next((r for r in standings if r["team_id"] == user), None)
    week = max(state.week, 1)
    opp = _opponent(snap, state, ev, week) if state.status in ("in_season", "playoffs") else None
    phase = {"drafting": "draft", "in_season": "regular_season", "playoffs": "playoffs", "offseason": "offseason",
             "complete": "complete"}[state.status]
    user_roster = state.rosters[user]
    team = snap.user_team
    this_week = None
    if opp is not None or state.status in ("in_season", "playoffs"):
        this_week = {
            "week": state.week, "opponent": {k: opp[k] for k in ("team_id", "name", "persona_id")} if opp else None,
            "bye": opp is None, "your_projection": round(ev.lineup_projection(state.lineups[user], week), 1),
            "opponent_projection": opp["projection"] if opp else None,
        }
    return {
        "id": row["id"], "status": state.status, "week": state.week, "phase": phase,
        "round": (state.week - snap.settings.regular_weeks) if state.status == "playoffs" else None,
        "seed": row.get("seed"), "engine_version": row.get("engine_version"),
        "scoring_model": row.get("scoring_model"), "settings": snap.settings.to_dict(),
        "you": {
            "team_id": user, "name": team.name,
            "wins": me["wins"] if me else 0, "losses": me["losses"] if me else 0, "ties": me["ties"] if me else 0,
            "pf": me["pf"] if me else 0.0, "pa": me["pa"] if me else 0.0, "rank": me["rank"] if me else None,
            "seed": me["seed"] if me else None,
        },
        "this_week": this_week,
        "pending": {
            "claims": len(state.claims), "inbox": len(state.offers),
            "lineup_warnings": len(lineup_warnings(ev, state.lineups[user], week)) if state.status in ("in_season", "playoffs") else 0,
            "roster_size": len(user_roster), "roster_limit": snap.settings.roster_limit,
            "cuts_needed": max(0, len(user_roster) - snap.settings.roster_limit),
        },
        "can_trade": trade_window(snap, state) is None,
        "trade_deadline_week": snap.settings.trade_deadline_week,
        "dynasty": dynasty_block(snap, state),
        "grade_letter": row.get("grade_letter"), "notes": list(snap.notes),
        "created_at": row.get("created_at"), "updated_at": row.get("updated_at"),
    }


# --------------------------------------------------------------------- draft


def draft_view(
    snap: GameSnapshot, state: GameState, ctx: DraftContext, seed: int, *, page: int = 1, page_size: int = 40,
    pos: str = "", q: str = "", full: bool = True,
) -> dict[str, Any]:
    ev = ctx.ev
    owners = state.owner_map()
    user = snap.user_team.tid
    total = ctx.total
    clock = ctx.on_clock()
    mine = [i + 1 for i, t in enumerate(ctx.order) if t == user]
    upcoming = [n for n in mine if n > state.pick_index]
    draft: dict[str, Any] = {
        "status": "complete" if state.pick_index >= total else "in_progress",
        "pick_no": min(state.pick_index + 1, total), "round": min(state.pick_index // snap.settings.teams + 1, snap.settings.rounds),
        "total_picks": total,
        "on_the_clock": ({"team_id": clock, "name": snap.team(clock).name, "is_you": clock == user} if clock else None),
        "your_pick_numbers": mine,
        "picks_until_you": (upcoming[0] - 1 - state.pick_index) if upcoming else None,
        "queue": list(state.queue),
        "your_roster": [player_row(snap, state, ev, p, owners) for p in state.rosters[user]],
    }
    if full:
        draft["order"] = [{"pick_no": i + 1, "round": i // snap.settings.teams + 1, "team_id": t} for i, t in enumerate(ctx.order)]
        draft["picks"] = [pick_row(snap, state, ev, owners, p) for p in state.picks]
        draft["teams"] = [
            {"team_id": t.tid, "name": t.name, "persona_id": t.persona_id, "is_you": t.is_user} for t in snap.teams
        ]
    taken = ctx.taken()
    needle = q.strip().lower()
    avail = [
        pid for pid in ctx.by_adp
        if pid not in taken and (not pos or snap.players[pid].pos == pos)
        and (not needle or needle in snap.players[pid].name.lower())
    ]
    page_size = max(1, min(PAGE_MAX, page_size))
    page = max(1, page)
    chunk = avail[(page - 1) * page_size: page * page_size]
    hint = None
    if state.status == "drafting" and state.pick_index < total and clock == user:
        pid = best_for_user(ctx, seed)
        hint = {"player": player_row(snap, state, ev, pid, owners),
                "why": f"Best available for your need: {snap.players[pid].pos}"}
    return {
        "draft": draft,
        "available": {"items": [player_row(snap, state, ev, p, owners) for p in chunk], "total": len(avail),
                      "page": page, "page_size": page_size},
        "hint": hint,
    }


def pick_row(snap: GameSnapshot, state: GameState, ev: Evaluator, owners: Mapping[str, str], p: Mapping[str, Any]) -> dict[str, Any]:
    player = snap.players[p["pid"]]
    return {
        "pick_no": p["n"] + 1, "round": p["round"], "team_id": p["team"],
        "player": player_row(snap, state, ev, p["pid"], owners), "adp": player.adp,
        "value_over_adp": round((p["n"] + 1) - player.adp, 1), "auto": p["auto"],
    }


# -------------------------------------------------------------------- league


def _asset_name(snap: GameSnapshot, pid: str) -> str:
    if is_pick_id(pid):
        _, season, rnd, orig = pid.split(":", 3)
        return f"{season} round {rnd} pick ({snap.team(orig).name})"
    return snap.players[pid].name


def _tx_text(snap: GameSnapshot, tx: Mapping[str, Any]) -> tuple[str, str]:
    name = lambda pid: _asset_name(snap, pid)
    kind = tx["type"]
    if kind == "reserve":
        where = {"ir": "IR", "taxi": "the taxi squad", "roster": "the active roster"}[tx["dst"]]
        return tx["team"], f"{snap.team(tx['team']).name} moved {name(tx['pid'])} to {where}"
    if kind == "trade":
        a, b = snap.team(tx["team_a"]).name, snap.team(tx["team_b"]).name
        return tx["team_a"], f"{a} traded {', '.join(name(p) for p in tx['give'])} to {b} for {', '.join(name(p) for p in tx['get'])}"
    team = snap.team(tx["team"]).name
    if kind == "waiver":
        drop = f", dropping {name(tx['drop'])}" if tx.get("drop") else ""
        return tx["team"], f"{team} added {name(tx['add'])}{drop}"
    return tx["team"], f"{team} dropped {name(tx['pid'])}"


def _tx_players(snap: GameSnapshot, tx: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The players a feed row names, for photos: ``role`` is add/drop/give/get."""

    roles: list[tuple[str, str | None]]
    if tx["type"] == "trade":
        roles = [("give", p) for p in tx["give"]] + [("get", p) for p in tx["get"]]
    elif tx["type"] == "waiver":
        roles = [("add", tx.get("add")), ("drop", tx.get("drop"))]
    else:
        roles = [("drop", tx.get("pid"))] if tx["type"] != "reserve" else [("move", tx.get("pid"))]
    return [
        {"role": role, "id": pid, "headshot_id": headshot_id(pid), "name": snap.players[pid].name,
         "pos": snap.players[pid].pos, "team": snap.players[pid].nfl_team}
        for role, pid in roles if pid and pid in snap.players and not is_pick_id(pid)
    ]


def league_view(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    S = snap.settings
    played = {h["week"]: h for h in state.history}
    schedule = []
    for w in range(1, S.regular_weeks + 1):
        if w in played:
            games = played[w]["games"]
        else:
            games = [{"home": h, "away": a, "home_pts": None, "away_pts": None, "winner": None} for h, a in snap.schedule[w - 1]]
        schedule.append({"week": w, "kind": "regular", "games": games})
    playoffs = None
    if state.playoff:
        pl = state.playoff
        for rnd in pl["rounds"]:
            schedule.append({"week": rnd["week"], "kind": "playoff", "games": rnd["games"]})
        playoffs = {"seeds": pl["seeds"], "slots": pl["slots"], "alive": pl["alive"], "rounds": pl["rounds"],
                    "champion": state.champion or None}
    power = sorted(snap.tids, key=lambda t: (-ev.lineup_total(state.rosters[t]) if state.rosters[t] else 0.0, t))
    teams = []
    for t in snap.teams:
        persona = PERSONAS.get(t.persona_id)
        roster = state.rosters[t.tid]
        teams.append({
            "team_id": t.tid, "name": t.name, "owner": t.owner, "is_you": t.is_user,
            "persona": {"id": t.persona_id, "label": persona.label if persona else "You",
                        "blurb": persona.blurb if persona else "You run this team."},
            "power_rank": power.index(t.tid) + 1,
            "avg_age": round(sum(snap.players[p].age for p in roster) / len(roster), 1) if roster else None,
        })
    tx = []
    for item in state.transactions[-60:][::-1]:
        tid, text = _tx_text(snap, item)
        tx.append({"week": item["week"], "type": item["type"], "team_id": tid, "text": text,
                   "players": _tx_players(snap, item)})
    return {"standings": standing_rows(snap, state), "schedule": schedule, "transactions": tx,
            "teams": teams, "playoffs": playoffs}


def team_roster(snap: GameSnapshot, state: GameState, tid: str) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    return {"team_id": tid, "players": [player_row(snap, state, ev, p, owners) for p in
                                        sorted(state.rosters[tid], key=lambda p: (-ev.ros_mean(p), p))],
            **reserve_block(snap, state, ev, tid, owners, max(state.week, 1))}


# --------------------------------------------------------------------- inbox


def inbox_view(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    items = []
    for o in state.offers:
        team = snap.team(o["team"])
        items.append({
            "id": o["id"], "type": "trade_offer",
            "from": {"team_id": team.tid, "name": team.name, "persona_id": team.persona_id},
            "you_give": [player_row(snap, state, ev, p, owners) for p in o["get"]],
            "you_get": [player_row(snap, state, ev, p, owners) for p in o["give"]],
            "message": o.get("message", ""), "expires_week": o["expires_week"],
        })
    return items


def pending_claims(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    return [
        {"id": c["id"], "add": player_row(snap, state, ev, c["add"], owners),
         "drop": player_row(snap, state, ev, c["drop"], owners) if c.get("drop") else None,
         "start_slot": c.get("start_slot")}
        for c in state.claims
    ]


def players_for(snap: GameSnapshot, state: GameState, pids: Sequence[str]) -> list[dict[str, Any]]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    return [player_row(snap, state, ev, p, owners) for p in pids]


__all__ = [
    "preview_block", "paywalled", "player_row", "players_page", "player_detail", "lineup_view", "game_view",
    "draft_view", "league_view", "pick_asset", "reserve_block", "dynasty_block", "team_roster", "inbox_view", "pending_claims", "players_for", "pick_row",
    "SORTS", "PAGE_MAX", "rank_teams",
]
