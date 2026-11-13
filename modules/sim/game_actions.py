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
from modules.sim.types import is_pick_id
from modules.sim.game_types import NON_TRADABLE, GameError, GameSnapshot, slot_positions


def _require_season(state: GameState, *, offseason_ok: bool = False) -> None:
    if state.status == "drafting":
        raise GameError("wrong_phase", "Finish the draft first.", phase="draft")
    if state.status == "complete":
        raise GameError("wrong_phase", "The season is over.", phase="complete")
    if state.status == "offseason" and not offseason_ok:
        raise GameError("wrong_phase", "That is not available in the offseason.", phase="offseason")


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
    _require_season(state, offseason_ok=True)
    user = snap.user_team.tid
    if state.where(user, pid) is None:
        if pid in snap.players and pid not in state.owner_map():
            return  # already released (a double tap, or a retry after a lost response): the cut is done
        raise ValueError("You can only cut players on your roster.")
    em.emit(state.week, "user", "cut", team=user, pid=pid, reason="cut")


# ------------------------------------------------------------ IR and taxi

DESTINATIONS = ("roster", "ir", "taxi")
LONG_INJURY_WEEKS = 4  # an AI manager stashes anyone out at least this long on IR


def taxi_eligible(snap: GameSnapshot, pid: str) -> bool:
    """Sleeper's usual taxi rule: a rookie, or a player whose years of NFL
    experience are below the league's ``taxi_years`` (2 = rookies and second-years)."""

    p = snap.players[pid]
    years = p.extra.get("years_exp")
    if years is None:
        return bool(p.extra.get("is_rookie")) and snap.settings.taxi_years >= 1
    return years < snap.settings.taxi_years


def check_move(snap: GameSnapshot, state: GameState, tid: str, pid: str, dst: str) -> str:
    """Validate moving ``pid`` to ``dst`` for ``tid``; returns where it is now.
    ValueError for a malformed request (422), GameError for a rule (200 + reason)."""

    S = snap.settings
    if dst not in DESTINATIONS:
        raise ValueError("dst must be one of: " + ", ".join(DESTINATIONS))
    if not S.reserves:
        raise GameError("reserves_unavailable", "This game has no IR or taxi squad.")
    src = state.where(tid, pid)
    if src is None:
        raise ValueError("That player is not on your team.")
    if src == dst:
        raise ValueError(f"That player is already on your {dst}.")
    if dst == "ir":
        if S.ir_slots <= 0 or len(state.ir[tid]) >= S.ir_slots:
            raise GameError("ir_full", "Your IR is full.")
        if src != "roster":
            raise GameError("ir_ineligible", "Only an active player can go on IR.")
        if state.out.get(pid, 0) <= 0:
            raise GameError("ir_ineligible", "Only an injured player (out) can go on IR.")
    elif dst == "taxi":
        if S.taxi_slots <= 0 or len(state.taxi[tid]) >= S.taxi_slots:
            raise GameError("taxi_full", "Your taxi squad is full.")
        if src != "roster":
            raise GameError("taxi_ineligible", "Only an active player can go on the taxi squad.")
        if not taxi_eligible(snap, pid):
            raise GameError("taxi_ineligible", "Only rookies and second-year players can go on the taxi squad.")
        if snap.players[pid].pos in NON_TRADABLE:
            raise GameError("taxi_ineligible", "Kickers and defenses cannot go on the taxi squad.")
    else:  # activate / promote
        if len(state.rosters[tid]) >= S.roster_limit:
            raise GameError("roster_full", "Open a roster spot first: cut or move a player.")
    return src


def move_player(em: Emitter, pid: str, dst: str) -> dict[str, Any]:
    """The user moves one of their players between roster, IR and taxi."""

    state, snap = em.state, em.snap
    _require_season(state, offseason_ok=True)
    user = snap.user_team.tid
    src = check_move(snap, state, user, pid, dst)
    em.emit(state.week, "user", "slot_move", team=user, pid=pid, src=src, dst=dst)
    return {"pid": pid, "src": src, "dst": dst}


