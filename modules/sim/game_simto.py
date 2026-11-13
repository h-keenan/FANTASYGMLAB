"""'Sim to...': play several weeks in one request, stopping early when the user has something to decide.

It is the same Advance, repeated: every week goes through ``game_engine.advance`` on one Emitter, so the event log (and
so the replayed state and digest) is identical to pressing Advance that many times, with an optional ``lineup_set`` event
before each week when the auto-set toggle is on (exactly what the Auto-set button emits). Nothing here draws randomness
or changes state itself.

Stops are checked BEFORE each week is played (including the first, unless ``force_first``), in this order: roster over the
limit (hard), a starter who is out / on a bye / an empty slot, trade offers about to expire, the free-preview paywall.
Reaching the target, the end of the season, or the time budget also ends the run. The reason carries a ``fix`` hint
(lineup | roster | inbox | premium) so the client can offer a button to the place that resolves it.
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Sequence

from modules.sim import game_actions as act
from modules.sim.game_engine import advance, standing_rows
from modules.sim.game_eval import Evaluator
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameError, GameSnapshot

TARGETS = ("weeks", "trade_deadline", "playoffs_start", "season_end")
MAX_WEEKS = 30  # a whole season plus playoffs plus slack; a runaway guard, never reached normally
TIME_BUDGET_S = 25.0
_FIX = {"roster_over_limit": "roster", "starter_out": "lineup", "starter_bye": "lineup", "empty_slot": "lineup",
        "trade_offers": "inbox", "premium_required": "premium"}


def options_for(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    """The 'Sim to...' choices that make sense right now (an in-season or playoff game only)."""

    if state.status not in ("in_season", "playoffs"):
        return []
    S = snap.settings
    W = state.week
    out: list[dict[str, Any]] = [{"id": "weeks", "weeks": 1, "label": "Next week"}]
    left = (S.regular_weeks - W + 1) if state.status == "in_season" else 0
    if state.status == "in_season":
        if left > 4:
            out.append({"id": "weeks", "weeks": 4, "label": "4 weeks"})
        if W < S.trade_deadline_week:
            out.append({"id": "trade_deadline", "label": f"Trade deadline (week {S.trade_deadline_week})"})
        if W <= S.regular_weeks:
            out.append({"id": "playoffs_start", "label": "End of regular season"})
    out.append({"id": "season_end", "label": "Through the playoffs" if not S.dynasty else "To the offseason"})
    return out


def target_reached(snap: GameSnapshot, state: GameState, target: str, weeks: int, played: int) -> bool:
    S = snap.settings
    if state.status in ("complete", "offseason"):
        return True
    if target == "weeks":
        return played >= weeks
    if target == "trade_deadline":
        return state.week >= S.trade_deadline_week or state.status != "in_season"
    if target == "playoffs_start":
        return state.status != "in_season"
    return False  # season_end: until the season is over (status above)


def validate(snap: GameSnapshot, state: GameState, target: str, weeks: int) -> None:
    if target not in TARGETS:
        raise GameError("bad_target", "Pick one of: " + ", ".join(TARGETS) + ".")
    if target == "weeks" and not 1 <= weeks <= MAX_WEEKS:
        raise GameError("bad_weeks", f"weeks must be between 1 and {MAX_WEEKS}.")
    if state.status not in ("in_season", "playoffs"):
        raise GameError("wrong_phase", "There is no season to simulate right now.", phase=state.status)
    if target_reached(snap, state, target, weeks, 0) and target != "weeks":
        raise GameError("target_passed", "You are already there.")


def stop_reason(snap: GameSnapshot, state: GameState, ev: Evaluator, *, pro: bool, paywalled: bool) -> dict[str, Any] | None:
    """The first thing the user must decide before the current week is played, or None."""

    user = snap.user_team.tid
    W = state.week
    over = len(state.rosters[user]) - snap.settings.roster_limit
    if over > 0:
        return _reason("roster_over_limit", W, f"Cut {over} player{'s' if over != 1 else ''} before simulating.", cuts_needed=over)
    if paywalled:
        return _reason("premium_required", W, "The free preview ends here. Pro unlocks the rest of the season.")
    for w in act.lineup_warnings(ev, state.lineups[user], W):
        slot, pid = w["slot"], w["player_id"]
        if pid is None:
            return _reason("empty_slot", W, f"You have an empty {slot} slot.", slot=slot)
        p = snap.players[pid]
        who = f"{p.name} ({p.pos})"
        code = "starter_bye" if ev.status(pid, W) == "bye" else "starter_out"
        what = "is on a bye" if code == "starter_bye" else "is out"
        return _reason(code, W, f"Your {p.pos} {what}: {who}.", slot=slot, player_id=pid)
    expiring = [o for o in state.offers if int(o.get("expires_week", 0)) <= W]
    if expiring:
        n = len(expiring)
        return _reason("trade_offers", W, f"{n} trade offer{'s' if n != 1 else ''} will expire this week.", count=n)
    return None


def _reason(code: str, week: int, message: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "week": week, "message": f"Stopped at Week {week}: {message[0].lower() + message[1:]}"
            if code != "premium_required" else message, "fix": _FIX[code], **extra}


# ---------------------------------------------------------------- the summary


def _you(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return next((r for r in rows if r["is_you"]), None)


def summarize(snap: GameSnapshot, before: Sequence[Mapping[str, Any]], recaps: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A compact picture of the skipped weeks: your results, record and rank change, injuries to your players,
    waiver and trade activity, the standings now, and the champion once the season ends."""

    weeks = []
    injuries: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    trades = 0
    for r in recaps:
        yg = r.get("your_game") or {}
        weeks.append({
            "week": r["week"], "kind": r["kind"], "round": r.get("round"), "result": yg.get("result"),
            "your_pts": yg.get("your_pts"), "opp_pts": yg.get("opp_pts"), "opponent": yg.get("opponent_name"),
            "auto_filled": list(yg.get("auto_filled_slots") or []),
        })
        injuries += [{"week": r["week"], "player": i["player"], "weeks": i["weeks"]} for i in r.get("injuries", []) if i.get("is_yours")]
        claims += [{"week": r["week"], **w} for w in r.get("waivers", []) if w.get("is_you")]
        trades += len(r.get("transactions", []))
    last = recaps[-1] if recaps else None
    after = last["standings"] if last else before
    b, a = _you(before), _you(after)
    return {
        "weeks": weeks,
        "record": {"before": _rec(b), "after": _rec(a)},
        "rank": {"before": b["rank"] if b else None, "after": a["rank"] if a else None},
        "pf": round((a["pf"] - b["pf"]) if a and b else 0.0, 1),
        "injuries": injuries, "claims": claims, "ai_trades": trades,
        "standings": [dict(r) for r in after],
        "champion": last.get("champion") if last else None,
        "season_complete": bool(last and last.get("season_complete")),
    }


