"""Opponent defenses (``defense_v`` 1+): who an NFL player faces each week and how hard that defense is on his position.

Pure and deterministic: everything here is a function of the game's seed, the season, the week and the NFL team list, so nothing is stored and a
replay or a resume sees the same matchups. The strengths are PUBLIC (they feed the projections the user reads, so start/sit advice can use them);
the weekly stat lines stay random around them.

Model
-----
* Every NFL team has a latent strength per position group ``QB / RB / WR / TE``: a *pass defense* factor (QB, WR, TE) or *run defense* factor (RB)
  shared by the group (``LOADING``), plus a position-specific part, scaled to a per-position standard deviation ``SD``.
* The strength evolves like the real thing: an AR(1) in time (``RHO``) with the stationary spread kept, so a top defense stays good but not forever.
* The matchup factor on an offensive player's weekly expected points is ``exp(strength[opponent, pos])`` (above 1 = a soft defense), bounded to
  ``exp(+-CLIP)``.
* The weekly NFL schedule pairs the teams that are not on a bye that week (a seeded permutation per season/week). The game has no real NFL schedule;
  what matters is that a player's opponent is deterministic, public, and not repeated every week.

Calibration (``docs/audits/2026-11-sim-desk-logic-realism-audit.md``, "Implemented"): public fantasy-points-allowed tables show the best and worst
defense vs a position about +-12-18 percent from the league mean in one season, but about half of that is sample noise and schedule (year-to-year
correlation of points allowed by position is roughly 0.3-0.5, and the sim already draws the noise). The persistent part is what is modelled: a
best-to-worst spread of about 11 percent (QB) to 15 percent (TE) across 32 teams, within the product brief's 10-15 percent; QBs sit lowest because the
passer's own volume absorbs a good coverage (his targets are spread over several receivers), TEs highest because their usage is the most
matchup-dependent. K and DEF are not modelled. The repo carries no opponent-level data (the panel has no opponent column), so these are the
documented-public-knowledge values, not fitted ones.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Mapping

import numpy as np

from modules.sim.rng import WorldRng

POSITIONS = ("QB", "RB", "WR", "TE")
SD = {"QB": 0.025, "RB": 0.028, "WR": 0.031, "TE": 0.034}  # standard deviation of log strength across teams (best-to-worst is about 4.1 sd at 32 teams)
UNIT = {"QB": 0, "WR": 0, "TE": 0, "RB": 1}  # 0 = pass defense, 1 = run defense
LOADING = 0.7  # share of a position's strength that is the unit's (pass / run), the rest is its own
RHO = 0.5  # year-to-year persistence of a defense's strength
CLIP = 0.12


def _is_team(t: str) -> bool:
    return bool(t) and t != "FA"


def nfl_teams(players: Mapping[str, object], bye_weeks: Mapping[str, int]) -> tuple[str, ...]:
    out = {t for t in bye_weeks if _is_team(t)}
    for p in players.values():
        t = str(getattr(p, "nfl_team", "") or "")
        if _is_team(t):
            out.add(t)
    return tuple(sorted(out))


@lru_cache(maxsize=256)
def _latent(seed: int, teams: tuple[str, ...], season: int) -> np.ndarray:
    """(teams, 2 + 4) standard-normal latents of ``season``: columns 0-1 the pass / run unit, 2-5 the QB / RB / WR / TE own part."""

    draw = WorldRng(seed).stream(season, "gdefense", 0).standard_normal((len(teams), 2 + len(POSITIONS)))
    if season <= 1:
        return draw
    return RHO * _latent(seed, teams, season - 1) + math.sqrt(1.0 - RHO * RHO) * draw


@lru_cache(maxsize=256)
def strengths(seed: int, teams: tuple[str, ...], season: int) -> dict[str, dict[str, float]]:
    """``{team: {pos: log strength}}`` for ``season`` (positive = a defense that gives up points to that position)."""

    z = _latent(seed, teams, max(1, season))
    own = math.sqrt(1.0 - LOADING * LOADING)
    out: dict[str, dict[str, float]] = {}
    for i, t in enumerate(teams):
        row = {}
        for j, pos in enumerate(POSITIONS):
            x = SD[pos] * (LOADING * z[i, UNIT[pos]] + own * z[i, 2 + j])
            row[pos] = max(-CLIP, min(CLIP, float(x)))
        out[t] = row
    return out


@lru_cache(maxsize=1024)
def _week_pairs(seed: int, teams: tuple[str, ...], byes: tuple[tuple[str, int], ...], season: int, week: int) -> dict[str, str]:
    bye = dict(byes)
    active = [t for t in teams if bye.get(t, 0) != week]
    perm = WorldRng(seed).stream(season, "gnflopp", int(week)).permutation(len(active))
    order = [active[int(i)] for i in perm]
    out: dict[str, str] = {}
    for i in range(0, len(order) - 1, 2):
        a, b = order[i], order[i + 1]
        out[a], out[b] = b, a
    return out


class Matchups:
    """The matchups of one season of one game."""

    def __init__(self, seed: int, season: int, teams: tuple[str, ...], byes: Mapping[str, int]) -> None:
        self.seed, self.season, self.teams = int(seed), max(1, int(season)), teams
        self.byes = tuple(sorted((t, int(w)) for t, w in byes.items() if _is_team(t)))

    def opponent(self, team: str, week: int) -> str | None:
        return _week_pairs(self.seed, self.teams, self.byes, self.season, int(week)).get(team)

    def strength(self, team: str, pos: str) -> float:
        return strengths(self.seed, self.teams, self.season).get(team, {}).get(pos, 0.0)

    def factor(self, team: str, pos: str, week: int) -> float:
        """Multiplier on ``team``'s ``pos`` player's expected points in ``week`` (1.0 without an opponent or for K / DEF)."""

        if pos not in SD:
            return 1.0
        opp = self.opponent(team, week)
        return math.exp(self.strength(opp, pos)) if opp else 1.0

    def info(self, team: str, pos: str, week: int) -> dict | None:
        opp = self.opponent(team, week)
        if pos not in SD or not opp:
            return None
        f = self.factor(team, pos, week)
        label = "soft" if f >= 1.03 else "tough" if f <= 0.97 else "even"
        return {"opponent": opp, "factor": round(f, 3), "label": label, "week": int(week)}


def for_snapshot(snap, season: int) -> Matchups:
    """The (memoized) ``Matchups`` of ``season`` for a game snapshot."""

    memo = getattr(snap, "_matchups", None)
    if memo is None:
        memo = {}
        object.__setattr__(snap, "_matchups", memo)
    m = memo.get(season)
    if m is None:
        m = memo[season] = Matchups(snap.seed, season, nfl_teams(snap.players, snap.bye_weeks), snap.bye_weeks)
    return m


__all__ = ["POSITIONS", "SD", "Matchups", "for_snapshot", "nfl_teams", "strengths"]
