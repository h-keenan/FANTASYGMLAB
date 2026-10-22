"""Matchup lineup planner: re-score an edited lineup and explain each swap.

FantasyDesk cannot change a Sleeper lineup, so this is a planner only. Every
number here comes from the same functions the Matchup scoreboard uses:
`matchup_win_probability.compute_live_win_probability` for the win chance and
projected totals, and `starter_expected_points` for a player's points. Every
pro/con bullet is derived from one computed value; nothing is invented.

Pure functions over plain dicts (the same player rows the Matchup payload
already carries), so they are testable without Sleeper or the player DB. The
slot eligibility map is passed in (services.mobile_api_service owns it).
"""

from __future__ import annotations

from typing import Any, Mapping

from modules import matchup_win_probability as wp

MAX_BULLETS = 4
# Below these, a difference is rounding noise and no bullet is shown.
_MIN_POINTS_DELTA = 0.05
_MIN_BAND_DELTA = 0.5
_MIN_WIN_DELTA_PCT = 1


class LineupError(ValueError):
    """A proposed lineup that cannot be a real roster lineup."""


def availability(player: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """("bye"|"out"|None, label). Bye and ruled-out players cannot score."""

    projection = player.get("projection") or {}
    if player.get("on_bye") or projection.get("status") == "bye_week":
        return "bye", "On a bye"
    reason = str(player.get("start_ineligible_reason") or "")
    if player.get("ruled_out") or reason in {"Out", "IR", "PUP", "Suspended"}:
        return "out", "Ruled out" if reason in {"", "Out"} else reason
    return None, None


def _is_locked(player: Mapping[str, Any]) -> bool:
    return player.get("game_started") is True


def _points(player: Mapping[str, Any] | None) -> float | None:
    """Expected points; a bye/out player is a real 0 (same as suggested moves)."""

    if player is None:
        return 0.0
    if availability(player)[0] is not None:
        return 0.0
    return wp.starter_expected_points(dict(player))


def _band(player: Mapping[str, Any], key: str) -> float | None:
    projection = player.get("projection") or {}
    if projection.get("status") != "ok":
        return None
    value = projection.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _fits(player: Mapping[str, Any], slot: str, eligible: Mapping[str, set[str]]) -> bool:
    position = str(player.get("position") or "").upper()
    if not position:
        return True  # unresolved identity (e.g. team DEF): not ours to reject
    return position in eligible.get(slot, set())


def validate_lineup(
    pool: Mapping[str, Mapping[str, Any]],
    lineup: list[Mapping[str, Any]],
    eligible: Mapping[str, set[str]],
) -> None:
    seen: set[str] = set()
    for entry in lineup:
        slot = str(entry.get("slot") or "")
        if slot not in eligible:
            raise LineupError(f"Unknown lineup slot {slot!r}.")
        player_id = entry.get("player_id")
        if player_id in (None, ""):
            continue
        player_id = str(player_id)
        if player_id not in pool:
            raise LineupError("That player is not on your roster.")
        if player_id in seen:
            raise LineupError("A player can only start in one slot.")
        seen.add(player_id)
        if not _fits(pool[player_id], slot, eligible):
            raise LineupError(f"{pool[player_id].get('name') or 'That player'} can't fill the {slot} slot.")


def lineup_starters(
    pool: Mapping[str, Mapping[str, Any]], lineup: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """The edited lineup as starter rows, each carrying the slot it fills."""

    rows: list[dict[str, Any]] = []
    for entry in lineup:
        player_id = entry.get("player_id")
        if player_id in (None, ""):
            continue
        row = dict(pool[str(player_id)])
        row["slot"] = entry.get("slot")
        rows.append(row)
    return rows


def evaluate(
    pool: Mapping[str, Mapping[str, Any]],
    lineup: list[Mapping[str, Any]],
    opponent_starters: list[dict[str, Any]],
) -> dict[str, Any]:
    starters = lineup_starters(pool, lineup)
    return {
        "starters": starters,
        "win_probability": wp.compute_live_win_probability(starters, opponent_starters),
    }


def _win_pct(result: Mapping[str, Any]) -> int | None:
    if result.get("available") is True and isinstance(result.get("probability"), (int, float)):
        return round(float(result["probability"]) * 100)
    return None


def _fmt(value: float) -> str:
    return f"{value:+.1f}".replace("-", "−")


def _swap_lineup(
    lineup: list[Mapping[str, Any]],
    slot: str,
    index: int,
    candidate_id: str,
    pool: Mapping[str, Mapping[str, Any]],
    eligible: Mapping[str, set[str]],
) -> list[dict[str, Any]] | None:
    """The lineup with `candidate_id` at lineup[index]. A candidate already
    starting elsewhere trades places with the occupant, and only when the
    occupant can legally take that slot; otherwise None."""

    occupant_id = lineup[index].get("player_id")
    new = [dict(e) for e in lineup]
    new[index]["player_id"] = candidate_id
    for j, entry in enumerate(new):
        if j == index or str(entry.get("player_id") or "") != candidate_id:
            continue
        if occupant_id in (None, ""):
            entry["player_id"] = None
        elif _fits(pool[str(occupant_id)], str(entry.get("slot")), eligible):
            entry["player_id"] = occupant_id
        else:
            return None
    return new


def candidates_for_slot(
    pool: Mapping[str, Mapping[str, Any]],
    lineup: list[Mapping[str, Any]],
    slot_index: int,
    opponent_starters: list[dict[str, Any]],
    eligible: Mapping[str, set[str]],
) -> dict[str, Any]:
    """Every roster player who could fill lineup[slot_index], each with
    computed pros and cons against the current occupant."""

    slot = str(lineup[slot_index].get("slot") or "")
    occupant_id = lineup[slot_index].get("player_id")
    occupant = pool.get(str(occupant_id)) if occupant_id not in (None, "") else None
    base = evaluate(pool, lineup, opponent_starters)["win_probability"]
    base_pct = _win_pct(base)
    base_points = _points(occupant)
    slot_locked = occupant is not None and _is_locked(occupant)

    starting_ids = {
        str(entry.get("player_id")) for entry in lineup if entry.get("player_id") not in (None, "")
    }
    out: list[dict[str, Any]] = []
    for player_id, player in pool.items():
        if player_id == str(occupant_id or ""):
            continue
        if str(player.get("roster_slot") or "") in {"ir", "taxi"}:
            continue
        if not _fits(player, slot, eligible):
            continue

        blocked: str | None = None
        kind, label = availability(player)
        if slot_locked:
            blocked = "locked"
        elif _is_locked(player):
            blocked = "locked"
        elif kind is not None:
            blocked = kind
        new_lineup = None if blocked else _swap_lineup(lineup, slot, slot_index, player_id, pool, eligible)
        if not blocked and new_lineup is None:
            continue  # would strand the displaced starter in a slot he can't fill

        result = evaluate(pool, new_lineup, opponent_starters) if new_lineup else None
        new_win = result["win_probability"] if result else None
        new_pct = _win_pct(new_win) if new_win else None
        win_delta = new_pct - base_pct if new_pct is not None and base_pct is not None else None

        cand_points = _points(player)
        points_delta = (
            round(cand_points - base_points, 1) if cand_points is not None and base_points is not None else None
        )
        out.append(
            {
                "player": dict(player),
                "selectable": blocked is None,
                "currently_starting": player_id in starting_ids,
                "blocked_reason": blocked,
                "points_delta": points_delta,
                "win_probability_delta": win_delta,
                "win_probability_after": new_win,
                "bullets": _bullets(player, occupant, points_delta, win_delta, kind, label, blocked),
            }
        )

    out.sort(
        key=lambda c: (
            not c["selectable"],
            # Bench and other non-starters first; swapping places with another
            # starter is the less common move, so those come after.
            bool(c["currently_starting"]),
            -(c["win_probability_delta"] if c["win_probability_delta"] is not None else -999),
            -(c["points_delta"] if c["points_delta"] is not None else -999),
            str(c["player"].get("name") or ""),
        )
    )
    return {"slot": slot, "slot_locked": slot_locked, "current_player_id": occupant_id, "candidates": out}


def _bullets(
    candidate: Mapping[str, Any],
    occupant: Mapping[str, Any] | None,
    points_delta: float | None,
    win_delta: int | None,
    kind: str | None,
    label: str | None,
    blocked: str | None,
) -> list[dict[str, str]]:
    """2-4 short bullets, each tied to one computed value, most decisive first."""

    bullets: list[dict[str, str]] = []

    def add(tone: str, text: str) -> None:
        bullets.append({"tone": tone, "text": text})

    if blocked == "locked":
        add("con", "Game already started")
    if kind is not None and label:
        add("con", label)
    elif str(candidate.get("injury_label") or ""):
        add("con", str(candidate["injury_label"]))
    if occupant is not None:
        occupant_kind, _ = availability(occupant)
        if occupant_kind == "bye":
            add("pro", "Replaces a player on a bye")
        elif occupant_kind == "out":
            add("pro", "Replaces a player who is out")

    if points_delta is not None and abs(points_delta) >= _MIN_POINTS_DELTA and blocked is None:
        add("pro" if points_delta > 0 else "con", f"{_fmt(points_delta)} projected pts")
    if win_delta is not None and abs(win_delta) >= _MIN_WIN_DELTA_PCT:
        add("pro" if win_delta > 0 else "con", f"{win_delta:+d}% win probability".replace("-", "−"))

    if blocked is None and occupant is not None:
        for key, word in (("high", "ceiling"), ("low", "floor")):
            mine, theirs = _band(candidate, key), _band(occupant, key)
            if mine is not None and theirs is not None and abs(mine - theirs) >= _MIN_BAND_DELTA:
                higher = mine > theirs
                add("pro" if higher else "con", f"{'Higher' if higher else 'Lower'} {word} ({mine:.0f} vs {theirs:.0f})")

    opponent = (candidate.get("projection") or {}).get("opponent")
    if opponent and blocked is None:
        add("neutral", f"Faces {opponent}")

    # Availability flags always survive the cap; then the rest in order.
    flags = [b for b in bullets if b["text"] in {"Game already started", label, candidate.get("injury_label")}]
    rest = [b for b in bullets if b not in flags]
    return (flags + rest)[:MAX_BULLETS]
