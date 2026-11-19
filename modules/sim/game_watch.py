"""Draft & Watch: the user's waivers and trades, played for them on two sliders (``watch_v`` 1+).

The user drafts, then watches. Lineups are always auto-set (auto-manage, see ``game_state.auto_manage_on``); this module adds the
two things the user would otherwise do by hand each week:

* waivers, need-based: ``hands_off`` only fills a starting slot nobody healthy can play; ``balanced`` also makes one add a week when
  it lifts the starting lineup by a clear margin; ``aggressive`` makes up to two, at a lower bar. An add drops the least useful bench
  player (never the lone K / DEF / QB) when the roster is full.
* trades: the AI managers' offers to the user are accepted only when they lift the user's starting lineup by a clear margin and
  do not cost future value: ``off`` accepts none, ``light`` at most one every four weeks, ``active`` up to one a week (four a season).

Everything goes through the same actions a person would use (``queue_claim``, ``respond_offer``), so the events, the waiver order
and the Wrapped / report-card data are the ordinary ones. Nothing here runs for a game without ``watch_v``.
"""

from __future__ import annotations

from modules.sim import game_actions as act
from modules.sim.game_ai import TradeDesk
from modules.sim.game_eval import Evaluator, team_params
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import SINGLETON_POSITIONS, GameError, GameSnapshot, slot_positions

# (lineup points a week an add must lift the lineup by, adds per week)
WAIVER_RULES = {"hands_off": (None, 0), "balanced": (4.0, 1), "aggressive": (1.5, 2)}
# (lineup points a week a trade must add, trades a week cap, weeks between trades, trades a season)
TRADE_RULES = {"off": None, "light": (4.0, 1, 4, 2), "active": (1.5, 1, 1, 4)}


def _vacancies(ev: Evaluator, roster, week: int) -> set[str]:
    return {pos for slot, pid in ev.best_lineup(roster, week)[0] if not pid for pos in slot_positions(slot)}


def manage_waivers(em: Emitter, snap: GameSnapshot, state: GameState, week: int) -> int:
    """Queue this week's claims for the user. Returns how many were queued."""

    user = snap.user_team.tid
    bar, cap = WAIVER_RULES.get(snap.settings.watch_waivers, WAIVER_RULES["balanced"])
    ev = Evaluator(snap, state)
    params = team_params(snap, user, state)
    roster = list(state.rosters[user])
    owned = state.owner_map()
    queued = 0
    claimed = {c["add"] for c in state.claims}
    starters = {pid for _, pid in ev.best_lineup(roster, week)[0] if pid}
    kept = {pos: sum(1 for p in roster if snap.players[p].pos == pos) for pos in SINGLETON_POSITIONS}
    droppable = sorted(
        (p for p in roster if p not in starters and not (snap.players[p].pos in kept and kept[snap.players[p].pos] <= 1)),
        key=lambda p: (ev.worth(params, p), p),
    )
    free = [p for p in snap.pids if p not in owned and p not in claimed and state.out.get(p, 0) == 0 and not ev.on_bye(p, week)]
    vacant = _vacancies(ev, roster, week)
    limit = snap.settings.roster_limit
    max_adds = max(cap, 1 if vacant else 0)
    while queued < max_adds:
        vacant = _vacancies(ev, roster, week)
        pool = [p for p in free if snap.players[p].pos in vacant] if vacant else free
        best = None
        for add in sorted(pool, key=lambda p: (-ev.worth(params, p), p))[:8]:
            drop = None if len(roster) < limit else (droppable[0] if droppable else None)
            if len(roster) >= limit and drop is None:
                continue
            new_roster = [p for p in roster if p != drop] + [add]
            gain = ev.lineup_total(new_roster) - ev.lineup_total(roster)
            if best is None or (-gain, add) < (-best[0], best[1]):
                best = (gain, add, drop)
        if best is None:
            break
        gain, add, drop = best
        if not vacant and (bar is None or gain < bar):
            break
        try:
            act.queue_claim(em, add, drop, None)
        except (ValueError, GameError):
            free.remove(add)
            continue
        queued += 1
        free.remove(add)
        if drop is not None:
            droppable.remove(drop)
            roster = [p for p in roster if p != drop]
        roster = roster + [add]  # plan the next add around this one
    return queued


def manage_trades(em: Emitter, snap: GameSnapshot, state: GameState, seed: int, week: int) -> int:
    """Accept at most one AI offer this week, if the slider allows it and it clears the bar. Returns 1 when a trade was made."""

    rule = TRADE_RULES.get(snap.settings.watch_trades)
    if rule is None or not state.offers or week > snap.settings.trade_deadline_week:
        return 0
    bar, _per_week, gap, season_cap = rule
    user = snap.user_team.tid
    made = [t for t in state.transactions if t.get("type") == "trade" and user in (t.get("team_a"), t.get("team_b"))]
    if state.trades_made.get(user, 0) >= season_cap:
        return 0
    last = max((int(t.get("week") or 0) for t in made), default=0)
    if last and week - last < gap:
        return 0
    ev = Evaluator(snap, state)
    params = team_params(snap, user, state)
    roster = list(state.rosters[user])
    base = ev.lineup_total(roster)
    best = None
    for offer in state.offers:
        gets, gives = list(offer["get"]), list(offer["give"])  # from the AI's side: it gets what the user gives
        if any(p not in snap.players for p in [*gets, *gives]):
            continue  # picks are not a lineup gain: a hands-off manager does not move them
        new_roster = [p for p in roster if p not in gets] + gives
        gain = ev.lineup_total(new_roster) - base
        worth = sum(ev.worth(params, p) for p in gives) - sum(ev.worth(params, p) for p in gets)
        if gain >= bar and worth >= 0 and (best is None or (-gain, offer["id"]) < (-best[0], best[1])):
            best = (gain, offer["id"])
    if best is None:
        return 0
    try:
        act.respond_offer(em, TradeDesk(ev, seed, week), best[1], "accept")
    except (ValueError, GameError):
        return 0
    return 1


def manage(em: Emitter, snap: GameSnapshot, state: GameState, seed: int, week: int) -> dict[str, int]:
    """One week of Draft & Watch management (before the week's waivers resolve)."""

    trades = manage_trades(em, snap, state, seed, week)
    waivers = manage_waivers(em, snap, state, week)
    return {"waivers": waivers, "trades": trades}


__all__ = ["manage", "manage_waivers", "manage_trades", "WAIVER_RULES", "TRADE_RULES"]
