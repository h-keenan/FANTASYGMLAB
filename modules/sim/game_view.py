"""JSON views of a game for the API: player rows, lineup, draft board, league.

Read-only over (snapshot, state). Nothing here changes state.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules.sim import scouting
from modules.sim.game_actions import lineup_warnings
from modules.sim.game_ai import trade_window
from modules.sim.game_draft import DraftContext, best_for_user
from modules.sim.game_engine import rank_teams, standing_rows
from modules.sim.game_eval import Evaluator
from modules.sim.game_state import GameState
from modules.sim import game_block as blockmod
from modules.sim.game_types import PREVIEW_PAYWALL_WEEK, GameSnapshot, headshot_id
from modules.sim.personas import PERSONAS
from modules.sim.season_label import season_label, season_label_for_year
from modules.sim.types import FLEX_SLOTS, is_pick_id

PAGE_MAX = 60
SORTS = ("projection", "value", "overall", "adp", "age", "name", "last_week", "season")


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
    # With team roles (player-model-3+) the shown projection is the role-resolved mean for the next game he can
    # play, so an injured starter shows what he does when back and only one backup shows the fill-in number.
    projection = ev.next_proj(pid, w) if ev.roles_on else ev.proj(pid, w)
    # Display only: a player who is on a bye (or out) this week is not projected any points this week. The engine and the AI
    # already treat him as 0 (``ev.proj``); only this row used to show the number he will post when he is back.
    proj_note = ev.status(pid, w) if state.status in ("in_season", "playoffs") else "healthy"
    next_projection = round(projection if ev.roles_on else ev.ros_mean(pid), 1)
    if proj_note != "healthy":
        projection = 0.0
    return {
        "id": pid, "headshot_id": headshot_id(pid), "name": p.name, "pos": p.pos, "team": p.nfl_team,
        "age": p.age, "adp": p.adp, "value": p.value, "overall": overall_ratings(snap).get(pid), "projection": round(projection, 1),
        "projection_note": proj_note if proj_note != "healthy" else None, "next_projection": next_projection, "projection_week": w, "ros_mean": round(ev.ros_mean(pid), 1),
        "role": ev.role_info(pid, w),
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
        "id": pid, "kind": "pick", "headshot_id": None, "name": f"{season_label_for_year(season, snap.settings.start_year)} Round {rnd}", "pos": "PICK", "team": "",
        "season": season, "season_label": season_label_for_year(season, snap.settings.start_year), "round": rnd, "orig_team_id": orig, "orig_team_name": snap.team(orig).name,
        "slot_hint": hint, "label": ev.pick_name(pid), "age": None, "adp": None, "value": round(ev.pick_value(pid), 1),
        "projection": 0.0, "ros_mean": 0.0, "floor": 0.0, "ceiling": 0.0, "status": "healthy", "out_weeks": 0,
        "bye_week": None, "owner": ({"type": "you" if team.is_user else "ai", "team_id": holder, "name": team.name}
                                      if team else {"type": "free_agent", "team_id": None, "name": None}),
        "squad": "picks", "last_week": None, "season_points": 0.0, "games": 0, "ppg": None,
    }


def value_ranks(snap: GameSnapshot) -> dict[str, int]:
    """1-based rank of every player by model value (best first), the basis of the board edge."""
    ranks = getattr(snap, "_value_ranks", None)
    if ranks is None:  # a frozen snapshot's values never change: rank once per snapshot, not per page request
        ordered = sorted(snap.pids, key=lambda pid: (-snap.players[pid].value, pid))
        ranks = {pid: i + 1 for i, pid in enumerate(ordered)}
        object.__setattr__(snap, "_value_ranks", ranks)
    return ranks


# Overall (1-99): where a player's value ranks among players at his position, the SAME definition and curve the real
# app's OVR gauge uses (modules/player_quick_view._overall_rating_from_percentile, BEGINNER_HELP.overallRating).
# The sim may not import real modules (test_sim_isolation), so the curve is copied here and
# tests/test_sim_overall.py pins it to the real one.
OVERALL_MAX = 99
OVERALL_MIN_POOL = 10
OVERALL_CURVE = ((0.0, 40.0), (0.50, 62.0), (0.80, 72.0), (0.93, 80.0), (0.97, 85.0), (0.995, 90.0), (1.0, float(OVERALL_MAX)))


def overall_from_percentile(percentile: float) -> int:
    clamped = min(1.0, max(0.0, percentile))
    rating = OVERALL_CURVE[-1][1]
    for (p_a, r_a), (p_b, r_b) in zip(OVERALL_CURVE, OVERALL_CURVE[1:]):
        if p_a <= clamped <= p_b:
            frac = 0.0 if p_b == p_a else (clamped - p_a) / (p_b - p_a)
            rating = r_a + frac * (r_b - r_a)
            break
    return int(min(OVERALL_MAX, max(1, round(rating))))


def overall_ratings(snap: GameSnapshot) -> dict[str, int]:
    """Overall (1-99) per player: percentile of model value within the position pool (ties share the average rank),
    through the real app's curve. A position pool thinner than OVERALL_MIN_POOL gets no overall (no fabricated rating)."""
    cached = getattr(snap, "_overall_ratings", None)
    if cached is None:  # a frozen snapshot's values never change: compute once per snapshot
        by_pos: dict[str, list[str]] = {}
        for pid in snap.pids:
            by_pos.setdefault(snap.players[pid].pos, []).append(pid)
        cached = {}
        for pids in by_pos.values():
            n = len(pids)
            if n < OVERALL_MIN_POOL:
                continue
            ordered = sorted(pids, key=lambda pid: snap.players[pid].value)
            i = 0
            while i < n:  # average rank for ties, like pandas rank(pct=True)
                j = i
                while j + 1 < n and snap.players[ordered[j + 1]].value == snap.players[ordered[i]].value:
                    j += 1
                pct = ((i + 1) + (j + 1)) / 2 / n
                for k in range(i, j + 1):
                    cached[ordered[k]] = overall_from_percentile(pct)
                i = j + 1
        object.__setattr__(snap, "_overall_ratings", cached)
    return cached


