"""League-scoped IDP values for the API: only leagues with defender slots get any.

Wires ``modules.idp_values`` (the model) to a Sleeper league payload and the
cached weekly stats. Leagues without IDP slots return ``idp: False`` and no
rows, so nothing about them changes.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Mapping

from modules import idp_scoring, idp_values, sleeper

CACHE_TTL_SECONDS = 300
_CACHE: Dict[tuple, tuple[float, Dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()

METHOD_NOTE = (
    "Model value, not a market price: projected defensive stats scored with this league's "
    "own scoring, measured against this league's IDP replacement level, on the same 0-10,000 "
    "scale as offensive values."
)


def league_idp_slots(roster_positions: Any) -> Dict[str, int]:
    slots: Dict[str, int] = {}
    for slot in roster_positions or ():
        name = str(slot or "").strip().upper()
        if name in idp_scoring.IDP_SLOT_NAMES:
            slots[name] = slots.get(name, 0) + 1
    return slots


def _weekly(stats: Mapping[str, Any], player_id: str) -> List[Mapping[str, Any]]:
    entry = stats.get(player_id)
    return list(entry.get("weekly") or []) if isinstance(entry, Mapping) else []


def build_league_idp_values(
    league: Mapping[str, Any],
    *,
    season: int | None = None,
    stats_by_season: Mapping[int, Mapping[str, Any]] | None = None,
    players: Mapping[str, Any] | None = None,
    before_week: int | None = None,
) -> Dict[str, Any]:
    """Values for every active defender in one league. ``stats_by_season`` and
    ``players`` are injectable for tests; production loads the cached stats
    (upgrading an IDP-less cache once) and Sleeper's player dump."""

    slots = league_idp_slots(league.get("roster_positions"))
    if not slots:
        return {"idp": False, "players": []}
    scoring = league.get("scoring_settings") or {}
    weights = idp_scoring.idp_scoring_weights(scoring)
    base: Dict[str, Any] = {
        "idp": True,
        "slots": slots,
        "unscored_keys": idp_scoring.unscored_idp_keys(scoring),
        "method": METHOD_NOTE,
    }
    if not weights:
        return {**base, "players": [], "reason": "no_idp_scoring"}

    selected = int(season or sleeper.default_player_stats_season())
    if stats_by_season is None:
        stats_by_season = {
            selected: sleeper.ensure_season_idp_stats(selected),
            selected - 1: sleeper.ensure_season_idp_stats(selected - 1),
            selected - 2: sleeper.get_season_player_stats(selected - 2, retain_weekly=True) or {},
        }
    cur, prior, prior2 = (stats_by_season.get(selected) or {}, stats_by_season.get(selected - 1) or {}, stats_by_season.get(selected - 2) or {})
    if not sleeper.season_stats_cache_has_idp(prior) and not sleeper.season_stats_cache_has_idp(cur):
        return {**base, "players": [], "reason": "defensive_stats_unavailable"}
    roster = players if players is not None else sleeper.get_players()

    defenders = []
    for pid, info in roster.items():
        if not isinstance(info, Mapping) or not idp_scoring.is_idp_position(info.get("position")):
            continue
        prior_rows, cur_rows = _weekly(prior, str(pid)), _weekly(cur, str(pid))
        if not prior_rows and not cur_rows:
            continue
        defenders.append(
            {
                "player_id": str(pid),
                "position": info.get("position"),
                "birth_date": info.get("birth_date"),
                "prior_rows": prior_rows,
                "prior2_rows": _weekly(prior2, str(pid)),
                "current_rows": cur_rows,
            }
        )
    teams = int(league.get("total_rosters") or 12)
    valued = idp_values.project_league_values(
        defenders, weights, slots=slots, teams=teams, season=selected, before_week=before_week
    )
    rows: List[Dict[str, Any]] = []
    below: List[str] = []
    for entry in valued:
        if entry.get("value") is None:
            continue
        info = roster.get(entry["player_id"]) or {}
        # Active defenders only: retired / released players have no team.
        if str(info.get("status") or "").lower() not in {"active", "inactive", "injured reserve", ""} or not info.get("team"):
            continue
        if int(entry["value"]) <= 0:
            # Projected, but not above this league's replacement level: reported
            # by id so clients can say "below replacement" instead of "no value".
            below.append(entry["player_id"])
            continue
        rows.append(
            {
                "player_id": entry["player_id"],
                "name": info.get("full_name") or " ".join(str(info.get(k) or "") for k in ("first_name", "last_name")).strip(),
                "position": info.get("position"),
                "family": entry["family"],
                "team": info.get("team"),
                "age": round(entry["age"], 1) if entry.get("age") is not None else info.get("age"),
                "injury_status": info.get("injury_status"),
                "value": int(entry["value"]),
                "ppg": round(float(entry["ppg"]), 2),
                "projected_points": round(float(entry["projected_points"]), 1),
                "points_over_replacement": round(float(entry["vor"]), 1),
                "confidence": entry["confidence"],
            }
        )
    rows.sort(key=lambda r: (-r["value"], r["name"]))
    for rank, row in enumerate(rows, start=1):
        row["idp_rank"] = rank
    return {**base, "players": rows, "below_replacement_ids": sorted(below)}


def cached_league_idp_values(league_id: str, league: Mapping[str, Any]) -> Dict[str, Any]:
    key = (str(league_id), sleeper.default_player_stats_season())
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    result = build_league_idp_values(league)
    with _CACHE_LOCK:
        _CACHE[key] = (now, result)
        if len(_CACHE) > 64:
            _CACHE.pop(min(_CACHE, key=lambda k: _CACHE[k][0]), None)
    return result
