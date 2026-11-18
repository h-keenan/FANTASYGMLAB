"""Live draft context: team stance, ages and needs, rookie ADP and class strength.

Handshake item 8 of docs/audits/2026-11-advice-handshakes.md. Until now the live
draft read none of this: ``live_draft._strategy_name`` looks for a team strategy
in the league settings but nothing ever filled it (so the age tilt always ran as
"balanced"), needs came from a separate coarse roster-count model, and the rookie
ADP gap and class strength never reached the hint.

This module builds one small context from the shared pieces:

* stance      declared Team Situation, else the team's resolved posture
              (``team_profile`` posture, the canonical refined classifier)
* needs       the profile's true needs (``roster_value_model.league_needs``)
* ages        the profile's per-position phase mix (``age_profile``): a room is
              "aging" when half or more of it (and at least two players) has
              reached the declining or cliff phase
* class       editorial / crowd class strength for the draft season
              (``trade_ideas._rookie_class_strength_multiplier``) plus how many
              prospects ``college_prospect_ingest`` has loaded for that class
* ADP gap     the existing rookie ADP read (``rookie_adp.value_vs_adp``)

``apply_to_settings`` hands the first three to ``live_draft`` through the league
settings dict (the channel ``_strategy_name`` already reads). ``notes_for`` turns
them into per-player reasons: every note names the factor behind it. The age
nudge stays inside the existing cap (well below one value tier). Pure, no I/O.

Kill switch: ``DYNASTYGM_LIVE_DRAFT_CONTEXT_V1`` (default ON; 0/false/off restores
the previous live draft output exactly). Sim AI GMs do not read this module."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from modules import experimental_graduation

LIVE_DRAFT_CONTEXT_ENV_KEY = "DYNASTYGM_LIVE_DRAFT_CONTEXT_V1"
DRAFT_POSITIONS = ("QB", "RB", "WR", "TE")
POSTURE_STRATEGY = {
    "contender": "contender",
    "fringe_contender": "balanced",
    "retool": "balanced",
    "rebuild": "rebuild",
    "tank": "rebuild",
}
STANCE_STRATEGY = {"competing": "contender", "rebuilding": "rebuild", "balanced": "balanced"}
STRATEGY_LABEL = {"contender": "Contending", "rebuild": "Rebuilding", "balanced": "Balanced"}
# A room is "aging" once this share (and at least MIN_AGING_PLAYERS) is declining or past the cliff.
AGING_SHARE = 0.5
MIN_AGING_PLAYERS = 2
# Extra dynasty age tilt for an aging room, inside live_draft's existing cap.
AGING_ROOM_YOUTH_BONUS = 0.75
AGING_ROOM_OLD_PENALTY = 0.5
STRONG_CLASS = 1.08
WEAK_CLASS = 0.92
ADP_NOTE_MIN_DELTA = 3.0


def enabled() -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(LIVE_DRAFT_CONTEXT_ENV_KEY, default=True)


def _short_name(name: Any) -> str:
    parts = str(name or "").split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else str(name or "")


def aging_rooms(age_block: Mapping[str, Any] | None) -> dict[str, dict[str, int]]:
    rooms: dict[str, dict[str, int]] = {}
    for pos, info in ((age_block or {}).get("by_position") or {}).items():
        mix = info.get("phase_mix") or {}
        past = int(mix.get("declining") or 0) + int(mix.get("cliff") or 0)
        count = int(info.get("count") or 0)
        if count and past >= MIN_AGING_PLAYERS and past / count >= AGING_SHARE:
            rooms[str(pos).upper()] = {"past_peak": past, "cliff": int(mix.get("cliff") or 0), "count": count}
    return rooms


def strategy_for(declared_stance: str, posture_key: Any) -> tuple[str, str]:
    declared = STANCE_STRATEGY.get(str(declared_stance or "").strip().lower())
    if declared:
        return declared, "declared"
    mapped = POSTURE_STRATEGY.get(str(posture_key or "").strip().lower())
    return (mapped, "auto") if mapped else ("", "")


def class_strength(season: Any, editorial_multiplier: float | None, crowd: Mapping[Any, Mapping[str, Any]] | None, prospects: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any] | None:
    """The draft class read: strong / average / weak plus how many prospects are tracked.

    Only claims a strength when there is a real basis (an editorial grade for the
    year or crowd scouting reports); otherwise only the tracked-prospect count."""

    try:
        year = int(season)
    except (TypeError, ValueError):
        return None
    crowd_entry = (crowd or {}).get(year) if crowd else None
    has_basis = editorial_multiplier is not None or bool(crowd_entry)
    multiplier = None
    if has_basis:
        multiplier = max(0.8, min(1.25, float(editorial_multiplier or 1.0) * float((crowd_entry or {}).get("multiplier", 1.0))))
    counts: dict[str, int] = {}
    for p in prospects:
        if str(p.get("draft_year") or "") == str(year):
            pos = str(p.get("position") or "").upper()
            if pos in DRAFT_POSITIONS:
                counts[pos] = counts.get(pos, 0) + 1
    if multiplier is None and not counts:
        return None
    label = None
    if multiplier is not None:
        label = "strong" if multiplier >= STRONG_CLASS else "weak" if multiplier <= WEAK_CLASS else "average"
    return {
        "year": year,
        "multiplier": round(multiplier, 3) if multiplier is not None else None,
        "label": label,
        "scouts": int((crowd_entry or {}).get("scout_count") or 0),
        "prospects_tracked": counts,
    }


def build_context(
    *,
    profile: Mapping[str, Any] | None,
    my_roster_id: Any,
    declared_stance: str = "",
    rookie_draft: bool = False,
    class_read: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """The live draft context for the user's team, or None when the profile has no row for it."""

    me = ((profile or {}).get("teams") or {}).get(str(my_roster_id))
    if not me:
        return None
    posture = me.get("posture") or {}
    strategy, source = strategy_for(declared_stance, posture.get("key"))
    needs = [str(p).upper() for p in (me.get("needs") or {}).get("needs") or () if str(p).upper() in DRAFT_POSITIONS]
    age = me.get("age") or {}
    return {
        "strategy": strategy,
        "strategy_source": source,
        "posture_label": posture.get("label"),
        "needs": needs,
        "aging_rooms": aging_rooms(age),
        "core_age": age.get("core_avg"),
        "cliff_count": len(age.get("cliff_ids") or ()),
        "rookie_draft": bool(rookie_draft),
        "class_strength": dict(class_read) if class_read else None,
    }


