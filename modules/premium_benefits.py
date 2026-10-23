from __future__ import annotations
from modules import product_copy

FREE_INCLUDES = (
    ("League import", "Load Sleeper leagues and keep the main roster tools useful."),
    ("Dashboard overview", "Today's Game Plan, limited Next Moves, and basic team needs."),
    ("What Changed", "Session history of meaningful recommendation transitions."),
    ("GM Targets (limited)", "Save up to three players you're actively considering."),
    ("Share Recommendation", "Download branded share cards from Trade Hub, Waivers, and Player Quick View."),
    ("Players explorer", "Filter the dynasty market and open Player Quick View."),
    ("Trade preview", "Top generated trade ideas so the page has immediate value."),
    ("Priority Adds", "Best waiver adds before deeper board and FAAB detail."),
    ("Core roster view", "Roster priorities, core assets, starters, and basic team context."),
)


# Launch-ready Premium depth only — must match effective_entitlement gates.
PREMIUM_INCLUDED_NOW = (
    ("More next moves", "Expanded Dashboard stack with deeper roster, trade, waiver, and health signals."),
    # League Pulse is only partly Pro: the mobile Dashboard locks its leader
    # tiles for Free (mobile/src/screens/DashboardScreen.tsx), but web-next's
    # League Pulse activity/streak card is free (LeaguePulseCard.tsx). This
    # names only the gated part.
    (
        "League Pulse leaders",
        "Top contender, rebuilder, draft-capital, and activity leader tiles on the mobile app Dashboard.",
    ),
    (product_copy.PREMIUM_FULL_TRADE_HUB, "More generated trade ideas, partner context, and player return search."),
    ("Full waiver board", "Stash candidates, watchlist depth, FAAB shortlist, and add/drop context."),
    ("Advanced roster decisions", "Trade-away, hold, drop, Deep Analysis, and bench-insulation reads."),
    (
        "Decision Memory",
        "Durable cross-session history of material GM priority changes beyond the current session.",
    ),
    (
        "GM Targets (full board)",
        "Save up to fifty players per league with PQV Add/Remove and workflow handoffs.",
    ),
    (
        # Real, shipped, premium.PREMIUM-gated feature (modules/portfolio_page.py,
        # mobile's GET /v1/portfolio) that was missing from this canonical list —
        # found during the welcome/paywall thoroughness pass. Added here (the
        # single source of truth) rather than inventing paywall copy for it.
        "Portfolio",
        "Your record, rank, and top need or opportunity across every saved league in one place.",
    ),
)


# Mobile Paywall's benefit checklist — grounded in PREMIUM_INCLUDED_NOW so web
# and mobile can never describe two different sets of gated Premium features,
# even though mobile's paywall wants short one-line copy instead of a
# title+description row. Served to the app via GET /v1/me
# (services/mobile_api_service.py), so a copy change here reaches mobile
# without a client release. Mobile keeps a hardcoded copy of this exact list
# as an offline/fetch-failure fallback only — see mobile/src/screens/PaywallScreen.tsx.
MOBILE_PREMIUM_BENEFIT_LINES: tuple[dict[str, str], ...] = (
    {"title": "More next moves", "line": "Your full Next Move briefing, not just the top 4"},
    {
        "title": "League Pulse leaders",
        "line": "League Pulse leaders in the mobile app — the league’s top contender, rebuilder, draft capital, and most active manager",
    },
    {
        "title": "Full waiver board",
        "line": "The complete waiver board — stash candidates, watchlist depth, and a FAAB shortlist",
    },
    {
        "title": product_copy.PREMIUM_FULL_TRADE_HUB,
        "line": "Every Trade Hub idea, not just the first 2",
    },
    {
        "title": "GM Targets (full board)",
        "line": "GM Targets watchlist up to 50 players (Free is capped at 3)",
    },
    {
        "title": "Portfolio",
        "line": "Portfolio — your record, rank, and top need across every saved league, not just one",
    },
)


def mobile_premium_benefit_lines() -> list[str]:
    """Single-line Premium benefit copy for the mobile Paywall screen.

    Every entry's `title` must exist in PREMIUM_INCLUDED_NOW, so this raises
    if a future edit renames or removes a benefit here without updating the
    other list — keeping web and mobile from silently drifting apart again.
    """
    known_titles = {title for title, _ in PREMIUM_INCLUDED_NOW}
    lines: list[str] = []
    for entry in MOBILE_PREMIUM_BENEFIT_LINES:
        title = entry["title"]
        if title not in known_titles:
            raise ValueError(f"Mobile Premium benefit line references unknown title: {title!r}")
        lines.append(entry["line"])
    return lines
