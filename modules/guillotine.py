"""Guillotine / chopped league support (slice 1).

Sleeper has no formal guillotine league type, so detection uses defensible
signals plus a manual per-league override. Everything here is pure: callers
pass real Sleeper payloads; nothing is guessed. Missing projections yield
``None`` (the UI then shows nothing) rather than an estimate.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

OVERRIDE_GUILLOTINE = "guillotine"
OVERRIDE_STANDARD = "standard"
VALID_OVERRIDES = (OVERRIDE_GUILLOTINE, OVERRIDE_STANDARD)

_NAME_RE = re.compile(r"\b(guillotine|chopped|the\s+chop|chop\s+league)\b", re.IGNORECASE)
_FLAG_KEY_RE = re.compile(r"guillotine|chopped", re.IGNORECASE)
_FALSEY = ("", "0", "false", "none", "null")


def clean_override(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in VALID_OVERRIDES else None


def _has_players(roster: Mapping[str, Any]) -> bool:
    return bool(roster.get("players"))


def empty_roster_ids(rosters: Iterable[Mapping[str, Any]]) -> list[str]:
    return [str(r.get("roster_id")) for r in rosters if not _has_players(r)]


def detect(
    league: Mapping[str, Any] | None,
    rosters: Sequence[Mapping[str, Any]] | None = None,
    override: str | None = None,
) -> dict[str, Any]:
    """Return ``{"is_guillotine": bool, "source": str}``.

    Order: manual override, explicit flag/name, then structural. Structural
    signal: in season past week 1, at least one fully emptied roster, and no
    more emptied rosters than completed weeks (one chop per week).
    """

    forced = clean_override(override)
    if forced == OVERRIDE_GUILLOTINE:
        return {"is_guillotine": True, "source": "override"}
    if forced == OVERRIDE_STANDARD:
        return {"is_guillotine": False, "source": "override"}
    league = league or {}
    settings = league.get("settings") if isinstance(league.get("settings"), Mapping) else {}
    metadata = league.get("metadata") if isinstance(league.get("metadata"), Mapping) else {}
    for container in (settings, metadata):
        for key, val in container.items():
            if _FLAG_KEY_RE.search(str(key)) and str(val).strip().lower() not in _FALSEY:
                return {"is_guillotine": True, "source": "league_flag"}
    if _NAME_RE.search(str(league.get("name") or "")):
        return {"is_guillotine": True, "source": "league_name"}
    try:
        leg = int(settings.get("leg") or 0)
    except (TypeError, ValueError):
        leg = 0
    if rosters and str(league.get("status") or "") == "in_season" and leg >= 2:
        empties = empty_roster_ids(rosters)
        if empties and len(empties) <= leg - 1 and len(empties) < len(rosters):
            return {"is_guillotine": True, "source": "empty_rosters"}
    return {"is_guillotine": False, "source": "none"}


def _points(entry: Mapping[str, Any] | None) -> float | None:
    if not entry:
        return None
    try:
        return float(entry.get("points"))
    except (TypeError, ValueError):
        return None


def weeks_survived(roster_id: str, weekly_matchups: Mapping[int, Sequence[Mapping[str, Any]]]) -> int:
    """Completed weeks in which this roster actually scored (> 0)."""

    count = 0
    for entries in weekly_matchups.values():
        entry = next((m for m in entries or [] if str(m.get("roster_id")) == roster_id), None)
        pts = _points(entry)
        if pts is not None and pts > 0:
            count += 1
    return count


def survival_status(
    my_roster: Mapping[str, Any],
    rosters: Sequence[Mapping[str, Any]],
    past_weeks: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rid = str(my_roster.get("roster_id"))
    return {
        "alive": _has_players(my_roster),
        "weeks_survived": weeks_survived(rid, past_weeks),
        "teams_alive": sum(1 for r in rosters if _has_players(r)),
        "teams_total": len(rosters),
    }


def chop_line(
    alive_roster_ids: Sequence[str],
    projected_by_roster: Mapping[str, float | None],
    my_roster_id: str,
) -> dict[str, Any] | None:
    """Lowest projected score among alive rosters. ``None`` unless EVERY alive
    roster has a real projection (a partial field could name the wrong line)."""

    if not alive_roster_ids:
        return None
    values: dict[str, float] = {}
    for rid in alive_roster_ids:
        v = projected_by_roster.get(rid)
        if v is None:
            return None
        values[rid] = float(v)
    low_id = min(values, key=lambda k: values[k])
    line = values[low_id]
    mine = values.get(my_roster_id)
    return {
        "line": round(line, 1),
        "my_projected": round(mine, 1) if mine is not None else None,
        "margin": round(mine - line, 1) if mine is not None else None,
        "at_risk": low_id == my_roster_id,
    }
