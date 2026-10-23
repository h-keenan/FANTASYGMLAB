"""This week's pairing and lineups for imported (non-Sleeper) leagues.

Dashboard and Matchup are built around Sleeper's weekly ``/matchups`` payload:
``{roster_id, matchup_id, points, starters, starters_points}``. This module
produces the same shape from each platform's public API, so the existing
Matchup / Dashboard engines run unchanged:

* Fleaflicker  ``FetchLeagueScoreboard`` (pairings, scores, current week) plus
               ``FetchRoster`` for each team shown (START slots, bench, points).
* MFL          ``TYPE=liveScoring`` (current week, pairings, scores and each
               side's starters in one call).
* ESPN         nothing extra: the week, pairings and starting slots were
               already read by the one ``espn_api`` league load.

Honesty rules:

* Players map through the snapshot's ``id_map`` (the same platform-id ->
  FantasyDesk-id crosswalk the roster import used). A starter that does not
  map is left out of ``starters`` and listed under ``unmapped``; it is never
  guessed, and the platform's own team total still counts it.
* Nothing is invented: a missing score stays ``None``, MFL (which sends no slot
  names) has empty ``slot_labels``, and an unpaired team has no opponent.
* No credentials: public leagues only.

Calls are cached for 30 seconds with single flight per key, and each platform
module's own throttle spaces them (Fleaflicker 0.5s, MFL 1.1s).
"""

from __future__ import annotations

from typing import Any

from modules import espn_leagues, external_leagues, fleaflicker_leagues, mfl_leagues
from modules.external_league_common import ExternalLeagueError, SnapshotCache, safe_int, safe_text

WEEK_TTL_SECONDS = 30

_week_cache = SnapshotCache(ttl=WEEK_TTL_SECONDS)
_lineup_cache = SnapshotCache(ttl=WEEK_TTL_SECONDS)


def clear_caches() -> None:
    _week_cache.clear()
    _lineup_cache.clear()


# ---------------------------------------------------------------------------
# Week state: current week + who plays whom
# ---------------------------------------------------------------------------


def _load_fleaflicker(league_key: str) -> dict[str, Any]:
    board = fleaflicker_leagues.fetch_scoreboard(league_key)
    pairs = [
        {"a": safe_int(g["a_id"]), "b": safe_int(g["b_id"]), "a_points": g["a_points"], "b_points": g["b_points"]}
        for g in board["games"]
    ]
    return {"week": board["week"], "pairs": pairs, "platform": "fleaflicker"}


def _load_mfl(league_key: str) -> dict[str, Any]:
    live = mfl_leagues.fetch_live_scoring(league_key)
    pairs: list[dict[str, Any]] = []
    lineups: dict[int, list[dict[str, Any]]] = {}
    for first, second in live["pairs"]:
        a, b = safe_int(first["team_id"]), safe_int(second["team_id"])
        pairs.append({"a": a, "b": b, "a_points": first["points"], "b_points": second["points"]})
        lineups[a] = first["starters"]
        lineups[b] = second["starters"]
    return {"week": live["week"], "pairs": pairs, "platform": "mfl", "mfl_starters": lineups}


def _load_espn(league_key: str) -> dict[str, Any]:
    snapshot = espn_leagues.get_league_snapshot(league_key)
    if not snapshot:
        raise ExternalLeagueError("espn_unavailable", espn_leagues.ERROR_MESSAGES["espn_unavailable"])
    state = snapshot.get("week_state") or {}
    pairs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for roster_id, info in (state.get("pairings") or {}).items():
        opponent = info.get("opponent") or ""
        if roster_id in seen or (opponent and opponent in seen):
            continue
        seen.add(roster_id)
        if opponent:
            seen.add(opponent)
            other = (state.get("pairings") or {}).get(opponent) or {}
            pairs.append(
                {
                    "a": safe_int(roster_id),
                    "b": safe_int(opponent),
                    "a_points": info.get("points"),
                    "b_points": other.get("points"),
                }
            )
    return {"week": safe_int(state.get("week")), "pairs": pairs, "platform": "espn"}


_LOADERS = {"fleaflicker": _load_fleaflicker, "mfl": _load_mfl, "espn": _load_espn}


def week_state(league_key: str, *, refresh: bool = False) -> dict[str, Any] | None:
    """``{week, pairs: [{a, b, a_points, b_points}], platform}`` or None when the platform can't be read."""

    loader = _LOADERS.get(external_leagues.platform_of(league_key))
    if loader is None:
        return None
    return _week_cache.get(league_key, loader, refresh=refresh)


def current_week(league_key: str) -> int:
    state = week_state(league_key)
    return safe_int(state.get("week")) if state else 0


def opponent_of(state: dict[str, Any], roster_id: int) -> dict[str, Any] | None:
    """The pairing involving ``roster_id`` oriented so ``mine`` is this roster, or None (bye / unpaired)."""

    for pair in state.get("pairs") or []:
        if pair["a"] == roster_id:
            return {"mine": pair["a"], "theirs": pair["b"], "mine_points": pair["a_points"], "theirs_points": pair["b_points"]}
        if pair["b"] == roster_id:
            return {"mine": pair["b"], "theirs": pair["a"], "mine_points": pair["b_points"], "theirs_points": pair["a_points"]}
    return None


# ---------------------------------------------------------------------------
# Lineups
# ---------------------------------------------------------------------------


