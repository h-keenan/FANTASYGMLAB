"""Deterministic retrospective grades over canonical History events.

History records stay immutable. Grades are computed from:
canonical transaction + current evaluation context + recorded later events.

No LLM. No invented historical prices. No invented post-event production.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


PENDING = "Pending"
CONFIDENCE_HIGH = "High confidence"
CONFIDENCE_MEDIUM = "Medium confidence"
CONFIDENCE_LOW = "Low confidence"
CONFIDENCE_PENDING = "Pending"

GRADE_SCALE = ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F")
RECENT_WEEK_THRESHOLD = 2

LENS_VALUE_AT_TRADE = "value_at_trade"
LENS_VALUE_NOW = "value_now"
LENS_TRAJECTORY = "trajectory"
LENS_ROSTER = "roster_outcome"
LENS_COST = "cost_efficiency"


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _historical_value(asset: Mapping[str, Any]) -> float | None:
    for key in ("value_at_trade", "historical_value", "value_at_event"):
        parsed = _float(asset.get(key))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _lookup_current(asset: Mapping[str, Any], lookup: Mapping[str, Mapping[str, Any]]) -> float | None:
    recorded = _float(asset.get("current_value"))
    if recorded is not None and recorded > 0:
        return recorded
    player_id = _text(asset.get("player_id"))
    row = lookup.get(player_id) if player_id else None
    if not isinstance(row, Mapping):
        return None
    for key in ("current_value", "value_score", "dynasty_score"):
        parsed = _float(row.get(key))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def letter_from_ratio(ratio: float) -> str:
    """Map received/sent current-value ratio onto the letter scale.

    1.0 is a fair exchange (B), not a forced winner. Both sides of a balanced
    trade can land in the B range.
    """

    bands = (
        (1.32, "A+"),
        (1.20, "A"),
        (1.12, "A-"),
        (1.05, "B+"),
        (0.97, "B"),
        (0.91, "B-"),
        (0.85, "C+"),
        (0.78, "C"),
        (0.70, "C-"),
        (0.55, "D"),
    )
    for floor, letter in bands:
        if ratio >= floor:
            return letter
    return "F"


def bump_letter(letter: str, steps: int) -> str:
    if letter == PENDING or letter not in GRADE_SCALE:
        return letter
    index = GRADE_SCALE.index(letter)
    return GRADE_SCALE[max(0, min(len(GRADE_SCALE) - 1, index - steps))]


def _side_assets(side: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(asset) for asset in side.get("receives") or [] if isinstance(asset, Mapping)]


def _player_ids(assets: Sequence[Mapping[str, Any]]) -> set[str]:
    return {_text(asset.get("player_id")) for asset in assets if _text(asset.get("player_id"))}


def player_later_dropped(
    player_id: str,
    *,
    after_timestamp: int,
    later_events: Sequence[Mapping[str, Any]],
) -> bool:
    if not player_id:
        return False
    for event in later_events:
        if _int(event.get("timestamp"), 0) <= after_timestamp:
            continue
        for side in event.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            for asset in list(side.get("drops") or []):
                if isinstance(asset, Mapping) and _text(asset.get("player_id")) == player_id:
                    return True
    return False


def _sum_values(assets: Sequence[Mapping[str, Any]], getter) -> tuple[float, int]:
    total = 0.0
    counted = 0
    for asset in assets:
        value = getter(asset)
        if value is None:
            continue
        total += value
        counted += 1
    return total, counted


def _tone_for_letter(letter: str) -> str:
    if letter == PENDING:
        return "pending"
    if letter.startswith("A"):
        return "success"
    if letter.startswith("B"):
        return "positive"
    if letter.startswith("C"):
        return "neutral"
    return "risk"


def _empty_side(team: str) -> dict[str, Any]:
    return {
        "team": team,
        "letter": PENDING,
        "tone": "pending",
        "confidence": CONFIDENCE_PENDING,
        "timing_label": "Too early",
        "why": "Not enough recorded evidence to grade this side yet.",
        "watch": "Grade will update as current values settle.",
        "lenses": [],
        "ratio": None,
    }


def grade_trade(
    transaction: Mapping[str, Any],
    *,
    player_lookup: Mapping[str, Mapping[str, Any]] | None = None,
    current_week: int = 0,
    later_events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    lookup = player_lookup or {}
    sides = [side for side in transaction.get("sides") or [] if isinstance(side, Mapping)]
    event_week = _int(transaction.get("week"), 0)
    weeks_elapsed = max(0, current_week - event_week) if current_week and event_week else 99
    recent = weeks_elapsed < RECENT_WEEK_THRESHOLD
    if len(sides) < 2:
        team = _text(sides[0].get("team_name"), "Unknown team") if sides else "Unknown team"
        return {
            "kind": "trade",
            "pending": True,
            "timing_label": "Too early",
            "sides": [_empty_side(team)],
        }

    received = [_side_assets(side) for side in sides[:2]]
    # What a side gave is what the other side received.
    given = [received[1], received[0]]
    graded_sides: list[dict[str, Any]] = []
    for index, side in enumerate(sides[:2]):
        team = _text(side.get("team_name"), "Unknown team")
        now_in, now_in_n = _sum_values(received[index], lambda asset: _lookup_current(asset, lookup))
        now_out, now_out_n = _sum_values(given[index], lambda asset: _lookup_current(asset, lookup))
        hist_in, hist_in_n = _sum_values(received[index], _historical_value)
        hist_out, hist_out_n = _sum_values(given[index], _historical_value)
        valued_now = now_in_n + now_out_n
        has_now = now_in_n > 0 and now_out_n > 0
        has_hist = hist_in_n > 0 and hist_out_n > 0
        lenses: list[dict[str, str]] = []
        if has_hist:
            lenses.append(
                {
                    "lens": LENS_VALUE_AT_TRADE,
                    "label": "Value at trade",
                    "note": "Recorded when the deal was logged.",
                }
            )
        if has_now:
            lenses.append(
                {
                    "lens": LENS_VALUE_NOW,
                    "label": "Value now",
                    "note": "Current market only — not reconstructed historical prices.",
                }
            )
        if has_hist and has_now:
            lenses.append(
                {
                    "lens": LENS_TRAJECTORY,
                    "label": "Asset trajectory",
                    "note": "Change from recorded trade-time value to current value.",
                }
            )
        dropped = [
            _text(asset.get("name"))
            for asset in received[index]
            if player_later_dropped(
                _text(asset.get("player_id")),
                after_timestamp=_int(transaction.get("timestamp"), 0),
                later_events=later_events or (),
            )
        ]
        if dropped:
            lenses.append(
                {
                    "lens": LENS_ROSTER,
                    "label": "Roster outcome",
                    "note": "Later History shows a received player was dropped.",
                }
            )

        if recent or not has_now:
            graded_sides.append(
                {
                    "team": team,
                    "letter": PENDING,
                    "tone": "pending",
                    "confidence": CONFIDENCE_PENDING,
                    "timing_label": "Too early" if recent else "Pending",
                    "why": (
                        "This deal is still too recent to force a letter grade."
                        if recent
                        else "Current player values are missing for one or both sides."
                    ),
                    "watch": "Letter grades appear after two completed weeks and current values.",
                    "lenses": lenses,
                    "ratio": None,
                }
            )
            continue

        ratio = now_in / now_out if now_out > 0 else (1.15 if now_in > 0 else 1.0)
        letter = letter_from_ratio(ratio)
        if has_hist:
            hist_ratio = hist_in / hist_out if hist_out > 0 else 1.0
            # Blend one step toward historical if it disagrees sharply.
            if hist_ratio >= 1.12 and ratio < 1.0:
                letter = bump_letter(letter, 1)
            elif hist_ratio <= 0.88 and ratio > 1.0:
                letter = bump_letter(letter, -1)
        if dropped:
            letter = bump_letter(letter, -1)
        if valued_now >= 4 and has_hist:
            confidence = CONFIDENCE_HIGH
        elif valued_now >= 2:
            confidence = CONFIDENCE_MEDIUM
        else:
            confidence = CONFIDENCE_LOW
        why = (
            f"Received {now_in:.0f} current value against {now_out:.0f} sent."
            if has_now
            else "Current values are incomplete."
        )
        watch = "Pick outcomes remain unresolved." if any(
            _text(asset.get("kind")) == "pick" for asset in received[index] + given[index]
        ) else "Grade can move as current values change."
        graded_sides.append(
            {
                "team": team,
                "letter": letter,
                "tone": _tone_for_letter(letter),
                "confidence": confidence,
                "timing_label": "Early grade" if weeks_elapsed < 6 else "Current grade",
                "why": why,
                "watch": watch,
                "lenses": lenses,
                "ratio": round(ratio, 3),
            }
        )

    pending = all(side["letter"] == PENDING for side in graded_sides)
    return {
        "kind": "trade",
        "pending": pending,
        "timing_label": graded_sides[0]["timing_label"] if graded_sides else "Pending",
        "sides": graded_sides,
        "zero_sum": False,
    }


def grade_waiver(
    transaction: Mapping[str, Any],
    *,
    player_lookup: Mapping[str, Mapping[str, Any]] | None = None,
    current_week: int = 0,
    later_events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    lookup = player_lookup or {}
    sides = [side for side in transaction.get("sides") or [] if isinstance(side, Mapping)]
    side = sides[0] if sides else {}
    team = _text(side.get("team_name"), "Unknown team")
    added = _side_assets(side)
    primary = added[0] if added else {}
    player_name = _text(primary.get("name"), "Pickup")
    faab = side.get("faab_spent")
    if faab is None:
        faab = transaction.get("faab")
    faab_value = _int(faab, 0)
    current = _lookup_current(primary, lookup)
    event_week = _int(transaction.get("week"), 0)
    weeks_elapsed = max(0, current_week - event_week) if current_week and event_week else 99
    recent = weeks_elapsed < RECENT_WEEK_THRESHOLD
    dropped = player_later_dropped(
        _text(primary.get("player_id")),
        after_timestamp=_int(transaction.get("timestamp"), 0),
        later_events=later_events or (),
    )
    lenses: list[dict[str, str]] = []
    if faab is not None:
        lenses.append(
            {
                "lens": LENS_COST,
                "label": "FAAB",
                "note": f"${faab_value}" if faab_value else "Zero-cost add",
            }
        )
    if current is not None:
        lenses.append(
            {
                "lens": LENS_VALUE_NOW,
                "label": "Value now",
                "note": "Current dynasty value of the added player.",
            }
        )
    if dropped:
        lenses.append(
            {
                "lens": LENS_ROSTER,
                "label": "Roster outcome",
                "note": "Later History records a drop of this player.",
            }
        )

    if recent or current is None:
        return {
            "kind": _text(transaction.get("type"), "waiver"),
            "pending": True,
            "player": player_name,
            "team": team,
            "letter": PENDING,
            "tone": "pending",
            "confidence": CONFIDENCE_PENDING,
            "timing_label": "Too early" if recent else "Pending",
            "faab": faab_value,
            "why": (
                "This pickup is too recent to force a letter grade."
                if recent
                else "No current player value is recorded for this add."
            ),
            "watch": "Grade appears after two completed weeks when current value exists.",
            "lenses": lenses,
        }

    if current >= 5500:
        letter = "A-"
    elif current >= 3500:
        letter = "B+"
    elif current >= 1800:
        letter = "B"
    elif current >= 900:
        letter = "C+"
    elif current >= 400:
        letter = "C"
    else:
        letter = "D"
    if faab_value == 0 and current >= 400:
        letter = bump_letter(letter, 1)
    if faab_value >= 80 and current < 1200:
        letter = bump_letter(letter, -2)
    elif faab_value >= 40 and current < 800:
        letter = bump_letter(letter, -1)
    if dropped:
        letter = bump_letter(letter, -2)
        if letter in {"A+", "A", "A-", "B+"}:
            letter = "C"
    confidence = CONFIDENCE_MEDIUM if current >= 900 else CONFIDENCE_LOW
    cost_note = "Zero-cost add" if faab_value == 0 else f"${faab_value} FAAB"
    why = f"{cost_note}. Current value {current:.0f}."
    if dropped:
        why += " Later dropped."
    return {
        "kind": _text(transaction.get("type"), "waiver"),
        "pending": False,
        "player": player_name,
        "team": team,
        "letter": letter,
        "tone": _tone_for_letter(letter),
        "confidence": confidence,
        "timing_label": "Early grade" if weeks_elapsed < 6 else "Current grade",
        "faab": faab_value,
        "why": why,
        "watch": "Grade tracks current value and roster retention, not invented scoring.",
        "lenses": lenses,
    }


def grade_transaction(
    transaction: Mapping[str, Any],
    *,
    player_lookup: Mapping[str, Mapping[str, Any]] | None = None,
    current_week: int = 0,
    later_events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    kind = _text(transaction.get("type")).casefold()
    if kind == "trade":
        return grade_trade(
            transaction,
            player_lookup=player_lookup,
            current_week=current_week,
            later_events=later_events,
        )
    if kind in {"waiver", "free_agent"}:
        return grade_waiver(
            transaction,
            player_lookup=player_lookup,
            current_week=current_week,
            later_events=later_events,
        )
    return None
