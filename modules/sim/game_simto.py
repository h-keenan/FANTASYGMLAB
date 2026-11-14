"""'Sim to...': play several weeks in one request, stopping early when the user has something to decide.

It is the same Advance, repeated: every week goes through ``game_engine.advance`` on one Emitter, so the event log (and
so the replayed state and digest) is identical to pressing Advance that many times, with an optional ``lineup_set`` event
before each week when the auto-set toggle is on (exactly what the Auto-set button emits). Nothing here draws randomness
or changes state itself.

Stops are checked BEFORE each week is played (including the first, unless ``force_first``), in this order: roster over the
limit (hard, only in saves from before the soft limit), the free-preview paywall, the trade deadline week, a starter hurt
last week, a starter who is out / on a bye / an empty slot (no fix), trade offers (new, or about to expire), a waiver claim
that cannot go through because the roster is full. Every stop except the first two is a per-run toggle (``Stops``); the
client persists the user's choices. Reaching the target, the end of the season, or the time budget also ends the run. The
reason carries a ``fix`` hint (lineup | roster | inbox | premium) so the client can offer a button to the place that resolves it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
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
        "trade_offers": "inbox", "premium_required": "premium", "trade_deadline": "inbox", "starter_injured": "lineup",
        "waiver_issue": "roster"}


@dataclass(frozen=True)
class Stops:
    """Which things stop a run (all on by default). The lineup auto-set is separate (``auto_set``)."""

    offers: bool = True  # a trade offer arrived during the run, or one is about to expire
    injuries: bool = True  # one of my starters got hurt in the week just played
    starters: bool = True  # a starter is out / on a bye / an empty slot that nothing can fix
    deadline: bool = True  # the last week trades are allowed
    roster: bool = True  # a queued waiver claim cannot go through because the roster is full

    @classmethod
    def parse(cls, raw: Mapping[str, Any] | None) -> "Stops":
        raw = dict(raw or {})
        bad = [k for k in raw if k not in cls.__dataclass_fields__]
        if bad:
            raise ValueError("Unknown stop: " + ", ".join(sorted(bad)) + ".")
        for k, v in raw.items():
            if not isinstance(v, bool):
                raise ValueError(f"stops.{k} must be true or false.")
        return cls(**raw)


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


def failing_claims(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    """Queued claims that would be turned away for a full roster, in the order they resolve (a claim that fails does not
    take a spot). Mirrors the rule in ``game_engine._resolve_waivers``."""

    S = snap.settings
    user = snap.user_team.tid
    size = len(state.rosters[user])
    bad = []
    for c in state.claims:
        if c["team"] != user:
            continue
        drop = c.get("drop")
        grows = 1 - (1 if drop and drop in state.rosters[user] else 0)
        after = size + grows
        if after > S.roster_limit and not (S.soft_limit and after <= size):
            bad.append(c)
            continue
        size = after
    return bad


def stop_reason(snap: GameSnapshot, state: GameState, ev: Evaluator, *, pro: bool, paywalled: bool, stops: Stops | None = None,
                seen_offers: frozenset[str] = frozenset(), hurt: Sequence[Mapping[str, Any]] = (), played: int = 0,
                auto_set: bool = False) -> dict[str, Any] | None:
    """The first thing the user must decide before the current week is played, or None."""

    stops = stops or Stops()
    user = snap.user_team.tid
    W = state.week
    over = len(state.rosters[user]) - snap.settings.roster_limit
    if over > 0 and not snap.settings.soft_limit:
        return _reason("roster_over_limit", W, f"Cut {over} player{'s' if over != 1 else ''} before simulating.", cuts_needed=over)
    if paywalled:
        return _reason("premium_required", W, "The free preview ends here. Pro unlocks the rest of the season.")
    if stops.deadline and played > 0 and state.status == "in_season" and W == snap.settings.trade_deadline_week:
        return _reason("trade_deadline", W, "this is the last week to trade.")
    if stops.injuries and hurt:
        h = hurt[0]
        p = snap.players[h["player"]["id"]]
        tail = " Your lineup was updated." if auto_set else ""
        return _reason("starter_injured", W, f"Your starter {p.name} ({p.pos}) was hurt, out {h['weeks']} week{'s' if h['weeks'] != 1 else ''}.{tail}",
                       player_id=h["player"]["id"], auto_set=auto_set)
    if stops.starters:
        for w in act.lineup_warnings(ev, state.lineups[user], W):
            slot, pid = w["slot"], w["player_id"]
            if pid is None:
                return _reason("empty_slot", W, f"You have an empty {slot} slot.", slot=slot)
            p = snap.players[pid]
            who = f"{p.name} ({p.pos})"
            code = "starter_bye" if ev.status(pid, W) == "bye" else "starter_out"
            what = "is on a bye" if code == "starter_bye" else "is out"
            return _reason(code, W, f"Your {p.pos} {what}: {who}.", slot=slot, player_id=pid)
    if stops.offers:
        fresh = [o for o in state.offers if o["id"] not in seen_offers]
        expiring = [o for o in state.offers if int(o.get("expires_week", 0)) <= W]
        if fresh or expiring:
            n = len(fresh) if fresh else len(expiring)
            what = "waiting" if fresh else "will expire this week"
            return _reason("trade_offers", W, f"{n} trade offer{'s' if n != 1 else ''} {what}.", count=n)
    if stops.roster:
        bad = failing_claims(snap, state)
        if bad:
            names = ", ".join(snap.players[c["add"]].name for c in bad[:2])
            over_now = max(0, len(state.rosters[user]) - snap.settings.roster_limit)
            why = f"over the limit by {over_now}" if over_now else "your roster is full"
            return _reason("waiver_issue", W, f"your claim for {names} cannot go through ({why}): add a drop or cut someone.", count=len(bad))
    return None


def _reason(code: str, week: int, message: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "week": week, "message": f"Stopped at Week {week}: {message[0].lower() + message[1:]}"
            if code != "premium_required" else message, "fix": _FIX[code], **extra}


# ---------------------------------------------------------------- the summary


def _you(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return next((r for r in rows if r["is_you"]), None)


def summarize(snap: GameSnapshot, before: Sequence[Mapping[str, Any]], recaps: Sequence[Mapping[str, Any]], *,
              lineup_changes: Sequence[Mapping[str, Any]] = (), state: GameState | None = None, auto_set: bool = False,
              fresh_offers: int = 0) -> dict[str, Any]:
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
        # What the run did for you and what is waiting (the end-of-run readout): lineup auto-sets, offers in the inbox, roster size.
        "auto_set": auto_set, "lineup_changes": [dict(c) for c in lineup_changes],
        "offers_pending": len(state.offers) if state is not None else 0, "offers_new": fresh_offers,
        "roster": ({"size": len(state.rosters[snap.user_team.tid]), "limit": snap.settings.roster_limit,
                    "over": max(0, len(state.rosters[snap.user_team.tid]) - snap.settings.roster_limit)} if state is not None else None),
    }


def _rec(row: Mapping[str, Any] | None) -> str | None:
    if row is None:
        return None
    return f"{row['wins']}-{row['losses']}" + (f"-{row['ties']}" if row["ties"] else "")


# ------------------------------------------------------------------- the run


def _lineup_changes(snap: GameSnapshot, week: int, before: Sequence[Sequence[Any]], after: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    out = []
    for (slot, was), (_, now) in zip(before, after):
        if was != now:
            out.append({"week": week, "slot": slot, "out": snap.players[was].name if was else None,
                        "in": snap.players[now].name if now else None})
    return out


def run(em: Emitter, snap: GameSnapshot, state: GameState, seed: int, *, target: str, weeks: int = 1, auto_set: bool = False,
        force_first: bool = False, pro: bool, paywalled_fn, budget_s: float = TIME_BUDGET_S, stops: Stops | None = None) -> dict[str, Any]:
    """Play weeks until the target, a stop reason or the time budget. Mutates ``state`` through ``em`` like Advance does."""

    validate(snap, state, target, weeks)
    stops = stops or Stops()
    before = standing_rows(snap, state)
    start_seq = state.seq
    user = snap.user_team.tid
    seen = frozenset(o["id"] for o in state.offers)  # offers already in the inbox when the run began are not news
    recaps: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    hurt: list[dict[str, Any]] = []
    stopped: dict[str, Any] | None = None
    deadline = time.monotonic() + budget_s
    played = 0
    while not target_reached(snap, state, target, weeks, played) and played < MAX_WEEKS:
        em.snap = snap.season_view(state.view_no)
        cur = em.snap
        if auto_set:
            was = [list(r) for r in state.lineups[user]]
            act.auto_lineup(em)
            changes += _lineup_changes(cur, state.week, was, state.lineups[user])
        reason = stop_reason(cur, state, Evaluator(cur, state), pro=pro, paywalled=paywalled_fn(state), stops=stops, seen_offers=seen,
                             hurt=hurt, played=played, auto_set=auto_set)
        hard = reason is not None and reason["code"] in ("roster_over_limit", "premium_required")
        if reason is not None and (hard or not (force_first and played == 0)):
            stopped = reason
            break
        if time.monotonic() > deadline and played > 0:
            stopped = {"code": "time_budget", "week": state.week, "fix": None,
                       "message": f"Paused at Week {state.week} to keep things quick. Sim again to continue."}
            break
        starters = {pid for _, pid in state.lineups[user] if pid}
        got = advance(em, cur, state, seed)
        recaps.extend(got)
        played += len(got)
        hurt = [i for r in got for i in r.get("injuries", []) if i.get("is_yours") and i["player"]["id"] in starters]
    fresh = sum(1 for o in state.offers if o["id"] not in seen)
    return {
        "target": target, "weeks_played": len(recaps), "stopped": stopped, "from_seq": start_seq, "to_seq": state.seq,
        "summary": (summarize(snap, before, recaps, lineup_changes=changes, state=state, auto_set=auto_set, fresh_offers=fresh)
                    if recaps else None),
        "recap": recaps[-1] if recaps else None,  # the last week in full (the recap screen); the rest are in the summary
    }


__all__ = ["TARGETS", "Stops", "failing_claims", "options_for", "run", "stop_reason", "summarize", "validate"]
