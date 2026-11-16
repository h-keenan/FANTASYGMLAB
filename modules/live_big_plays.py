"""Latest big play for the live Matchup card.

There is no play-by-play feed, but every starter's live stat line is polled
(modules.live_stat_lines). A "big play" is what changed in that line between
two polls: a touchdown, a 20+ yard gain, a turnover or a 2-point conversion.
Honest by construction: yardage is quoted as one play ("38-yd TD catch") only
when exactly one catch / carry / completion landed; when several things landed
between polls the event is a combined "drive" ("TD catch and 45 yds") marked
``approx``. Times are when we noticed the change, not the play clock.

State (the previous snapshot plus the recent events) lives in Redis per
league + week + matchup pair, so every worker and every viewer of the same
matchup shares one history. Redis trouble fails open to "no events".
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Mapping

from modules import redis_cache

logger = logging.getLogger(__name__)

LONG_GAIN_YARDS = 20
MAX_STORED_EVENTS = 12
MAX_RETURNED_EVENTS = 3
EVENT_RETENTION_SECONDS = 6 * 3600
# A baseline older than this could span many plays; re-baseline, do not guess.
MAX_BASELINE_AGE_SECONDS = 20 * 60
STATE_TTL_SECONDS = 12 * 3600

# Sleeper scoring_settings keys that map 1:1 onto a live stat key.
_SCORED_STATS: tuple[str, ...] = (
    "pass_yd", "pass_td", "pass_int", "pass_2pt",
    "rush_yd", "rush_td", "rush_2pt",
    "rec", "rec_yd", "rec_td", "rec_2pt",
    "fum_lost", "fgm", "xpm", "def_td", "int", "fum_rec", "sack", "safe", "blk_kick",
)


def _num(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and value == value else 0.0


def _delta(prev: Mapping[str, Any], nxt: Mapping[str, Any], key: str) -> float:
    return _num(nxt.get(key)) - _num(prev.get(key))


def score_stat_delta(
    prev: Mapping[str, Any] | None, nxt: Mapping[str, Any] | None, scoring_settings: Mapping[str, Any] | None
) -> float | None:
    """Fantasy points the stat delta is worth under the league's own scoring
    (PPR / half / standard differ only in the ``rec`` weight). None when the
    league scoring is unknown. Bonus tiers (e.g. 100-yard bonuses) are not
    modeled; callers prefer the platform's own points delta when they have it."""

    if nxt is None or not isinstance(scoring_settings, Mapping):
        return None
    total = 0.0
    for key in _SCORED_STATS:
        weight = _num(scoring_settings.get(key))
        if weight:
            total += weight * _delta(prev or {}, nxt, key)
    return round(total, 1)


def _plural(n: float, one: str, many: str) -> str:
    return one if n == 1 else f"{int(n)} {many}"


