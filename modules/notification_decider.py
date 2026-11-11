"""Per-user notification decider. Pure functions, no I/O, no football compute.

The sweep (modules.push_triggers) derives *candidate* items from its
detectors; this module decides what, if anything, one user actually gets in
this run. Stages, in order, each recording a ``suppress_reason`` for every
item it drops so the decision is auditable:

1. ``stale``        - item carries ``expires_at`` that has passed (e.g. a
                      lineup-lock heads-up after kickoff).
2. ``not_on_roster``- item flagged ``requires_roster`` whose player is not on
                      the user's roster in that league (news/injury
                      relevance: never alert about someone you do not own).
3. ``league_muted`` / ``league_critical_only`` - per-league override.
4. ``digest``       - category is in digest mode and the user's digest
                      window is not open. HELD, not dropped (nothing is
                      logged as sent, so the next in-window run re-derives
                      it). Critical categories are never digested.
5. quiet hours      - user-editable window in the user's timezone. The whole
                      batch is held, except critical items when the user
                      opted into ``critical_breaks_quiet``.
6. weekly cap       - rolling-7-day cap with one slot reserved for critical
                      categories (same rule as before, now user-configurable).

Dedupe against already-sent items is done by the sweep *before* this runs (it
needs a DB read); priority ordering and batching happen in
``build_batched_message``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

from modules import notification_prefs

CRITICAL = notification_prefs.CRITICAL_CATEGORIES
# Categories that are only ever about a player on YOUR roster: dropped when
# the player is not on the user's roster in that league.
ROSTER_SCOPED_CATEGORIES = frozenset({"injury"})


@dataclass
class Decision:
    allowed: list[dict[str, Any]] = field(default_factory=list)
    suppressed: list[tuple[dict[str, Any], str]] = field(default_factory=list)
    # "" when something may be sent, else why the whole batch was held:
    # quiet_hours | digest | capped | count_unavailable | nothing_left
    held: str = ""


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def in_quiet_hours(local_hour: int, start: int, end: int) -> bool:
    """[start, end) on a 24h clock; wraps midnight when start > end."""

    if start == end:
        return False
    if start > end:
        return local_hour >= start or local_hour < end
    return start <= local_hour < end


def digest_window_open(local_hour: int, digest_hour: int) -> bool:
    return local_hour in {(digest_hour + i) % 24 for i in range(notification_prefs.DIGEST_WINDOW_HOURS)}


def cap_filter(items: list[dict[str, Any]], *, sent_this_week: int, cap: int) -> list[dict[str, Any]]:
    """One slot is reserved for critical categories: others stop at cap-1."""

    if sent_this_week >= cap:
        return []
    if sent_this_week >= cap - 1:
        return [item for item in items if item.get("category") in CRITICAL]
    return list(items)


def decide(
    candidates: list[dict[str, Any]],
    *,
    prefs: Mapping[str, Any],
    now: datetime,
    local_hour: int,
    sent_this_week_fn: Callable[[], int | None],
    default_cap: int,
    roster_ids_by_league: Mapping[str, set[str]] | None = None,
) -> Decision:
    decision = Decision()
    live: list[dict[str, Any]] = []
    overrides = prefs.get("league_overrides") or {}
    modes = prefs.get("category_modes") or {}
    for item in candidates:
        category = item.get("category")
        league_id = str(item.get("league_id") or "")
        expires = _as_utc(item.get("expires_at")) if item.get("expires_at") else None
        if expires is not None and expires <= now:
            decision.suppressed.append((item, "stale"))
            continue
        if (item.get("requires_roster") or category in ROSTER_SCOPED_CATEGORIES) and roster_ids_by_league is not None and league_id in roster_ids_by_league:
            if str(item.get("player_id") or "") not in roster_ids_by_league[league_id]:
                decision.suppressed.append((item, "not_on_roster"))
                continue
        league_mode = overrides.get(league_id, "all")
        if league_mode == "mute":
            decision.suppressed.append((item, "league_muted"))
            continue
        if league_mode == "critical" and category not in CRITICAL:
            decision.suppressed.append((item, "league_critical_only"))
            continue
        live.append(item)

    # Digest: held (not dropped) until the user's digest window opens.
    window_open = digest_window_open(local_hour, int(prefs.get("digest_hour", 8)))
    ready: list[dict[str, Any]] = []
    digest_held = 0
    for item in live:
        category = item.get("category")
        if modes.get(category) == "digest" and category not in CRITICAL and not window_open:
            digest_held += 1
            continue
        ready.append(item)
    if not ready:
        decision.held = "digest" if digest_held else "nothing_left"
        return decision

    quiet = bool(prefs.get("quiet_hours_enabled", True)) and in_quiet_hours(
        local_hour, int(prefs.get("quiet_start", 22)), int(prefs.get("quiet_end", 8))
    )
    if quiet:
        if prefs.get("critical_breaks_quiet"):
            ready = [item for item in ready if item.get("category") in CRITICAL]
        else:
            ready = []
        if not ready:
            decision.held = "quiet_hours"
            return decision

    sent = sent_this_week_fn()
    if sent is None:
        decision.held = "count_unavailable"
        return decision
    cap = int(prefs.get("weekly_cap") or default_cap)
    allowed = cap_filter(ready, sent_this_week=sent, cap=cap)
    for item in ready:
        if item not in allowed:
            decision.suppressed.append((item, "capped"))
    if not allowed:
        decision.held = "capped"
        return decision
    decision.allowed = allowed
    return decision


# --- deep links -----------------------------------------------------------
# Sleeper/ESPN expose no write API, so a notification "action" is a deep link
# to the exact screen. `url` is the canonical web path (also what a web-push
# or email channel would open); the mobile app routes from category + ids in
# the same payload (mobile/src/lib/pushRouting.ts), kept in lockstep by tests.

_CATEGORY_PATH = {
    "lineup_lock": "/matchup/{league}",
    "trade_deadline": "/trade-hub/{league}",
    "waiver_reminder": "/waivers/{league}",
    "recap": "/league-recaps/{league}",
    "weekly_roundup": "/league-recaps/{league}",
}


def deep_link_for(item: Mapping[str, Any]) -> str:
    """Web path for the screen this item's tap should land on ("" if none)."""

    category = str(item.get("category") or "")
    league = quote(str(item.get("league_id") or ""), safe="")
    if category == "trade_followup":
        return "/alerts"
    if not league:
        return ""
    if category == "weekly_roundup":
        query = {"tab": "roundup"}
        if item.get("week"):
            query["week"] = str(item["week"])
        return f"/league-recaps/{league}?{urlencode(query)}"
    template = _CATEGORY_PATH.get(category)
    if template:
        return template.format(league=league)
    player = quote(str(item.get("player_id") or ""), safe="")
    if player:
        return f"/players/{league}/{player}"
    return f"/dashboard/{league}"