def adp_edge(adp: float | None, value_rank: int | None) -> float | None:
    """ADP minus value rank. Positive: the market drafts him later than the model ranks him (a steal);
    negative: the market takes him earlier than the model would (a reach). Independent of the pick on the clock."""
    if adp is None or value_rank is None:
        return None
    return round(float(adp) - float(value_rank), 1)


def players_page(
    snap: GameSnapshot, state: GameState, *, q: str = "", pos: str = "", status: str = "", team: str = "",
    sort: str = "projection", page: int = 1, page_size: int = 25, seed: int | None = None,
) -> dict[str, Any]:
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    user = snap.user_team.tid
    w = max(state.week, 1)
    bidx = blockmod.block_index(snap, state, ev, seed) if seed is not None else {}
    needle = q.strip().lower()
    # QB/RB/WR/TE/K/DEF, or a flex eligibility group (FLEX, REC_FLEX, SUPER_FLEX) from the lineup slot definitions.
    pos_group = FLEX_SLOTS.get(pos) or frozenset({pos})
    pids = []
    for pid in snap.pids:
        p = snap.players[pid]
        if pos and p.pos not in pos_group:
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
        if status == "block" and pid not in bidx:
            continue
        if team and owner != team:
            continue
        pids.append(pid)

    overall_by_pid = overall_ratings(snap) if sort == "overall" else {}

    def key(pid: str):
        p = snap.players[pid]
        if sort == "value":
            return (-p.value, pid)
        if sort == "overall":
            # The shown OVR rating, never the model's internal trade value (that number is not shown in the UI).
            return (-(overall_by_pid.get(pid) or 0), -p.value, pid)
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
        return (-(ev.next_proj(pid, w) if ev.roles_on else ev.proj(pid, w)), -ev.ros_mean(pid), pid)

    pids.sort(key=key)
    page_size = max(1, min(PAGE_MAX, page_size))
    page = max(1, page)
    chunk = pids[(page - 1) * page_size: page * page_size]
    ranks = value_ranks(snap)
    items = []
    for pid in chunk:
        row = player_row(snap, state, ev, pid, owners)
        row["value_rank"] = ranks.get(pid)
        row["adp_edge"] = adp_edge(row["adp"], ranks.get(pid))
        items.append(row)
    blockmod.attach(items, bidx)
    return {"items": items, "total": len(pids), "page": page, "page_size": page_size}


def player_detail(snap: GameSnapshot, state: GameState, pid: str, seed: int | None = None) -> dict[str, Any]:
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
    row = player_row(snap, state, ev, pid, owners)
    if seed is not None:
        blockmod.attach([row], blockmod.block_index(snap, state, ev, seed))
    ranks = value_ranks(snap)
    same_pos = sorted((q for q in snap.pids if snap.players[q].pos == row["pos"]), key=lambda q: (-snap.players[q].value, q))
    row["value_rank"] = ranks.get(pid)
    row["pos_value_rank"] = same_pos.index(pid) + 1 if pid in same_pos else None
    out = {
        "player": row, "weeks": weeks, "history": history, "news": news,
        "ros": ros_summary(ev, pid, weeks), "projection_flat": projection_is_flat(weeks),
    }
    profile = scouting_view(snap, state, ev, pid)
    if profile is not None:
        out["scouting"] = profile
    return out


