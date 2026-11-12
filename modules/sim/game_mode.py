"""League mode: the one place that says how a redraft game differs from a
dynasty one.

Everything that depends on "what is a player worth" or "what does an AI manager
want" asks the ``ModePolicy`` of the game's mode instead of hard-coding it, so
dynasty can be added later by filling in one more policy (and flipping
``available``) rather than hunting through the draft, trade and waiver code.

* ``redraft`` (the only playable mode today): a player is worth what he scores
  this season. Trade worth uses the settings-aware one-season ``value`` (so
  superflex, TE premium and roster shape all matter), ignores age, and every AI
  manager leans win-now; personas keep their taste, not their dynasty horizon.
* ``dynasty`` (declared, not playable): worth blends the dynasty market value
  and age by each manager's horizon, as the original game rules did. Selecting
  it is refused by ``GameSettings.parse`` until the rest of dynasty (rookie
  drafts, picks, multi-season) exists.

``rules`` is the version of the valuation rules a save was created under.
Saves made before modes existed carry ``rules == 1`` and keep the original
market-and-age valuation, so shipping this never changes an in-flight game.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

MODES = ("redraft", "dynasty")
DEFAULT_MODE = "redraft"
RULES_VERSION = 2  # 1 = pre-mode saves (market + age valuation)


@dataclass(frozen=True)
class ModePolicy:
    mode: str
    label: str
    available: bool
    vorp_weight: float  # draft value: share from value-over-replacement (rest: market)
    season_valuation: bool  # trade/waiver worth from this season's value, ignoring age
    horizon_floor: float  # AI managers never weigh "now" below this
    pitches: Mapping[str, str] = field(default_factory=dict)  # persona id -> offer pitch
    blurbs: Mapping[str, str] = field(default_factory=dict)  # persona id -> setup blurb

    def horizon(self, base: float) -> float:
        return max(self.horizon_floor, min(1.0, base))

    def to_dict(self) -> dict[str, object]:
        return {"id": self.mode, "label": self.label, "available": self.available}


_REDRAFT_PITCH = {
    "contender": "wants proven production for the title run",
    "rebuilder": "is shopping depth for a starter",
    "value_shark": "thinks this is a fair swap",
    "youth_hoarder": "likes how this fits their lineup",
    "specialist": "is loading up at one position",
    "passive": "rarely deals, but likes this one",
    "chaos": "had a feeling about this one",
}
_REDRAFT_BLURB = {
    "contender": "Chases the best weekly lineup and pays up in value for proven production.",
    "rebuilder": "Trades depth and name value for starters, a little less win-now than the rest.",
    "value_shark": "Only accepts clear wins. Rarely overpays, rarely gets fleeced.",
    "youth_hoarder": "Trades on gut feel for upside; leans on young players but plays to win this year.",
    "specialist": "Overvalues one favorite position and builds around it.",
    "passive": "Rarely trades and sometimes forgets to update the lineup.",
    "chaos": "Unpredictable. Might fleece you, might hand you a gift.",
}

POLICIES: dict[str, ModePolicy] = {
    "redraft": ModePolicy(
        "redraft", "Redraft", True, vorp_weight=0.85, season_valuation=True, horizon_floor=0.8,
        pitches=_REDRAFT_PITCH, blurbs=_REDRAFT_BLURB,
    ),
    "dynasty": ModePolicy(
        "dynasty", "Dynasty", False, vorp_weight=0.75, season_valuation=False, horizon_floor=0.0,
    ),
}
# Saves created before modes existed (rules == 1).
LEGACY_POLICY = replace(POLICIES["redraft"], vorp_weight=0.75, season_valuation=False, horizon_floor=0.0,
                        pitches={}, blurbs={})


def policy_for(mode: str, rules: int = RULES_VERSION) -> ModePolicy:
    if rules < 2:
        return LEGACY_POLICY
    return POLICIES.get(mode, POLICIES[DEFAULT_MODE])


def mode_options() -> list[dict[str, object]]:
    return [POLICIES[m].to_dict() for m in MODES]


__all__ = [
    "MODES", "DEFAULT_MODE", "RULES_VERSION", "ModePolicy", "POLICIES", "LEGACY_POLICY", "policy_for",
    "mode_options",
]
