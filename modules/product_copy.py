"""Canonical customer-facing nouns and loading/CTA copy.

Presentation only. Does not change routing, entitlements, or football logic.
Surface names must stay aligned with ``ui_architecture.PLATFORM_DESTINATIONS``.
"""

from __future__ import annotations

from modules.ui_architecture import PLATFORM_DESTINATIONS


def destination_label(key: str) -> str:
    needle = str(key or "").strip()
    for page in PLATFORM_DESTINATIONS:
        if page.key == needle:
            return page.label
    return needle.replace("_", " ").title()


PLAYERS = destination_label("players")
TRADE_HUB = destination_label("trade_hub")
LEAGUE_OVERVIEW = destination_label("rankings")
DASHBOARD = destination_label("dashboard")
MY_TEAM = destination_label("my_team")
WAIVERS = destination_label("waivers")
PREMIUM = destination_label("premium")

LOAD_LEAGUES_CTA = "Load my leagues"
OPEN_LEAGUE_CTA = "Open league"
CONTINUE_LAST_LEAGUE_CTA = "Continue last league"
CHOOSE_LEAGUE_TITLE = "Choose a league"
LOADING_LEAGUES = "Loading leagues from Sleeper…"
LOADING_TRADE_IDEAS = "Loading trade ideas…"

PLAYERS_PAGE_SUBTITLE = (
    "Search the dynasty market, compare ranked players and supported draft capital, "
    "then open Player Quick View."
)
PLAYERS_EXPLORER_TITLE = "Search players and picks"
PLAYERS_EXPLORER_SUBTITLE = (
    "Find players and draft capital quickly, compare current context, "
    "then open Player Quick View."
)
PLAYERS_SOURCE_LABEL = PLAYERS

PREMIUM_FULL_TRADE_HUB = f"Full {TRADE_HUB}"

ROSTER_MISMATCH_TITLE = "Roster not found"
ROSTER_MISMATCH_BODY = (
    "No roster matched this Sleeper username in the selected league."
)
ROSTER_MISMATCH_RECOVERY = "Check the username and import again."

STARTUP_BLOCKED_TITLE = "Startup draft is still active"
STARTUP_BLOCKED_RECOVERY = (
    "Use Draft Center until the startup draft completes and rosters are populated."
)

LOOKUP_ERROR_TITLE = "Leagues could not be loaded"
LOOKUP_RECOVERY = "Check the username, then try Load my leagues again."

SIDEBAR_IMPORT_NOTE = "Same Sleeper import as the main page."

DEPRECATED_CUSTOMER_TERMS = (
    "Players & Picks",
    "Load leagues for user",
    "Building the trade board",
    "Full trade board",
    "Player & Asset Explorer",
    "Trade Board",
)