def ai_manage_reserves(em: Emitter, ev: Evaluator, tid: str) -> list[dict[str, Any]]:
    """What a sensible AI manager does with IR and the taxi squad: activate
    anyone back to health when there is a spot (or make one), stash long-term
    injured players on IR, and (dynasty) hold eligible young bench players on
    the taxi squad, promoting one who would start."""

    snap, state = em.snap, em.state
    S = snap.settings
    if not S.reserves or snap.team(tid).is_user:
        return []
    moves: list[dict[str, Any]] = []
    params = team_params(snap, tid)

    def go(pid: str, dst: str) -> None:
        src = state.where(tid, pid)
        em.emit(state.week, tid, "slot_move", team=tid, pid=pid, src=src, dst=dst)
        moves.append({"team": tid, "pid": pid, "src": src, "dst": dst})

    # 1. healthy players off IR (cut the worst bench player if the roster is full)
    for pid in sorted(state.ir[tid]):
        if state.out.get(pid, 0) > 0:
            continue
        if len(state.rosters[tid]) >= S.roster_limit:
            best, _ = ev.best_lineup(state.rosters[tid], state.week)
            starters = {p for _, p in best if p}
            bench = sorted((p for p in state.rosters[tid] if p not in starters), key=lambda p: (ev.worth(params, p), p))
            if not bench or ev.worth(params, bench[0]) >= ev.worth(params, pid):
                continue
            em.emit(state.week, tid, "drop", team=tid, pid=bench[0], reason="make_room")
        go(pid, "roster")
    # 2. long-term injured onto IR
    if S.ir_slots:
        hurt = sorted(
            (p for p in state.rosters[tid] if state.out.get(p, 0) >= LONG_INJURY_WEEKS),
            key=lambda p: (-state.out.get(p, 0), p),
        )
        for pid in hurt:
            if len(state.ir[tid]) >= S.ir_slots:
                break
            go(pid, "ir")
    # 3. taxi squad (dynasty): promote anyone who would start, then fill with eligible bench youth
    if S.taxi_slots and S.dynasty:
        best, _ = ev.best_lineup([*state.rosters[tid], *state.taxi[tid]], state.week)
        starters = {p for _, p in best if p}
        for pid in sorted(state.taxi[tid]):
            if pid in starters and len(state.rosters[tid]) < S.roster_limit:
                go(pid, "roster")
        best, _ = ev.best_lineup(state.rosters[tid], state.week)
        starters = {p for _, p in best if p}
        stash = sorted(
            (p for p in state.rosters[tid] if p not in starters and snap.players[p].pos not in NON_TRADABLE and taxi_eligible(snap, p)),
            key=lambda p: (snap.players[p].age, -snap.players[p].market, p),
        )
        for pid in stash:
            if len(state.taxi[tid]) >= S.taxi_slots:
                break
            go(pid, "taxi")
    return moves


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
    if len(state.rosters[tid]) > snap.settings.roster_limit:
        ai_manage_reserves(em, ev, tid)  # IR and taxi first: they free spots without losing anyone
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
    def owns(tid: str, pid: str) -> bool:
        return state.pick_owner.get(pid) == tid if is_pick_id(pid) else state.where(tid, pid) is not None

    if not all(owns(ai, p) for p in ai_gives) or not all(owns(user, p) for p in ai_gets):
        raise GameError("offer_invalid", "Those players have moved, so the offer is off.")
    em.emit(state.week, "user", "inbox_response", id=offer_id, action="accept")
    return execute_trade(em, ai, user, ai_gives, ai_gets, key="", source="ai_offer")


__all__ = [
    "validate_lineup", "set_lineup", "auto_lineup", "lineup_warnings", "queue_claim", "cancel_claim",
    "cut_player", "preview_trade", "send_trade", "respond_offer", "execute_trade", "enforce_roster_cap",
]
