"""The ONE accent-color mapping for nav / GM orb / feature-catalog destinations.

Web (navDestinations.ts, featureCatalog.ts) and the app (GmOrb.tsx,
featureCatalog.ts) each hand-picked a color per destination and drifted: Alerts
was amber on web and red in the app, Matchup red vs green, Waivers teal vs
green, Trade Hub / GM Plan / Draft Center gold in the app only, and so on.

The values are the shared SEMANTIC tokens (web ``--color-<name>``), never hex:

    accent       interaction / primary surfaces
    success      roster / lineup / healthy
    warning      time-sensitive heads-up
    danger       head-to-head, high-stakes, deadline surfaces
    opportunity  pickups and games (the token name matches the concept)
    diagnostic   analytical, read-only research surfaces
    information  news / recaps (same hue as accent)
    premium      ranking / prestige / community surfaces

Keys are the feature-catalog ids (identical on web and app); a nav / orb row
looks itself up by id (its label lowercased, spaces to hyphens).
``scripts/sync_destination_accents.py`` generates the TypeScript copy shared by
web-next and mobile; each side's test pins its catalog and nav to it.
"""

from __future__ import annotations

TOKENS = ("accent", "success", "warning", "danger", "opportunity", "diagnostic", "information", "premium")

ACCENT_BY_DESTINATION: dict[str, str] = {
    "dashboard": "accent",
    "alerts": "warning",
    "my-team": "success",
    "matchup": "danger",
    "waivers": "opportunity",
    "players": "diagnostic",
    "league-rankings": "premium",
    "playoff-odds": "premium",
    "trade-hub": "accent",
    "trade-finder": "accent",
    "trade-analyzer": "accent",
    "trade-history": "diagnostic",
    "community": "premium",
    "gm-plan": "success",
    "draft-center": "danger",
    "fantasy-sim": "opportunity",
    "live-draft": "danger",
    "league-recaps": "information",
    "games": "opportunity",
    "commissioner": "diagnostic",
    "college-scouting": "success",
    "news": "information",
    "portfolio": "premium",
}


def table() -> dict:
    return {"tokens": list(TOKENS), "accents": ACCENT_BY_DESTINATION}
