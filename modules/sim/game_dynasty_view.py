"""JSON views for dynasty mode: draft picks, the offseason and the dynasty summary.

Read-only over (snapshot, state). ``snap`` must be the season view for
``state.view_no`` (the API passes it that way).
"""

from __future__ import annotations

from typing import Any

from modules.sim.game_ai import trade_window
from modules.sim.game_dynasty import class_strength, dynasty_summary, rookies_available
from modules.sim.game_eval import Evaluator
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot
from modules.sim.game_view import pick_asset, player_row, reserve_block


def picks_view(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    """Every team's draft picks (with real, traded ownership) and what each is worth."""

    ev = Evaluator(snap, state)
    user = snap.user_team.tid
    teams = []
    for t in snap.teams:
        rows = [pick_asset(snap, state, ev, p) for p in sorted(state.picks_of(t.tid), key=lambda p: (p.split(":")[1], int(p.split(":")[2]), p))]
        for r in rows:
            r["own"] = r["orig_team_id"] == t.tid
        teams.append({"team_id": t.tid, "name": t.name, "is_you": t.is_user, "picks": rows,
                      "total_value": round(sum(r["value"] for r in rows), 1)})
    return {
        "enabled": snap.settings.dynasty, "draft_year": ev.draft_year_now(), "rounds": snap.settings.rookie_rounds,
        "years": snap.settings.pick_years, "you": next(t for t in teams if t["team_id"] == user)["picks"] if teams else [],
        "teams": teams,
    }


def _move(prev, cur) -> dict[str, Any]:
    return {"age_before": prev.age, "age_after": cur.age, "mean_before": round(prev.mean, 1), "mean_after": round(cur.mean, 1),
            "delta": round(cur.mean - prev.mean, 1)}


def offseason_view(snap: GameSnapshot, state: GameState, *, pos: str = "", limit: int = 40) -> dict[str, Any]:
    off = state.offseason or {}
    S = snap.settings
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    user = snap.user_team.tid
    prev = snap.root.season_view(state.season_no)
    last = state.seasons[-1] if state.seasons else None
    # Aging report on the user's roster: who rose, who fell, from last season's pool to this one.
    roster = [p for p in state.holdings(user) if p in snap.players and p in prev.players]
    movers = sorted(
        ({**player_row(snap, state, ev, p, owners), **_move(prev.players[p], snap.players[p])} for p in roster),
        key=lambda r: (-abs(r["delta"]), r["id"]),
    )
    retired = []
    for p in off.get("retired", ()):
        if p in prev.players:
            pl = prev.players[p]
            retired.append({"id": p, "name": pl.name, "pos": pl.pos, "age": pl.age, "market": pl.market, "is_yours": False})
    for r in retired:
        r["is_yours"] = off.get("retired_owner", {}).get(r["id"]) == user
    order = []
    for n, pick in enumerate(off.get("order", ())):
        _, year, rnd, orig = pick.split(":", 3)
        made = next((m for m in off.get("picks", ()) if m["pick"] == pick), None)
        holder = made["team"] if made else state.pick_owner.get(pick)
        order.append({
            "n": n + 1, "round": int(rnd), "pick": pick, "orig_team_id": orig, "orig_team_name": snap.team(orig).name,
            "team_id": holder, "team_name": snap.team(holder).name if holder else None, "is_yours": holder == user,
            "traded": holder != orig,
            "made": ({"id": made["pid"], "name": snap.players[made["pid"]].name, "pos": snap.players[made["pid"]].pos} if made else None),
        })
    idx = int(off.get("pick_index", 0))
    clock = order[idx] if off.get("stage") == "rookie_draft" and idx < len(order) else None
    avail = [p for p in rookies_available(snap, state) if not pos or snap.players[p].pos == pos.upper()]
    over = max(0, len(state.rosters[user]) - S.roster_limit)
    stage = off.get("stage")
    return {
        "stage": stage, "year": off.get("year"), "season_no": state.season_no, "seasons": S.seasons,
        "next_year": off.get("year"), "last_season": last,
        # The incoming class is simulated (names and talent generated, scaled to this league's pool).
        "rookie_class": {"generated": True, "strength": class_strength(snap.root, state.view_no)[1],
                         "size": len([1 for p in snap.players.values() if p.extra.get("draft_year") == float(off.get("year") or 0)])},
        "retired": retired, "movers": movers[:12], "your_picks_this_draft": [o for o in order if o["is_yours"]],
        "draft": {
            "round_count": S.rookie_rounds, "total": len(order), "pick_index": idx, "order": order,
            "on_clock": clock, "your_turn": bool(clock and clock["is_yours"]),
            "available": [player_row(snap, state, ev, p, owners) for p in avail[:limit]], "available_count": len(avail),
        },
        "roster": {"size": len(state.rosters[user]), "limit": S.roster_limit, "cuts_needed": over,
                   **reserve_block(snap, state, ev, user, owners, 1)},
        "can_trade": trade_window(snap, state) is None and stage != "rookie_draft",
        "next": {"review": "start_rookie_draft", "rookie_draft": "finish_draft", "cutdown": "start_season"}.get(stage or ""),
        "picks_held": len(state.picks_of(user)),
    }


def summary_view(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    return dynasty_summary(snap, state)


__all__ = ["picks_view", "offseason_view", "summary_view"]
