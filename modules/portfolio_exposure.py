"""Cross-league player exposure for Portfolio ("which players do I own where?").

Built from the same cached building blocks ``dashboard_engine.build_league_summary``
(Portfolio's per-league row) reads: the cached Sleeper league/rosters wrappers and
``league_value_settings.build_valued_players_frame_cached``. No new Sleeper calls
beyond what Portfolio already makes, and no new valuation math: a player's value
is his score in each league's own valuation (lens score field), summed across the
leagues that own him.

Session-independent, like ``build_league_summary``: callers pass the Sleeper
username and players DB path; Supabase and entitlement checks live in the API layer.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules import dashboard_engine, league_value_settings, sleeper

TOP_CONCENTRATION_N = 5


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def build_league_ownership(
    *, league_id: str, league_name: str, lens: str, sleeper_username: str, players_db_path: str
) -> dict[str, Any]:
    """One league's owned players with values, or ``{"ok": False, "reason": ...}``.

    Mirrors ``build_league_summary``'s everyday skip states (never raises for them).
    """

    if not _text(sleeper_username):
        return {"ok": False, "reason": "no_sleeper_username_linked"}
    user_id = dashboard_engine._resolve_sleeper_user_id_for_league_summary(sleeper_username)
    if not user_id:
        return {"ok": False, "reason": "sleeper_user_not_found"}
    league = dashboard_engine._get_league_for_league_summary(league_id)
    if not league:
        return {"ok": False, "reason": "league_not_found"}
    if _text(league.get("season")) != _text(sleeper.default_player_stats_season()):
        return {"ok": False, "reason": "league_season_ended"}
    rosters = dashboard_engine._get_rosters_for_league_summary(league_id)
    mine = next((r for r in rosters if _text(r.get("owner_id")) == user_id), None)
    if mine is None:
        return {"ok": False, "reason": "not_a_member_of_league"}
    owned = {_text(pid) for pid in (mine.get("players") or []) if _text(pid)}
    if not owned:
        return {"ok": False, "reason": "empty_roster"}
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if valued.empty:
        return {"ok": False, "reason": "no_player_data"}
    score_field = league_value_settings.valuation_score_field(lens)
    frame = valued[valued["player_id"].astype(str).isin(owned)]
    players = []
    for _, row in frame.iterrows():
        players.append(
            {
                "player_id": _text(row.get("player_id")),
                "name": _text(row.get("name")),
                "position": _text(row.get("position")),
                "team": _text(row.get("team")),
                "value": _number(row.get(score_field)),
            }
        )
    return {"ok": True, "league_id": league_id, "league_name": league_name, "players": players}


def aggregate_exposure(per_league: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Fold per-league ownership into per-player exposure plus totals.

    ``per_league`` items are the ``ok`` results of :func:`build_league_ownership`.
    Players are sorted by exposure (leagues owned), then total value.
    """

    results = [r for r in per_league if r.get("ok")]
    league_count = len(results)
    by_player: dict[str, dict[str, Any]] = {}
    for result in results:
        for player in result.get("players") or []:
            pid = player["player_id"]
            entry = by_player.setdefault(
                pid,
                {
                    "player_id": pid,
                    "name": player["name"],
                    "position": player["position"],
                    "team": player["team"],
                    "leagues": [],
                    "total_value": 0.0,
                },
            )
            entry["leagues"].append(
                {
                    "league_id": result["league_id"],
                    "league_name": result["league_name"],
                    "value": round(player["value"], 1),
                }
            )
            entry["total_value"] += player["value"]

    total_value = sum(e["total_value"] for e in by_player.values())
    players = []
    for entry in by_player.values():
        count = len(entry["leagues"])
        players.append(
            {
                "player_id": entry["player_id"],
                "name": entry["name"],
                "position": entry["position"],
                "team": entry["team"],
                "leagues_owned": count,
                "league_names": sorted(item["league_name"] for item in entry["leagues"]),
                "leagues": sorted(entry["leagues"], key=lambda item: item["league_name"]),
                "share_of_leagues": round(count / league_count, 4) if league_count else 0.0,
                "value": round(entry["total_value"], 1),
                "share_of_value": round(entry["total_value"] / total_value, 4) if total_value else 0.0,
            }
        )
    players.sort(key=lambda p: (-p["leagues_owned"], -p["value"], p["name"]))

    position_value: dict[str, float] = {}
    position_count: dict[str, int] = {}
    for p in players:
        key = p["position"] or "Other"
        position_value[key] = position_value.get(key, 0.0) + p["value"]
        position_count[key] = position_count.get(key, 0) + p["leagues_owned"]
    by_position = [
        {
            "position": pos,
            "value": round(val, 1),
            "share_of_value": round(val / total_value, 4) if total_value else 0.0,
            "roster_spots": position_count[pos],
        }
        for pos, val in sorted(position_value.items(), key=lambda kv: -kv[1])
    ]
    top = sorted(players, key=lambda p: -p["value"])[:TOP_CONCENTRATION_N]
    top_value = sum(p["value"] for p in top)
    return {
        "league_count": league_count,
        "player_count": len(players),
        "total_value": round(total_value, 1),
        "players": players,
        "by_position": by_position,
        "concentration": {
            "top_n": TOP_CONCENTRATION_N,
            "top_share_of_value": round(top_value / total_value, 4) if total_value else 0.0,
            "top_players": [{"player_id": p["player_id"], "name": p["name"], "value": p["value"]} for p in top],
        },
    }