def apply_to_settings(settings: Mapping[str, Any], ctx: Mapping[str, Any] | None) -> dict[str, Any]:
    """League settings with the context filled into the keys ``live_draft`` reads."""

    out = dict(settings or {})
    if not ctx or not enabled():
        return out
    if ctx.get("strategy"):
        out["team_strategy"] = ctx["strategy"]
    out["profile_needs"] = list(ctx.get("needs") or [])
    out["aging_rooms"] = dict(ctx.get("aging_rooms") or {})
    return out


def room_is_aging(settings: Mapping[str, Any] | None, position: str) -> bool:
    return str(position).upper() in ((settings or {}).get("aging_rooms") or {})


def notes_for(rec: Mapping[str, Any], ctx: Mapping[str, Any] | None) -> list[str]:
    """Why this player fits (or not) this team: one note per real factor."""

    if not ctx or not enabled():
        return []
    pos = str(rec.get("position") or "").upper()
    name = _short_name(rec.get("name"))
    notes: list[str] = []
    if pos in (ctx.get("needs") or ()):
        notes.append(f"Fills a true {pos} need")
    room = (ctx.get("aging_rooms") or {}).get(pos)
    if room:
        notes.append(f"Your {pos} room is aging ({room['past_peak']} of {room['count']} past their prime)")
    delta = rec.get("adp_delta")
    if delta is not None and rec.get("adp_verdict") in {"value", "reach"} and abs(float(delta)) >= ADP_NOTE_MIN_DELTA:
        if rec["adp_verdict"] == "value":
            notes.append(f"We rank {name} {abs(float(delta)):.0f} spots above his ADP, so he may be a value")
        else:
            notes.append(f"{name} is going {abs(float(delta)):.0f} spots earlier than our rank (ADP reach risk)")
    cls = ctx.get("class_strength") or {}
    if ctx.get("rookie_draft") and cls.get("label") in {"strong", "weak"}:
        notes.append(f"The {cls['year']} class reads {cls['label']}, which {'supports reaching a little for upside' if cls['label'] == 'strong' else 'argues for taking proven value'}")
    return notes


def summary(ctx: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The compact header block for the clients: parts for the collapsed line and lines for the expanded body."""

    if not ctx or not enabled():
        return None
    parts: list[str] = []
    lines: list[str] = []
    label = STRATEGY_LABEL.get(str(ctx.get("strategy") or ""))
    if label:
        parts.append(label)
        src = "your declared stance" if ctx.get("strategy_source") == "declared" else "your roster's resolved posture"
        lines.append(f"{label}: from {src}, so the board leans {'younger' if ctx['strategy'] == 'rebuild' else 'toward proven value' if ctx['strategy'] == 'contender' else 'on both'}")
    if ctx.get("needs"):
        parts.append("need " + "/".join(ctx["needs"]))
        lines.append("True needs: " + ", ".join(ctx["needs"]) + " (the league need model, not a roster count)")
    rooms = ctx.get("aging_rooms") or {}
    if rooms:
        parts.append(", ".join(sorted(rooms)) + " aging")
        lines.append("Aging rooms: " + ", ".join(f"{pos} ({r['past_peak']} of {r['count']} past prime)" for pos, r in sorted(rooms.items())) + "; younger options get a small boost")
    cls = ctx.get("class_strength")
    if ctx.get("rookie_draft") and cls:
        bits = []
        if cls.get("label"):
            bits.append(f"{cls['year']} class reads {cls['label']}" + (f" (x{cls['multiplier']:.2f})" if cls.get("multiplier") else ""))
        tracked = cls.get("prospects_tracked") or {}
        if tracked:
            bits.append(f"{sum(tracked.values())} prospects tracked (" + ", ".join(f"{p} {n}" for p, n in sorted(tracked.items())) + ")")
        if bits:
            parts.append(f"{cls['year']} class {cls['label']}" if cls.get("label") else f"{cls['year']} class")
            lines.append("; ".join(bits))
    if not parts:
        return None
    return {"parts": parts[:4], "lines": lines}
