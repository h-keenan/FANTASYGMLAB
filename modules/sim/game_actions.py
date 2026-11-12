"""The user's commands: lineup, waiver claims, cuts, trades, inbox.

Each command validates against the current state, then emits events through an
``Emitter`` (which also applies them). A command that raises emitted nothing the
caller should keep: the API persists ``em.events`` only after success.
Illegal input raises ``ValueError`` (HTTP 422); a rule violation raises
``GameError`` (HTTP 200 with a ``reason``).

Events: ``lineup_set`` {team, slots, auto}, ``waiver_claim`` {id, team, add,
drop, start_slot}, ``waiver_cancel`` {id}, ``cut`` {team, pid}, ``trade``
{team_a, team_b, give, get, key, source}, ``trade_reject`` / ``trade_counter``
{key, ...}, ``inbox_response`` {id, action}.
"""

from __future__ import annotations

from typing import Any, Sequence

from modules.sim.game_ai import (
    AI_SEASON_TRADE_CAP,
    TradeDesk,
    Verdict,
    offer_key,
    trade_window,
    validate_offer,
)
from modules.sim.game_eval import Evaluator, team_params
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameError, GameSnapshot, slot_positions


def _require_season(state: GameState) -> None:
    if state.status == "drafting":
        raise GameError("wrong_phase", "Finish the draft first.", phase="draft")
    if state.status == "complete":
        raise GameError("wrong_phase", "The season is over.", phase="complete")


# ------------------------------------------------------------------ lineup


def validate_lineup(snap: GameSnapshot, state: GameState, slots: Sequence[Sequence[Any]]) -> list[list]:
    expected = list(snap.settings.slots)
    if len(slots) != len(expected):
        raise ValueError(f"lineup must have exactly {len(expected)} slots: {', '.join(expected)}")
    roster = set(state.rosters[snap.user_team.tid])
    seen: set[str] = set()
    out: list[list] = []
    for want, row in zip(expected, slots):
        slot, pid = row[0], row[1]
        if slot != want:
            raise ValueError(f"slots must be in league order: {', '.join(expected)}")
        if pid is None or pid == "":
            out.append([slot, None])
            continue
        pid = str(pid)
        if pid not in roster:
            raise ValueError("A lineup player is not on your roster.")
        if pid in seen:
            raise ValueError("A player is in the lineup twice.")
        if snap.players[pid].pos not in slot_positions(slot):
            raise ValueError(f"{snap.players[pid].name} cannot play {slot}.")
        seen.add(pid)
        out.append([slot, pid])
    return out


def set_lineup(em: Emitter, slots: Sequence[Sequence[Any]]) -> None:
    state, snap = em.state, em.snap
    _require_season(state)
    clean = validate_lineup(snap, state, slots)
    em.emit(state.week, "user", "lineup_set", team=snap.user_team.tid, slots=clean, auto=False)


def auto_lineup(em: Emitter) -> None:
    state, snap = em.state, em.snap
    _require_season(state)
    user = snap.user_team.tid
    slots, _ = Evaluator(snap, state).best_lineup(state.rosters[user], state.week)
    em.emit(state.week, "user", "lineup_set", team=user, slots=slots, auto=True)


def lineup_warnings(ev: Evaluator, lineup: Sequence[Sequence[Any]], week: int) -> list[dict[str, Any]]:
    out = []
    for slot, pid in lineup:
        if not pid:
            out.append({"code": "empty_slot", "slot": slot, "player_id": None})
            continue
        status = ev.status(pid, week)
        if status != "healthy":
            out.append({"code": status, "slot": slot, "player_id": pid})
    return out


# ----------------------------------------------------------- claims and cuts


def queue_claim(em: Emitter, add: str, drop: str | None, start_slot: str | None) -> dict[str, Any]:
    state, snap = em.state, em.snap
    _require_season(state)
    user = snap.user_team.tid
    if add not in snap.players:
        raise ValueError("Unknown player.")
    if add in state.owner_map():
        raise ValueError("That player is not a free agent.")
    if drop is not None and drop not in state.rosters[user]:
        raise ValueError("You can only drop players on your roster.")
    if start_slot is not None and snap.players[add].pos not in slot_positions(start_slot):
        raise ValueError(f"{snap.players[add].name} cannot play {start_slot}.")
    if start_slot is not None and start_slot not in snap.settings.slots:
        raise ValueError("Unknown lineup slot.")
    if any(c["add"] == add for c in state.claims):
        raise ValueError("You already have a claim on that player.")
    if drop is not None and any(c.get("drop") == drop for c in state.claims):
        raise ValueError("That player is already being dropped by another claim.")
    cid = f"c{state.seq}"
    em.emit(state.week, "user", "waiver_claim", id=cid, team=user, add=add, drop=drop, start_slot=start_slot)
    return next(c for c in state.claims if c["id"] == cid)


def cancel_claim(em: Emitter, claim_id: str) -> None:
    state = em.state
    _require_season(state)
    if not any(c["id"] == claim_id for c in state.claims):
        raise ValueError("No such claim.")
    em.emit(state.week, "user", "waiver_cancel", id=claim_id)


