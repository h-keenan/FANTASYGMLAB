"""The GM game's Home dashboard and the scouting view of any team.

Read-only over (snapshot, state), like ``game_view``. Nothing here changes
state or draws randomness (the one seed it takes only replays the AI manager's
own lineup choice, so the matchup shows the lineup that will actually play).

Every recommendation weighs several real factors (this week's projected gain,
what the player did lately, how thin the position is on your roster, byes and
injuries) and says which ones in ``reasons``; no single-rule shortcuts.
"""

from __future__ import annotations

import logging

import math
from typing import Any, Mapping, Sequence

from modules.sim import game_block as blockmod
from modules.sim.game_actions import lineup_warnings
from modules.sim.game_ai import ai_lineup, trade_window
from modules.sim.game_engine import standing_rows
from modules.sim.game_eval import Evaluator
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot, slot_positions
from modules.sim.game_view import (
    pick_asset,
    _opponent,
    _tx_players,
    _tx_text,
    player_row,
    reserve_block,
    team_roster,
)
from modules.sim.lineup import pick_lineup
from modules.sim.personas import PERSONAS
from modules.sim.types import FLEX_SLOTS, GAME_POSITIONS, is_pick_id

BYE_LOOKAHEAD = 3  # weeks (including this one) a bye alert looks ahead
MAX_WAIVER_SUGGESTIONS = 4
MAX_COVER_NAMES = 3
WAIVER_CANDIDATES = 70
MIN_SUGGESTION_GAIN = 0.8  # points of lineup improvement worth mentioning
HOT_DELTA = 4.0  # points over the frozen projection to call a week hot
RECENT_MOVES = 6
TRADE_SPOTLIGHT_WEEKS = 3


# ----------------------------------------------------------------- helpers


def _win_prob(mu_a: float, sd_a: float, mu_b: float, sd_b: float) -> float:
    """Normal approximation of 'team A outscores team B'."""

    spread = math.sqrt(sd_a * sd_a + sd_b * sd_b)
    if spread <= 1e-9:
        return 0.5 if mu_a == mu_b else (1.0 if mu_a > mu_b else 0.0)
    return 0.5 * (1.0 + math.erf((mu_a - mu_b) / (spread * math.sqrt(2.0))))


def _lineup_sd(snap: GameSnapshot, ev: Evaluator, lineup: Sequence[Sequence[Any]], week: int) -> float:
    var = 0.0
    for _, pid in lineup:
        if pid and ev.proj(pid, week) > 0:
            var += snap.players[pid].sd ** 2
    return math.sqrt(var)


def _record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in ("wins", "losses", "ties", "pf", "pa", "rank", "streak", "seed", "playoff_status")}


def _effective(ev: Evaluator, pid: str) -> float:
    """Season-style worth of a player to a lineup: byes ignored, long injuries discounted."""

    return ev.ros_mean(pid) * (1.0 if ev.state.out.get(pid, 0) <= 2 else 0.3)


def _persona(snap: GameSnapshot, persona_id: str) -> dict[str, str]:
    persona = PERSONAS.get(persona_id)
    return {"id": persona_id, "label": persona.label if persona else "You",
            "blurb": persona.blurb if persona else "You run this team."}


def _team_ref(snap: GameSnapshot, tid: str) -> dict[str, Any]:
    team = snap.team(tid)
    return {"team_id": tid, "name": team.name, "persona_id": team.persona_id, "is_you": team.is_user}


def _pos_labels(ev: Evaluator, roster: Sequence[str]) -> dict[str, str]:
    """pid -> 'WR1': the player's rank among his position on this roster."""

    out: dict[str, str] = {}
    by_pos: dict[str, list[str]] = {}
    for pid in roster:
        by_pos.setdefault(ev.snap.players[pid].pos, []).append(pid)
    for pos, pids in by_pos.items():
        for i, pid in enumerate(sorted(pids, key=lambda p: (-ev.ros_mean(p), p))):
            out[pid] = f"{pos}{i + 1}"
    return out


# ------------------------------------------------------------ scouting a team


