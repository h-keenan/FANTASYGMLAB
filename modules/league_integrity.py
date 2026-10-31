"""League integrity signals for commissioners: tanking, lineup integrity,
collusion-style trades and inactive managers.

Pure functions over already-fetched Sleeper payloads (no network, no player
database, no clock), so the whole engine is testable with synthetic leagues.
``services/mobile_api_service.py`` gathers the inputs and calls
``build_league_integrity``. Full write-up: docs/commissioner-tools.md.

Principles
----------
* Never one rule. A team's band comes from several independent factor groups
  (lineup behaviour, roster/transaction behaviour) interpreted through
  context (standings, rules). One group alone is capped at "Worth a look".
* Only real data. Every number is read from Sleeper matchups (``players_points``
  per player per week), rosters and transactions. No projections are invented:
  "typical score" is the median of the player's own earlier non-zero weekly
  scores in this league, and it is only used when it exists.
* Calm and explainable. Output is a band, a confidence, concrete evidence
  lines, and the innocent explanations that could produce the same pattern.
  It is a prompt to look, never a verdict.

What Sleeper's public API cannot tell us (stated in ``limits`` too): who was
injured or inactive in a given past week, the league's draft-order rule, and
what managers agreed to off-platform. Those are handled by excluding what we
can (bye weeks, zero-point players) and by labelling the rest as unknown.
"""

from __future__ import annotations

import statistics
from typing import Any, Callable, Iterable, Mapping, Sequence

from modules import trade_value_bands

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

BAND_FINE = "fine"
BAND_LOOK = "worth_a_look"
BAND_STRONG = "strong"
BAND_NOT_ENOUGH = "not_enough_data"

BAND_LABELS = {
    BAND_FINE: "Lineup looks fine",
    BAND_LOOK: "Worth a look",
    BAND_STRONG: "Strong signals",
    BAND_NOT_ENOUGH: "Not enough weeks yet",
}

DRAFT_RULE_RECORD = "record"  # worst record picks first
DRAFT_RULE_LOTTERY = "lottery"  # lottery / non-record order
DRAFT_RULE_UNKNOWN = "unknown"  # Sleeper does not publish it; the default
DRAFT_RULES = (DRAFT_RULE_RECORD, DRAFT_RULE_LOTTERY, DRAFT_RULE_UNKNOWN)

# ---------------------------------------------------------------------------
# Thresholds (documented in docs/commissioner-tools.md; tests pin behaviour)
# ---------------------------------------------------------------------------

MIN_WEEKS_FOR_BAND = 3  # fewer evaluated weeks -> "not enough weeks yet"
MIN_WEEKS_FOR_STRONG = 4
MIN_FLAGGED_FOR_LOOK = 2  # a one-off week never moves a band
MIN_FLAGGED_FOR_STRONG = 3

EXANTE_FULL_GAP_PCT = 0.25  # 25% below the best typical lineup = full severity
SLOT_FULL_COUNT_SHARE = 1 / 3  # a third of slots wasted = full severity
WEEK_FLAG_THRESHOLD = 0.30  # league-adjusted severity needed to flag a week
LOOK_SCORE = 0.30
STRONG_SCORE = 0.55
STRONG_MIN_LINEUP = 0.50  # corroboration: both groups must be non-trivial
STRONG_MIN_ROSTER = 0.25

LINEUP_WEIGHT = 0.65
ROSTER_WEIGHT = 0.35

# Context multipliers applied to a flagged week's severity. They scale how
# readily the same behaviour reads as tanking; they never raise a clean team.
CONTEXT_MULT_ELIMINATED_RECORD = 1.0
CONTEXT_MULT_ELIMINATED_OTHER = 0.95
CONTEXT_MULT_UNKNOWN = 0.9
CONTEXT_MULT_ALIVE = 0.85
CONTEXT_MULT_CLINCHED = 0.7

RECENT_STARTER_WEEKS = 3  # a dropped player counts if started within N weeks
LOPSIDED_BAND_IDS = {"decline", "hard"}  # trade_value_bands ladder
COLLUSION_MIN_TRADES = 2
COLLUSION_MIN_LOPSIDED = 2
COLLUSION_STRONG_LOPSIDED = 3
INACTIVE_MIN_WEEKS = 4  # identical lineup + no moves for N weeks

NON_STARTING_SLOTS = {"BN", "IR", "TAXI"}

_POSITION_ALIASES = {
    "DE": "DL", "DT": "DL", "NT": "DL", "EDGE": "DL",
    "OLB": "LB", "ILB": "LB", "MLB": "LB",
    "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB",
    "PK": "K", "DST": "DEF", "D/ST": "DEF",
}

_SLOT_ELIGIBLE: dict[str, frozenset[str]] = {
    "QB": frozenset({"QB"}),
    "RB": frozenset({"RB"}),
    "WR": frozenset({"WR"}),
    "TE": frozenset({"TE"}),
    "K": frozenset({"K"}),
    "DEF": frozenset({"DEF"}),
    "DL": frozenset({"DL"}),
    "LB": frozenset({"LB"}),
    "DB": frozenset({"DB"}),
    "FLEX": frozenset({"RB", "WR", "TE"}),
    "WRRB_FLEX": frozenset({"RB", "WR"}),
    "REC_FLEX": frozenset({"WR", "TE"}),
    "SUPER_FLEX": frozenset({"QB", "RB", "WR", "TE"}),
    "OP": frozenset({"QB", "RB", "WR", "TE"}),
    "IDP_FLEX": frozenset({"DL", "LB", "DB"}),
}

