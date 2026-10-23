"""Dashboard "This week" strip: the three moves for the week, in plain English.

Pure functions over data the Dashboard endpoint has already computed (the
roster's Sleeper `starters`, the roster frame, the composed briefing items and
the cached Trade Hub idea list). No I/O and no new engine calls, so it adds
nothing to the Dashboard cold-load path. FantasyDesk cannot change a Sleeper
lineup, so the lineup row only ever points at Matchup.

Rows (any of them is omitted when there is no real data for it):
  lineup  - "set" or the specific starter problem (empty slot, ruled out, bye)
  waiver  - the existing Top Waiver Opportunity, only when the engine made one
  trade   - the existing Top Trade Opportunity, or an explicit "hold" derived
            only from the engine returning no idea (or the deadline passing)

Outside the season there is one next action instead of three rows.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules import league_calendar
from modules.rankings import is_ruled_out

_WHY_MAX = 140
_POSTURE_PHRASE = {
    "rebuilding": "rebuilding",
    "competing": "competing",
    "balanced": "balanced",
}


def _clip(text: Any, limit: int = _WHY_MAX) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,;:.") + "…"


def _row(
    key: str,
    status: str,
    tone: str,
    headline: str,
    why: str,
    cta_label: str | None = None,
    route: str | None = None,
    player_id: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "status": status,
        "tone": tone,
        "headline": headline,
        "why": why,
        "cta_label": cta_label,
        "route": route,
        "player_id": player_id,
    }


def _next_action(label: str, why: str, route: str, headline: str) -> dict[str, Any]:
    return {
        "mode": "next_action",
        "week": None,
        "rows": [],
        "next_action": {"headline": headline, "why": why, "cta_label": label, "route": route},
    }


def offseason_this_week(league: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """One clear next action for a league that is not in season."""

    status = str((league or {}).get("status") or "").strip().lower()
    if status == "pre_draft":
        return _next_action(
            "Prep your draft",
            "Your league's draft hasn't started. Your pick values and rookie ranks are ready.",
            "draft_center",
            "Get ready for your draft",
        )
    if status == "drafting":
        return _next_action(
            "Open the live draft",
            "Your draft is in progress. Roster moves wait until it finishes.",
            "live_draft",
            "Your draft is live",
        )
    if league_calendar.is_in_season(league):
        return None
    return _next_action(
        "Find trade targets",
        "There is no lineup to set until the season starts. Trades are open now, so this is when to build.",
        "trade_hub",
        "Plan your offseason",
    )


def not_ready_this_week(reason: str) -> dict[str, Any] | None:
    """The single next action when the Dashboard can't build a roster view."""

    if reason in {
        "no_sleeper_username_linked",
        "sleeper_user_not_found",
        "not_a_member_of_league",
        "espn_team_not_selected",
    }:
        return _next_action(
            "Connect a league",
            "Link your Sleeper account so we can read your roster and build your week.",
            "connect_league",
            "Connect a league to get started",
        )
    if reason == "empty_roster":
        return _next_action(
            "Open the draft center",
            "Your roster has no players yet, which is normal while a draft is still running.",
            "draft_center",
            "Your roster fills after the draft",
        )
    return None


def _starter_ids(roster: Mapping[str, Any] | None) -> list[str] | None:
    starters = (roster or {}).get("starters")
    if not isinstance(starters, (list, tuple)) or not starters:
        return None
    return [str(pid) if pid not in (None, "") else "0" for pid in starters]


def _healthy(row: Mapping[str, Any]) -> bool:
    return not is_ruled_out(str(row.get("status") or ""), str(row.get("injury_status") or ""))