def derive_play(prev: Mapping[str, Any] | None, nxt: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The big play (if any) behind a stat-line delta, else None.

    Returns ``{"description", "approx", "kinds"}``; ``kinds`` holds the
    categories seen (td, long, turnover, two_point, defense).
    """

    if prev is None or nxt is None:
        return None

    def d(key: str) -> float:
        return _delta(prev, nxt, key)

    kinds: list[str] = []
    labels: list[str] = []

    def add(kind: str, count: float, one: str, many: str) -> None:
        if count > 0:
            kinds.append(kind)
            labels.append(_plural(count, one, many))

    add("td", d("pass_td"), "passing TD", "passing TDs")
    add("td", d("rush_td"), "rushing TD", "rushing TDs")
    add("td", d("rec_td"), "TD catch", "TD catches")
    add("defense", d("def_td"), "defensive TD", "defensive TDs")
    add("defense", d("safe"), "safety", "safeties")
    add("turnover", d("pass_int"), "interception", "interceptions")
    add("turnover", d("fum_lost"), "fumble lost", "fumbles lost")
    add("two_point", d("pass_2pt") + d("rush_2pt") + d("rec_2pt"), "2-pt conversion", "2-pt conversions")

    # A single play: exactly one catch / carry / completion landed.
    counts = {"catch": d("rec"), "run": d("rush_att"), "pass": d("pass_cmp")}
    yards_by = {"catch": d("rec_yd"), "run": d("rush_yd"), "pass": d("pass_yd")}
    td_by = {"catch": d("rec_td"), "run": d("rush_td"), "pass": d("pass_td")}
    landed = [noun for noun, count in counts.items() if count > 0]
    if len(landed) == 1 and counts[landed[0]] == 1:
        noun = landed[0]
        yards = yards_by[noun]
        if td_by[noun] == 1 and len(labels) == 1:
            lead = f"{int(round(yards))}-yd " if yards > 0 else ""
            return {"description": f"{lead}TD {noun}", "approx": False, "kinds": ["td"]}
        if not labels and yards >= LONG_GAIN_YARDS:
            return {"description": f"{int(round(yards))}-yd {noun}", "approx": False, "kinds": ["long"]}

    yards = max(d("rec_yd"), 0.0) + max(d("rush_yd"), 0.0)
    if yards <= 0 and d("pass_td") > 0:
        yards = max(d("pass_yd"), 0.0)
    if not labels and yards < LONG_GAIN_YARDS:
        return None
    pieces = list(labels)
    if yards > 0:
        pieces.append(f"{int(round(yards))} yds")
        if not labels:
            kinds.append("long")
    if len(pieces) == 1:
        # A lone turnover / 2-pt is exact; a yardage-only stretch is combined.
        return {"description": pieces[0], "approx": not labels, "kinds": sorted(set(kinds))}
    text = ", ".join(pieces[:-1]) + " and " + pieces[-1]
    return {"description": text, "approx": True, "kinds": sorted(set(kinds))}


def derive_events(
    prev_snapshot: Mapping[str, Any],
    next_snapshot: Mapping[str, Any],
    *,
    now: float,
    scoring_settings: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Big-play events between two snapshots ``{key: {..., "points", "stats"}}``.

    Points are the platform's own scoring delta when both snapshots carry it
    (source of truth), else the stat delta scored with the league's settings."""

    events: list[dict[str, Any]] = []
    for key, current in next_snapshot.items():
        before = prev_snapshot.get(key)
        if not isinstance(before, Mapping) or not isinstance(current, Mapping):
            continue
        play = derive_play(before.get("stats"), current.get("stats"))
        if play is None:
            continue
        points: float | None = None
        if current.get("points") is not None and before.get("points") is not None:
            points = round(_num(current["points"]) - _num(before["points"]), 1)
        if points is None or abs(points) < 0.05:
            points = score_stat_delta(before.get("stats"), current.get("stats"), scoring_settings)
        if points is None or abs(points) < 0.05:
            continue
        events.append(
            {
                "id": f"{key}:{round(_num(current.get('points')), 1)}:{play['description']}",
                "at": int(now * 1000),
                "player_id": current.get("player_id"),
                "name": current.get("name"),
                "position": current.get("position"),
                "team": current.get("team"),
                "roster_id": current.get("roster_id"),
                "points": points,
                "description": play["description"],
                "approx": play["approx"],
                "kinds": play["kinds"],
            }
        )
    return sorted(events, key=lambda e: -abs(e["points"]))


def snapshot_from_sides(sides: list[tuple[str, list[dict[str, Any]]]]) -> dict[str, dict[str, Any]]:
    """Snapshot of every started starter: ``[(roster_id, real_starters), ...]``."""

    out: dict[str, dict[str, Any]] = {}
    for roster_id, starters in sides:
        for starter in starters or []:
            pid = starter.get("player_id")
            stats = starter.get("stats")
            if not pid or starter.get("game_started") is not True or not isinstance(stats, dict):
                continue
            points = starter.get("actual_points")
            out[f"{roster_id}:{pid}"] = {
                "player_id": str(pid),
                "name": starter.get("name"),
                "position": starter.get("position"),
                "team": starter.get("team"),
                "roster_id": str(roster_id),
                "points": points if isinstance(points, (int, float)) else None,
                "stats": stats,
            }
    return out


def state_key(league_id: str, week: int, roster_ids: list[str]) -> str:
    return redis_cache.build_cache_key("live_big_plays", str(league_id), int(week), tuple(sorted(map(str, roster_ids))))


def ingest(
    league_id: str,
    week: int,
    sides: list[tuple[str, list[dict[str, Any]]]],
    *,
    scoring_settings: Mapping[str, Any] | None = None,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Diff this poll against the stored snapshot, persist, return recent events
    (newest first, both rosters). Fails open to ``[]``."""

    now = time.time() if now is None else now
    snapshot = snapshot_from_sides(sides)
    key = state_key(league_id, week, [rid for rid, _ in sides])
    try:
        client = redis_cache.get_redis_client()
        raw = client.get(key)
        state = json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001 - never breaks the matchup
        logger.debug("big play state unavailable", exc_info=True)
        return []
    events = [e for e in state.get("events", []) if now * 1000 - _num(e.get("at")) <= EVENT_RETENTION_SECONDS * 1000]
    baseline = state.get("snap") or {}
    if snapshot and baseline and now - _num(state.get("t")) <= MAX_BASELINE_AGE_SECONDS:
        seen = {e.get("id") for e in events}
        fresh = [
            e
            for e in derive_events(baseline, snapshot, now=now, scoring_settings=scoring_settings)
            if e["id"] not in seen
        ]
        events = sorted(fresh + events, key=lambda e: -_num(e.get("at")))[:MAX_STORED_EVENTS]
    if snapshot:
        try:
            client.set(key, json.dumps({"t": now, "snap": snapshot, "events": events}), ex=STATE_TTL_SECONDS)
        except Exception:  # noqa: BLE001
            logger.debug("big play state write failed", exc_info=True)
    return events


def present(events: list[dict[str, Any]], my_roster_id: str) -> list[dict[str, Any]]:
    """The wire shape for one viewer: newest first, side relative to them."""

    return [
        {
            "id": e["id"],
            "at": e["at"],
            "player_id": e.get("player_id"),
            "name": e.get("name"),
            "position": e.get("position"),
            "team": e.get("team"),
            "side": "mine" if str(e.get("roster_id")) == str(my_roster_id) else "opponent",
            "points": e["points"],
            "description": e["description"],
            "approx": bool(e.get("approx")),
        }
        for e in events[:MAX_RETURNED_EVENTS]
    ]
