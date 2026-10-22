"""Individual-defensive-player (IDP) fantasy points from a league's own scoring.

Offense uses each league's ``scoring_settings``; this does the same for
defenders. Inputs are the per-week defensive rows retained by
``modules.sleeper`` (``WEEKLY_IDP_FIELD_MAP``); the league's scoring keys are
Sleeper's own ``idp_*`` names, so the points are a plain sum of
``stat * league_value``.

What is deliberately not scored: Sleeper threshold bonuses that need a
per-game total we do not retain as a bonus flag (``bonus_tkl_10p`` and
similar). They are reported in ``unscored_keys`` so callers can say so rather
than silently under-count.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

IDP_POSITIONS = frozenset({"DL", "LB", "DB", "DE", "DT", "CB", "S", "OLB", "ILB", "MLB", "FS", "SS", "EDGE"})
# Sleeper roster slots that hold a defender.
IDP_SLOT_NAMES = frozenset({"DL", "LB", "DB", "IDP_FLEX", "DE", "DT", "CB", "S"})
# Sleeper labels collapse to the three scoring families used by lineup slots.
IDP_SLOT_FAMILY = {
    "DL": "DL", "DE": "DL", "DT": "DL", "EDGE": "DL",
    "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB",
}

# Stat fields on a retained weekly row that a league can score.
SCORED_ROW_FIELDS = (
    "idp_tkl_solo", "idp_tkl_ast", "idp_tkl", "idp_tkl_loss", "idp_sack", "idp_qb_hit",
    "idp_int", "idp_pass_def", "idp_ff", "idp_fum_rec", "idp_def_td", "idp_safe",
    "idp_blk_kick", "idp_sack_yd", "idp_int_ret_yd", "idp_fum_ret_yd", "idp_pass_def_3p",
)
# Per-game threshold bonuses a league can award: scoring key -> (row field, minimum).
THRESHOLD_BONUSES = {
    "bonus_tkl_10p": ("idp_tkl", 10.0),
    "bonus_sack_2p": ("idp_sack", 2.0),
}
# Defensive bonus keys we cannot score from retained data (they need a return
# yardage on a single score, which the weekly row only has as a game total).
_KNOWN_UNSCORED_PREFIXES = ("bonus_tkl", "bonus_sack", "bonus_def", "bonus_idp")


def idp_slot_family(position: Any) -> str | None:
    """DL/LB/DB for any defender position label, else None."""

    return IDP_SLOT_FAMILY.get(str(position or "").strip().upper())


def is_idp_position(position: Any) -> bool:
    return str(position or "").strip().upper() in IDP_POSITIONS


def league_has_idp(roster_positions: Iterable[Any] | None) -> bool:
    """True when a league's lineup has at least one defender slot."""

    return any(str(slot or "").strip().upper() in IDP_SLOT_NAMES for slot in (roster_positions or ()))


def idp_scoring_weights(scoring_settings: Mapping[str, Any] | None) -> Dict[str, float]:
    """The league's non-zero scored defensive stats, ``{row_field: points_per_unit}``."""

    weights: Dict[str, float] = {}
    for field in SCORED_ROW_FIELDS:
        try:
            value = float((scoring_settings or {}).get(field) or 0.0)
        except (TypeError, ValueError):
            continue
        if value:
            weights[field] = value
    for key, _rule in THRESHOLD_BONUSES.items():
        try:
            value = float((scoring_settings or {}).get(key) or 0.0)
        except (TypeError, ValueError):
            continue
        if value:
            weights[key] = value
    return weights


def unscored_idp_keys(scoring_settings: Mapping[str, Any] | None) -> List[str]:
    """Defensive bonus keys the league uses that this module does not score."""

    return sorted(
        key
        for key, value in (scoring_settings or {}).items()
        if str(key).startswith(_KNOWN_UNSCORED_PREFIXES) and value and key not in THRESHOLD_BONUSES
    )


def idp_weekly_points(row: Mapping[str, Any] | None, weights: Mapping[str, float]) -> float | None:
    """Fantasy points for one retained weekly row, or None when the row has no
    defensive data (cache predates IDP retention, or an offensive player).

    A played defender whose Sleeper payload omitted every scored stat (all
    zero) still has ``defensive_snaps`` and scores 0.0; a row without any IDP
    field or defensive snaps is unknown, never 0.
    """

    if not isinstance(row, Mapping):
        return None
    has_defense = "defensive_snaps" in row or any(field in row for field in SCORED_ROW_FIELDS)
    if not has_defense:
        return None
    total = 0.0
    for field, per_unit in weights.items():
        rule = THRESHOLD_BONUSES.get(field)
        if rule is not None:
            stat = row.get(rule[0])
            if stat is not None and float(stat) >= rule[1]:
                total += float(per_unit)
            continue
        value = row.get(field)
        if value is not None:
            total += float(value) * float(per_unit)
    return total


def idp_season_points(
    weekly: Iterable[Mapping[str, Any]] | None,
    weights: Mapping[str, float],
    *,
    through_week: int | None = None,
) -> Dict[str, Any]:
    """Games, points and PPG over weekly rows, optionally cut off at a week
    (inclusive) so callers can stay point-in-time."""

    games = 0
    points = 0.0
    for row in weekly or ():
        if not isinstance(row, Mapping):
            continue
        if through_week is not None and int(row.get("week") or 0) > int(through_week):
            continue
        pts = idp_weekly_points(row, weights)
        if pts is None:
            continue
        games += 1
        points += pts
    return {"games": games, "points": points, "ppg": (points / games) if games else None}
