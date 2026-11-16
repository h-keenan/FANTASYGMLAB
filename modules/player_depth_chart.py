"""A player's real NFL depth chart for the Player Quick View: the ordered
list of his team's players at the same depth-chart slot, his place in it, and
each player's move since the last weekly snapshot.

Source: Sleeper's player directory (``depth_chart_position`` and
``depth_chart_order``, the same fields modules.rankings reads) and the weekly
order snapshots modules.depth_chart_history already writes. Nothing new is
fetched or stored. Sleeper's order is the team's own listing and is not always
contiguous (a WR can be "LWR 3"), so ``order`` is shown as Sleeper gives it and
the list is sorted by it.

The payload is plain data (``entries`` + ``self_order`` + labels) so the shared
client component can draw any team/slot's chart, including a simulated one.
"""

from __future__ import annotations

from typing import Any, Mapping

from modules import depth_chart_history

MAX_ENTRIES = 10
_EXCLUDED_STATUSES = {"retired"}

SLOT_LABELS = {
    "QB": "Quarterbacks", "RB": "Running backs", "TE": "Tight ends", "K": "Kickers", "P": "Punters", "LS": "Long snappers",
    "LWR": "Wide receivers (left)", "RWR": "Wide receivers (right)", "SWR": "Wide receivers (slot)",
    "OL": "Offensive line", "LDE": "Defensive end (left)", "RDE": "Defensive end (right)",
    "LDT": "Defensive tackle (left)", "RDT": "Defensive tackle (right)", "NT": "Nose tackle",
    "LOLB": "Outside linebacker (left)", "ROLB": "Outside linebacker (right)",
    "LILB": "Inside linebacker (left)", "RILB": "Inside linebacker (right)", "MLB": "Middle linebacker",
    "LCB": "Cornerback (left)", "RCB": "Cornerback (right)", "NB": "Nickel back", "SS": "Strong safety", "FS": "Free safety",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _order(raw: Mapping[str, Any]) -> int | None:
    try:
        value = int(float(raw.get("depth_chart_order")))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def previous_orders(snapshots: Mapping[str, Any] | None, current_week_key: str | None = None) -> dict[str, int]:
    """player_id -> depth order in the latest weekly snapshot BEFORE the
    current week (the same comparison record_depth_chart_snapshot makes)."""

    snapshots = snapshots or {}
    current = current_week_key or depth_chart_history._current_week_key()
    prior = [key for key in snapshots if key < current]
    if not prior:
        return {}
    chosen = snapshots.get(max(prior))
    if not isinstance(chosen, dict):
        return {}
    out: dict[str, int] = {}
    for pid, order in chosen.items():
        try:
            out[str(pid)] = int(order)
        except (TypeError, ValueError):
            continue
    return out


def build_depth_chart(
    player_id: str,
    directory: Mapping[str, Any],
    *,
    snapshots: Mapping[str, Any] | None = None,
    current_week_key: str | None = None,
) -> dict[str, Any]:
    pid = str(player_id)
    me = directory.get(pid)
    base: dict[str, Any] = {"ok": True, "player_id": pid, "team": None, "slot": None, "slot_label": None, "self_order": None, "entries": [], "total": 0, "reason": ""}
    if not isinstance(me, Mapping):
        return {**base, "reason": "not_found"}
    team = _text(me.get("team")).upper()
    slot = _text(me.get("depth_chart_position")).upper()
    self_order = _order(me)
    if not team:
        return {**base, "reason": "no_team"}
    if not slot or self_order is None:
        return {**base, "team": team, "reason": "not_on_depth_chart"}

    previous = previous_orders(snapshots, current_week_key)
    members: list[tuple[int, str, str, Mapping[str, Any]]] = []
    for other_id, raw in directory.items():
        if not isinstance(raw, Mapping):
            continue
        if _text(raw.get("team")).upper() != team or _text(raw.get("depth_chart_position")).upper() != slot:
            continue
        if _text(raw.get("status")).lower() in _EXCLUDED_STATUSES:
            continue
        order = _order(raw)
        if order is None:
            continue
        name = _text(raw.get("full_name")) or " ".join(p for p in (_text(raw.get("first_name")), _text(raw.get("last_name"))) if p)
        members.append((order, name, str(other_id), raw))
    members.sort(key=lambda m: (m[0], m[1], m[2]))

    entries = []
    for order, name, other_id, raw in members[:MAX_ENTRIES]:
        prior = previous.get(other_id)
        entries.append({
            "player_id": other_id,
            "name": name,
            "position": _text(raw.get("position")).upper() or None,
            "team": team,
            "order": order,
            "status": _text(raw.get("status")) or None,
            "injury_status": _text(raw.get("injury_status")) or None,
            "is_self": other_id == pid,
            # Positive = moved up since the last weekly snapshot; None = no prior reading.
            "change": (prior - order) if prior is not None else None,
        })
    if not any(e["is_self"] for e in entries):
        # He is deeper than the cap: keep him visible instead of cutting him off.
        mine = next((m for m in members if m[2] == pid), None)
        if mine is not None:
            order, name, other_id, raw = mine
            prior = previous.get(pid)
            entries.append({
                "player_id": pid, "name": name, "position": _text(raw.get("position")).upper() or None, "team": team,
                "order": order, "status": _text(raw.get("status")) or None, "injury_status": _text(raw.get("injury_status")) or None,
                "is_self": True, "change": (prior - order) if prior is not None else None,
            })
    return {**base, "team": team, "slot": slot, "slot_label": SLOT_LABELS.get(slot, slot), "self_order": self_order, "entries": entries, "total": len(members)}