def _rec(row: Mapping[str, Any] | None) -> str | None:
    if row is None:
        return None
    return f"{row['wins']}-{row['losses']}" + (f"-{row['ties']}" if row["ties"] else "")


# ------------------------------------------------------------------- the run


def run(em: Emitter, snap: GameSnapshot, state: GameState, seed: int, *, target: str, weeks: int = 1, auto_set: bool = False,
        force_first: bool = False, pro: bool, paywalled_fn, budget_s: float = TIME_BUDGET_S) -> dict[str, Any]:
    """Play weeks until the target, a stop reason or the time budget. Mutates ``state`` through ``em`` like Advance does."""

    validate(snap, state, target, weeks)
    before = standing_rows(snap, state)
    start_seq = state.seq
    recaps: list[dict[str, Any]] = []
    stopped: dict[str, Any] | None = None
    deadline = time.monotonic() + budget_s
    played = 0
    while not target_reached(snap, state, target, weeks, played) and played < MAX_WEEKS:
        em.snap = snap.season_view(state.view_no)
        cur = em.snap
        if auto_set:
            act.auto_lineup(em)
        reason = stop_reason(cur, state, Evaluator(cur, state), pro=pro, paywalled=paywalled_fn(state))
        hard = reason is not None and reason["code"] in ("roster_over_limit", "premium_required")
        if reason is not None and (hard or not (force_first and played == 0)):
            stopped = reason
            break
        if time.monotonic() > deadline and played > 0:
            stopped = {"code": "time_budget", "week": state.week, "fix": None,
                       "message": f"Paused at Week {state.week} to keep things quick. Sim again to continue."}
            break
        got = advance(em, cur, state, seed)
        recaps.extend(got)
        played += len(got)
    return {
        "target": target, "weeks_played": len(recaps), "stopped": stopped, "from_seq": start_seq, "to_seq": state.seq,
        "summary": summarize(snap, before, recaps) if recaps else None,
        "recap": recaps[-1] if recaps else None,  # the last week in full (the recap screen); the rest are in the summary
    }


__all__ = ["TARGETS", "options_for", "run", "stop_reason", "summarize", "validate"]
