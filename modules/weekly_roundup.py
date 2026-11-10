"""Weekly Team Roundup: hindsight lineup review for one team and one completed week.

Answers "what did my lineup leave on the bench, and could I have known?":

1. Actuals: every starter's real points (Sleeper ``starters_points`` /
   ``players_points``, already in the league's own scoring).
2. Hindsight-optimal lineup from the roster that week, respecting the league's
   real lineup slots (``roster_positions``: FLEX, SUPER_FLEX, REC_FLEX, IDP...).
3. The swaps that would have gained points, and the total left on the bench.
4. A predictability tag per swap, from point-in-time projections: what the
   model would have said using only games played BEFORE that week (the same
   retroactive replay ``scripts/projection_scoreboard.py`` uses). Sleeper keeps
   no point-in-time injury history, so availability is not replayed; the
   ``method`` note in every payload says so. The tag is deliberately
   conservative: the backtest (docs/projection-scoreboard.md) shows the model
   does not beat Sleeper's own projections, so "foreseeable" needs a clear edge.
5. A templated takeaway (no LLM) and a season-to-date "bench regret" tally.

Everything here is a pure function of injected data. The thin orchestrator
``build_roundup`` takes already-fetched Sleeper payloads; services own the I/O.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

FORESEEABLE = "foreseeable"
COIN_FLIP = "coin_flip"
UNFORESEEABLE = "unforeseeable"
PREDICTABILITY_LABELS = {
    FORESEEABLE: "Foreseeable",
    COIN_FLIP: "Coin flip",
    UNFORESEEABLE: "Unforeseeable",
}

# A miss is "foreseeable" only when the projection favoured the benched player
# by at least this many points AND by this share of the pair's combined spread.
MIN_FORESEEABLE_EDGE_PTS = 2.0
MIN_FORESEEABLE_EDGE_SD_SHARE = 0.75
# Swaps smaller than this are noise, not mistakes worth surfacing.
MIN_SWAP_GAIN_PTS = 0.5
# A week's leftover points under this read as "a clean week".
CLEAN_WEEK_BENCH_PTS = 3.0

METHOD_NOTE = (
    "Predictability uses retroactive point-in-time projections: what our model would have "
    "projected using only games played before this week. Injury and inactive reports are "
    "not replayed, so this reflects usage and matchup history rather than that week's news. "
    "Reception scoring is adjusted to your league; other custom scoring is approximated. "
    "Treat tags as context, not a verdict."
)

_NEG = -1.0e6

_FLEX_ELIGIBLE: dict[str, frozenset[str]] = {
    "FLEX": frozenset({"RB", "WR", "TE"}),
    "SUPER_FLEX": frozenset({"QB", "RB", "WR", "TE"}),
    "REC_FLEX": frozenset({"WR", "TE"}),
    "WRRB_FLEX": frozenset({"WR", "RB"}),
    "WR/RB": frozenset({"WR", "RB"}),
    "IDP_FLEX": frozenset({"DL", "LB", "DB"}),
}
_FIXED_SLOTS = frozenset({"QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB"})
_POSITION_ALIASES = {"DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "MLB": "LB", "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB", "PK": "K", "DST": "DEF", "D/ST": "DEF"}
_NON_STARTING_SLOTS = frozenset({"BN", "IR", "TAXI"})


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(out) or math.isinf(out) else out


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_position(value: Any) -> str:
    pos = _text(value).upper()
    return _POSITION_ALIASES.get(pos, pos)


def starting_slots(roster_positions: Sequence[Any] | None) -> list[str]:
    """League starting slots in Sleeper order (aligned with the ``starters`` array)."""

    return [
        _text(slot).upper()
        for slot in (roster_positions or [])
        if _text(slot) and _text(slot).upper() not in _NON_STARTING_SLOTS
    ]


def slot_accepts(slot: str, position: str) -> bool:
    pos = normalize_position(position)
    if slot in _FLEX_ELIGIBLE:
        return pos in _FLEX_ELIGIBLE[slot]
    return slot in _FIXED_SLOTS and slot == pos


def _hungarian_max(weight: list[list[float]]) -> list[int]:
    """Max-weight assignment for an n x m matrix (n <= m). Returns the chosen
    column per row. Classic O(n^2 m) potentials algorithm on negated weights."""

    n = len(weight)
    m = len(weight[0]) if n else 0
    cost = [[-w for w in row] for row in weight]
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j], way[j] = cur, j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            assignment[p[j] - 1] = j - 1
    return assignment


def optimal_lineup(
    slots: Sequence[str],
    points: Mapping[str, float],
    positions: Mapping[str, str],
) -> list[tuple[str, str | None]]:
    """Best possible lineup: ``[(slot, player_id | None)]`` in slot order.

    Exact (assignment problem), so overlapping flex rules (REC_FLEX + WRRB_FLEX
    + SUPER_FLEX) are handled correctly. A slot with no eligible player stays
    empty (``None``).
    """

    pids = [pid for pid in points if pid in positions]
    if not slots:
        return []
    n = len(slots)
    # Pad with "empty" columns so every slot can be left unfilled.
    columns: list[str | None] = [*pids, *([None] * n)]
    weight = [
        [
            (_NEG if pid is None else points[pid]) if (pid is None or slot_accepts(slot, positions[pid])) else _NEG * 2
            for pid in columns
        ]
        for slot in slots
    ]
    chosen = _hungarian_max(weight)
    out: list[tuple[str, str | None]] = []
    for slot, col in zip(slots, chosen):
        pid = columns[col] if col >= 0 else None
        if pid is not None and not slot_accepts(slot, positions[pid]):
            pid = None
        out.append((slot, pid))
    return out


# --- projections -------------------------------------------------------------


def league_scoring_profile(league: Mapping[str, Any] | None) -> dict[str, float]:
    """Reception value and TE-premium bonus from the league's own scoring settings."""

    scoring = (league or {}).get("scoring_settings") if isinstance(league, Mapping) else None
    scoring = scoring if isinstance(scoring, Mapping) else {}
    return {"rec": _num(scoring.get("rec"), 0.0), "te_bonus": _num(scoring.get("bonus_rec_te"), 0.0)}