def _position_report(snap: GameSnapshot, ev: Evaluator) -> dict[str, list[dict[str, Any]]]:
    """Per team, per position: starter-group strength ranked across the league."""

    S = snap.settings
    starters: dict[str, float] = {}
    for pos in S.pool_positions:
        weight = float(sum(1 for s in S.slots if s == pos))
        for slot in S.slots:
            if slot in FLEX_SLOTS and pos in FLEX_SLOTS[slot]:
                weight += 1.0 / len(FLEX_SLOTS[slot])
        if weight > 0:
            starters[pos] = weight
    raw: dict[str, dict[str, tuple[float, int]]] = {}
    for tid in snap.tids:
        by_pos: dict[str, list[float]] = {}
        for pid in ev.state.rosters[tid]:
            by_pos.setdefault(snap.players[pid].pos, []).append(_effective(ev, pid))
        raw[tid] = {}
        for pos, weight in starters.items():
            vals = sorted(by_pos.get(pos, []), reverse=True)
            k = max(1, int(round(weight)))
            raw[tid][pos] = (sum(vals[:k]), max(0, len(vals) - k))
    n = len(snap.tids)
    report: dict[str, list[dict[str, Any]]] = {tid: [] for tid in snap.tids}
    for pos, weight in starters.items():
        order = sorted(snap.tids, key=lambda t: (-raw[t][pos][0], t))
        for tid in snap.tids:
            rank = order.index(tid) + 1
            strength, depth = raw[tid][pos]
            level = "strength" if rank <= max(1, math.ceil(n / 3)) else "need" if rank > n - max(1, math.ceil(n / 3)) else "ok"
            report[tid].append({
                "pos": pos, "rank": rank, "teams": n, "level": level, "depth": depth,
                "starters": max(1, int(round(weight))), "strength": round(strength, 1),
            })
    return report


def team_detail(snap: GameSnapshot, state: GameState, tid: str, seed: int = 0) -> dict[str, Any]:
    """Everything the 'open a team' sheet shows: roster, record, lineup,
    strengths and needs, injuries, recent moves, trade availability."""

    ev = Evaluator(snap, state)
    owners = state.owner_map()
    team = snap.team(tid)
    week = max(state.week, 1)
    rows = standing_rows(snap, state) if state.status != "drafting" else []
    row = next((r for r in rows if r["team_id"] == tid), None)
    roster = state.rosters[tid]
    power = sorted(snap.tids, key=lambda t: (-ev.lineup_total(state.rosters[t]) if state.rosters[t] else 0.0, t))
    positions = _position_report(snap, ev)[tid] if roster else []
    lineup_slots, projected = ev.best_lineup(roster, week) if roster else ([], 0.0)
    if state.status in ("in_season", "playoffs") and tid != snap.user_team.tid:
        lineup_slots = ai_lineup(ev, tid, week, seed)
        projected = ev.lineup_projection(lineup_slots, week)
    elif tid == snap.user_team.tid and any(p for _, p in state.lineups[tid]):
        lineup_slots = state.lineups[tid]
        projected = ev.lineup_projection(lineup_slots, week)
    moves = []
    for item in reversed(state.transactions):
        involved = {item.get("team"), item.get("team_a"), item.get("team_b")}
        if tid not in involved:
            continue
        _, text = _tx_text(snap, item)
        moves.append({"week": item["week"], "type": item["type"], "text": text, "players": _tx_players(snap, item)})
        if len(moves) >= 5:
            break
    next_game = None
    if state.status == "in_season" and 1 <= week <= snap.settings.regular_weeks:
        for home, away in snap.schedule[week - 1]:
            if tid in (home, away):
                other = away if home == tid else home
                next_game = {"week": week, "opponent": _team_ref(snap, other)}
    window = trade_window(snap, state)
    out = {
        "team_id": tid,
        "team": {
            "team_id": tid, "name": team.name, "owner": team.owner, "is_you": team.is_user,
            "persona": _persona(snap, team.persona_id),
            "record": _record(row) if row else None,
            "power_rank": power.index(tid) + 1,
            "avg_age": round(sum(snap.players[p].age for p in roster) / len(roster), 1) if roster else None,
            "roster_size": len(roster),
        },
        "players": team_roster(snap, state, tid)["players"],
        **reserve_block(snap, state, ev, tid, owners, week),
        "lineup": [
            {"slot": slot, "player": player_row(snap, state, ev, pid, owners, week=week) if pid else None}
            for slot, pid in lineup_slots
        ],
        "projected_total": round(projected, 1),
        "positions": positions,
        "strengths": [p["pos"] for p in positions if p["level"] == "strength"],
        "needs": [p["pos"] for p in positions if p["level"] == "need"],
        "injuries": [
            player_row(snap, state, ev, pid, owners, week=week)
            for pid in roster if state.out.get(pid, 0) > 0
        ],
        "recent": moves,
        "next_game": next_game,
        "trade": {"open": window is None and tid != snap.user_team.tid, "reason": window},
    }
    if snap.settings.block:
        bidx = blockmod.block_index(snap, state, ev, seed)
        blockmod.attach(out["players"] + out["ir"] + out["taxi"] + out["injuries"] + [s["player"] for s in out["lineup"] if s["player"]], bidx)
    return out


