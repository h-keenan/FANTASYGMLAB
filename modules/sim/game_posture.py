"""AI posture that follows the standings (``posture_v`` 1): contenders and rebuilders react mid-season.

Before it, an AI team's win-now / future horizon was a persona constant for the whole game (``GameTeam.horizon``), so a "contender" with a 2-6 record still
bought and a "rebuilder" in first place still sold. Here each AI team keeps a **posture** (buy / sell / hold) that is re-read at the start of every
regular-season week from several real factors, and that moves the team's horizon (and how often it shops) for everything the AI decides that week:
trade value, who it asks for, waiver claims, the block.

Factors (``playoff_odds``): the record so far (shrunk toward .500 early), the lineup it can actually field (so a hot start on a thin roster is not believed
blindly, and a bad start on a loaded one is not written off), the games left, and where the playoff line sits (the expected wins of the last team in
and the first team out, against the spread two teams' remaining schedules carry). The odds are a normal approximation, not a simulation.

Hysteresis: a team enters ``buy`` at 65% odds and leaves it below 45%, enters ``sell`` at 12% and leaves it above 30%, and any change holds for at least
two weeks, so a team on the line does not flip every Sunday; buy and sell are never swapped directly (it passes through hold). The posture is event-sourced
(``posture`` events carry only the changes) so replays are exact; it is cleared at the start of each season and starts after ``MIN_GAMES`` games.
"""

from __future__ import annotations

import math
from typing import Any

from modules.sim.game_eval import Evaluator
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSnapshot

BUY, SELL = "buy", "sell"
MIN_GAMES = 4          # games played before the standings say anything
LAST_WEEKS = 1         # no change in the final regular-season week
ENTER_BUY, EXIT_BUY = 0.65, 0.45
ENTER_SELL, EXIT_SELL = 0.12, 0.30
MIN_TENURE = 2         # weeks a posture (or a return to hold) is kept
BUY_SHIFT, SELL_SHIFT = 0.25, -0.30
ACTIVITY_BOOST = 1.25  # a buyer or a seller shops more than a team standing pat


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def playoff_odds(snap: GameSnapshot, state: GameState, ev: Evaluator | None = None) -> dict[str, float]:
    """Each team's chance of making the playoffs from the record, the roster it can field and the games left."""

    ev = ev or Evaluator(snap, state)
    S = snap.settings
    totals = {t: ev.lineup_total(state.rosters[t]) if state.rosters[t] else 0.0 for t in snap.tids}
    mean_total = sum(totals.values()) / max(1, len(totals)) or 1.0
    exp: dict[str, float] = {}
    left: dict[str, int] = {}
    for t in snap.tids:
        rec = state.stand[t]
        gp = int(rec["w"] + rec["l"] + rec["t"])
        g = max(0, S.regular_weeks - gp)
        p_rec = (rec["w"] + 0.5 * rec["t"] + 3.0) / (gp + 6.0)
        p_pow = min(0.85, max(0.15, 0.5 + 1.2 * (totals[t] / mean_total - 1.0)))
        p = 0.6 * p_rec + 0.4 * p_pow
        exp[t] = rec["w"] + 0.5 * rec["t"] + g * p
        left[t] = g
    ranked = sorted(exp.values(), reverse=True)
    k = max(1, min(S.playoff_teams, len(ranked) - 1))
    line = 0.5 * (ranked[k - 1] + ranked[k])
    out = {}
    for t in snap.tids:
        sigma = math.sqrt(0.48 * left[t] + 0.8)
        out[t] = round(_phi((exp[t] - line) / sigma), 4)
    return out


def next_stance(stance: str, odds: float) -> str:
    """The hysteresis rule: the stance a team in ``stance`` takes at these odds."""

    if stance == BUY:
        return "" if odds < EXIT_BUY else BUY
    if stance == SELL:
        return "" if odds > EXIT_SELL else SELL
    if odds >= ENTER_BUY:
        return BUY
    if odds <= ENTER_SELL:
        return SELL
    return ""


def update_posture(em: Emitter, snap: GameSnapshot, state: GameState, week: int) -> dict[str, dict[str, Any]]:
    """Start of a regular-season week: re-read every AI team's posture, emit one ``posture`` event with the changes."""

    S = snap.settings
    if S.posture_v < 1 or state.status != "in_season" or week > S.regular_weeks - LAST_WEEKS:
        return {}
    if min(int(r["w"] + r["l"] + r["t"]) for r in state.stand.values()) < MIN_GAMES:
        return {}
    odds = playoff_odds(snap, state)
    changes: dict[str, dict[str, Any]] = {}
    for t in snap.teams:
        if t.is_user:
            continue
        cur = state.posture.get(t.tid) or {}
        if cur and week - int(cur.get("week", 0)) < MIN_TENURE:
            continue
        new = next_stance(cur.get("stance", ""), odds[t.tid])
        if new != cur.get("stance", ""):
            changes[t.tid] = {"stance": new, "week": week, "odds": odds[t.tid]}
    if changes:
        em.emit(week, "engine", "posture", teams=changes)
    return changes


def apply_posture(params: Any, stance: str) -> Any:
    """``params`` (a ``TeamParams``) shifted for a buy / sell posture: a buyer weighs this season's production more, a seller the future, both shop more."""

    from dataclasses import replace

    if stance == BUY:
        shift = BUY_SHIFT
    elif stance == SELL:
        shift = SELL_SHIFT
    else:
        return params
    return replace(params, horizon=min(0.95, max(0.05, params.horizon + shift)), activity=min(0.95, params.activity * ACTIVITY_BOOST) if params.activity > 0 else 0.0)


__all__ = ["BUY", "SELL", "playoff_odds", "next_stance", "update_posture", "apply_posture"]
