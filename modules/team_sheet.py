"""Pure shaping for the Desk team sheet (GET /v1/leagues/{id}/teams/{roster_id}/sheet).

Composition only: every number comes from a model that already exists (the
team-rankings row, the opponent profile's need model, the valued player frame,
Sleeper rosters across the season chain). Nothing here scores, ranks or
classifies; it labels and orders what those produce so the sheet and the Fantasy
Sim team sheet read the same way.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import pandas as pd

from modules import injury_status
from modules.coerce import float_nan_to_none

POSITION_ORDER = ("QB", "RB", "WR", "TE", "K", "DEF")
_HEALTHY = {"", "active", "none", "nan", "healthy"}
_SKIP_IDS = {"", "0", "None", "nan"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def streak_label(current_streak: Any) -> str:
    """+12 -> "W12", -3 -> "L3", 0/unknown -> ""."""

    try:
        n = int(current_streak or 0)
    except (TypeError, ValueError):
        return ""
    if n > 0:
        return f"W{n}"
    if n < 0:
        return f"L{abs(n)}"
    return ""


def playoff_flag(status: Any) -> str:
    """Standings label ("In"/"Out"/...) to the lowercase key the sheet chip reads."""

    key = _text(status).lower()
    return key if key in {"in", "out", "clinched", "bye", "eliminated"} else ""


def room_level(tag: Any) -> str:
    """The need model's tag -> the sheet's level. The league rank only labels the
    card; it never decides strength or need (modules.opponent_profile.room_reads)."""

    return {"need": "need", "surplus": "strength"}.get(_text(tag), "solid")


def position_cards(
    rooms: Sequence[Mapping[str, Any]], depth: Mapping[str, int]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    cards: list[dict[str, Any]] = []
    strengths: list[str] = []
    needs: list[str] = []
    for room in rooms:
        pos = _text(room.get("position"))
        level = room_level(room.get("tag"))
        if level == "strength":
            strengths.append(pos)
        elif level == "need":
            needs.append(pos)
        cards.append(
            {
                "pos": pos,
                "level": level,
                "rank": int(room.get("rank") or 0),
                "teams": int(room.get("of") or 0),
                "depth": int(depth.get(pos, 0)),
            }
        )
    return cards, strengths, needs


def roster_rows(valued: pd.DataFrame, roster: Mapping[str, Any], score_field: str) -> list[dict[str, Any]]:
    """Every player on the roster (best value first within position)."""

    ids = [str(p) for p in (roster.get("players") or []) if str(p) not in _SKIP_IDS]
    if valued is None or valued.empty or not ids:
        return []
    starters = {str(p) for p in (roster.get("starters") or []) if str(p) not in _SKIP_IDS}
    reserve = {str(p) for p in (roster.get("reserve") or [])}
    taxi = {str(p) for p in (roster.get("taxi") or [])}
    frame = valued[valued["player_id"].astype(str).isin(set(ids))]
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        pid = str(row.get("player_id"))
        injury = _text(row.get("injury_status"))
        roster_status = _text(row.get("status"))
        if injury.lower() in _HEALTHY and injury_status.is_unavailable(roster_status, injury):
            injury = roster_status  # Sleeper can record "Injured Reserve" on the roster status with a blank injury designation
        value = float_nan_to_none(row.get(score_field))
        age = float_nan_to_none(row.get("age"))
        rows.append(
            {
                "player_id": pid,
                "name": _text(row.get("name")) or "Player",
                "position": _text(row.get("position")),
                "team": _text(row.get("team")),
                "age": None if age is None else int(age),
                "injury_status": injury if injury.lower() not in _HEALTHY else "",
                "value": None if value is None else round(value, 1),
                "slot": "ir" if pid in reserve else "taxi" if pid in taxi else "starter" if pid in starters else "bench",
            }
        )

    def _key(r: dict[str, Any]) -> tuple[int, float]:
        pos = r["position"]
        return (POSITION_ORDER.index(pos) if pos in POSITION_ORDER else len(POSITION_ORDER), -(r["value"] or 0.0))

    rows.sort(key=_key)
    return rows


def depth_by_position(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        if r.get("slot") in {"ir", "taxi"}:
            continue
        out[r["position"]] = out.get(r["position"], 0) + 1
    return out


def injuries(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Rostered players with a real Sleeper injury designation."""

    return [dict(r) for r in rows if r.get("injury_status")]


def season_result(
    season_rosters: Sequence[Mapping[str, Any]], owner_id: str, season: str, league_id: str
) -> dict[str, Any] | None:
    """One past season for the owner's roster: record, points for, finish.

    Finish is the regular-season standings place (wins, then points for), the
    same order the standings board uses. None when the owner had no roster then.
    """

    def _s(r: Mapping[str, Any]) -> Mapping[str, Any]:
        return r.get("settings") if isinstance(r.get("settings"), Mapping) else {}

    def _pf(r: Mapping[str, Any]) -> float:
        s = _s(r)
        return float(s.get("fpts") or 0) + float(s.get("fpts_decimal") or 0) / 100.0

    if not owner_id:
        return None
    mine = next((r for r in season_rosters if _text(r.get("owner_id")) == owner_id), None)
    if mine is None:
        return None
    order = sorted(season_rosters, key=lambda r: (-int(_s(r).get("wins") or 0), -_pf(r)))
    place = next((i for i, r in enumerate(order, 1) if r is mine), None)
    s = _s(mine)
    wins, losses, ties = int(s.get("wins") or 0), int(s.get("losses") or 0), int(s.get("ties") or 0)
    if wins + losses + ties == 0:
        return None
    return {
        "season": season,
        "league_id": league_id,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "points_for": round(_pf(mine), 1),
        "place": place,
        "of": len(season_rosters),
    }
