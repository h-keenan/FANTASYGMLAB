"""One NFL team-code vocabulary.

Sleeper's codes are the app's canonical codes. Providers disagree on a few
franchises (relocations, abbreviation style); every consumer used to carry its
own partial copy of the alias table. This is the single copy. Provider-specific
codes that exist for one provider only (MyFantasyLeague's ``GBP``/``KCC``...)
stay with that provider and layer on top via ``canonical_team(code, extra=...)``.
"""

from __future__ import annotations

from typing import Any, Mapping

NFL_TEAM_CODES = frozenset(
    "ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split()
)

# Relocated / renamed franchises and alternate abbreviation styles -> Sleeper code.
TEAM_CODE_ALIASES: Mapping[str, str] = {
    "LA": "LAR",
    "STL": "LAR",
    "OAK": "LV",
    "SD": "LAC",
    "JAC": "JAX",
    "WSH": "WAS",
}


def canonical_team(code: Any, *, extra: Mapping[str, str] | None = None) -> str:
    """Upper-cased Sleeper-style team code; unknown codes pass through unchanged."""

    text = str(code or "").strip().upper()
    if extra and text in extra:
        text = extra[text]
    return TEAM_CODE_ALIASES.get(text, text)