def scouting_view(snap: GameSnapshot, state: GameState, ev: Evaluator, pid: str) -> dict[str, Any] | None:
    """The generated scouting profile and development curve of a generated rookie (None for everyone else).

    Pure function of the player's record, so the same prospect reads the same at the draft, in his first season and
    years later; only the confidence (and so how much of the true curve is revealed) moves with time."""
    p = snap.players[pid]
    if "scout_seed" not in p.extra:
        return None
    games = len(state.games_played(pid)) if state.status != "offseason" else 0
    return scouting.build_profile(
        pos=p.pos, age=p.age, name=p.name, extra=p.extra, mean=ev.ros_mean(pid), draft_year=int(p.extra.get("draft_year") or 0) or None,
        years_exp=float(p.extra.get("years_exp", 0.0)), games=games,
    )


def projection_is_flat(weeks: Sequence[Mapping[str, Any]]) -> bool:
    """True when every playable (not bye, not out) week carries the same projection and band.

    The engine projects a healthy player at his rest-of-season mean every week (there is no NFL opponent
    model), so today this is always true; it is reported so clients render one rest-of-season summary instead of
    a list of identical rows, and start charting the moment the projection genuinely varies by week."""
    playable = [(w["projection"], w["floor"], w["ceiling"]) for w in weeks if not w["bye"] and not w["out"]]
    return len(set(playable)) <= 1


def ros_summary(ev: Evaluator, pid: str, weeks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Rest-of-season line: per-game mean and band, how many weeks he can still play, and the bye / out weeks."""
    floor, ceiling = ev.band(pid)
    return {
        "mean": round(ev.ros_mean(pid), 1), "floor": round(floor, 1), "ceiling": round(ceiling, 1),
        "weeks_left": len(weeks), "playable_weeks": sum(1 for w in weeks if not w["bye"] and not w["out"]),
        "bye_week": next((w["week"] for w in weeks if w["bye"]), None),
        "out_weeks": [w["week"] for w in weeks if w["out"]],
    }


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
        "season_label": season_label(state.season_no, S.start_year + state.season_no - 1 if S.start_year else None),
        "stage": (state.offseason or {}).get("stage") if state.status == "offseason" else None,
        "picks_held": len(state.picks_of(user)), "titles": sum(1 for a in state.seasons if a["champion"] and a["champion"]["is_you"]),
        "last_season": state.season_no >= S.seasons,
    }


def pending_block(snap: GameSnapshot, state: GameState, ev: Evaluator | None = None) -> dict[str, Any]:
    """The badge counts of the game header (claims, inbox, lineup warnings, roster size)."""

    ev = ev or Evaluator(snap, state)
    user = snap.user_team.tid
    user_roster = state.rosters[user]
    live = state.status in ("in_season", "playoffs")
    return {
        "claims": len(state.claims), "inbox": len(state.offers),
        "lineup_warnings": len(lineup_warnings(ev, state.lineups[user], max(state.week, 1))) if live else 0,
        "roster_size": len(user_roster), "roster_limit": snap.settings.roster_limit,
        "cuts_needed": max(0, len(user_roster) - snap.settings.roster_limit),
        "limit_blocks": not snap.settings.soft_limit,  # limit_v 0 saves: over the limit blocks Advance; newer: it only blocks adding players
    }


def game_delta(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    """The slice of ``game`` a small action can change, returned with the action's own response so the
    client updates its header without refetching the whole game."""

    return {
        "status": state.status, "week": state.week, "pending": pending_block(snap, state),
        "can_trade": trade_window(snap, state) is None,
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
        "pending": pending_block(snap, state, ev),
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
        draft["picks"] = [pick_row(snap, state, ev, owners, p) for p in state.picks if p["pid"] in snap.players]  # a later season's view omits retired players
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
    player = snap.players.get(pid)
    if player is None:
        # A past season's move can name someone the current season's view no longer
        # carries (retired, or a rookie of an earlier class): look in the other views.
        root = snap.root
        for other in (root, *getattr(root, "_views", {}).values()):
            player = other.players.get(pid)
            if player is not None:
                break
    return player.name if player is not None else "a former player"


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
        why = {"bye": " to cover a bye", "injury": " to cover an injury", "depth": " for depth"}.get(str(tx.get("why") or ""), "")
        return tx["team"], f"{team} added {name(tx['add'])}{why}{drop}"
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
            **({"via_block": True} if o.get("via_block") else {}),
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
    "draft_view", "league_view", "game_delta", "pending_block", "pick_asset", "reserve_block", "dynasty_block", "team_roster", "inbox_view", "pending_claims", "players_for", "pick_row",
    "SORTS", "PAGE_MAX", "rank_teams",
]