SURPLUS_DEPTH = 2  # players beyond a position's starters before it reads as a surplus to trade from (never at a position of need)
TOP_ASSETS = 3


def league_rosters(snap: GameSnapshot, state: GameState, seed: int = 0) -> dict[str, Any]:
    """Every team's full roster in one payload (the League tab's who-has-who view and the trade partner list).

    One Evaluator and one position report for the whole league, no per-team requests. Each team carries its
    record, power rank, strengths / needs / surplus by position, its top assets and every player it holds
    (roster, IR and taxi; ``squad`` on a row says which)."""

    ev = Evaluator(snap, state)
    owners = state.owner_map()
    week = max(state.week, 1)
    rows = standing_rows(snap, state) if state.status != "drafting" else []
    by_team = {r["team_id"]: r for r in rows}
    power = sorted(snap.tids, key=lambda t: (-ev.lineup_total(state.rosters[t]) if state.rosters[t] else 0.0, t))
    report = _position_report(snap, ev)
    bidx = blockmod.block_index(snap, state, ev, seed)  # {} unless the game has a trade block
    blocks = {b["team_id"]: b for b in blockmod.league_blocks(snap, state, ev, seed)} if bidx or snap.settings.block else {}
    teams = []
    for t in snap.teams:
        tid = t.tid
        roster = state.rosters[tid]
        held = [*roster, *state.ir.get(tid, ()), *state.taxi.get(tid, ())]
        positions = report[tid] if roster else []
        rows_ = [player_row(snap, state, ev, pid, owners, week=week) for pid in sorted(held, key=lambda p: (-snap.players[p].value, p))]
        teams.append({
            "team_id": tid, "name": t.name, "owner": t.owner, "is_you": t.is_user, "persona": _persona(snap, t.persona_id),
            "record": _record(by_team[tid]) if tid in by_team else None,
            "power_rank": power.index(tid) + 1,
            "avg_age": round(sum(snap.players[p].age for p in roster) / len(roster), 1) if roster else None,
            "roster_size": len(roster),
            "positions": positions,
            "strengths": [p["pos"] for p in positions if p["level"] == "strength"],
            "needs": [p["pos"] for p in positions if p["level"] == "need"],
            "surplus": [p["pos"] for p in positions if p["depth"] >= SURPLUS_DEPTH and p["level"] != "need"],
            "top_assets": rows_[:TOP_ASSETS],
            "players": rows_,
        })
        blockmod.attach(rows_, bidx)
        if snap.settings.block:  # absent on a save from before the block, so its payload is unchanged
            b = blocks.get(tid)
            teams[-1]["block"] = {"stance": b["stance"], "looking_for": b["looking_for"], "items": [{"id": i["id"], "why": i["why"]} for i in b["items"]]} if b else None
    return {"teams": teams, "week": week}


# ------------------------------------------------------------------- matchup


def _matchup(snap: GameSnapshot, state: GameState, ev: Evaluator, rows: Sequence[Mapping[str, Any]], seed: int) -> dict[str, Any] | None:
    user = snap.user_team.tid
    week = max(state.week, 1)
    opp = _opponent(snap, state, ev, week)
    if opp is None:
        return {"week": state.week, "bye": True, "kind": "regular", "opponent": None, "rows": []}
    owners = state.owner_map()
    mine = state.lineups[user]
    theirs = ai_lineup(ev, opp["team_id"], week, seed)
    slot_rows = []
    for i, (slot, pid) in enumerate(mine):
        opid = theirs[i][1] if i < len(theirs) else None
        slot_rows.append({
            "slot": slot,
            "you": player_row(snap, state, ev, pid, owners, week=week) if pid else None,
            "opp": player_row(snap, state, ev, opid, owners, week=week) if opid else None,
        })
    you_mu = ev.lineup_projection(mine, week)
    opp_mu = ev.lineup_projection(theirs, week)

    def shown_total(lineup: Sequence[Sequence]) -> float:
        """The displayed total: the sum of the per-slot numbers the user sees (each rounded to a tenth), counting
        what scores this week (an out or bye starter counts 0). Summing the exact values and rounding once made
        the total differ from the visible slots by a tenth or two (123.1 total over slots adding to 122.9)."""
        return round(sum(round(ev.proj(row[1], week), 1) for row in lineup if row[1]), 1)

    prob = _win_prob(you_mu, _lineup_sd(snap, ev, mine, week), opp_mu, _lineup_sd(snap, ev, theirs, week))
    opp_row = next((r for r in rows if r["team_id"] == opp["team_id"]), None)
    you_row = next((r for r in rows if r["team_id"] == user), None)
    flagged = lambda side: sum(1 for r in slot_rows if r[side] and r[side]["status"] != "healthy")
    return {
        "week": state.week, "bye": False, "kind": "playoff" if state.status == "playoffs" else "regular",
        "opponent": {**_team_ref(snap, opp["team_id"]), "record": _record(opp_row) if opp_row else None,
                     "persona": _persona(snap, opp["persona_id"])},
        "you_record": _record(you_row) if you_row else None,
        "you_projection": shown_total(mine), "opp_projection": shown_total(theirs),
        "win_prob": round(prob, 3),
        "rows": slot_rows, "you_flagged": flagged("you"), "opp_flagged": flagged("opp"),
    }


