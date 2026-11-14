"""The trade block: assets a team is shopping, and the AI's reaction to yours.

The user's block lives in the event log (``block_set``) and the state (``state.block``); the AI teams' blocks are a pure
function of (snapshot, state, week, seed), so they are never stored, change from week to week, and replay exactly. All of
it exists only in games with ``block_v >= 1``; an older save has no block and behaves exactly as before.

AI realism: a contender sells depth (bench players at a position it is already deep at) and spare picks, a rebuilder sells
aging vets, a balanced team a bench piece; each lists at most ``MAX_BLOCK_ITEMS`` assets, only some teams list in a given
week (frequency capped), and a team asks for the position it is shortest at. Offers to the user's block follow the same
rules as every other AI offer (roster legality on both sides, injury / IR valuation, one per team, three per week league-wide),
with at most ``MAX_BLOCK_OFFERS`` of the three coming from the block.
"""

from __future__ import annotations

from typing import Any, Mapping

from modules.sim.game_ai import TradeDesk, trade_window
from modules.sim.game_eval import USER_PARAMS, Evaluator, team_params
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import NON_TRADABLE, GameError, GameSnapshot
from modules.sim.rng import WorldRng
from modules.sim.types import is_pick_id

MAX_BLOCK_ITEMS = 8  # the user's block
MAX_AI_BLOCK_ITEMS = 3  # one AI team's block
MAX_BLOCK_OFFERS = 2  # of the three offers a week, at most this many answer the block
BLOCK_OFFER_BONUS = 100.0  # a deal that answers the block is the one the user asked for: it outranks the rest
AI_BLOCK_CHANCE = 1.4  # x the team's activity: not every team shops every week
MAX_AI_BLOCKS_PER_WEEK = 5  # teams shopping at once, league-wide (the shelf stays readable)
HINT_POSITIONS = ("QB", "RB", "WR", "TE")
STANCES = (("contending", 0.65), ("rebuilding", 0.35))  # horizon >= first, horizon <= second


def stance_of(horizon: float) -> str:
    return "contending" if horizon >= 0.65 else "rebuilding" if horizon <= 0.35 else "balanced"


def user_block(snap: GameSnapshot, state: GameState) -> dict[str, dict[str, Any]]:
    """The user's block, minus anything that left the team (traded, cut, spent): derived, so no extra events."""

    if not snap.settings.block:
        return {}
    user = snap.user_team.tid
    held = set(state.holdings(user)) | set(state.picks_of(user))
    return {pid: dict(v) for pid, v in state.block.items() if pid in held}


# ------------------------------------------------------------------ the user's block


def set_block(em: Emitter, asset_id: str, on: bool, looking_for: str | None = None) -> None:
    state, snap = em.state, em.snap
    if not snap.settings.block:
        raise GameError("block_unavailable", "The trade block is not part of this game.")
    user = snap.user_team.tid
    if state.status in ("drafting", "complete"):
        raise GameError("wrong_phase", "The trade block opens once the season starts.", phase=state.status)
    if looking_for is not None and looking_for not in HINT_POSITIONS:
        raise ValueError("looking_for must be QB, RB, WR or TE.")
    if on:
        if is_pick_id(asset_id):
            if not snap.settings.policy.dynasty or state.pick_owner.get(asset_id) != user:
                raise ValueError("You can only block picks you own.")
        elif asset_id not in snap.players or asset_id not in state.holdings(user):
            raise ValueError("You can only put your own players on the block.")
        elif snap.players[asset_id].pos in NON_TRADABLE:  # the block stays K/DEF-free: AI offers around it never involve them
            raise ValueError("Kickers and defenses cannot be traded.")
        if asset_id not in user_block(snap, state) and len(user_block(snap, state)) >= MAX_BLOCK_ITEMS:
            raise GameError("block_full", f"Your block holds {MAX_BLOCK_ITEMS} assets at most. Take one off first.")
    elif asset_id not in state.block:
        return  # nothing to do: no event for a no-op
    em.emit(state.week, "user", "block_set", pid=asset_id, on=bool(on), looking_for=looking_for if on else None)


# --------------------------------------------------------------------- the AI blocks


def trading(snap: GameSnapshot, state: GameState) -> bool:
    return snap.settings.block and state.status in ("in_season", "offseason") and trade_window(snap, state) is None


def _draw(snap: GameSnapshot, state: GameState, seed: int, tid: str) -> float:
    """The team's draw for this week: it shops when the draw is under its chance, and the lowest draws shop first."""

    return float(WorldRng(seed).stream(max(state.week, 1), "gblock", 1 + snap.tids.index(tid)).random())


