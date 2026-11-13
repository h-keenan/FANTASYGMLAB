"""The Fantasy Sim notification center: items derived from the event log (replay-safe, no engine state of its own).

Pure (no I/O): ``derive`` takes the frozen snapshot view, the folded state and the recent events and returns the
newest-first list the bell shows. Event-derived items (offers, expiries, claims, injuries, recaps, the title) have the
event's ``seq`` and never change. A few items describe the CURRENT state (lineup issues, the trade deadline, the draft
clock): they take a stable synthetic ``seq`` (the week boundary, or the latest event while drafting) so marking all read
keeps them read until the week moves on. The read cursor lives on the client; ``since`` is that cursor and ``unread``
counts items with a larger seq.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules.sim.game_actions import lineup_warnings
from modules.sim.game_eval import Evaluator
from modules.sim.game_state import GameState
from modules.sim.game_types import GameSnapshot
from modules.sim.types import is_pick_id

MAX_ITEMS = 40
EVENT_WINDOW = 400  # how many recent events are read per request


def _asset(snap: GameSnapshot, pid: str) -> str:
    if is_pick_id(pid):
        _, season, rnd, _orig = pid.split(":", 3)
        return f"{season} round {rnd} pick"
    p = snap.players.get(pid)
    return p.name if p else "a player"


def _names(snap: GameSnapshot, pids: Sequence[str]) -> str:
    shown = [_asset(snap, p) for p in pids[:2]]
    extra = len(pids) - 2
    return ", ".join(shown) + (f" +{extra}" if extra > 0 else "")


def _team(snap: GameSnapshot, tid: str) -> str:
    try:
        return snap.team(tid).name
    except KeyError:
        return "A team"


def _item(seq: int, n: int, week: int, kind: str, icon: str, headline: str, screen: str, **target: Any) -> dict[str, Any]:
    return {"id": f"{kind}:{seq}:{n}", "seq": seq, "week": week, "kind": kind, "icon": icon, "headline": headline,
            "target": {"screen": screen, **target}}


def derive(
    snap: GameSnapshot, state: GameState, events: Sequence[Mapping[str, Any]], since: int = 0, limit: int = MAX_ITEMS
) -> dict[str, Any]:
    user = snap.user_team.tid
    items: list[dict[str, Any]] = []
    offers: dict[str, dict[str, Any]] = {}
    responded: dict[str, str] = {}
    boundaries: list[tuple[int, int]] = []  # (seq, week) of each week_advanced
    for ev in events:
        seq, week, typ, p = int(ev["seq"]), int(ev["week"]), ev["type"], ev["payload"]
        if typ == "inbox_offer":
            offers[p["id"]] = {"seq": seq, "week": week, "team": p["team"], "expires": int(p.get("expires_week", week)), "p": p}
            items.append(_item(seq, 0, week, "offer", "trade", f"{_team(snap, p['team'])} wants {_names(snap, p.get('get', []))}", "trades", offer_id=p["id"]))
        elif typ == "inbox_response":
            responded[p["id"]] = str(p.get("action", ""))
        elif typ == "trade" and p.get("source") != "ai_ai" and user in (p.get("team_a"), p.get("team_b")):
            other = p["team_b"] if p["team_a"] == user else p["team_a"]
            items.append(_item(seq, 0, week, "trade", "trade", f"Trade done with {_team(snap, other)}", "team"))
        elif typ == "waiver_result" and p.get("team") == user:
            name = _asset(snap, p["add"])
            if p.get("ok"):
                items.append(_item(seq, 0, week, "claim_won", "waiver", f"Claim won: {name}", "team", player_id=p["add"]))
            else:
                why = str(p.get("reason") or "").replace("_", " ")
                items.append(_item(seq, 0, week, "claim_lost", "waiver", f"Claim lost: {name}" + (f" ({why})" if why else ""), "players", player_id=p["add"]))
        elif typ == "injury":
            for n, (pid, weeks) in enumerate(p.get("items", ())):
                if state.where(user, pid) is not None:
                    items.append(_item(seq, n, week, "injury", "injury", f"{_asset(snap, pid)} is out {int(weeks)} week{'' if int(weeks) == 1 else 's'}", "team", player_id=pid))
        elif typ == "week_advanced":
            boundaries.append((seq, week))
            items.append(_item(seq, 0, week, "recap", "matchup", f"Week {week} recap is ready", "home"))
        elif typ == "season_complete" and p.get("champion"):
            items.append(_item(seq, 1, week, "title", "check", f"Season over: {_team(snap, p['champion'])} won it all", "league"))
    # Offers that left the inbox without an answer expired at the first boundary after their week.
    live_ids = {o["id"] for o in state.offers}
    for oid, info in offers.items():
        if oid in live_ids or oid in responded:
            continue
        after = next(((s, w) for s, w in boundaries if s > info["seq"] and w >= info["expires"]), None)
        if after:
            items.append(_item(after[0], 2, after[1], "offer_expired", "trade", f"Offer from {_team(snap, info['team'])} expired", "trades"))

    week = state.week
    boundary = int(getattr(state, "boundary_seq", 0) or 0)
    if state.status in ("in_season", "playoffs"):
        warnings = lineup_warnings(Evaluator(snap, state), state.lineups[user], max(1, week))
        if warnings:
            n = len(warnings)
            items.append(_item(boundary, 3, week, "lineup", "alert", f"{n} lineup issue{'' if n == 1 else 's'}: a bye, injured or empty starter", "team"))
        deadline = snap.settings.trade_deadline_week
        if state.status == "in_season" and 0 <= deadline - week <= 1:
            left = deadline - week
            items.append(_item(boundary, 4, week, "deadline", "bye", "Last week to trade" if left == 0 else "Trade deadline is next week", "trades"))
    elif state.status == "drafting":
        from modules.sim.game_draft import DraftContext  # lazy: keeps the module import graph small

        if DraftContext(snap, state).on_clock() == user:
            items.append(_item(int(state.seq), 5, 0, "draft", "alert", "You are on the clock in the draft", "draft"))

    items.sort(key=lambda i: (-i["seq"], i["id"]))
    items = items[:limit]
    return {"items": items, "unread": sum(1 for i in items if i["seq"] > since), "seq": int(state.seq)}


__all__ = ["derive", "MAX_ITEMS", "EVENT_WINDOW"]
