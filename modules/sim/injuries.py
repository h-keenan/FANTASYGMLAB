"""What a Sim injury actually is (``injury_v`` 1+): a body part / injury type behind the weeks a player misses.

The length of an injury is still decided by the player model (or the labelled fallback); this module only *names* it, after the
fact, from a separate seeded stream (``ginjtype``), so turning it on never moves a score, a length or any other draw. A longer
injury maps to a more severe type: a 1-2 week injury is a tweak (hamstring, ankle, a concussion that clears protocol), a season-
ending one is a tear or a break (ACL, Achilles). Position shifts the odds: quarterbacks hurt shoulders and hands, backs and
receivers hamstrings and knees, kickers hip flexors and quads.

Pure and import-light: the engine calls ``draw_injury_type`` once per new injury and writes the result into the ``injury`` event.
"""

from __future__ import annotations

from typing import Any, Mapping

# (weeks <= bound) -> severity band. 9+ is the model's "long" injury, usually the rest of the season.
BANDS: tuple[tuple[int, str], ...] = ((2, "minor"), (5, "moderate"), (8, "major"), (99, "severe"))

# severity -> [(type, weight)]. Every type is a plain label the UI shows as-is ("Hamstring", "High ankle sprain").
TYPES: dict[str, tuple[tuple[str, float], ...]] = {
    "minor": (
        ("Hamstring", 18.0), ("Ankle", 16.0), ("Knee", 9.0), ("Groin", 7.0), ("Calf", 7.0), ("Shoulder", 7.0), ("Concussion", 10.0),
        ("Ribs", 5.0), ("Back", 6.0), ("Quad", 6.0), ("Hand", 4.0), ("Illness", 3.0), ("Foot", 4.0), ("Hip", 3.0),
    ),
    "moderate": (
        ("Hamstring strain", 16.0), ("High ankle sprain", 16.0), ("MCL sprain", 11.0), ("Concussion", 11.0), ("Shoulder sprain", 9.0),
        ("Groin strain", 6.0), ("Foot", 7.0), ("Rib fracture", 5.0), ("Hip", 4.0), ("Broken hand", 6.0), ("Calf strain", 5.0), ("Back", 4.0),
    ),
    "major": (
        ("Torn hamstring", 14.0), ("Broken collarbone", 8.0), ("Lisfranc sprain", 10.0), ("Fractured foot", 11.0), ("Torn labrum", 8.0),
        ("Severe MCL sprain", 12.0), ("Broken wrist", 8.0), ("Fractured fibula", 7.0), ("Concussion", 6.0), ("Sports hernia", 6.0), ("Dislocated shoulder", 10.0),
    ),
    "severe": (
        ("Torn ACL", 30.0), ("Torn Achilles", 14.0), ("Fractured leg", 10.0), ("Torn pectoral", 8.0), ("Torn labrum", 8.0),
        ("Lisfranc fracture", 8.0), ("Neck injury", 6.0), ("Broken ankle", 8.0), ("Torn patellar tendon", 4.0), ("Broken collarbone", 4.0),
    ),
}

# position -> {type: weight multiplier}. Anything not listed keeps weight 1.
POSITION_TILT: dict[str, dict[str, float]] = {
    "QB": {"Shoulder": 2.5, "Shoulder sprain": 2.5, "Dislocated shoulder": 2.0, "Hand": 2.5, "Broken hand": 2.5, "Ribs": 2.0, "Concussion": 1.4, "Hamstring": 0.5, "Hamstring strain": 0.5, "Torn hamstring": 0.5, "Groin": 0.4, "Calf": 0.5},
    "RB": {"Knee": 1.5, "MCL sprain": 1.4, "Hamstring": 1.2, "Ribs": 1.3, "Concussion": 1.2, "Torn ACL": 1.2, "Hand": 0.7},
    "WR": {"Hamstring": 1.5, "Hamstring strain": 1.5, "Torn hamstring": 1.4, "High ankle sprain": 1.2, "Ankle": 1.2, "Concussion": 1.3, "Groin": 1.3, "Shoulder": 0.8},
    "TE": {"Knee": 1.3, "Ankle": 1.2, "Concussion": 1.2, "Hand": 1.2, "Shoulder": 1.1},
    "K": {"Quad": 4.0, "Hip": 3.0, "Groin": 2.5, "Calf": 2.0, "Illness": 2.0, "Concussion": 0.1, "Shoulder": 0.1, "Ribs": 0.2, "Knee": 0.7},
}


def band_for(weeks: int) -> str:
    for bound, name in BANDS:
        if int(weeks) <= bound:
            return name
    return BANDS[-1][1]


def weighted_types(pos: str, weeks: int) -> list[tuple[str, float]]:
    """The (type, weight) table for a position and an injury length: severity from the weeks, then the position's tilt."""

    tilt = POSITION_TILT.get(pos, {})
    return [(name, w * tilt.get(name, 1.0)) for name, w in TYPES[band_for(weeks)]]


def draw_injury_type(pos: str, weeks: int, u: float) -> str:
    """One type for ``u`` in [0, 1): a pure function of its arguments (the engine supplies ``u`` from the ``ginjtype`` stream)."""

    table = weighted_types(pos, weeks)
    total = sum(w for _, w in table)
    target = min(max(float(u), 0.0), 0.999999999) * total
    acc = 0.0
    for name, w in table:
        acc += w
        if target < acc:
            return name
    return table[-1][0]


def out_label(kind: str | None, weeks: int) -> str:
    """"Hamstring · out 4 wks" (or "Out 4 wks" with no type): the one line every surface shows for a current injury."""

    n = int(weeks)
    span = f"out {n} wk{'' if n == 1 else 's'}"
    return f"{kind} · {span}" if kind else span.capitalize()


def kinds_from_event(payload: Mapping[str, Any]) -> dict[str, str]:
    """{pid: type} from an ``injury`` event payload (empty for an event from before ``injury_v``)."""

    raw = payload.get("kinds") or {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, Mapping) else {}


__all__ = ["BANDS", "TYPES", "POSITION_TILT", "band_for", "weighted_types", "draw_injury_type", "out_label", "kinds_from_event"]
