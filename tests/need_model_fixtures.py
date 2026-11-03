"""Hand-built results of the one need model (``roster_value_model.assess_needs``).

Consumers read the model's output; their tests state the room they want
("RB is a need, WR has two surplus players") instead of building a league
big enough for the lineup model to say it.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from modules import model_status, roster_value_model

_NEED_TYPES = {"primary": "short-term starter coverage", "secondary": "short-term starter coverage"}


def room(
    position: str,
    tier: str = "covered",
    *,
    slot: str | None = None,
    rank: int | None = None,
    of: int = 12,
    surplus_ids: Sequence[str] = (),
    injured: Sequence[str] = (),
    future_gap: bool = False,
    strength: bool = False,
    starters: int = 1,
) -> dict[str, Any]:
    """One position of an ``assess_needs`` result."""

    if rank is None:
        rank = {"primary": 11, "secondary": 10, "watch": 7, "covered": 3}[tier]
    pct = 0.0 if of <= 1 else (rank - 1) / (of - 1)
    need_type = _NEED_TYPES.get(tier) or ("long-term upside" if future_gap else "covered")
    return {
        "position": position,
        "tier": tier,
        "score": round(pct, 3),
        "starters": starters,
        "weakest_slot": {"slot": slot or position, "rank": rank, "of": of, "pct": pct, "ppg": 10.0},
        "slot_ranks": [],
        "upgrade": {"ppw": 0.0, "ros": 0.0, "name": "", "player_id": "", "ppg": None},
        "healthy_count": starters + 1,
        "required_depth": starters + 1,
        "depth_short": 0,
        "injured_starters": list(injured),
        "aging_starters": [],
        "future_gap": future_gap,
        "need_type": need_type,
        "relative_weakness": pct >= roster_value_model.SECONDARY_RANK_PCT,
        "strength": strength,
        "surplus": bool(surplus_ids) and tier in ("watch", "covered"),
        "surplus_player_ids": list(surplus_ids) if tier in ("watch", "covered") else [],
        "reasons": [f"{slot or position} is {rank}th of {of} in the league"] if pct >= 0.45 else [],
    }


def team_needs(*rooms: dict[str, Any]) -> dict[str, Any]:
    """An ``assess_needs`` result, rooms in the order given (weakest first)."""

    return {
        "model_version": roster_value_model.MODEL_VERSION,
        "positions": list(rooms),
        "needed_positions": [r["position"] for r in rooms if r["tier"] in ("primary", "secondary")],
        "model_status": model_status.ok(),
    }


def league_needs(by_roster: dict[Any, dict[str, Any]]) -> roster_value_model.LeagueNeeds:
    return roster_value_model.LeagueNeeds(
        by_roster={str(k): v for k, v in by_roster.items()}, status=model_status.ok()
    )
