"""How last season went, carried into next season's projection (``stability_v`` 1).

Pure and deterministic. Used only by the dynasty offseason (``game_dynasty.season_snapshot``) to move a player's hidden projection; nothing here is
ever shown to a user, and nothing that reaches a view reads it (``tests/test_sim_game_player_model.py`` keeps the ``game_*.py`` modules free of the
hidden season story, which is why this lives in its own module).

Before ``stability_v`` a player's projection aged by the age curve alone, so a breakout or a bust was pure noise that the next year erased: the
sim's realized year-over-year ratios were 0.83 / 0.79 / 0.88 for a WR 22 / TE 23 / RB 22 against the real panel's 1.05 / 1.14 / 1.07, and the spread
of projections only ever grew (a random walk), so a ten-season league ended up with a few stars and no middle class. Two terms fix the mechanism:

* **outcome carry** (``OUTCOME_WEIGHT``): the log of (realized / projected points per game) of the season just played, centered on the position's
  median result and clipped, enters next year's projection with weight 0.5. A projection is a posterior; last year's production is evidence;
* **regression to the typical starter** (``REVERSION``): each year the log-projection closes a share of its gap to the position's typical starter
  in the league's season-1 pool, so the spread of projections is stationary (an AR(1) rather than a random walk).
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from modules.sim import aging
from modules.sim.game_types import GameSnapshot

SKILL = ("QB", "RB", "WR", "TE")


def talent_center(root: GameSnapshot, anchor_rows: Mapping[str, Mapping[str, Any]], level_ranks: Mapping[str, int]) -> dict[str, float]:
    """The log-projection of a typical rostered starter at each position in the league's season-1 pool (the geometric mean of its top
    ``level_ranks[pos]`` players): what a projection regresses toward. Fixed for the life of the save."""

    cached = getattr(root, "_talent_center", None)
    if cached is None:
        cached = {}
        for pos in SKILL:
            means = sorted((r["mean"] for r in anchor_rows.values() if r["pos"] == pos and r["mean"] > 0), reverse=True)[: level_ranks[pos]]
            if means:
                cached[pos] = sum(math.log(m) for m in means) / len(means)
        object.__setattr__(root, "_talent_center", cached)
    return cached


def next_projection_shift(
    root: GameSnapshot, prev: GameSnapshot, season: int, anchor_rows: Mapping[str, Mapping[str, Any]], level_ranks: Mapping[str, int],
) -> dict[str, float]:
    """``{pid: log multiplier}`` to apply to each QB/RB/WR/TE's projection on top of his age curve, going into dynasty season ``season``.

    The realized side is read from the same season profile the engine played (``ScoringSession`` keys it by the game's season seed and the
    player), so it is a pure function of the save and costs nothing when the season was just played (the session is cached on the snapshot)."""

    from modules.sim.game_dynasty import season_seed
    from modules.sim.game_engine import session_for

    session = session_for(prev, season_seed(root.seed, season - 1))
    raw: dict[str, float] = {}
    for pid in prev.pids:
        p = prev.players[pid]
        if p.pos not in SKILL or p.mean <= 0.0:
            continue
        profile = session.profile(pid)  # the labelled FallbackModel has a season "talent" multiplier instead of the real model's story
        mult = float(getattr(profile, "season_multiplier", getattr(profile, "talent", 1.0)))
        raw[pid] = math.log(max(0.05, mult))
    center: dict[str, float] = {}
    for pos in SKILL:
        xs = sorted(v for pid, v in raw.items() if prev.players[pid].pos == pos)
        center[pos] = xs[len(xs) // 2] if xs else 0.0
    lo, hi = aging.OUTCOME_CLIP
    pull = talent_center(root, anchor_rows, level_ranks)
    out: dict[str, float] = {}
    for pid, v in raw.items():
        p = prev.players[pid]
        shift = aging.OUTCOME_WEIGHT * min(hi, max(lo, v - center[p.pos]))
        if p.pos in pull:
            shift -= aging.REVERSION * max(0.0, math.log(max(0.5, p.mean)) - pull[p.pos])  # one-sided: only a projection above the typical starter regresses down
        out[pid] = shift
    return out


__all__ = ["next_projection_shift", "talent_center"]