# ----------------------------------------------------------- waivers & byes


def _free_agents(snap: GameSnapshot, state: GameState, ev: Evaluator, week: int) -> list[str]:
    owned = state.owner_map()
    pool = [
        pid for pid in snap.pids
        if pid not in owned and snap.players[pid].pos in GAME_POSITIONS and ev.ros_mean(pid) > 0
    ]
    pool.sort(key=lambda p: (-ev.ros_mean(p), p))
    return pool


def _waiver_suggestions(snap: GameSnapshot, state: GameState, ev: Evaluator, week: int, free: Sequence[str]) -> list[dict[str, Any]]:
    user = snap.user_team.tid
    roster = list(state.rosters[user])
    owners = state.owner_map()
    labels = _pos_labels(ev, roster)
    base_lineup, base_total = ev.best_lineup(roster, week)
    base_starters = {pid for _, pid in base_lineup if pid}
    queued = {c["add"] for c in state.claims}
    ros_base = pick_lineup(ev.plan, [(_effective(ev, p), p, snap.players[p].pos) for p in roster])[1]
    full = len(roster) >= snap.settings.roster_limit
    singles = {"K", "DEF"}
    out: list[dict[str, Any]] = []
    for pid in free[:WAIVER_CANDIDATES]:
        if pid in queued or ev.out_in(pid, week):
            continue
        pos = snap.players[pid].pos
        now_lineup, now_total = ev.best_lineup(roster + [pid], week)
        gain_now = now_total - base_total
        ros_total = pick_lineup(ev.plan, [(_effective(ev, p), p, snap.players[p].pos) for p in roster + [pid]])[1]
        gain_ros = ros_total - ros_base
        if max(gain_now, gain_ros) < MIN_SUGGESTION_GAIN:
            continue
        now_starters = {p for _, p in now_lineup if p}
        displaced = [p for p in base_starters if p not in now_starters]
        reasons: list[str] = []
        # Starters you set who cannot play this week (out or bye) that this player could take over from.
        hole = next(
            (p for slot, p in state.lineups[user]
             if p and ev.status(p, week) != "healthy" and pos in slot_positions(slot)),
            None,
        )
        covers = hole
        if pid in now_starters and gain_now >= MIN_SUGGESTION_GAIN:
            if hole:
                why = "out" if ev.status(hole, week) == "out" else "bye"
                reasons.append(f"Covers {snap.players[hole].name} ({why}): +{gain_now:.1f} pts this week")
            elif displaced:
                reasons.append(f"+{gain_now:.1f} pts this week over {snap.players[displaced[0]].name}")
            else:
                reasons.append(f"+{gain_now:.1f} pts this week in an open starting slot")
        elif gain_ros >= MIN_SUGGESTION_GAIN:
            reasons.append(f"+{gain_ros:.1f} pts per week rest of season")
        mine_at = sorted((p for p in roster if snap.players[p].pos == pos), key=lambda p: (-ev.ros_mean(p), p))
        if len(mine_at) < max(2, sum(1 for s in snap.settings.slots if s == pos) + 1) and pos not in singles:
            reasons.append(f"Thin at {pos}: you only carry {len(mine_at)}")
        last = state.last_points(pid)
        if last is not None and last >= 12.0:
            reasons.append(f"Scored {last:.1f} last week")
        drop = None
        if full:
            keep = now_starters
            cands = sorted((p for p in roster if p not in keep), key=lambda p: (ev.ros_mean(p), p))
            if cands:
                drop = player_row(snap, state, ev, cands[0], owners, week=week)
        out.append({
            "player": player_row(snap, state, ev, pid, owners, week=week),
            "gain_now": round(gain_now, 1), "gain_ros": round(gain_ros, 1), "reasons": reasons,
            "drop": drop, "covers": player_row(snap, state, ev, covers, owners, week=week) if covers else None,
            "for_slot": labels.get(hole or (displaced[0] if displaced else "")),
        })
    out.sort(key=lambda s: (-(max(s["gain_now"], 0.0) + 0.6 * max(s["gain_ros"], 0.0)), s["player"]["id"]))
    picked: list[dict[str, Any]] = []
    seen_pos: dict[str, int] = {}
    for s in out:  # at most two per position so one hole does not eat the list
        p = s["player"]["pos"]
        if seen_pos.get(p, 0) >= 2:
            continue
        seen_pos[p] = seen_pos.get(p, 0) + 1
        picked.append(s)
        if len(picked) >= MAX_WAIVER_SUGGESTIONS:
            break
    return picked


