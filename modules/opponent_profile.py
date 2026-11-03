"""Opponent profile card: one league roster read the way a GM scouts it.

Everything here is a pure read of numbers the app already computes for every
roster (the league summary frame's per-position room scores, the rankings
frame's starter/bench/draft-capital ranks, the need model's per-room read,
``trade_hub_engine.roster_posture`` for direction). Nothing is invented:

- a position's strength is its rank among the league's rosters for that room;
- "surplus" and "need" are the one need model's call
  (``modules.roster_value_model``): a need is a room whose starting slots trail
  the league or are short or hurt, and a surplus is a room holding a healthy
  player beyond the starters and one cover who could start for a typical team.
  Neither is re-derived here from the rank;
- the trade angle only appears when one side's need meets the other side's
  surplus, and names a real surplus player to prefill the Trade Analyzer with.

When the inputs are too thin (tiny league, no picks data) the field is left
``None`` and the client shows nothing rather than a guess.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

POSITIONS: tuple[str, ...] = ("QB", "RB", "WR", "TE")
# Below this many rosters a "rank within the league" read is noise.
MIN_LEAGUE_SIZE = 4

_NEEDY = {"short_term_need"}


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(out) else out


def position_ranks(df_summary: pd.DataFrame, roster_id: Any) -> list[dict[str, Any]]:
    """Per-room league rank (1 = best) for one roster, from ``{pos}_score``."""

    if df_summary is None or df_summary.empty:
        return []
    target = str(roster_id)
    ids = df_summary["roster_id"].astype(str)
    if target not in set(ids):
        return []
    size = len(df_summary)
    out: list[dict[str, Any]] = []
    for position in POSITIONS:
        column = f"{position.lower()}_score"
        if column not in df_summary.columns:
            continue
        scores = pd.to_numeric(df_summary[column], errors="coerce").fillna(0.0)
        if float(scores.max()) <= 0:
            continue
        mine = float(scores[ids == target].iloc[0])
        rank = int((scores > mine).sum()) + 1
        out.append({"position": position, "rank": rank, "of": size, "score": round(mine, 1)})
    return out


def starter_bench_read(starter_rank: Any, bench_rank: Any, size: int) -> dict[str, Any] | None:
    """Starter strength vs bench depth, as league ranks and a plain label."""

    s, b = _num(starter_rank), _num(bench_rank)
    if s is None or b is None or size < MIN_LEAGUE_SIZE:
        return None
    gap = b - s
    threshold = max(3.0, round(size * 0.25))
    if gap >= threshold:
        label, note = "Starter-heavy", "Strong starting lineup, thin bench"
    elif gap <= -threshold:
        label, note = "Deep bench", "Bench ranks well above the starting lineup"
    else:
        label, note = "Balanced", "Starters and bench rank about the same"
    return {
        "starter_rank": int(s),
        "bench_rank": int(b),
        "of": size,
        "label": label,
        "note": note,
    }


def room_reads(
    ranks: Sequence[Mapping[str, Any]], model_rooms: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Tag each room, and list the surplus and need positions.

    ``model_rooms`` maps position -> ``{"classification", "surplus"}`` from the
    need model. A room that is a need is never also a surplus (the model only
    reports surplus for rooms that are not needs). The rank only labels the row
    (``item["rank"]``); it never decides the tag.
    """

    rows: list[dict[str, Any]] = []
    surplus: list[str] = []
    needs: list[str] = []
    for item in ranks:
        position = str(item["position"])
        room = model_rooms.get(position) or {}
        classification = str(room.get("classification") or "covered")
        tag = None
        if classification in _NEEDY:
            tag = "need"
            needs.append(position)
        elif room.get("surplus"):
            tag = "surplus"
            surplus.append(position)
        rows.append({**item, "classification": classification, "tag": tag})
    return rows, surplus, needs


