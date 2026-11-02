"""Player availability for the quick view: a clean label for a non-healthy
Sleeper injury status plus the real detail fields that came with it.

Only what the directory actually carries is returned. Sleeper has no
expected-return field, so ``return_note`` is the honest "No return date
reported" unless the report text itself is all we have (shown as ``report``,
never parsed into a date). The news item that may explain the status is
matched separately (see news_explaining_injury) and is never presented as the
proven cause: callers label it "Latest injury report".
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules import injury_status
from modules.news_signal import EVENT_INJURY

NO_RETURN_DATE = "No return date reported"
# Table ``kind`` -> the availability block's severity: "out" = not playing,
# "doubt" = likely out, "question" = game-time, "other".
_SEVERITY_BY_KIND = {
    "reserve": "out", "season_ending": "out", "suspended": "out", "out": "out",
    "game_time": "question", "not_active": "other",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def build_availability(
    status: Any,
    body_part: Any = None,
    notes: Any = None,
) -> dict[str, Any] | None:
    """None for a healthy / unknown status, else the availability block."""

    raw = _text(status)
    if not raw:
        return None
    row = injury_status.designation(raw)
    if row is not None and not row.designation:
        return None  # Healthy / Active
    if row is not None:
        label, severity = row.label, _SEVERITY_BY_KIND.get(row.kind, "other")
        if row.kind == "game_time" and row.p_play <= injury_status.LIKELY_OUT_P_PLAY:
            severity = "doubt"
    else:
        # A tag the table has no row for: show Sleeper's own words, never parsed.
        label, severity = (raw if len(raw) <= 40 else ""), "other"
    if not label:
        return None
    return {
        "status": raw,
        "label": label,
        "severity": severity,
        "unavailable": severity in {"out", "doubt"},
        "body_part": _text(body_part) or None,
        "report": _text(notes) or None,
        "return_note": NO_RETURN_DATE,
    }


def news_explaining_injury(
    items: Iterable[Mapping[str, Any]],
    *,
    now_ts: float,
    max_age_days: int = 30,
) -> Mapping[str, Any] | None:
    """Most recent injury-type item within the window, else None. Items must
    already be matched to the player and carry ``event_type`` and
    ``published_ts``; an undated item is never picked."""

    cutoff = now_ts - max_age_days * 86400
    best: Mapping[str, Any] | None = None
    best_ts = 0.0
    for item in items:
        if item.get("event_type") != EVENT_INJURY or item.get("speculative"):
            continue
        try:
            ts = float(item.get("published_ts") or 0)
        except (TypeError, ValueError):
            continue
        if ts >= cutoff and ts > best_ts:
            best, best_ts = item, ts
    return best
