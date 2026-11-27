"""Commissioner "Lineup check": every team's SET lineup vs their best lineup for
the current week, so a commissioner can spot a tanking (or just absent) team
before the games start.

Pure presentation math over rows the Matchup engine already builds
(``_real_current_lineup`` for the lineup the manager set, ``_suggested_lineup_split``
for the best one, ``_suggested_lineup_moves`` for the fixing swaps). Nothing is
invented here: points are ``matchup_win_probability.starter_expected_points``
(the same number Matchup uses), availability is the injury table's own
``ruled_out`` call, and the kickoff lock is ``modules.lineup_lock``. Signals,
not verdicts. Docs: docs/commissioner-tools.md.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules import lineup_lock, matchup_win_probability

# "Possible tanking" needs BOTH an absolute and a relative gap, so a one-slot
# coin-flip on a deep roster never flags and a thin-scoring league still can.
TANKING_MIN_GAP = 8.0
TANKING_MIN_GAP_PCT = 0.12

_IR_WORDS = {"ir", "pup", "nfi", "reserve", "injured reserve"}


def _round1(value: float) -> float:
    return round(float(value), 1)


def _is_bye(player: Mapping[str, Any]) -> bool:
    return (player.get("projection") or {}).get("status") == "bye_week"


def _is_ruled_out(player: Mapping[str, Any]) -> bool:
    from modules.rankings import is_ruled_out  # local: same import-cycle guard as the lineup engine

    return is_ruled_out(str(player.get("status") or ""), str(player.get("injury_status") or ""))


def availability_kind(player: Mapping[str, Any]) -> str | None:
    """"bye", "ir" or "out" when this starter cannot score this week, else None."""

    if _is_bye(player):
        return "bye"
    if _is_ruled_out(player):
        words = {str(player.get("status") or "").strip().lower(), str(player.get("injury_status") or "").strip().lower()}
        return "ir" if words & _IR_WORDS else "out"
    return None


def starter_points(player: Mapping[str, Any]) -> float | None:
    """Expected week points: 0 for a bye/ruled-out player (a known zero), else the Matchup model's number or None."""

    if availability_kind(player) is not None and player.get("game_started") is not True:
        return 0.0
    points = matchup_win_probability.starter_expected_points(dict(player))
    return _round1(points) if points is not None else None


_FLAG_LABEL = {"bye": "On bye", "ir": "On IR", "out": "Out"}


def _starter_row(player: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "slot": player.get("slot"),
        "player_id": player.get("player_id"),
        "name": player.get("name"),
        "position": player.get("position"),
        "team": player.get("team"),
        "points": starter_points(player),
        "availability": availability_kind(player),
        "injury_label": player.get("injury_label") or "",
        "locked": lineup_lock.is_locked(player),
    }


def _swap_row(move: Mapping[str, Any]) -> dict[str, Any]:
    def side(p: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if p is None:
            return None
        return {k: p.get(k) for k in ("player_id", "name", "position", "team", "points")}

    return {
        "slot": move.get("slot"),
        "start": side(move.get("start")),
        "over": side(move.get("over")),
        "over_reason": move.get("over_reason"),
        "gain": move.get("gain"),
    }


def build_team_row(
    *,
    roster_id: str,
    team_name: str,
    owner_name: str | None,
    avatar_url: str | None,
    real: Mapping[str, Any],
    suggested_starters: Iterable[Mapping[str, Any]],
    moves: Iterable[Mapping[str, Any]] | None,
    projection_ready: bool,
) -> dict[str, Any]:
    """One team's row. ``real`` is ``_real_current_lineup``'s dict."""

    set_players = list(real.get("real_starters") or [])
    empty_slots = [str(s) for s in (real.get("real_empty_slots") or [])]
    has_lineup = bool(real.get("has_live_data"))
    starters = [_starter_row(p) for p in set_players]
    best = list(suggested_starters)

    flags: list[dict[str, Any]] = []
    info: list[dict[str, Any]] = []
    if not has_lineup:
        flags.append({"kind": "no_lineup", "label": "No lineup set", "player": None, "slot": None})
    for row in starters:
        # A starter who got hurt after kickoff is locked: nothing to fix, so it is information
        # ("left_game"), never a flag that makes the lineup look broken.
        if row["availability"] and row["locked"]:
            info.append({"kind": "left_game", "label": "Left game (injury)", "player": row["name"], "slot": row["slot"]})
        elif row["availability"]:
            flags.append(
                {"kind": row["availability"], "label": _FLAG_LABEL[row["availability"]], "player": row["name"], "slot": row["slot"]}
            )
    for slot in empty_slots:
        flags.append({"kind": "empty", "label": "Empty slot", "player": None, "slot": slot})
    locked_count = sum(1 for r in starters if r["locked"])

    set_points = best_points = gap = gap_pct = None
    partial = False
    if projection_ready:
        set_vals = [r["points"] for r in starters]
        partial = any(v is None for v in set_vals)
        set_total = sum(v for v in set_vals if v is not None)
        best_vals = [starter_points(p) for p in best]
        best_total = sum(v for v in best_vals if v is not None)
        set_points, best_points = _round1(set_total), _round1(best_total)
        # Never below zero: a locked-in lineup can already be the best reachable one.
        gap = max(0.0, _round1(best_total - set_total))
        gap_pct = round(gap / best_total, 3) if best_total > 0 else None

    # A partial set lineup (an unmodeled starter counted as 0) would overstate the gap, so it never flags by itself.
    tanking = bool(
        gap is not None
        and not partial
        and gap >= TANKING_MIN_GAP
        and (gap_pct or 0.0) >= TANKING_MIN_GAP_PCT
    )
    return {
        "roster_id": roster_id,
        "team_name": team_name,
        "owner_name": owner_name,
        "avatar_url": avatar_url,
        "has_lineup": has_lineup,
        "starters": starters,
        "set_points": set_points,
        "best_points": best_points,
        "gap": gap,
        "gap_pct": gap_pct,
        "partial": partial,
        "possible_tanking": tanking,
        "flags": flags,
        "info": info,
        "locked_count": locked_count,
        # Moves the engine already drops when either player is locked, so these are all still doable.
        "swaps": [_swap_row(m) for m in (moves or [])],
    }


def sort_teams(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Largest gap first; teams with no gap (no projections) last, by flag count then name."""

    return sorted(
        teams,
        key=lambda t: (
            t["gap"] is None,
            -(t["gap"] or 0.0),
            -len(t["flags"]),
            str(t["team_name"]).lower(),
        ),
    )


LIMITS = [
    "Points are this week's projections (or the real score once a player's game starts). They are estimates, not certainties.",
    "The best lineup respects locks: a player whose game has started cannot be swapped, so a team that is already locked in shows what is still fixable.",
    "A big gap is a prompt to look, not a verdict. Managers miss a week, wait on a late injury report, or have not opened the app yet.",
]