def to_league_points(ppr_points: float, *, position: str, receptions: float, scoring: Mapping[str, float]) -> float:
    """PPR points -> the league's reception scoring, given that game's receptions."""

    pos = normalize_position(position)
    if pos not in {"RB", "WR", "TE"}:
        return ppr_points
    out = ppr_points - (1.0 - _num(scoring.get("rec"), 1.0)) * receptions
    if pos == "TE":
        out += _num(scoring.get("te_bonus"), 0.0) * receptions
    return out


def swap_predictability(
    *,
    started_actual: float,
    benched_actual: float,
    started_proj: Mapping[str, Any] | None,
    benched_proj: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Tag one missed swap using point-in-time projections.

    Projections are ``{"points": float, "sd": float}`` (league scoring; ``sd`` is
    the half-width of the ~68% interval).

    - foreseeable: the projection favoured the benched player by a clear margin
      (>= MIN_FORESEEABLE_EDGE_PTS and >= 0.75 of the pair's combined spread).
    - unforeseeable: the projection favoured the player started, and the result
      fell outside the typical range (benched player spiked or starter flopped).
    - coin_flip: everything else, including pairs with no usable projection
      (new players, DEF/IDP), which is stated in ``reason``.
    """

    if not started_proj or not benched_proj:
        return {
            "predictability": COIN_FLIP,
            "edge": None,
            "reason": "Not enough earlier-game history to project one of these players.",
        }
    pa, sa = _num(started_proj.get("points")), max(0.5, _num(started_proj.get("sd"), 4.0))
    pb, sb = _num(benched_proj.get("points")), max(0.5, _num(benched_proj.get("sd"), 4.0))
    edge = pb - pa
    spread = math.hypot(sa, sb)
    if edge >= max(MIN_FORESEEABLE_EDGE_PTS, MIN_FORESEEABLE_EDGE_SD_SHARE * spread):
        return {
            "predictability": FORESEEABLE,
            "edge": round(edge, 1),
            "reason": f"Our projection had the benched player ahead by {edge:.1f} pts before the week.",
        }
    tail = benched_actual > pb + sb or started_actual < pa - sa
    if edge <= 0 and tail:
        return {
            "predictability": UNFORESEEABLE,
            "edge": round(edge, 1),
            "reason": "The projection favoured the player you started; this result was outside either player's typical range.",
        }
    return {
        "predictability": COIN_FLIP,
        "edge": round(edge, 1),
        "reason": "The projections were close enough that either start was reasonable.",
    }


# --- one week ----------------------------------------------------------------


def _player_view(pid: str | None, meta: Mapping[str, Mapping[str, Any]], points: Mapping[str, float]) -> dict[str, Any]:
    info = meta.get(pid or "") or {}
    return {
        "player_id": pid,
        "name": _text(info.get("name")) or (pid or ""),
        "position": normalize_position(info.get("position")),
        "team": _text(info.get("team")),
        "points": round(_num(points.get(pid or "")), 1) if pid else 0.0,
    }


def build_week_roundup(
    *,
    week: int,
    slots: Sequence[str],
    starters: Sequence[Any],
    players_points: Mapping[str, Any],
    meta: Mapping[str, Mapping[str, Any]],
    projections: Mapping[str, Mapping[str, Any]] | None = None,
    excluded_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Hindsight review of one week for one team.

    ``starters`` is Sleeper's slot-ordered list (``"0"`` = empty slot);
    ``players_points`` maps every rostered player to his points that week.
    ``excluded_ids`` (IR/taxi) cannot be slotted in the hindsight lineup.
    """

    projections = projections or {}
    excluded = {str(x) for x in excluded_ids}
    points = {str(pid): _num(pts) for pid, pts in players_points.items()}
    positions = {pid: normalize_position((meta.get(pid) or {}).get("position")) for pid in points}
    positions = {pid: pos for pid, pos in positions.items() if pos}
    slot_list = list(slots)
    started = [(_text(pid) if _text(pid) not in {"", "0"} else None) for pid in list(starters)[: len(slot_list)]]
    started += [None] * (len(slot_list) - len(started))

    actual_total = sum(points.get(pid, 0.0) for pid in started if pid)
    pool = {pid: pts for pid, pts in points.items() if pid not in excluded or pid in started}
    best = optimal_lineup(slot_list, pool, positions)
    optimal_total = sum(points.get(pid, 0.0) for _, pid in best if pid)
    # Hindsight can never be worse than what was actually started.
    if optimal_total < actual_total:
        best = list(zip(slot_list, started))
        optimal_total = actual_total
    bench_points = round(optimal_total - actual_total, 1)

    optimal_ids = {pid for _, pid in best if pid}
    started_ids = {pid for pid in started if pid}
    outs = [(slot_list[i], pid) for i, pid in enumerate(started) if pid and pid not in optimal_ids]
    outs += [(slot_list[i], None) for i, pid in enumerate(started) if pid is None]
    ins = sorted((pid for pid in optimal_ids if pid not in started_ids), key=lambda p: -points[p])

    # Pair each dropped starter with the best benched player who could fill that
    # very slot; largest gains first so the headline miss is the real one.
    swaps_raw: list[tuple[float, str, str | None, str]] = []
    remaining_ins = list(ins)
    pending = sorted(outs, key=lambda o: points.get(o[1] or "", 0.0))
    unmatched: list[tuple[str, str | None]] = []
    for slot, out_pid in pending:
        choice = next((p for p in remaining_ins if slot_accepts(slot, positions.get(p, ""))), None)
        if choice is None:
            unmatched.append((slot, out_pid))
            continue
        remaining_ins.remove(choice)
        swaps_raw.append((points[choice] - points.get(out_pid or "", 0.0), out_pid or "", choice, slot))
    for (slot, out_pid), choice in zip(unmatched, list(remaining_ins)):
        swaps_raw.append((points[choice] - points.get(out_pid or "", 0.0), out_pid or "", choice, slot))

    swaps: list[dict[str, Any]] = []
    for gain, out_pid, in_pid, slot in sorted(swaps_raw, key=lambda s: -s[0]):
        if gain < MIN_SWAP_GAIN_PTS or not in_pid:
            continue
        tag = swap_predictability(
            started_actual=points.get(out_pid, 0.0),
            benched_actual=points[in_pid],
            started_proj=projections.get(out_pid) if out_pid else None,
            benched_proj=projections.get(in_pid),
        )
        swaps.append(
            {
                "slot": slot,
                "started": _player_view(out_pid or None, meta, points),
                "benched": _player_view(in_pid, meta, points),
                "gain": round(gain, 1),
                "started_projection": _proj_view(projections.get(out_pid)) if out_pid else None,
                "benched_projection": _proj_view(projections.get(in_pid)),
                **tag,
            }
        )

    foreseeable_pts = round(sum(s["gain"] for s in swaps if s["predictability"] == FORESEEABLE), 1)
    unlisted = round(bench_points - sum(s["gain"] for s in swaps), 1)
    lineup = [
        {"slot": slot, "actual": _player_view(pid, meta, points), "optimal": _player_view(best[i][1], meta, points)}
        for i, (slot, pid) in enumerate(zip(slot_list, started))
    ]
    result = {
        "week": int(week),
        "actual_points": round(actual_total, 1),
        "optimal_points": round(optimal_total, 1),
        "left_on_bench": bench_points,
        "foreseeable_points": foreseeable_pts,
        "lineup": lineup,
        "swaps": swaps,
        "unattributed_points": max(0.0, unlisted),
    }
    result["takeaway"] = week_takeaway(result)
    return result


def _proj_view(proj: Mapping[str, Any] | None) -> dict[str, float] | None:
    if not proj:
        return None
    return {"points": round(_num(proj.get("points")), 1), "sd": round(_num(proj.get("sd")), 1)}


def week_takeaway(result: Mapping[str, Any]) -> str:
    swaps = list(result.get("swaps") or [])
    left = _num(result.get("left_on_bench"))
    if left < CLEAN_WEEK_BENCH_PTS or not swaps:
        return "Clean week: your lineup was within a few points of the best possible one."
    counts = {tag: sum(1 for s in swaps if s["predictability"] == tag) for tag in PREDICTABILITY_LABELS}
    n = len(swaps)
    foreseeable = counts[FORESEEABLE]
    if foreseeable == 0 and counts[UNFORESEEABLE] == n:
        return "Every miss this week was a spike or flop nobody could have projected. No lineup lesson here."
    if foreseeable == 0:
        return "None of your misses had a clear projection edge before the week. These were close calls, not blunders."
    if foreseeable == n:
        noun = "miss was" if n == 1 else "misses were"
        return f"{'This' if n == 1 else 'All ' + str(n)} {noun} visible before kickoff: the benched player had a clear projection edge."
    return f"{foreseeable} of {n} misses were visible before kickoff (a clear projection edge); the rest were close calls or surprises."


def push_headline(result: Mapping[str, Any]) -> str:
    """Lock-screen text. No league or team names (see push_triggers privacy rule)."""

    week = int(result.get("week") or 0)
    left = _num(result.get("left_on_bench"))
    swaps = list(result.get("swaps") or [])
    if left < CLEAN_WEEK_BENCH_PTS or not swaps:
        return f"Your week {week} roundup is ready: a clean lineup week, nearly optimal."
    top = swaps[0]
    return (
        f"Your week {week} roundup is ready: you left {left:.1f} pts on the bench. "
        f"Biggest miss: {top['started']['name']} ({top['started']['points']:.1f}) over "
        f"{top['benched']['name']} ({top['benched']['points']:.1f})."
    )


# --- season ------------------------------------------------------------------


def season_tally(weeks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Season-to-date bench regret across the weeks reviewed."""

    rows = [
        {
            "week": int(w["week"]),
            "actual_points": _num(w.get("actual_points")),
            "optimal_points": _num(w.get("optimal_points")),
            "left_on_bench": _num(w.get("left_on_bench")),
            "foreseeable_points": _num(w.get("foreseeable_points")),
        }
        for w in weeks
    ]
    rows.sort(key=lambda r: r["week"])
    n = len(rows)
    total = round(sum(r["left_on_bench"] for r in rows), 1)
    foreseeable = round(sum(r["foreseeable_points"] for r in rows), 1)
    per_week = round(total / n, 1) if n else 0.0
    share = round(foreseeable / total, 2) if total > 0 else 0.0
    if n == 0:
        summary = ""
    elif total <= 0:
        summary = f"Over {n} week{'s' if n != 1 else ''} you never left points on the bench."
    else:
        summary = (
            f"Over {n} week{'s' if n != 1 else ''} you left {total:.1f} pts on the bench "
            f"({per_week:.1f} per week); about {round(share * 100)}% of that was foreseeable."
        )
    return {
        "weeks_reviewed": n,
        "total_left_on_bench": total,
        "avg_left_on_bench": per_week,
        "foreseeable_points": foreseeable,
        "foreseeable_share": share,
        "weeks": rows,
        "summary": summary,
    }


# --- orchestration (data already fetched) ------------------------------------


def point_in_time_projections(
    *,
    week: int,
    player_ids: Iterable[str],
    meta: Mapping[str, Mapping[str, Any]],
    weekly_by_player: Mapping[str, Sequence[Mapping[str, Any]]],
    scoring: Mapping[str, float],
    baseline_fn: Any,
) -> dict[str, dict[str, float]]:
    """``{player_id: {points, sd}}`` in league scoring from games before ``week``.

    ``baseline_fn`` is ``modules.player_projections.baseline_weekly_points``
    (injected so tests need no stats cache). A player without usable earlier
    production gets no entry; callers then tag the pair as a coin flip.
    """

    rows = [{"player_id": pid, "position": normalize_position((meta.get(pid) or {}).get("position"))} for pid in player_ids]
    base = baseline_fn(rows, weekly_by_player=dict(weekly_by_player), as_of_week=int(week)) or {}
    out: dict[str, dict[str, float]] = {}
    for pid, entry in base.items():
        history = [r for r in (weekly_by_player.get(pid) or []) if r.get("week") is not None and int(r["week"]) < int(week)]
        recs = [_num(r.get("receptions")) for r in history if r.get("receptions") is not None]
        rec_pg = sum(recs) / len(recs) if recs else 0.0
        pos = normalize_position((meta.get(pid) or {}).get("position"))
        out[pid] = {
            "points": to_league_points(_num(entry.get("ppg")), position=pos, receptions=rec_pg, scoring=scoring),
            "sd": _num(entry.get("sd"), 4.0),
        }
    return out


def build_roundup(
    *,
    league: Mapping[str, Any],
    roster: Mapping[str, Any],
    matchups_by_week: Mapping[int, Sequence[Mapping[str, Any]]],
    week: int,
    meta: Mapping[str, Mapping[str, Any]],
    weekly_by_player: Mapping[str, Sequence[Mapping[str, Any]]],
    baseline_fn: Any,
) -> dict[str, Any]:
    """Roundup for ``week`` plus the season tally over every week up to it.

    Weeks where the roster has no matchup row are skipped. Returns
    ``{"roundup": {...} | None, "season": {...}, "method": str}``.
    """

    slots = starting_slots(league.get("roster_positions"))
    scoring = league_scoring_profile(league)
    roster_id = roster.get("roster_id")
    excluded = [str(p) for p in (roster.get("reserve") or [])] + [str(p) for p in (roster.get("taxi") or [])]

    def one_week(w: int) -> dict[str, Any] | None:
        mine = next(
            (m for m in matchups_by_week.get(w) or [] if str(m.get("roster_id")) == str(roster_id)),
            None,
        )
        if not mine or not isinstance(mine.get("players_points"), Mapping) or not mine.get("starters"):
            return None
        pts = {str(k): v for k, v in mine["players_points"].items()}
        projections = point_in_time_projections(
            week=w,
            player_ids=list(pts),
            meta=meta,
            weekly_by_player=weekly_by_player,
            scoring=scoring,
            baseline_fn=baseline_fn,
        )
        return build_week_roundup(
            week=w,
            slots=slots,
            starters=mine["starters"],
            players_points=pts,
            meta=meta,
            projections=projections,
            excluded_ids=excluded,
        )

    results = {w: r for w in sorted(matchups_by_week) if w <= week and (r := one_week(w)) is not None}
    return {
        "roundup": results.get(week),
        "season": season_tally(list(results.values())),
        "method": METHOD_NOTE,
    }


# --- I/O wrapper shared by the API and the push sweep -------------------------


def _meta_from_sleeper_players(players: Mapping[str, Any], ids: Iterable[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for pid in ids:
        raw = players.get(pid) if isinstance(players, Mapping) else None
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("full_name")) or f"{_text(raw.get('first_name'))} {_text(raw.get('last_name'))}".strip()
        position = raw.get("position") or ((raw.get("fantasy_positions") or [""])[0] if raw.get("fantasy_positions") else "")
        out[pid] = {"name": name or pid, "position": _text(position), "team": _text(raw.get("team"))}
    return out


def completed_week(league: Mapping[str, Any], league_id: str) -> tuple[int, dict[int, list[dict[str, Any]]]]:
    """Latest completed week (same detection League Recaps uses) and the raw
    Sleeper matchups for weeks 1..that week. ``(0, {})`` offseason / not started."""

    from modules import league_recaps, sleeper

    _, _, max_history_week = league_recaps.league_history_window(league)
    by_week = sleeper.get_matchups_for_weeks(league_id, range(1, max(1, max_history_week) + 1))
    rows = league_recaps.build_matchup_history_rows(league_id, max_history_week, fetch_matchups=lambda lid, w: by_week.get(w) or [])
    week = league_recaps.completed_recap_week(league, rows)
    if week <= 0:
        return 0, {}
    return week, {w: list(by_week.get(w) or []) for w in range(1, week + 1)}


def build_for_league(
    league_id: str,
    league: Mapping[str, Any],
    roster: Mapping[str, Any],
    *,
    week: int | None = None,
    completed: tuple[int, dict[int, list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    """Fetch what is needed and build the roundup for ``week`` (default: latest
    completed). Returns ``{"max_completed_week", "week", "roundup", "season",
    "method", "reason"}``; ``reason`` is non-empty when there is nothing to show."""

    from modules import player_projections, sleeper

    latest, matchups = completed if completed is not None else completed_week(league, league_id)
    if latest <= 0:
        return {"max_completed_week": 0, "week": 0, "roundup": None, "season": None, "method": METHOD_NOTE, "reason": "no_completed_week"}
    target = latest if week is None else max(1, min(int(week), latest))
    ids = {str(pid) for rows in matchups.values() for m in rows if str(m.get("roster_id")) == str(roster.get("roster_id")) for pid in (m.get("players_points") or {})}
    meta = _meta_from_sleeper_players(sleeper.get_players() or {}, ids)
    try:
        season = int(league.get("season") or sleeper.default_player_stats_season())
    except (TypeError, ValueError):
        season = sleeper.default_player_stats_season()
    weekly = sleeper.cached_season_weekly_map(season)
    built = build_roundup(
        league=league,
        roster=roster,
        matchups_by_week=matchups,
        week=target,
        meta=meta,
        weekly_by_player=weekly,
        baseline_fn=player_projections.baseline_weekly_points,
    )
    built.update({"max_completed_week": latest, "week": target, "reason": "" if built["roundup"] else "no_matchup_data"})
    return built


def gate_for_free(payload: dict[str, Any]) -> dict[str, Any]:
    """Free tier: headline numbers, takeaway and the single biggest swap.
    Full lineup, remaining swaps and the season tally are Pro."""

    out = dict(payload)
    roundup = out.get("roundup")
    if roundup:
        roundup = dict(roundup)
        roundup["swaps_total"] = len(roundup.get("swaps") or [])
        roundup["swaps"] = list(roundup.get("swaps") or [])[:1]
        roundup["lineup"] = []
        out["roundup"] = roundup
    out["season"] = None
    return out