def _lineup_row(
    league: Mapping[str, Any],
    roster: Mapping[str, Any] | None,
    roster_rows: Mapping[str, Mapping[str, Any]],
    bye_player_ids: Iterable[str],
    week: int | None,
) -> dict[str, Any] | None:
    if league_calendar.is_best_ball(league):
        return _row(
            "lineup",
            "Set",
            "positive",
            "Best ball: Sleeper sets your lineup",
            "Your league picks the highest scorers each week, so there is nothing to start or sit.",
        )
    starters = _starter_ids(roster)
    if starters is None:
        return None
    byes = {str(pid) for pid in bye_player_ids}
    starter_set = {pid for pid in starters if pid != "0"}
    empty_slots = sum(1 for pid in starters if pid == "0")
    problems: list[tuple[str, str, str, str]] = []  # (player_id, name, position, reason)
    for pid in starters:
        row = roster_rows.get(pid)
        if pid == "0" or row is None:
            continue
        name = str(row.get("name") or "A starter")
        position = str(row.get("position") or "")
        if not _healthy(row):
            problems.append((pid, name, position, "is out"))
        elif pid in byes:
            problems.append((pid, name, position, "is on a bye"))

    if not problems and not empty_slots:
        suffix = f" in Week {week}" if week else " this week"
        return _row(
            "lineup",
            "Set",
            "positive",
            "Your lineup looks set",
            f"None of your {len(starter_set)} starters is out or on a bye{suffix}.",
            "Review lineup",
            "matchup",
        )

    if problems:
        pid, name, position, reason = problems[0]
        more = len(problems) - 1 + (1 if empty_slots else 0)
        headline = f"Check Matchup: {name} {reason}"
        if more > 0:
            headline += f" (+{more} more)"
        # Need: is there a healthy, non-bye bench player at that position?
        bench_fill = [
            r
            for other, r in roster_rows.items()
            if other not in starter_set
            and str(r.get("position") or "") == position
            and _healthy(r)
            and other not in byes
        ]
        if bench_fill:
            why = f"A starter who can't play scores zero. You have a healthy {position} on your bench who can step in."
        else:
            why = f"A starter who can't play scores zero, and you have no healthy {position} on your bench. Check waivers too."
        return _row("lineup", "Check", "risk", headline, why, "Review lineup", "matchup", player_id=pid)

    plural = "" if empty_slots == 1 else "s"
    return _row(
        "lineup",
        "Check",
        "risk",
        f"Check Matchup: {empty_slots} empty starting slot{plural}",
        "An empty slot scores zero. Fill it before your players kick off.",
        "Review lineup",
        "matchup",
    )


def _waiver_row(items: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    for item in items:
        if item.get("destination") != "waivers":
            continue
        name = str(item.get("route_player_name") or item.get("headline") or "").strip()
        why = _clip(item.get("reason") or item.get("supporting_context"))
        if not name or not why:
            return None
        return _row(
            "waiver",
            "Add",
            "waiver",
            f"Top add: {name}",
            why,
            "Claim a waiver",
            "waivers",
            player_id=str(item.get("route_player_id") or ""),
        )
    return None


def _is_trade_item(item: Mapping[str, Any]) -> bool:
    presentation = item.get("presentation")
    return isinstance(presentation, Mapping) and "trade_package" in presentation


def _trade_row(
    items: Iterable[Mapping[str, Any]],
    trade_records: list[Any] | None,
    deadline_passed: bool,
    stance: str,
) -> dict[str, Any] | None:
    if deadline_passed:
        return _row(
            "trade",
            "Hold",
            "neutral",
            "Hold: the trade deadline has passed",
            "Trades reopen after the season, so your roster is what you play with.",
        )
    for item in items:
        if not _is_trade_item(item):
            continue
        why = _clip(item.get("reason") or item.get("supporting_context"))
        headline = str(item.get("headline") or "").strip()
        if not headline or not why:
            return None
        return _row(
            "trade",
            "Idea",
            "trade",
            headline,
            why,
            "See the trade",
            "trade_hub",
            player_id=str(item.get("route_player_id") or ""),
        )
    # "Hold" only when the engine really searched and returned nothing.
    if trade_records is not None and len(trade_records) == 0:
        posture = _POSTURE_PHRASE.get(str(stance or "").strip().lower())
        tail = f" Staying put fits a {posture} team." if posture else ""
        return _row(
            "trade",
            "Hold",
            "neutral",
            "Hold: no trade improves your team",
            f"No offer in your league clears the value bar right now.{tail}",
        )
    return None


def build_this_week(
    *,
    league: Mapping[str, Any] | None,
    roster: Mapping[str, Any] | None,
    roster_rows: Mapping[str, Mapping[str, Any]],
    bye_player_ids: Iterable[str],
    items: Iterable[Mapping[str, Any]],
    trade_records: list[Any] | None,
    stance: str = "",
) -> dict[str, Any] | None:
    """The "This week" payload, or None when there is nothing real to show."""

    if not league_calendar.is_in_season(league):
        return offseason_this_week(league)
    league = league or {}
    week = league_calendar.current_league_week(league)
    item_list = list(items)
    rows = [
        _lineup_row(league, roster, roster_rows, bye_player_ids, week),
        _waiver_row(item_list),
        _trade_row(item_list, trade_records, league_calendar.trade_deadline_passed(league), stance),
    ]
    rows = [row for row in rows if row]
    if not rows:
        return None
    return {"mode": "in_season", "week": week, "rows": rows, "next_action": None}