def strongest_weakest(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if len(rows) < 2 or int(rows[0]["of"]) < MIN_LEAGUE_SIZE:
        return None, None
    best = min(rows, key=lambda r: (r["rank"], -float(r["score"])))
    worst = max(rows, key=lambda r: (r["rank"], -float(r["score"])))
    if best["position"] == worst["position"]:
        return None, None
    pick = lambda r: {"position": r["position"], "rank": r["rank"], "of": r["of"]}  # noqa: E731
    return pick(best), pick(worst)


def surplus_candidates(
    roster_df: pd.DataFrame | None, surplus_player_ids: Mapping[str, Sequence[str]], score_field: str
) -> dict[str, list[dict[str, Any]]]:
    """The need model's surplus players per position, best value first."""

    out: dict[str, list[dict[str, Any]]] = {}
    if roster_df is None or roster_df.empty:
        return out
    by_id = {str(row.get("player_id")): row for _, row in roster_df.iterrows()}
    for position, ids in surplus_player_ids.items():
        if position not in POSITIONS:
            continue
        for player_id in ids:
            row = by_id.get(str(player_id))
            value = _num(row.get(score_field)) if row is not None else None
            if row is None or value is None or value <= 0:
                continue
            out.setdefault(position, []).append(
                {
                    "player_id": str(player_id),
                    "name": str(row.get("name") or ""),
                    "position": position,
                    "team": str(row.get("team") or ""),
                    "_value": value,
                }
            )
    for players in out.values():
        players.sort(key=lambda p: -p["_value"])
    return out


def _public(player: Mapping[str, Any], *, side: str) -> dict[str, Any]:
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "position": player["position"],
        "team": player["team"],
        "side": side,
    }


def trade_angle(
    *,
    my_needs: Iterable[str],
    my_surplus: Iterable[str],
    their_needs: Iterable[str],
    their_surplus: Iterable[str],
    their_bench: Mapping[str, Sequence[Mapping[str, Any]]],
    my_bench: Mapping[str, Sequence[Mapping[str, Any]]],
    my_ranks: Mapping[str, int] | None = None,
    their_ranks: Mapping[str, int] | None = None,
) -> dict[str, Any] | None:
    """The best fit between my needs/surplus and theirs, or ``None`` when none.

    Two kinds of fit: I need a room they have surplus in ("want"), or they need
    a room I have surplus in ("give"). Within a kind the room with the widest
    league-rank gap between the two rosters wins, preferring a room that has a
    real bench player to name. ``target.side`` is "receive" when the prefill
    asks for their bench player and "send" when it offers one of mine; the
    web/mobile Trade Analyzer files either side from a single player id (the
    existing quick-add prefill).
    """

    my_ranks = my_ranks or {}
    their_ranks = their_ranks or {}
    my_need_set, their_surplus_set = set(my_needs), set(their_surplus)
    their_need_set, my_surplus_set = set(their_needs), set(my_surplus)

    def gap(position: str) -> int:
        return abs(int(my_ranks.get(position, 0)) - int(their_ranks.get(position, 0)))

    def ordered(positions: list[str], bench: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
        return sorted(positions, key=lambda p: (not bench.get(p), -gap(p), p))

    want = ordered([p for p in POSITIONS if p in my_need_set and p in their_surplus_set], their_bench)
    give = ordered([p for p in POSITIONS if p in their_need_set and p in my_surplus_set], my_bench)
    if not want and not give:
        return None

    parts: list[str] = []
    target: dict[str, Any] | None = None
    if want:
        position = want[0]
        parts.append(f"You are short at {position} and they have {position} depth.")
        candidates = their_bench.get(position) or []
        if candidates:
            target = _public(candidates[0], side="receive")
    if give:
        position = give[0]
        parts.append(f"They are short at {position} and you have {position} depth.")
        candidates = my_bench.get(position) or []
        if target is None and candidates:
            target = _public(candidates[0], side="send")
    return {"text": " ".join(parts), "target": target}


def pick_capital(
    row: Mapping[str, Any], flow: Mapping[str, Any] | None, size: int
) -> dict[str, Any] | None:
    """Future-pick capital: league rank, count, 1sts, and recent 1st flow."""

    rank = _num(row.get("draft_capital_rank"))
    count = _num(row.get("pick_count"))
    firsts = _num(row.get("first_rounders"))
    if rank is None and count is None:
        return None
    flow = flow or {}
    return {
        "rank": int(rank) if rank is not None else None,
        "of": size,
        "pick_count": int(count) if count is not None else None,
        "first_rounders": int(firsts) if firsts is not None else None,
        "firsts_acquired": int(flow.get("firsts_acquired") or 0),
        "firsts_sent": int(flow.get("firsts_sent") or 0),
    }