LIMITS = [
    "Sleeper's public API does not say who was injured or inactive in a past week. We exclude bye weeks and "
    "players who scored zero, but a late scratch can still look like a lineup mistake.",
    "Sleeper does not publish your league's draft-order rule, so context defaults to \"unknown\" unless you set it.",
    "Trade value uses current player values and does not price draft picks, so trades involving picks are never "
    "scored as lopsided.",
    "Lineup history is read from each week's saved Sleeper matchup. Playoff weeks are excluded, so toilet-bowl "
    "and consolation brackets are never counted.",
    "Best-ball leagues have no manager-set lineups, so lineup signals are not shown for them.",
    "This is a prompt to look, not a verdict. Every flag lists innocent explanations to check first.",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _norm_position(value: Any) -> str:
    text = str(value or "").strip().upper()
    return _POSITION_ALIASES.get(text, text)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _starting_slots(roster_positions: Sequence[Any]) -> list[str]:
    return [str(p).upper() for p in roster_positions or [] if str(p).upper() not in NON_STARTING_SLOTS]


def best_lineup(
    slots: Sequence[str],
    candidates: Mapping[str, tuple[str, float]],
) -> tuple[dict[int, str], float]:
    """Best legal lineup. ``candidates``: player_id -> (position, score).

    Fills the narrowest slots first and takes the best remaining eligible
    player for each. That is optimal when flex eligibility nests (RB/WR/TE
    inside FLEX inside SUPER_FLEX), which covers Sleeper's standard formats.
    Returns ({slot_index: player_id}, total).
    """

    order = sorted(range(len(slots)), key=lambda i: (len(_SLOT_ELIGIBLE.get(slots[i], ())) or 99, i))
    used: set[str] = set()
    chosen: dict[int, str] = {}
    total = 0.0
    for idx in order:
        eligible = _SLOT_ELIGIBLE.get(slots[idx])
        if not eligible:
            continue
        best_id = None
        best_score = None
        for pid, (pos, score) in candidates.items():
            if pid in used or pos not in eligible:
                continue
            if best_score is None or score > best_score:
                best_id, best_score = pid, score
        if best_id is not None and best_score is not None:
            used.add(best_id)
            chosen[idx] = best_id
            total += best_score
    return chosen, total


# ---------------------------------------------------------------------------
# Weekly facts
# ---------------------------------------------------------------------------

def _entry_points(entry: Mapping[str, Any]) -> dict[str, float]:
    raw = entry.get("players_points") if isinstance(entry.get("players_points"), Mapping) else {}
    out: dict[str, float] = {}
    for pid, pts in raw.items():
        value = _num(pts)
        if value is not None:
            out[str(pid)] = value
    return out


def _typical_scores(weekly: Mapping[int, Sequence[Mapping[str, Any]]], week: int) -> dict[str, float]:
    """player_id -> median of earlier non-zero weekly scores in this league."""

    history: dict[str, list[float]] = {}
    for wk, entries in weekly.items():
        if wk >= week:
            continue
        for entry in entries or []:
            for pid, pts in _entry_points(entry).items():
                if pts != 0.0:
                    history.setdefault(pid, []).append(pts)
    return {pid: float(statistics.median(vals)) for pid, vals in history.items() if vals}


def _week_played(entries: Sequence[Mapping[str, Any]]) -> bool:
    """A week counts once at least one team has non-zero points."""

    return any((_num(e.get("points")) or 0.0) != 0.0 for e in entries or [])


def _analyse_entry(
    entry: Mapping[str, Any],
    *,
    week: int,
    slots: Sequence[str],
    meta: Mapping[str, Mapping[str, Any]],
    typical: Mapping[str, float],
    on_bye: Callable[[str, int], bool],
    excluded: set[str],
) -> dict[str, Any]:
    points = _entry_points(entry)
    starters = [str(s) for s in (entry.get("starters") or [])]
    name = lambda pid: str((meta.get(pid) or {}).get("name") or f"Player {pid}")  # noqa: E731
    pos_of = lambda pid: _norm_position((meta.get(pid) or {}).get("position"))  # noqa: E731
    team_of = lambda pid: str((meta.get(pid) or {}).get("team") or "")  # noqa: E731

    roster_ids = [str(p) for p in (entry.get("players") or []) if str(p) not in excluded]
    starter_set = {s for s in starters if s and s != "0"}

    actual = _num(entry.get("points"))
    if actual is None:
        actual = sum(points.get(s, 0.0) for s in starter_set)

    # Hindsight best lineup (real points). Context only: everyone has a gap.
    hind_cands = {
        pid: (pos_of(pid), points[pid])
        for pid in set(roster_ids) | starter_set
        if pid in points and pos_of(pid)
    }
    _, optimal = best_lineup(slots, hind_cands)

    empty_slots = sum(1 for s in starters if not s or s == "0")
    if len(starters) < len(slots):
        empty_slots += len(slots) - len(starters)

    bench = [pid for pid in roster_ids if pid not in starter_set]
    live_bench = [pid for pid in bench if points.get(pid, 0.0) > 0.0 and pos_of(pid)]

    dead_alt: list[str] = []
    bye_alt: list[str] = []
    for idx, pid in enumerate(starters):
        if not pid or pid == "0":
            continue
        slot_ok = _SLOT_ELIGIBLE.get(slots[idx]) if idx < len(slots) else None
        if not slot_ok or not any(pos_of(b) in slot_ok for b in live_bench):
            continue
        if on_bye(team_of(pid), week):
            bye_alt.append(pid)
        elif points.get(pid, 0.0) == 0.0:
            dead_alt.append(pid)

    # Ex-ante view: typical scores known before the week. Bench players who
    # scored zero are assumed unavailable (benefit of the doubt).
    ex_ante_available = False
    exante_gap = 0.0
    best_typ = 0.0
    worst_swap: tuple[str, str, float, float] | None = None
    typ_cands = {
        pid: (pos_of(pid), typical[pid])
        for pid in roster_ids
        if pid in typical and pos_of(pid) and pid not in bye_alt
        and not on_bye(team_of(pid), week)
        and (points.get(pid, 0.0) != 0.0 or pid in starter_set)
    }
    if typ_cands and any(s in typical for s in starter_set):
        ex_ante_available = True
        chosen, best_typ = best_lineup(slots, typ_cands)
        starters_typ = 0.0
        for s in starter_set:
            if on_bye(team_of(s), week):
                continue
            starters_typ += typical.get(s, points.get(s, 0.0))
        exante_gap = max(0.0, best_typ - starters_typ)
        # The single most telling swap: best benched player vs weakest starter at a shared position.
        for pid in chosen.values():
            if pid in starter_set:
                continue
            pos = pos_of(pid)
            rivals = [s for s in starter_set if s in typical and pos_of(s) == pos]
            if rivals:
                weakest = min(rivals, key=lambda s: typical[s])
                diff = typical[pid] - typical[weakest]
                if diff > 0 and (worst_swap is None or diff > worst_swap[3] - worst_swap[2]):
                    worst_swap = (pid, weakest, typical[weakest], typical[pid])

    n_slots = max(1, len(slots))
    sev_slots = _clamp(((empty_slots_with_alt(empty_slots, live_bench)) + len(dead_alt) + len(bye_alt)) / n_slots / SLOT_FULL_COUNT_SHARE)
    if ex_ante_available and best_typ > 0:
        sev_exante = _clamp((exante_gap / best_typ) / EXANTE_FULL_GAP_PCT)
        severity = 0.6 * sev_exante + 0.4 * sev_slots
    else:
        sev_exante = None
        severity = 0.8 * sev_slots

    return {
        "actual": round(actual, 2),
        "best_possible": round(optimal, 2),
        "efficiency": round(actual / optimal, 3) if optimal > 0 else None,
        "empty_slots": empty_slots,
        "dead_starters": [pid for pid in dead_alt],
        "bye_starters": [pid for pid in bye_alt],
        "exante_gap": round(exante_gap, 2),
        "exante_best": round(best_typ, 2),
        "exante_available": ex_ante_available,
        "swap": worst_swap,
        "points": points,
        "severity": severity,
        "starters": starters,
        "names": {pid: name(pid) for pid in set(starters) | set(roster_ids) if pid and pid != "0"},
        "positions": {pid: pos_of(pid) for pid in set(starters) | set(roster_ids) if pid and pid != "0"},
    }


def empty_slots_with_alt(empty_slots: int, live_bench: Sequence[str]) -> int:
    """An empty slot only counts against the manager if a live body sat on the bench."""

    return min(empty_slots, len(live_bench))


# ---------------------------------------------------------------------------
# Standings context
# ---------------------------------------------------------------------------

def _week_results(entries: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """roster_id -> win credit (1 / 0.5 / 0) from head-to-head pairs."""

    groups: dict[Any, list[Mapping[str, Any]]] = {}
    for e in entries or []:
        mid = e.get("matchup_id")
        if mid is None:
            continue
        groups.setdefault(mid, []).append(e)
    out: dict[str, float] = {}
    for pair in groups.values():
        if len(pair) != 2:
            continue
        a, b = pair
        pa, pb = _num(a.get("points")) or 0.0, _num(b.get("points")) or 0.0
        ra, rb = str(a.get("roster_id")), str(b.get("roster_id"))
        if pa == pb:
            out[ra] = out.get(ra, 0.0) + 0.5
            out[rb] = out.get(rb, 0.0) + 0.5
        elif pa > pb:
            out[ra] = out.get(ra, 0.0) + 1.0
            out[rb] = out.get(rb, 0.0) + 0.0
        else:
            out[rb] = out.get(rb, 0.0) + 1.0
            out[ra] = out.get(ra, 0.0) + 0.0
    return out


def _context_at(
    wins_before: Mapping[str, float],
    *,
    weeks_left: int,
    playoff_teams: int,
) -> dict[str, str]:
    """roster_id -> 'eliminated' | 'clinched' | 'alive' using exact win bounds.

    Same conservative certification as modules.playoff_simulator (ties on
    wins are unresolved, so only strict separation certifies anything).
    """

    if playoff_teams <= 0 or not wins_before:
        return {rid: "unknown" for rid in wins_before}
    ids = list(wins_before)
    floors = [wins_before[r] for r in ids]
    out: dict[str, str] = {}
    for i, rid in enumerate(ids):
        ceiling_i = floors[i] + weeks_left
        others = [j for j in range(len(ids)) if j != i]
        ahead_for_sure = sum(1 for j in others if floors[j] > ceiling_i)
        can_catch = sum(1 for j in others if floors[j] + weeks_left >= floors[i])
        if ahead_for_sure >= playoff_teams:
            out[rid] = "eliminated"
        elif can_catch < playoff_teams:
            out[rid] = "clinched"
        else:
            out[rid] = "alive"
    return out


def _context_multiplier(state: str, draft_rule: str) -> float:
    if state == "eliminated":
        if draft_rule == DRAFT_RULE_RECORD:
            return CONTEXT_MULT_ELIMINATED_RECORD
        if draft_rule == DRAFT_RULE_LOTTERY:
            return CONTEXT_MULT_ELIMINATED_OTHER
        return CONTEXT_MULT_UNKNOWN
    if state == "clinched":
        return CONTEXT_MULT_CLINCHED
    if state == "alive":
        return CONTEXT_MULT_ALIVE
    return CONTEXT_MULT_UNKNOWN


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

def _asset_value(asset: Mapping[str, Any], values: Mapping[str, Mapping[str, Any]]) -> float | None:
    if asset.get("kind") != "player":
        return None
    row = values.get(str(asset.get("player_id")))
    return _num((row or {}).get("value_score")) if row else None


def trade_legs(
    transactions: Iterable[Mapping[str, Any]],
    values: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Two-party player-for-player trades with a value delta per side.

    ``delta`` is value received minus value sent, in the same units as the
    trade engine's score ladder (modules.trade_value_bands). Trades involving
    picks, three-way trades, or any unvalued player are returned with
    ``valued=False`` and are never scored.
    """

    out: list[dict[str, Any]] = []
    for tx in transactions:
        if str(tx.get("type")) != "trade" or str(tx.get("status")) != "complete":
            continue
        sides = [s for s in (tx.get("sides") or []) if isinstance(s, Mapping)]
        roster_ids = [_int(s.get("roster_id")) for s in sides]
        has_picks = bool(tx.get("draft_picks"))
        legs: dict[int, dict[str, Any]] = {}
        valued = len(sides) == 2 and not has_picks
        for side, rid in zip(sides, roster_ids):
            got = [_asset_value(a, values) for a in side.get("receives") or [] if isinstance(a, Mapping)]
            sent = [_asset_value(a, values) for a in side.get("drops") or [] if isinstance(a, Mapping)]
            if any(v is None for v in got) or any(v is None for v in sent) or not got or not sent:
                valued = False
            legs[rid] = {
                "received": sum(v for v in got if v is not None),
                "sent": sum(v for v in sent if v is not None),
                "received_names": [str(a.get("name") or a.get("player_id")) for a in side.get("receives") or [] if isinstance(a, Mapping)],
                "sent_names": [str(a.get("name") or a.get("player_id")) for a in side.get("drops") or [] if isinstance(a, Mapping)],
            }
        out.append({
            "transaction_id": tx.get("transaction_id"),
            "week": _int(tx.get("week")),
            "roster_ids": roster_ids,
            "valued": valued,
            "has_picks": has_picks,
            "legs": legs,
        })
    return out


def _lopsided_losers(legs: Sequence[Mapping[str, Any]]) -> list[tuple[int, int, float, dict[str, Any]]]:
    """(loser_roster, winner_roster, loser_delta, trade) for valued lopsided trades."""

    result: list[tuple[int, int, float, dict[str, Any]]] = []
    for trade in legs:
        if not trade["valued"]:
            continue
        a, b = trade["roster_ids"]
        for loser, winner in ((a, b), (b, a)):
            leg = trade["legs"][loser]
            delta = leg["received"] - leg["sent"]
            if trade_value_bands.band_for_score(delta).id in LOPSIDED_BAND_IDS:
                result.append((loser, winner, delta, dict(trade)))
    return result


def collusion_pairs(legs: Sequence[Mapping[str, Any]], team_names: Mapping[str, str]) -> list[dict[str, Any]]:
    by_pair: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for trade in legs:
        if len(trade["roster_ids"]) == 2:
            by_pair.setdefault(tuple(sorted(trade["roster_ids"])), []).append(trade)  # type: ignore[arg-type]
    lopsided = _lopsided_losers(legs)
    pairs: list[dict[str, Any]] = []
    for (a, b), trades in by_pair.items():
        if len(trades) < COLLUSION_MIN_TRADES:
            continue
        # Same direction: the same manager is the repeated winner.
        wins: dict[int, list[tuple[int, float, dict[str, Any]]]] = {a: [], b: []}
        for loser, winner, delta, trade in lopsided:
            if {loser, winner} == {a, b}:
                wins[winner].append((loser, delta, trade))
        beneficiary = max(wins, key=lambda r: len(wins[r]))
        count = len(wins[beneficiary])
        if count < COLLUSION_MIN_LOPSIDED:
            continue
        giver = b if beneficiary == a else a
        band = BAND_STRONG if count >= COLLUSION_STRONG_LOPSIDED else BAND_LOOK
        lines = []
        for _, delta, trade in sorted(wins[beneficiary], key=lambda x: x[1]):
            leg = trade["legs"][giver]
            label = trade_value_bands.band_for_score(delta).direction_label.replace("against you", "against them")
            lines.append(
                f"Week {trade['week']}: {team_names.get(str(giver), 'Team')} sent "
                f"{', '.join(leg['sent_names'][:3])} for {', '.join(leg['received_names'][:3])} ({label})."
            )
        pairs.append({
            "roster_ids": [a, b],
            "beneficiary_roster_id": beneficiary,
            "giver_roster_id": giver,
            "beneficiary_name": team_names.get(str(beneficiary), f"Team {beneficiary}"),
            "giver_name": team_names.get(str(giver), f"Team {giver}"),
            "trades_between": len(trades),
            "lopsided_same_direction": count,
            "band": band,
            "band_label": BAND_LABELS[band],
            "confidence": "medium" if count >= COLLUSION_STRONG_LOPSIDED else "low",
            "evidence": lines,
            "innocent_explanations": [
                "The two managers are friends or family and trade often.",
                "One side is rebuilding and the other contending, so value is not the only goal.",
                "Current values can miss injuries, scarcity or league-specific scoring.",
                "Draft picks, which this check does not price, may have changed hands off-platform.",
            ],
        })
    pairs.sort(key=lambda p: (-p["lopsided_same_direction"], -p["trades_between"]))
    return pairs


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def build_league_integrity(
    *,
    league: Mapping[str, Any],
    rosters: Sequence[Mapping[str, Any]],
    weekly: Mapping[int, Sequence[Mapping[str, Any]]],
    player_meta: Mapping[str, Mapping[str, Any]],
    profiles: Mapping[str, Mapping[str, Any]],
    transactions: Sequence[Mapping[str, Any]] = (),
    values: Mapping[str, Mapping[str, Any]] | None = None,
    on_bye: Callable[[str, int], bool] | None = None,
    draft_rule: str = DRAFT_RULE_UNKNOWN,
    current_week: int | None = None,
) -> dict[str, Any]:
    """Assemble the per-team integrity report. See module docstring."""

    values = values or {}
    on_bye = on_bye or (lambda team, week: False)
    draft_rule = draft_rule if draft_rule in DRAFT_RULES else DRAFT_RULE_UNKNOWN
    settings = league.get("settings") if isinstance(league.get("settings"), Mapping) else {}
    slots = _starting_slots(league.get("roster_positions") or [])
    playoff_start = _int(settings.get("playoff_week_start"), 0)
    playoff_teams = _int(settings.get("playoff_teams"), 0)
    reg_weeks = playoff_start - 1 if playoff_start > 1 else 0
    team_names = {str(rid): str((p or {}).get("team_name") or f"Team {rid}") for rid, p in profiles.items()}
    owner_names = {str(rid): str((p or {}).get("owner_name") or "") for rid, p in profiles.items()}

    base: dict[str, Any] = {
        "ok": True,
        "reason": "",
        "draft_order_rule": draft_rule,
        "limits": list(LIMITS),
        "teams": [],
        "collusion": [],
        "inactive": [],
        "weeks_evaluated": 0,
        "summary": {BAND_FINE: 0, BAND_LOOK: 0, BAND_STRONG: 0, BAND_NOT_ENOUGH: 0},
    }
    if _int(settings.get("best_ball")) == 1:
        return {**base, "reason": "best_ball"}
    if not slots or not weekly:
        return {**base, "reason": "no_lineup_data"}

    played_weeks = sorted(
        w for w, entries in weekly.items()
        if _week_played(entries) and (not reg_weeks or w <= reg_weeks) and (current_week is None or w < current_week)
    )
    # A week still in progress (the current Sleeper leg) is never evaluated.
    if not played_weeks:
        return {**base, "reason": "not_enough_weeks"}

    excluded_by_roster: dict[str, set[str]] = {}
    for r in rosters:
        excluded_by_roster[str(r.get("roster_id"))] = {
            str(p) for p in list(r.get("reserve") or []) + list(r.get("taxi") or [])
        }

    # Pass 1: per-roster per-week facts, then league-adjusted severity.
    facts: dict[str, dict[int, dict[str, Any]]] = {}
    wins_before: dict[int, dict[str, float]] = {}
    running: dict[str, float] = {str(r.get("roster_id")): 0.0 for r in rosters}
    for week in sorted(w for w in weekly if (not reg_weeks or w <= reg_weeks)):
        wins_before[week] = dict(running)
        for rid, credit in _week_results(weekly[week]).items():
            running[rid] = running.get(rid, 0.0) + credit
    for week in played_weeks:
        typical = _typical_scores(weekly, week)
        for entry in weekly[week]:
            rid = str(entry.get("roster_id"))
            facts.setdefault(rid, {})[week] = _analyse_entry(
                entry, week=week, slots=slots, meta=player_meta, typical=typical,
                on_bye=on_bye, excluded=excluded_by_roster.get(rid, set()),
            )
    for week in played_weeks:
        sevs = [f[week]["severity"] for f in facts.values() if week in f]
        baseline = statistics.median(sevs) if sevs else 0.0
        for f in facts.values():
            if week in f:
                f[week]["adjusted"] = max(0.0, f[week]["severity"] - baseline)

    # Context per week.
    context: dict[int, dict[str, str]] = {}
    for week in played_weeks:
        left = max(0, reg_weeks - (week - 1)) if reg_weeks else 0
        context[week] = _context_at(wins_before.get(week, {}), weeks_left=left, playoff_teams=playoff_teams) \
            if reg_weeks and playoff_teams else {rid: "unknown" for rid in wins_before.get(week, {})}

    # Roster / transaction behaviour.
    legs = trade_legs(transactions, values)
    lopsided = _lopsided_losers(legs)
    roster_notes = _roster_behaviour(
        transactions=transactions, facts=facts, legs=legs, lopsided=lopsided, values=values,
        player_meta=player_meta, played_weeks=played_weeks, team_names=team_names,
    )

    teams: list[dict[str, Any]] = []
    for r in rosters:
        rid = str(r.get("roster_id"))
        weeks_f = facts.get(rid, {})
        teams.append(_score_team(
            rid=rid, weeks=weeks_f, context=context, draft_rule=draft_rule,
            notes=roster_notes.get(rid, {}), team_name=team_names.get(rid, f"Team {rid}"),
            owner_name=owner_names.get(rid, ""), n_slots=len(slots),
        ))
    order = {BAND_STRONG: 0, BAND_LOOK: 1, BAND_FINE: 2, BAND_NOT_ENOUGH: 3}
    teams.sort(key=lambda t: (order[t["band"]], -t["score"], t["team_name"]))
    for t in teams:
        base["summary"][t["band"]] += 1

    result = {
        **base,
        "teams": teams,
        "weeks_evaluated": len(played_weeks),
        "last_week": played_weeks[-1],
        "regular_season_weeks": reg_weeks or None,
        "collusion": collusion_pairs(legs, team_names),
        "inactive": _inactive_managers(facts, transactions, team_names, owner_names, played_weeks),
    }
    if len(played_weeks) < MIN_WEEKS_FOR_BAND:
        result["reason"] = "not_enough_weeks"
    return result


def _roster_behaviour(
    *,
    transactions: Sequence[Mapping[str, Any]],
    facts: Mapping[str, Mapping[int, Mapping[str, Any]]],
    legs: Sequence[Mapping[str, Any]],
    lopsided: Sequence[tuple[int, int, float, dict[str, Any]]],
    values: Mapping[str, Mapping[str, Any]],
    player_meta: Mapping[str, Mapping[str, Any]],
    played_weeks: Sequence[int],
    team_names: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    notes: dict[str, dict[str, Any]] = {}

    def bucket(rid: Any) -> dict[str, Any]:
        return notes.setdefault(str(rid), {"drops": [], "sells": [], "lopsided": [], "adds": 0, "moves": 0})

    for tx in transactions:
        if str(tx.get("status")) != "complete":
            continue
        week = _int(tx.get("week"))
        for rid in tx.get("roster_ids") or []:
            bucket(rid)["moves"] += 1
        for side in tx.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            rid = str(side.get("roster_id"))
            if str(tx.get("type")) in {"waiver", "free_agent"} and any(
                a.get("kind") == "player" for a in side.get("receives") or [] if isinstance(a, Mapping)
            ):
                bucket(rid)["adds"] += 1
            for asset in side.get("drops") or []:
                if not isinstance(asset, Mapping) or asset.get("kind") != "player":
                    continue
                if str(tx.get("type")) == "trade":
                    continue
                pid = str(asset.get("player_id"))
                recent = [w for w in played_weeks if week - RECENT_STARTER_WEEKS <= w < week + 1]
                started = []
                for w in recent:
                    f = (facts.get(rid) or {}).get(w)
                    if f and pid in f["starters"]:
                        started.append(w)
                # A player who has not scored recently is an ordinary cut.
                if started and (facts.get(rid) or {}).get(started[-1], {}).get("points", {}).get(pid, 0.0) > 0:
                    nm = (player_meta.get(pid) or {}).get("name") or asset.get("name") or pid
                    bucket(rid)["drops"].append(
                        {"week": week, "player": str(nm), "text": f"Week {week}: dropped {nm}, who started for them in week {started[-1]}."}
                    )
    # Sells: shipping player value for picks (reuses the existing buy/sell read).
    for tx in transactions:
        if str(tx.get("type")) != "trade" or str(tx.get("status")) != "complete":
            continue
        picks = tx.get("draft_picks") or []
        for side in tx.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            rid = _int(side.get("roster_id"))
            sent = [_asset_value(a, values) for a in side.get("drops") or [] if isinstance(a, Mapping)]
            got = [_asset_value(a, values) for a in side.get("receives") or [] if isinstance(a, Mapping)]
            sent_v = sum(v for v in sent if v is not None)
            got_v = sum(v for v in got if v is not None)
            picks_in = sum(1 for p in picks if p.get("to_roster_id") == rid)
            picks_out = sum(1 for p in picks if p.get("from_roster_id") == rid)
            if sent_v > got_v and picks_in > picks_out:
                names = ", ".join(str(a.get("name") or a.get("player_id")) for a in side.get("drops") or [] if isinstance(a, Mapping) and a.get("kind") == "player")[:80]
                bucket(rid)["sells"].append({"week": _int(tx.get("week")), "text": f"Week {_int(tx.get('week'))}: traded {names or 'players'} for picks."})
    for loser, winner, delta, trade in lopsided:
        leg = trade["legs"][loser]
        label = trade_value_bands.band_for_score(delta).direction_label.replace("against you", "against them")
        bucket(loser)["lopsided"].append({
            "week": trade["week"],
            "text": f"Week {trade['week']}: sent {', '.join(leg['sent_names'][:3])} to {team_names.get(str(winner), 'another team')} for "
                    f"{', '.join(leg['received_names'][:3])} ({label}).",
        })
    return notes


def _score_team(
    *,
    rid: str,
    weeks: Mapping[int, Mapping[str, Any]],
    context: Mapping[int, Mapping[str, str]],
    draft_rule: str,
    notes: Mapping[str, Any],
    team_name: str,
    owner_name: str,
    n_slots: int,
) -> dict[str, Any]:
    ordered = sorted(weeks)
    n = len(ordered)
    flagged: list[int] = []
    adj_by_week: dict[int, float] = {}
    states: dict[int, str] = {}
    for w in ordered:
        state = context.get(w, {}).get(rid, "unknown")
        states[w] = state
        adj = weeks[w].get("adjusted", 0.0) * _context_multiplier(state, draft_rule)
        adj_by_week[w] = adj
        if adj >= WEEK_FLAG_THRESHOLD:
            flagged.append(w)

    longest = run = 0
    prev = None
    for w in ordered:
        if w in flagged:
            run = run + 1 if prev is not None and prev in flagged else 1
            longest = max(longest, run)
        prev = w
    latest = 0
    for w in reversed(ordered):
        if w in flagged:
            latest += 1
        else:
            break

    f = len(flagged)
    persistence = _clamp(0.5 * min(1.0, longest / 3) + 0.5 * min(1.0, (f / n) / 0.5)) if n else 0.0
    if f < MIN_FLAGGED_FOR_LOOK:
        persistence = min(persistence, 0.35)
    magnitude = statistics.mean(adj_by_week[w] for w in flagged) if flagged else 0.0
    lineup = persistence * min(1.0, magnitude / 0.6)

    drops, sells, lopsided = notes.get("drops", []), notes.get("sells", []), notes.get("lopsided", [])
    adds = int(notes.get("adds", 0))
    roster_score = _clamp(
        0.45 * min(1.0, len(drops) / 2) + 0.35 * min(1.0, len(sells) / 2) + 0.35 * min(1.0, len(lopsided) / 1)
        + (0.10 if adds == 0 and n >= 5 else 0.0)
    )
    score = LINEUP_WEIGHT * lineup + ROSTER_WEIGHT * roster_score

    corroborated = lineup >= STRONG_MIN_LINEUP and roster_score >= STRONG_MIN_ROSTER
    if n < MIN_WEEKS_FOR_BAND:
        band = BAND_NOT_ENOUGH
    elif f >= MIN_FLAGGED_FOR_STRONG and n >= MIN_WEEKS_FOR_STRONG and score >= STRONG_SCORE and corroborated:
        band = BAND_STRONG
    elif f >= MIN_FLAGGED_FOR_LOOK and score >= LOOK_SCORE:
        band = BAND_LOOK
    else:
        band = BAND_FINE

    # Context is the team's standing now (latest evaluated week); the weeks
    # flagged while still alive are called out separately in the context line.
    dominant = states[ordered[-1]] if ordered else "unknown"
    interpretation, context_line = _interpret(dominant, draft_rule, roster_score > 0, f)
    alive_flagged = [w for w in flagged if states.get(w) == "alive"]
    if flagged and dominant == "eliminated" and alive_flagged:
        context_line += (
            f" {len(alive_flagged)} of the {f} flagged weeks came before elimination, while the team was still in the race."
        )

    evidence: list[dict[str, Any]] = []
    for w in sorted(flagged, key=lambda x: -adj_by_week[x])[:4]:
        evidence.append({"kind": "lineup", "week": w, "text": _week_line(w, weeks[w])})
    for item in (drops + sells + lopsided)[:4]:
        evidence.append({"kind": "roster", "week": item["week"], "text": item["text"]})
    if f:
        evidence.append({
            "kind": "persistence", "week": None,
            "text": f"{f} of {n} weeks flagged; longest run {longest}"
                    + (f"; still flagged in the latest {latest}." if latest else "."),
        })
    evidence.append({"kind": "context", "week": None, "text": context_line})

    if band == BAND_NOT_ENOUGH:
        confidence = "low"
    elif n >= 6 and corroborated:
        confidence = "high"
    elif n >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "roster_id": _int(rid),
        "team_name": team_name,
        "owner_name": owner_name,
        "band": band,
        "band_label": BAND_LABELS[band],
        "score": round(score, 3),
        "confidence": confidence,
        "interpretation": interpretation,
        "context": dominant,
        "weeks": {"evaluated": n, "flagged": f, "longest_streak": longest, "latest_streak": latest},
        "factors": {
            "lineup": {"score": round(lineup, 3), "persistence": round(persistence, 3)},
            "roster": {
                "score": round(roster_score, 3),
                "productive_drops": len(drops),
                "sell_trades": len(sells),
                "lopsided_trades": len(lopsided),
                "waiver_adds": adds,
            },
        },
        "evidence": evidence if band in {BAND_LOOK, BAND_STRONG} else evidence[-1:],
        "innocent_explanations": _innocent(band, weeks, flagged, drops, lopsided, dominant),
        "series": [
            {"week": w, "actual": weeks[w]["actual"], "best_possible": weeks[w]["best_possible"],
             "efficiency": weeks[w]["efficiency"], "flagged": w in flagged}
            for w in ordered
        ],
    }


def _week_line(week: int, f: Mapping[str, Any]) -> str:
    parts: list[str] = []
    swap = f.get("swap")
    names = f.get("names") or {}
    if swap:
        bench_id, start_id, start_typ, bench_typ = swap
        parts.append(
            f"started {names.get(start_id, start_id)} (typical {start_typ:.1f}) over "
            f"{names.get(bench_id, bench_id)} (typical {bench_typ:.1f})"
        )
    if f.get("empty_slots"):
        parts.append(f"{f['empty_slots']} empty starting slot(s) with players on the bench")
    if f.get("dead_starters"):
        parts.append("started " + ", ".join(names.get(p, p) for p in f["dead_starters"][:2]) + " who scored 0 with live bench options")
    if f.get("bye_starters"):
        parts.append("started " + ", ".join(names.get(p, p) for p in f["bye_starters"][:2]) + " on a bye with live bench options")
    if f.get("exante_available") and f.get("exante_gap"):
        parts.append(f"{f['exante_gap']:.1f} pts below the best typical lineup")
    return f"Week {week}: " + ("; ".join(parts) if parts else "lineup well below what the roster could field") + "."


def _interpret(state: str, draft_rule: str, has_roster: bool, flagged: int) -> tuple[str, str]:
    if not flagged:
        return "none", "No weeks flagged."
    if state == "eliminated":
        if draft_rule == DRAFT_RULE_RECORD:
            return "possible_tanking", (
                "Eliminated from the playoffs, and draft order follows record, so a losing incentive exists. "
                "Whether it is allowed is a league-rules call."
            )
        if draft_rule == DRAFT_RULE_LOTTERY:
            return "possible_tanking", (
                "Eliminated from the playoffs; a lottery or non-record draft order weakens the incentive to lose."
            )
        return "possible_tanking", (
            "Eliminated from the playoffs. We cannot read the league's draft-order rule from Sleeper, "
            "so the incentive is unknown."
        )
    if state == "clinched":
        return "possible_resting", "Already clinched a playoff spot, so resting players is a plausible reason."
    if state == "alive":
        return "possible_inactivity", (
            "Still in the playoff race, so losing offers no benefit. This pattern fits inactivity or "
            "mismanagement better than tanking."
        )
    return "unclear", "Standings context is unavailable (no playoff settings), so the pattern is not interpreted."


def _innocent(
    band: str, weeks: Mapping[int, Mapping[str, Any]], flagged: Sequence[int],
    drops: Sequence[Any], lopsided: Sequence[Any], state: str,
) -> list[str]:
    if band in {BAND_FINE, BAND_NOT_ENOUGH}:
        return []
    out = ["Late injury or inactive designations after the manager last set the lineup look identical in saved data."]
    if any(weeks[w].get("bye_starters") for w in flagged):
        out.append("A bye-week conflict at a thin position.")
    if any(weeks[w].get("empty_slots") for w in flagged):
        out.append("The manager may be away or the app may have failed to save a lineup.")
    if drops:
        out.append("Dropped players may have had injuries, suspensions or roster-limit pressure we cannot see.")
    if lopsided:
        out.append("Current trade values can miss injuries, scarcity and league-specific scoring.")
    if state == "alive":
        out.append("A still-alive team may simply be new, busy or unfamiliar with the roster rules.")
    out.append("Check with the manager before drawing a conclusion.")
    return out


def _inactive_managers(
    facts: Mapping[str, Mapping[int, Mapping[str, Any]]],
    transactions: Sequence[Mapping[str, Any]],
    team_names: Mapping[str, str],
    owner_names: Mapping[str, str],
    played_weeks: Sequence[int],
) -> list[dict[str, Any]]:
    moves_by_week: dict[str, set[int]] = {}
    for tx in transactions:
        for rid in tx.get("roster_ids") or []:
            moves_by_week.setdefault(str(rid), set()).add(_int(tx.get("week")))
    out: list[dict[str, Any]] = []
    for rid, weeks in facts.items():
        ordered = sorted(weeks)
        unchanged = 0
        best_run = 0
        for prev, cur in zip(ordered, ordered[1:]):
            same = weeks[prev]["starters"] == weeks[cur]["starters"]
            moved = cur in moves_by_week.get(rid, set())
            unchanged = unchanged + 1 if same and not moved else 0
            best_run = max(best_run, unchanged)
        unset = [w for w in ordered if weeks[w]["empty_slots"] and weeks[w]["empty_slots"] > 0]
        no_moves = not moves_by_week.get(rid)
        reasons = []
        if best_run + 1 >= INACTIVE_MIN_WEEKS and no_moves:
            reasons.append(f"Same starting lineup for {best_run + 1} weeks in a row and no roster moves all season.")
        if len(unset) >= 2:
            reasons.append(f"Empty starting slot(s) in {len(unset)} weeks (weeks {', '.join(str(w) for w in unset[:5])}).")
        if reasons:
            out.append({
                "roster_id": _int(rid),
                "team_name": team_names.get(rid, f"Team {rid}"),
                "owner_name": owner_names.get(rid, ""),
                "evidence": reasons,
                "innocent_explanations": [
                    "A settled lineup of healthy starters needs no changes.",
                    "The manager may be away, or may manage the team outside the weeks we can see.",
                ],
            })
    out.sort(key=lambda x: -len(x["evidence"]))
    return out