def _map_players(
    items: list[dict[str, Any]], id_map: dict[str, str], fantasy_team: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    mapped: list[dict[str, Any]] = []
    unmapped: list[dict[str, str]] = []
    for item in items:
        canonical = id_map.get(safe_text(item.get("platform_id")))
        if canonical:
            mapped.append({**item, "player_id": canonical})
        else:
            unmapped.append(
                {
                    "name": safe_text(item.get("name")),
                    "position": safe_text(item.get("position")),
                    "team": safe_text(item.get("team")),
                    "slot": safe_text(item.get("slot")),
                    "fantasy_team": fantasy_team,
                    "reason": "no_unique_match",
                }
            )
    return mapped, unmapped


def _team_name(snapshot: dict[str, Any], roster_id: int) -> str:
    for team in snapshot.get("teams") or []:
        if safe_int(team.get("roster_id")) == roster_id:
            return safe_text(team.get("team_name"))
    return ""


def _mfl_lineup_items(league_key: str, state: dict[str, Any], roster_id: int) -> list[dict[str, Any]]:
    parsed = mfl_leagues.parse_league_key(league_key)
    season = parsed[1] if parsed else 0
    items: list[dict[str, Any]] = []
    for starter in (state.get("mfl_starters") or {}).get(roster_id, []):
        info = None
        try:
            info = mfl_leagues.player_info(season, starter["platform_id"]) if season else None
        except ExternalLeagueError:
            info = None
        items.append(
            {
                "platform_id": starter["platform_id"],
                "name": (info or {}).get("name", ""),
                "position": (info or {}).get("position", ""),
                "team": (info or {}).get("team", ""),
                "slot": "",
                "points": starter.get("points"),
                "projected_points": None,
            }
        )
    return items


def lineup_for(league_key: str, roster_id: int, state: dict[str, Any]) -> dict[str, Any] | None:
    """One roster's lineup for the state's week, mapped to FantasyDesk player ids.

    ``{starters, starters_points, slot_labels, unmapped, bench, empty_slots}``;
    ``starters`` / ``starters_points`` / ``slot_labels`` are parallel and exclude
    unmapped starters. None when the lineup can't be read."""

    snapshot = external_leagues.get_league_snapshot(league_key)
    if not snapshot:
        return None
    id_map = snapshot.get("id_map") or {}
    platform = state.get("platform")
    team_name = _team_name(snapshot, roster_id)
    bench_items: list[dict[str, Any]] = []
    empty_slots: list[str] = []
    if platform == "fleaflicker":
        week = safe_int(state.get("week"))

        def _load(_: str) -> dict[str, Any]:
            return fleaflicker_leagues.fetch_lineup(league_key, str(roster_id), week)

        raw = _lineup_cache.get(f"{league_key}|{roster_id}|{week}", _load)
        if raw is None:
            return None
        starter_items = raw["starters"]
        bench_items = raw["bench"]
        empty_slots = list(raw["empty_slots"])
    elif platform == "mfl":
        starter_items = _mfl_lineup_items(league_key, state, roster_id)
        if not starter_items:
            return None
        # A starter MFL lists that is not a valued player (coach, team unit we
        # don't value) has no position: skip it rather than call it unmapped.
        starter_items = [
            item for item in starter_items if item["platform_id"] in id_map or item.get("position")
        ]
    elif platform == "espn":
        stored = (snapshot.get("lineups") or {}).get(str(roster_id))
        if stored is None:
            return None
        return {
            "starters": list(stored.get("starters") or []),
            "starters_points": [],
            "slot_labels": list(stored.get("slots") or []),
            "projected_points": {},
            "unmapped": [{**item, "fantasy_team": team_name, "reason": "no_unique_match"} for item in stored.get("unmapped") or []],
            "bench": [],
            "empty_slots": [],
        }
    else:
        return None

    mapped, unmapped = _map_players(starter_items, id_map, team_name)
    bench, _ = _map_players(bench_items, id_map, team_name)
    return {
        "starters": [item["player_id"] for item in mapped],
        "starters_points": [item.get("points") for item in mapped],
        "slot_labels": [item["slot"] for item in mapped] if all(item.get("slot") for item in mapped) else [],
        "projected_points": {item["player_id"]: item["projected_points"] for item in mapped if item.get("projected_points") is not None},
        "unmapped": unmapped,
        "bench": [item["player_id"] for item in bench],
        "empty_slots": empty_slots,
    }


def matchup_entries(
    league_key: str, roster_id: int, state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Sleeper-shaped ``(my_entry, opponent_entry)`` for this week, or None on a bye / unpaired team."""

    pairing = opponent_of(state, roster_id)
    if pairing is None or not pairing["theirs"]:
        return None
    entries: list[dict[str, Any]] = []
    for side, points in ((pairing["mine"], pairing["mine_points"]), (pairing["theirs"], pairing["theirs_points"])):
        lineup = lineup_for(league_key, side, state) or {}
        entries.append(
            {
                "roster_id": side,
                "matchup_id": min(pairing["mine"], pairing["theirs"]),
                "points": points,
                "starters": list(lineup.get("starters") or []),
                "starters_points": list(lineup.get("starters_points") or []),
                "slot_labels": list(lineup.get("slot_labels") or []),
                "projected_points": dict(lineup.get("projected_points") or {}),
                "unmapped": list(lineup.get("unmapped") or []),
                "bench": list(lineup.get("bench") or []),
                "empty_slots": list(lineup.get("empty_slots") or []),
            }
        )
    return entries[0], entries[1]