def cut_player(em: Emitter, pid: str) -> None:
    state, snap = em.state, em.snap
    _require_season(state)
    user = snap.user_team.tid
    if pid not in state.rosters[user]:
        raise ValueError("You can only cut players on your roster.")
    em.emit(state.week, "user", "cut", team=user, pid=pid, reason="cut")


# ------------------------------------------------------------------ trades


def enforce_roster_cap(em: Emitter, ev: Evaluator, tid: str) -> list[str]:
    """AI teams over the limit cut their lowest-value bench players. The user is
    never cut for: they must do it themselves before advancing."""

    snap, state = em.snap, em.state
    if snap.team(tid).is_user:
        return []
    params = team_params(snap, tid)
    cut: list[str] = []
    ev = Evaluator(snap, state)
    while len(state.rosters[tid]) > snap.settings.roster_limit:
        roster = state.rosters[tid]
        best, _ = ev.best_lineup(roster, state.week)
        starters = {pid for _, pid in best if pid}
        bench = sorted((p for p in roster if p not in starters), key=lambda p: (ev.worth(params, p), p))
        if not bench:
            break
        em.emit(state.week, tid, "drop", team=tid, pid=bench[0], reason="roster_limit")
        cut.append(bench[0])
    return cut


def execute_trade(
    em: Emitter, a: str, b: str, give: Sequence[str], get: Sequence[str], *, key: str, source: str
) -> dict[str, Any]:
    state, snap = em.state, em.snap
    em.emit(state.week, "user" if snap.team(a).is_user or snap.team(b).is_user else "engine", "trade",
            team_a=a, team_b=b, give=list(give), get=list(get), key=key, source=source)
    ev = Evaluator(snap, state)
    for tid in (a, b):
        enforce_roster_cap(em, ev, tid)
    return {"team_a": a, "team_b": b, "give": list(give), "get": list(get), "source": source}


def _gate_trade(snap: GameSnapshot, state: GameState, partner: str) -> None:
    closed = trade_window(snap, state)
    if closed == "wrong_phase":
        raise GameError("wrong_phase", "Finish the draft first.", phase="draft")
    if closed:
        raise GameError(closed, "Trading is closed.")
    if state.trades_made[partner] >= AI_SEASON_TRADE_CAP:
        raise GameError("partner_trade_limit", "That team has made all the trades it will this season.")


def preview_trade(desk: TradeDesk, partner: str, give: Sequence[str], get: Sequence[str]) -> Verdict:
    """Read-only. Same function the real send uses, so the answers agree."""

    snap, state = desk.snap, desk.state
    validate_offer(snap, state, partner, give, get)
    _gate_trade(snap, state, partner)
    return desk.verdict(partner, give, get)


def send_trade(
    em: Emitter, desk: TradeDesk, partner: str, give: Sequence[str], get: Sequence[str]
) -> tuple[Verdict, dict[str, Any] | None]:
    snap, state = desk.snap, desk.state
    validate_offer(snap, state, partner, give, get)
    _gate_trade(snap, state, partner)
    key = offer_key(partner, give, get)
    if key in state.offer_keys:
        raise GameError("duplicate_offer", "You already made that offer this week.")
    verdict = desk.verdict(partner, give, get)
    user = snap.user_team.tid
    if verdict.decision == "accept":
        trade = execute_trade(em, user, partner, give, get, key=key, source="user_offer")
        return verdict, trade
    kind = "trade_counter" if verdict.decision == "counter" else "trade_reject"
    em.emit(state.week, "user", kind, key=key, team=partner, give=list(give), get=list(get),
            reason=verdict.reason_code)
    return verdict, None


# -------------------------------------------------------------------- inbox


def respond_offer(em: Emitter, desk: TradeDesk, offer_id: str, action: str) -> dict[str, Any] | None:
    state, snap = em.state, em.snap
    if action not in ("accept", "decline"):
        raise ValueError("action must be 'accept' or 'decline'.")
    offer = next((o for o in state.offers if o["id"] == offer_id), None)
    if offer is None:
        raise GameError("offer_invalid", "That offer is no longer available.")
    if action == "decline":
        em.emit(state.week, "user", "inbox_response", id=offer_id, action="decline")
        return None
    user, ai = snap.user_team.tid, offer["team"]
    closed = trade_window(snap, state)
    if closed:
        raise GameError(closed, "Trading is closed.")
    if state.trades_made[ai] >= AI_SEASON_TRADE_CAP:
        raise GameError("partner_trade_limit", "That team has made all the trades it will this season.")
    ai_gives, ai_gets = offer["give"], offer["get"]  # from the AI's side
    if not all(p in state.rosters[ai] for p in ai_gives) or not all(p in state.rosters[user] for p in ai_gets):
        raise GameError("offer_invalid", "Those players have moved, so the offer is off.")
    em.emit(state.week, "user", "inbox_response", id=offer_id, action="accept")
    return execute_trade(em, ai, user, ai_gives, ai_gets, key="", source="ai_offer")


__all__ = [
    "validate_lineup", "set_lineup", "auto_lineup", "lineup_warnings", "queue_claim", "cancel_claim",
    "cut_player", "preview_trade", "send_trade", "respond_offer", "execute_trade", "enforce_roster_cap",
]
