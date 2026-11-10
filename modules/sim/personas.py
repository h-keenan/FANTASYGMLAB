"""AI manager personas and the user's auto-GM parameters.

A persona is a parameter vector, nothing else: decisions stay rule-based and
deterministic given the seed. The user's strategy is translated into the same
``TeamParams`` so the user's team is driven by the identical machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

import numpy as np

from modules.sim.types import POSITIONS, Strategy


@dataclass(frozen=True)
class TeamParams:
    horizon: float  # 0 = pure future/market value, 1 = pure win-now production
    accept_threshold: float  # value units a proposal must clear to be accepted
    propose_min: float  # value units a team must gain to propose a trade
    activity: float  # chance per week to go looking for a trade
    noise_sd: float  # value-unit noise on acceptance
    waiver_aggr: float  # chance per week to look at the wire
    age_penalty: float = 0.04  # market-value haircut per year over 26, scaled by (1 - horizon)
    pos_bias: Mapping[str, float] = field(default_factory=dict)
    max_trades: int = 3


@dataclass(frozen=True)
class Persona:
    pid: str
    label: str
    blurb: str
    params: TeamParams


PERSONAS: dict[str, Persona] = {
    "contender": Persona(
        "contender", "Contender",
        "Win-now. Pays up in youth and market value for proven weekly production.",
        TeamParams(0.85, 3.0, 4.0, 0.35, 2.0, 0.6),
    ),
    "rebuilder": Persona(
        "rebuilder", "Rebuilder",
        "Sells aging vets, hoards young, high-upside assets and market value.",
        TeamParams(0.2, 3.0, 4.0, 0.35, 2.0, 0.4, age_penalty=0.05),
    ),
    "value_shark": Persona(
        "value_shark", "Value Shark",
        "Only accepts clear wins. Rarely overpays, rarely gets fleeced.",
        TeamParams(0.5, 9.0, 7.0, 0.30, 1.0, 0.7),
    ),
    "youth_hoarder": Persona(
        "youth_hoarder", "Youth Hoarder",
        "Loves young players, discounts anyone past 26 heavily.",
        TeamParams(0.15, 4.0, 5.0, 0.30, 3.0, 0.5, age_penalty=0.07),
    ),
    "specialist": Persona(
        "specialist", "Position Specialist",
        "Overvalues one position group and won't sell it cheap.",
        TeamParams(0.55, 4.0, 5.0, 0.25, 4.0, 0.5),
    ),
    "passive": Persona(
        "passive", "Passive Manager",
        "Rarely trades, slow on the wire. Needs a very good offer.",
        TeamParams(0.5, 12.0, 9.0, 0.08, 1.0, 0.15),
    ),
    "chaos": Persona(
        "chaos", "Wildcard",
        "High variance. Will say yes to odd offers and make odd offers.",
        TeamParams(0.5, -1.0, 0.0, 0.45, 12.0, 0.5),
    ),
}
PERSONA_ORDER = tuple(PERSONAS)
MAX_PER_PERSONA = 3

HORIZON_BY_POSTURE = {"win_now": 0.85, "balanced": 0.55, "rebuild": 0.2}


def user_params(strategy: Strategy) -> TeamParams:
    """Translate the user's strategy into engine parameters.

    Aggressiveness 0 means the auto-GM never trades; 1 means it hunts weekly
    and accepts thin edges. Posture sets the win-now/future horizon.
    """

    aggr = strategy.trade_aggressiveness
    horizon = HORIZON_BY_POSTURE[strategy.posture]
    return TeamParams(
        horizon=horizon,
        accept_threshold=7.0 - 4.0 * aggr,
        propose_min=6.0 - 3.0 * aggr,
        activity=0.0 if aggr <= 0 else 0.1 + 0.5 * aggr,
        noise_sd=0.0,
        waiver_aggr=strategy.waiver_aggressiveness,
        age_penalty=0.04,
        max_trades=0 if aggr <= 0 else 1 + int(round(3 * aggr)),
    )


def assign_personas(
    rng: np.random.Generator,
    team_ids: list[str],
    power_pct: Mapping[str, float],
    avg_age: Mapping[str, float],
) -> dict[str, Persona]:
    """Deterministic persona per AI team from the world seed.

    Multi-factor: the team's real strength (power_pct, 1 = best), roster age and
    seeded randomness all shift affinity, with a cap per persona so a league
    never fills with one personality. ``team_ids`` must already exclude the
    user's team and be in a stable order.
    """

    ages = list(avg_age.values()) or [26.0]
    median_age = float(np.median(ages))
    order = list(rng.permutation(len(team_ids)))
    counts: dict[str, int] = {}
    out: dict[str, Persona] = {}
    cap = max(MAX_PER_PERSONA, -(-len(team_ids) // len(PERSONA_ORDER)) + 1)
    for position in order:
        tid = team_ids[int(position)]
        strength = float(power_pct.get(tid, 0.5))
        older = float(avg_age.get(tid, median_age)) - median_age
        affinity = {
            "contender": 1.5 * strength + 0.15 * older,
            "rebuilder": 1.5 * (1 - strength) + 0.15 * older,
            "value_shark": 0.3,
            "youth_hoarder": 0.9 * (1 - strength) - 0.15 * older,
            "specialist": 0.2,
            "passive": 0.1,
            "chaos": 0.0,
        }
        gumbel = rng.gumbel(size=len(PERSONA_ORDER))
        ranked = sorted(
            range(len(PERSONA_ORDER)),
            key=lambda i: -(affinity[PERSONA_ORDER[i]] + 0.8 * float(gumbel[i])),
        )
        for i in ranked:
            pid = PERSONA_ORDER[i]
            if counts.get(pid, 0) < cap:
                counts[pid] = counts.get(pid, 0) + 1
                persona = PERSONAS[pid]
                params = persona.params
                if pid == "specialist":
                    favorite = POSITIONS[int(rng.integers(0, 4))]
                    params = replace(params, pos_bias={favorite: 0.25})
                    persona = Persona(pid, persona.label, f"{persona.blurb} Favorite: {favorite}.", params)
                elif pid == "chaos":
                    params = replace(params, horizon=float(rng.uniform(0.2, 0.8)))
                    persona = Persona(pid, persona.label, persona.blurb, params)
                out[tid] = persona
                break
    return out