def ai_block(desk: TradeDesk, tid: str, seed: int) -> dict[str, Any] | None:
    """What ``tid`` is shopping this week (None if it is not shopping): ``{team_id, stance, looking_for, items: [{id, why}]}``."""

    snap, state, ev = desk.snap, desk.state, desk.ev
    if not trading(snap, state) or tid == snap.user_team.tid:
        return None
    params = team_params(snap, tid)
    if params.activity <= 0 or state.trades_made[tid] >= params.max_trades:
        return None
    if _draw(snap, state, seed, tid) > AI_BLOCK_CHANCE * params.activity:
        return None
    week = max(state.week, 1)
    stance = stance_of(params.horizon)
    roster = list(state.rosters[tid])
    lineup, _ = ev.best_lineup(roster, week)
    starters = {pid for _, pid in lineup if pid}
    need_pos, ratio = desk.need_position(tid)
    short = {need_pos} if ratio < 0.95 else set()
    held = [p for p in desk.tradable(tid) if not is_pick_id(p)]
    bench = [p for p in held if p not in starters and p in roster]

    def sell_rank(p: str) -> tuple:  # what the team gives up most easily: it values him least relative to the market
        return (-(ev.worth(USER_PARAMS, p) - ev.worth(params, p)), p)

    items: list[tuple[str, str]] = []
    if stance == "rebuilding":
        vets = sorted((p for p in held if snap.players[p].age >= 28 and snap.players[p].pos not in short and state.out.get(p, 0) == 0),
                      key=lambda p: (-ev.ros_mean(p), p))
        items += [(p, "Selling a veteran") for p in vets[:2]]
    elif stance == "contending":
        deep = sorted((p for p in bench if snap.players[p].pos not in short), key=sell_rank)
        items += [(p, "Selling depth") for p in deep[:2]]
        picks = sorted(desk.tradable(tid) if snap.settings.policy.dynasty else [], key=lambda p: (not is_pick_id(p), sell_rank(p)))
        picks = [p for p in picks if is_pick_id(p)]
        if picks:
            items.append((picks[0], "Moving a pick"))
    if len(items) < 1:
        spare = sorted((p for p in bench if snap.players[p].pos not in short), key=sell_rank)
        items += [(p, "Shopping a bench piece") for p in spare[:1]]
    seen: set[str] = set()
    out = []
    for pid, why in items:
        if pid in seen or len(out) >= MAX_AI_BLOCK_ITEMS:
            continue
        seen.add(pid)
        out.append({"id": pid, "why": why})
    if not out:
        return None
    return {"team_id": tid, "stance": stance, "looking_for": need_pos if short else None, "items": out}


def league_blocks(snap: GameSnapshot, state: GameState, ev: Evaluator, seed: int) -> list[dict[str, Any]]:
    """Every AI team that is shopping this week, best-known first (by team order)."""

    if not trading(snap, state):
        return []
    desk = TradeDesk(ev, seed, max(state.week, 1))
    found = []
    for tid in snap.tids:
        b = ai_block(desk, tid, seed)
        if b is not None:
            found.append((_draw(snap, state, seed, tid), snap.tids.index(tid), b))
    found.sort(key=lambda f: (f[0], f[1]))
    return [b for _, _, b in sorted(found[:MAX_AI_BLOCKS_PER_WEEK], key=lambda f: f[1])]


def block_index(snap: GameSnapshot, state: GameState, ev: Evaluator, seed: int) -> dict[str, dict[str, Any]]:
    """asset_id -> the little record a list row shows: ``{by, mine, looking_for, why}`` (empty when the game has no block)."""

    if not snap.settings.block:
        return {}
    out: dict[str, dict[str, Any]] = {}
    user = snap.user_team.tid
    for pid, v in user_block(snap, state).items():
        out[pid] = {"by": user, "mine": True, "looking_for": v.get("looking_for"), "why": "On your block"}
    for b in league_blocks(snap, state, ev, seed):
        for it in b["items"]:
            out[it["id"]] = {"by": b["team_id"], "mine": False, "looking_for": b["looking_for"], "why": it["why"]}
    return out


def attach(rows: list[dict[str, Any]], index: Mapping[str, Mapping[str, Any]]) -> None:
    """Add ``block`` to each player row on the block (rows not on it are left alone, so a game without a block serializes as before)."""

    if not index:
        return
    for r in rows:
        hit = index.get(r.get("id"))
        if hit is not None:
            r["block"] = dict(hit)


def block_message(snap: GameSnapshot, tid: str, asked: list[str], sent: list[str], hint: str | None) -> str:
    """The offer note for a deal that answers the user's block: only claims what the deal really contains."""

    names = ", ".join(snap.players[p].name if not is_pick_id(p) else "a pick" for p in asked)
    msg = f"{snap.team(tid).name} saw {names} on your block."
    if hint and any(not is_pick_id(p) and snap.players[p].pos == hint for p in sent):
        msg += f" They can send the {hint} you are looking for."
    return msg


__all__ = ["MAX_BLOCK_ITEMS", "ai_block", "attach", "block_index", "block_message", "league_blocks", "set_block", "stance_of", "user_block"]