def bye_alerts(snap: GameSnapshot, state: GameState, ev: Evaluator, free: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Upcoming byes that take a starter out of your lineup, with who covers it.

    A starter is whoever the best lineup would play if byes did not exist
    (the players you actually rely on). ``covered_by`` is a healthy bench
    player who can take the slot that week; if there is none, the alert lists
    free agents worth a claim."""

    if state.status != "in_season":
        return []
    user = snap.user_team.tid
    roster = list(state.rosters[user])
    owners = state.owner_map()
    labels = _pos_labels(ev, roster)
    free = list(free) if free is not None else _free_agents(snap, state, ev, state.week)
    first = max(state.week, 1)
    alerts: list[dict[str, Any]] = []
    for w in range(first, min(snap.settings.regular_weeks, first + BYE_LOOKAHEAD - 1) + 1):
        assignment, _ = pick_lineup(ev.plan, ev.entries(roster, w, bye=False))
        starters = {pid: slot for slot, pid in assignment if pid}
        used: set[str] = set()  # one bench player cannot cover two byes in the same week
        for pid, slot in sorted(starters.items(), key=lambda kv: (-ev.ros_mean(kv[0]), kv[0])):
            if not ev.on_bye(pid, w):
                continue
            pos = snap.players[pid].pos
            eligible = slot_positions(slot)
            bench = [
                p for p in roster
                if p not in starters and p not in used and snap.players[p].pos in eligible
                and not ev.on_bye(p, w) and not ev.out_in(p, w)
            ]
            bench.sort(key=lambda p: (-ev.ros_mean(p), p))
            cover = bench[0] if bench else None
            if cover:
                used.add(cover)
            fills = [
                p for p in free
                if snap.players[p].pos == pos and not ev.on_bye(p, w) and not ev.out_in(p, w)
            ][:MAX_COVER_NAMES]
            label = labels.get(pid, pos)
            names = ", ".join(snap.players[p].name for p in fills)
            if cover:
                msg = f"Your {label} {snap.players[pid].name} is on bye in Week {w}. {snap.players[cover].name} can fill in from your bench."
            elif fills:
                msg = f"Your {label} {snap.players[pid].name} is on bye in Week {w}. Look at the wire for a fill-in: {names}."
            else:
                msg = f"Your {label} {snap.players[pid].name} is on bye in Week {w} and nobody on the wire fits."
            alerts.append({
                "week": w, "weeks_away": w - first, "slot": slot, "pos_label": label,
                "player": player_row(snap, state, ev, pid, owners, week=w),
                "covered": cover is not None,
                "covered_by": player_row(snap, state, ev, cover, owners, week=w) if cover else None,
                "replacements": [player_row(snap, state, ev, p, owners, week=w) for p in fills],
                "message": msg,
            })
    alerts.sort(key=lambda a: (a["week"], a["covered"], a["player"]["id"]))
    return alerts


# ----------------------------------------------------------- the rest of Home


def _injuries(snap: GameSnapshot, state: GameState, ev: Evaluator, week: int) -> list[dict[str, Any]]:
    user = snap.user_team.tid
    owners = state.owner_map()
    started = {pid for _, pid in state.lineups[user] if pid}
    news = {n["pid"]: n for n in state.news}
    rows = []
    for pid in state.rosters[user]:
        weeks = state.out.get(pid, 0)
        if weeks <= 0:
            continue
        rows.append({
            "player": player_row(snap, state, ev, pid, owners, week=week), "out_weeks": weeks,
            "starting": pid in started,
            "note": (f"Hurt in Week {news[pid]['week']}" if pid in news else "Out since the start of the season"),
        })
    rows.sort(key=lambda r: (not r["starting"], -r["player"]["ros_mean"], r["player"]["id"]))
    return rows


def _hot_cold(snap: GameSnapshot, state: GameState, ev: Evaluator, week: int, free: Sequence[str]) -> dict[str, Any]:
    user = snap.user_team.tid
    owners = state.owner_map()

    def trend(pid: str) -> dict[str, Any] | None:
        last = state.last_points(pid)
        if last is None:
            return None
        proj = snap.players[pid].mean
        return {"player": player_row(snap, state, ev, pid, owners, week=week), "last_week": round(last, 1),
                "delta": round(last - proj, 1), "avg": round(sum(state.games_played(pid)) / len(state.games_played(pid)), 1)}

    mine = [t for t in (trend(p) for p in state.rosters[user]) if t and snap.players[t["player"]["id"]].mean >= 5.0]
    hot = sorted((t for t in mine if t["delta"] >= HOT_DELTA), key=lambda t: (-t["delta"], t["player"]["id"]))[:3]
    cold = sorted((t for t in mine if t["delta"] <= -HOT_DELTA), key=lambda t: (t["delta"], t["player"]["id"]))[:3]
    wire = [t for t in (trend(p) for p in free[:120]) if t and t["last_week"] >= 10.0 and t["delta"] > 0]
    wire.sort(key=lambda t: (-t["delta"], t["player"]["id"]))
    return {"hot": hot, "cold": cold, "wire": wire[:3]}


def _standings(snap: GameSnapshot, state: GameState, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    S = snap.settings
    user = snap.user_team.tid
    spots = S.playoff_teams
    me = next((r for r in rows if r["team_id"] == user), None)
    played = len(state.history)
    margin = None
    if me and state.status == "in_season" and len(rows) > spots:
        wins = lambda r: r["wins"] + 0.5 * r["ties"]
        if me["rank"] <= spots:
            margin = wins(me) - wins(rows[spots])
        else:
            margin = wins(me) - wins(rows[spots - 1])
    return {
        "rows": [
            {k: r[k] for k in ("rank", "team_id", "name", "is_you", "persona_id", "wins", "losses", "ties", "pf", "pa",
                               "streak", "seed", "playoff_status")}
            for r in rows
        ],
        "playoff_spots": spots, "games_left": max(0, S.regular_weeks - played),
        "your_rank": me["rank"] if me else None, "margin": margin,
        "in_playoffs": bool(me and me["playoff_status"] in ("in", "alive", "champion")),
    }


def _league_moves(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    recent = []
    for item in state.transactions[-RECENT_MOVES:][::-1]:
        tid, text = _tx_text(snap, item)
        recent.append({"week": item["week"], "type": item["type"], "team_id": tid, "text": text,
                       "players": _tx_players(snap, item)})
    cutoff = max(1, state.week - TRADE_SPOTLIGHT_WEEKS)
    best = None
    best_score = -1.0
    for item in state.transactions:
        if item["type"] != "trade" or item["week"] < cutoff:
            continue
        moved = [p for p in (*item["give"], *item["get"]) if p in snap.players]
        score = sum(snap.players[p].value for p in moved)
        if score >= best_score:
            best, best_score = item, score
    spotlight = None
    if best is not None:
        _, text = _tx_text(snap, best)
        moved = [p for p in (*best["give"], *best["get"]) if p in snap.players]
        top = max(moved, key=lambda p: (snap.players[p].value, p)) if moved else None
        a, b = _team_ref(snap, best["team_a"]), _team_ref(snap, best["team_b"])
        spotlight = {
            "week": best["week"], "text": text, "team_a": a, "team_b": b, "players": _tx_players(snap, best),
            "headline": (f"{snap.players[top].name} ({snap.players[top].pos}) is the centerpiece" if top else "A notable swap"),
        }
    return {"recent": recent, "spotlight": spotlight}


def _checklist(
    snap: GameSnapshot, state: GameState, warnings: Sequence[Mapping[str, Any]], suggestions: Sequence[Mapping[str, Any]],
    alerts: Sequence[Mapping[str, Any]], inbox: int, cuts: int, window: str | None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if cuts and snap.settings.soft_limit:  # limit_v 1+: a note, never a blocker
        items.append({"id": "cuts", "label": f"Over the limit by {cuts}", "target": "team", "done": False,
                      "severity": "warning", "detail": "Cut or trade to add players. You can still advance."})
    elif cuts:
        items.append({"id": "cuts", "label": f"Cut {cuts} player{'s' if cuts != 1 else ''}", "target": "team", "done": False,
                      "severity": "danger", "detail": "Your roster is over the limit; you cannot advance until you cut."})
    n = len(warnings)
    items.append({
        "id": "lineup", "label": "Set your lineup", "target": "team", "done": n == 0,
        "severity": "danger" if n else "ok",
        "detail": (f"{n} starter slot{'s' if n != 1 else ''} need attention (out, on bye or empty)." if n else "Every starter is healthy and playing."),
    })
    queued = len(state.claims)
    if suggestions:
        top = suggestions[0]["player"]["name"]
        items.append({"id": "waivers", "label": "Check the waiver wire", "target": "players", "done": queued > 0,
                      "severity": "warning" if queued == 0 else "ok",
                      "detail": (f"{queued} claim{'s' if queued != 1 else ''} queued." if queued else f"Top target: {top}.")})
    else:
        items.append({"id": "waivers", "label": "Check the waiver wire", "target": "players", "done": True,
                      "severity": "ok", "detail": "Nothing on the wire beats your roster right now."})
    uncovered = [a for a in alerts if not a["covered"]]
    if alerts:
        items.append({
            "id": "byes", "label": "Cover your bye weeks", "target": "players", "done": not uncovered,
            "severity": "warning" if uncovered else "ok",
            "detail": (uncovered[0]["message"] if uncovered else "Your bench covers every upcoming bye."),
        })
    items.extend(_reserve_items(snap, state))
    if window is None:
        items.append({"id": "offers", "label": "Answer trade offers", "target": "trades", "done": inbox == 0,
                      "severity": "accent" if inbox else "ok",
                      "detail": (f"{inbox} offer{'s' if inbox != 1 else ''} waiting in your inbox." if inbox else "No offers waiting.")})
    return items


def _reserve_items(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    """IR and taxi housekeeping for the checklist (nothing for a game without reserve squads)."""

    S = snap.settings
    if not S.reserves:
        return []
    user = snap.user_team.tid
    items: list[dict[str, Any]] = []
    healthy = [p for p in state.ir[user] if state.out.get(p, 0) <= 0 and p in snap.players]
    if healthy:
        items.append({"id": "ir_activate", "label": "Activate a healthy player from IR", "target": "team", "done": False,
                      "severity": "warning",
                      "detail": f"{snap.players[healthy[0]].name} is healthy and still on your IR."})
    if S.ir_slots and len(state.ir[user]) < S.ir_slots:
        hurt = sorted((p for p in state.rosters[user] if state.out.get(p, 0) >= 4), key=lambda p: (-state.out[p], p))
        if hurt:
            items.append({"id": "ir_stash", "label": "Free a roster spot with IR", "target": "team", "done": False,
                          "severity": "accent",
                          "detail": f"{snap.players[hurt[0]].name} is out {state.out[hurt[0]]} weeks; IR frees a spot."})
    return items


def _extras(snap: GameSnapshot, state: GameState, ev: Evaluator) -> dict[str, Any]:
    out: dict[str, Any] = {}
    user = snap.user_team.tid
    if snap.settings.reserves:
        out["reserves"] = {"ir_used": len(state.ir[user]), "ir_slots": snap.settings.ir_slots,
                           "taxi_used": len(state.taxi[user]), "taxi_slots": snap.settings.taxi_slots}
    if snap.settings.dynasty:
        picks = sorted(state.picks_of(user))
        out["dynasty"] = {
            "season_no": state.season_no, "seasons": snap.settings.seasons,
            "picks_held": len(picks), "picks_value": round(sum(ev.pick_value(p) for p in picks), 1),
            "next_pick": min(picks, key=lambda p: (p.split(":")[1], int(p.split(":")[2]))) if picks else None,
        }
    return out


_log = logging.getLogger(__name__)


def home_view(snap: GameSnapshot, state: GameState, seed: int) -> dict[str, Any]:
    """Every card is built on its own: one failing card is logged and marked in
    ``errors`` (the client hides it) while the rest of the page still renders."""

    errors: dict[str, str] = {}

    def card(name: str, build: Any, fallback: Any) -> Any:
        try:
            return build()
        except Exception as exc:  # noqa: BLE001 - isolate one card from the page
            _log.exception("sim home card failed card=%s week=%s", name, state.week)
            errors[name] = type(exc).__name__
            return fallback

    ev = Evaluator(snap, state)
    user = snap.user_team.tid
    week = max(state.week, 1)
    rows = standing_rows(snap, state)
    free = card("free_agents", lambda: _free_agents(snap, state, ev, week), [])
    warnings = card("lineup", lambda: lineup_warnings(ev, state.lineups[user], week), [])
    suggestions = card("waiver_suggestions", lambda: _waiver_suggestions(snap, state, ev, week, free), [])
    alerts = card("bye_alerts", lambda: bye_alerts(snap, state, ev, free), [])
    window = trade_window(snap, state)
    inbox = len(state.offers)
    cuts = max(0, len(state.rosters[user]) - snap.settings.roster_limit)
    owners = state.owner_map()

    def build_offers() -> list[dict[str, Any]]:
        out = []
        for o in state.offers[:3]:
            team = snap.team(o["team"])
            out.append({
                "id": o["id"], "from": {"team_id": team.tid, "name": team.name, "persona_id": team.persona_id},
                "you_give": [player_row(snap, state, ev, p, owners) for p in o["get"]],
                "you_get": [player_row(snap, state, ev, p, owners) for p in o["give"]],
                "expires_week": o["expires_week"],
            })
        return out

    offers = card("inbox", build_offers, [])
    return {
        "week": state.week, "phase": "playoffs" if state.status == "playoffs" else "regular_season",
        "matchup": card("matchup", lambda: _matchup(snap, state, ev, rows, seed), None),
        "checklist": card("checklist", lambda: _checklist(snap, state, warnings, suggestions, alerts, inbox, cuts, window), []),
        "inbox": {"count": inbox, "open": window is None, "items": offers},
        "waiver_suggestions": suggestions,
        "bye_alerts": alerts,
        "injuries": card("injuries", lambda: _injuries(snap, state, ev, week), []),
        "hot_cold": card("hot_cold", lambda: _hot_cold(snap, state, ev, week, free), {}),
        "standings": card("standings", lambda: _standings(snap, state, rows), None),
        "league": card("league", lambda: _league_moves(snap, state), None),
        **card("extras", lambda: _extras(snap, state, ev), {}),
        "errors": errors,
    }


__all__ = ["home_view", "team_detail", "bye_alerts"]


# ----------------------------------------------------------------- trade block


def block_view(snap: GameSnapshot, state: GameState, seed: int) -> dict[str, Any]:
    """The Trades tab's block: yours (with the position hint), every AI team shopping this week with its stated needs, and how
    many of this week's offers came from your block."""

    if not snap.settings.block:
        return {"enabled": False, "mine": [], "league": [], "offers_from_block": 0, "max_items": 0}
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    week = max(state.week, 1)
    mine = []
    for pid, v in blockmod.user_block(snap, state).items():
        asset = pick_asset(snap, state, ev, pid) if is_pick_id(pid) else player_row(snap, state, ev, pid, owners, week=week)
        mine.append({"asset": asset, "looking_for": v.get("looking_for"), "since_week": v.get("week")})
    mine.sort(key=lambda m: (m["since_week"] or 0, m["asset"]["id"]))
    bidx = blockmod.block_index(snap, state, ev, seed)
    blockmod.attach([m["asset"] for m in mine], bidx)
    report = _position_report(snap, ev)
    league = []
    for b in blockmod.league_blocks(snap, state, ev, seed):
        tid = b["team_id"]
        league.append({
            "team_id": tid, "name": snap.team(tid).name, "stance": b["stance"], "looking_for": b["looking_for"],
            "needs": [p["pos"] for p in report[tid] if p["level"] == "need"],
            "items": [{"asset": pick_asset(snap, state, ev, i["id"]) if is_pick_id(i["id"]) else player_row(snap, state, ev, i["id"], owners, week=week), "why": i["why"]} for i in b["items"]],
        })
    blockmod.attach([i["asset"] for b in league for i in b["items"]], bidx)
    return {"enabled": True, "mine": mine, "league": league, "max_items": blockmod.MAX_BLOCK_ITEMS,
            "offers_from_block": sum(1 for o in state.offers if o.get("via_block"))}
