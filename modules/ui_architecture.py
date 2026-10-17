from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PageDefinition:
    key: str
    label: str
    group: str
    purpose: str
    notes: str = ""
    category: str = "EXPERIMENTAL"
    beta_visible: bool = False
    domain: str = "GENERAL"


# Category meanings (PR #226 graduation):
# CORE / SUPPORT — launch surfaces
# CONDITIONAL — launch-ready, visible only when enabled_experimental (or SHOW_EXPERIMENTAL for Ops)
# EXPERIMENTAL — kill-switch / SHOW_EXPERIMENTAL only; not launch-critical
# ARCHIVED — never in nav (superseded / duplicate); handlers may remain for safety
# FOUNDER_OPS / FOUNDER_LABS / DEV_ONLY — ops tooling
#
# Domain meanings (structural web/mobile shell-parity pass, 2026-10-11):
# a SEPARATE axis from `group` (desktop sidebar caption, legacy) and
# `category` (visibility tier — who can see it, untouched by this pass).
# `domain` is the single user-facing taxonomy shared by the desktop sidebar
# and the mobile-web destination sheet, mirroring mobile app's GmOrb.tsx
# three destination groups (coreLeagueDestinations / gmToolsDestinations /
# generalDestinations):
#   LEAGUE   — roster/league/weekly surfaces (mobile's coreLeagueDestinations)
#   GM_TOOLS — trade, waiver, draft, and team-stance workflows (mobile's
#              gmToolsDestinations)
#   GENERAL  — account-wide/marketing/legal surfaces (mobile's
#              generalDestinations)
#   OPS      — founder/dev-only tooling; not part of mobile's nav at all
DOMAIN_ORDER: Tuple[str, ...] = ("LEAGUE", "GM_TOOLS", "GENERAL", "OPS")
DOMAIN_LABELS: dict = {
    "LEAGUE": "League",
    "GM_TOOLS": "GM Tools",
    "GENERAL": "General",
    "OPS": "Internal",
}

# The 4 standalone legal documents collapsed into the single "legal" nav
# entry (structural web/mobile shell-parity pass, 2026-10-11), matching
# mobile's one parametrized LegalPage screen. These keys stay fully
# routable (still PageDefinition entries below, still in
# current_platform_destinations/routable_platform_destinations) so any
# existing `?page=terms` / `?page=privacy` / `?page=subscription_terms` /
# `?page=no_affiliation` deep link keeps working unchanged — this constant
# only tells the nav-rendering loops (desktop sidebar, mobile destination
# sheet) to skip drawing a separate button for them, since "legal" is the
# one button a user clicks.
LEGAL_CONSOLIDATED_SUBKEYS: Tuple[str, ...] = (
    "terms",
    "privacy",
    "subscription_terms",
    "no_affiliation",
)

PLATFORM_DESTINATIONS: Tuple[PageDefinition, ...] = (
    PageDefinition("dashboard", "Dashboard", "HOME", "Primary franchise landing page.", category="CORE", beta_visible=True, domain="LEAGUE"),
    PageDefinition(
        "portfolio",
        "Portfolio",
        "HOME",
        "Standing, record, and top need or opportunity across every saved league at once (Premium).",
        category="CORE",
        beta_visible=True,
        domain="GENERAL",
    ),
    PageDefinition(
        "alerts",
        "Alerts",
        "HOME",
        "Priority signals and activity timeline for the current league.",
        category="CORE",
        beta_visible=True,
        domain="LEAGUE",
    ),
    PageDefinition(
        "gm_plan",
        "GM Plan",
        "HOME",
        "Season-arc roadmap: where you stand, your best trade paths, and roster construction, framed by your declared Team Situation.",
        category="CORE",
        beta_visible=True,
        domain="GM_TOOLS",
    ),
    PageDefinition("my_team", "My Team", "ROSTER", "Hands-on roster management surface.", category="CORE", beta_visible=True, domain="LEAGUE"),
    PageDefinition(
        "matchup",
        "Matchup",
        "ROSTER",
        "This week's real head-to-head: live Sleeper lineup/points for both rosters, plus real per-player weekly projections.",
        category="CORE",
        beta_visible=True,
        domain="LEAGUE",
    ),
    PageDefinition(
        "players",
        "Players",
        "ROSTER",
        "Discover and filter players across the league pool into Player Quick View.",
        category="CORE",
        beta_visible=True,
        domain="LEAGUE",
    ),
    # Waivers lives in the LEAGUE domain, matching mobile's GmOrb.tsx (it
    # sits in the LEAGUE group alongside Matchup/My Team, not the GM Tools
    # group) — moved out of the Trade Hub/Trade Finder/Trade Analyzer
    # tri-tab's former GM_TOOLS slot, where it had been inconsistent with
    # mobile's own standalone top-level Waivers screen.
    PageDefinition("waivers", "Waivers", "TRANSACTIONS", "Find available upgrades, injury replacements, and FAAB guidance.", category="CORE", beta_visible=True, domain="LEAGUE"),
    PageDefinition(
        "gm_targets",
        "GM Targets",
        "ROSTER",
        "Keep an eye on players you're considering buying, selling, adding, or monitoring.",
        category="CONDITIONAL",
        domain="GM_TOOLS",
    ),
    PageDefinition(
        "team_stance",
        "Team Situation",
        "SUPPORT",
        "Declare your team's stance (Rebuilding/Competing/Balanced) and manage protected players — biases trade-idea language only, never valuation.",
        category="CONDITIONAL",
        domain="GM_TOOLS",
    ),
    PageDefinition(
        "player_detail",
        "Player Detail",
        "ROSTER",
        "Archived full-page profile — Player Quick View is canonical.",
        category="ARCHIVED",
        domain="LEAGUE",
    ),
    PageDefinition("rankings", "League Rankings", "LEAGUE", "League-wide power, franchise value, pressure signals, and team context.", category="CORE", beta_visible=True, domain="LEAGUE"),
    # GM Orb visible sections are page.domain (League / GM Tools / General),
    # not group. Recaps stays CORE so it's visible by default; group=LEAGUE
    # is sidebar-caption-legacy only, domain=LEAGUE drives the shared taxonomy.
    PageDefinition(
        "league_recaps",
        "League Recaps / History",
        "LEAGUE",
        "Weekly recap, transaction history, and season storylines — what mattered and what happened.",
        category="CORE",
        beta_visible=True,
        domain="LEAGUE",
    ),
    PageDefinition(
        "teams",
        "Teams",
        "LEAGUE",
        "Archived — League Rankings owns the Teams section.",
        category="ARCHIVED",
        domain="LEAGUE",
    ),
    PageDefinition(
        "weekly_report",
        "Weekly Report",
        "LEAGUE",
        "Archived — Dashboard owns daily briefing; week semantics unfinished.",
        category="ARCHIVED",
        domain="LEAGUE",
    ),
    PageDefinition("trade_hub", "Trade Hub", "TRANSACTIONS", "Find realistic trades for your roster — ranked by fit and fairness.", category="CORE", beta_visible=True, domain="GM_TOOLS"),
    PageDefinition(
        "trade_finder",
        "Trade Finder",
        "TRANSACTIONS",
        "Select specific players from your roster and search for realistic packages the league would trade for them.",
        category="CORE",
        beta_visible=True,
        domain="GM_TOOLS",
    ),
    PageDefinition(
        "trade_analyzer",
        "Trade Analyzer",
        "TRANSACTIONS",
        "Evaluate an incoming dynasty offer — accept, decline, or counter.",
        category="CORE",
        beta_visible=True,
        domain="GM_TOOLS",
    ),
    PageDefinition(
        "trade_history",
        "Trade History",
        "TRANSACTIONS",
        "Trades you've confirmed you made, plus a real before/after read once a "
        "confirmed trade has had a few weeks to play out — matches mobile's Trade History screen.",
        category="CORE",
        beta_visible=True,
        domain="GM_TOOLS",
    ),
    PageDefinition("startup_draft_center", "Startup Draft Center", "DRAFT", "Startup-only draft-first dashboard.", category="CORE", beta_visible=True, domain="GM_TOOLS"),
    PageDefinition("draft_summary", "Draft Center", "DRAFT", "Primary rookie-draft, draft posture, and pick-strategy workspace.", category="CORE", beta_visible=True, domain="GM_TOOLS"),
    PageDefinition(
        "live_draft",
        "Live Draft",
        "DRAFT",
        "Read-only Sleeper live draft assistant for active draft rooms.",
        category="CONDITIONAL",
        domain="GM_TOOLS",
    ),
    PageDefinition(
        "college_scouting",
        "College Scouting",
        "DRAFT",
        "Submit a 1-5 grade on college prospects, pooled into a shared signal, plus a personal watchlist.",
        category="CORE",
        beta_visible=True,
        domain="GM_TOOLS",
    ),
    PageDefinition(
        "news",
        "News",
        "INTELLIGENCE",
        "General NFL news feed — injury, role, transaction, and off-field "
        "signal, grouped by day and event type. Not roster-scoped: see "
        "Dashboard for the 3-tile roster digest, or Alerts for the "
        "roster-aware activity timeline.",
        category="CORE",
        beta_visible=True,
        domain="GENERAL",
    ),
    PageDefinition(
        "archetypes",
        "Archetypes",
        "INTELLIGENCE",
        "Archived standalone archetypes route — League Rankings owns franchise context.",
        category="ARCHIVED",
        domain="LEAGUE",
    ),
    PageDefinition(
        "manager_tendencies",
        "Manager Tendencies",
        "INTELLIGENCE",
        "Archived standalone route — Trade Hub and League Rankings own tendencies context.",
        category="ARCHIVED",
        domain="GM_TOOLS",
    ),
    PageDefinition("premium", "Premium", "SUPPORT", "Free and Premium plan preview for FantasyDesk.", category="SUPPORT", beta_visible=True, domain="GENERAL"),
    PageDefinition("methodology", "How We Evaluate", "SUPPORT", "How FantasyDesk evaluates players in league context, and how rankings differ from trade recommendations.", category="SUPPORT", beta_visible=True, domain="GENERAL"),
    PageDefinition("about_disclaimer", "About / Disclaimer", "SUPPORT", "Product information, recommendation limits, and general disclaimer.", category="SUPPORT", beta_visible=True, domain="GENERAL"),
    # The 4 standalone legal documents below stay routable (still visible,
    # still SUPPORT category) so `?page=terms` etc. keep working directly,
    # but LEGAL_CONSOLIDATED_SUBKEYS (above) tells the nav-rendering loops to
    # skip a separate button for each — "legal" (below) is the one nav entry.
    PageDefinition("terms", "Terms of Use", "SUPPORT", "Plain-language terms for using FantasyDesk.", category="SUPPORT", beta_visible=True, domain="GENERAL"),
    PageDefinition("privacy", "Privacy Policy", "SUPPORT", "How FantasyDesk may handle usernames, league context, preferences, and feedback.", category="SUPPORT", beta_visible=True, domain="GENERAL"),
    PageDefinition("subscription_terms", "Subscription Terms", "SUPPORT", "Auto-renewal, billing, and cancellation terms for FantasyDesk Premium.", category="SUPPORT", beta_visible=True, domain="GENERAL"),
    PageDefinition("no_affiliation", "No-Affiliation Disclaimer", "SUPPORT", "Independent-product and third-party ownership notice.", category="SUPPORT", beta_visible=True, domain="GENERAL"),
    PageDefinition(
        "legal",
        "Legal",
        "SUPPORT",
        "Terms of Use, Privacy Policy, Subscription Terms, and the No-Affiliation Disclaimer in one place.",
        category="SUPPORT",
        beta_visible=True,
        domain="GENERAL",
    ),
    PageDefinition(
        "founder_ops",
        "Founder Ops",
        "OPS",
        "Founder-only operational health and read-only diagnostics.",
        category="FOUNDER_OPS",
        beta_visible=False,
        domain="OPS",
    ),
    PageDefinition(
        "founder_labs",
        "Founder Labs",
        "OPS",
        "Trusted founder/dev inventory of dormant and hidden product surfaces.",
        category="FOUNDER_LABS",
        beta_visible=False,
        domain="OPS",
    ),
)

MOBILE_PRIMARY_DESTINATION_KEYS: Tuple[str, ...] = (
    "dashboard",
    "my_team",
    "trade_hub",
    "rankings",
    "draft_summary",
    "waivers",
)

ARCHIVED_DESTINATION_KEYS: Tuple[str, ...] = tuple(
    page.key for page in PLATFORM_DESTINATIONS if page.category == "ARCHIVED"
)


def _destination_visible(
    page: PageDefinition,
    *,
    show_experimental: bool = False,
    show_dev: bool = False,
    show_founder_ops: bool = False,
    show_founder_labs: bool = False,
    enabled_experimental: Tuple[str, ...] = (),
) -> bool:
    if page.category == "ARCHIVED":
        return False
    if page.category == "FOUNDER_OPS":
        return bool(show_founder_ops)
    if page.category == "FOUNDER_LABS":
        return bool(show_founder_labs)
    if page.category == "DEV_ONLY":
        return bool(show_dev)
    if page.category == "CONDITIONAL":
        return bool(show_experimental or page.key in set(enabled_experimental))
    if page.category == "EXPERIMENTAL":
        return bool(
            page.beta_visible
            or show_experimental
            or page.key in set(enabled_experimental)
        )
    return page.category in {"CORE", "SUPPORT"}


def current_platform_destinations(
    startup_mode: bool,
    *,
    show_experimental: bool = False,
    show_dev: bool = False,
    show_founder_ops: bool = False,
    show_founder_labs: bool = False,
    enabled_experimental: Tuple[str, ...] = (),
) -> Tuple[PageDefinition, ...]:
    labels = {
        "startup_draft_center": "Startup Draft Center",
    }
    destinations = []
    for page in PLATFORM_DESTINATIONS:
        if not _destination_visible(
            page,
            show_experimental=show_experimental,
            show_dev=show_dev,
            show_founder_ops=show_founder_ops,
            show_founder_labs=show_founder_labs,
            enabled_experimental=enabled_experimental,
        ):
            continue
        if startup_mode and page.key == "draft_summary":
            continue
        if not startup_mode and page.key == "startup_draft_center":
            continue
        destinations.append(
            PageDefinition(
                key=page.key,
                label=labels.get(page.key, page.label),
                group=page.group,
                purpose=page.purpose,
                notes=page.notes,
                category=page.category,
                beta_visible=page.beta_visible,
                domain=page.domain,
            )
        )
    return tuple(destinations)


def routable_platform_destinations(
    startup_mode: bool,
    *,
    show_experimental: bool = False,
    show_dev: bool = False,
    show_founder_ops: bool = False,
    show_founder_labs: bool = False,
    enabled_experimental: Tuple[str, ...] = (),
    labs_review_keys: Tuple[str, ...] = (),
) -> Tuple[PageDefinition, ...]:
    """Nav destinations plus Labs-only review routes. Does not put extras in customer nav."""

    visible = current_platform_destinations(
        startup_mode,
        show_experimental=show_experimental,
        show_dev=show_dev,
        show_founder_ops=show_founder_ops,
        show_founder_labs=show_founder_labs,
        enabled_experimental=enabled_experimental,
    )
    if not labs_review_keys:
        return visible
    existing = {page.key for page in visible}
    extra: list[PageDefinition] = []
    allowed = set(labs_review_keys)
    for page in PLATFORM_DESTINATIONS:
        if page.key in existing or page.key not in allowed:
            continue
        extra.append(page)
    return visible + tuple(extra)


def mobile_primary_destinations(
    startup_mode: bool,
    *,
    show_experimental: bool = False,
    show_dev: bool = False,
    show_founder_ops: bool = False,
    show_founder_labs: bool = False,
) -> Tuple[PageDefinition, ...]:
    destination_map = {
        page.key: page
        for page in current_platform_destinations(
            startup_mode,
            show_experimental=show_experimental,
            show_dev=show_dev,
            show_founder_ops=show_founder_ops,
            show_founder_labs=show_founder_labs,
        )
    }
    keys = MOBILE_PRIMARY_DESTINATION_KEYS
    if startup_mode:
        keys = (
            "dashboard",
            "startup_draft_center",
            "players",
            "waivers",
        )
    return tuple(
        destination_map[key]
        for key in keys
        if key in destination_map
    )


def mobile_secondary_destinations(
    startup_mode: bool,
    *,
    show_experimental: bool = False,
    show_dev: bool = False,
    show_founder_ops: bool = False,
    show_founder_labs: bool = False,
) -> Tuple[PageDefinition, ...]:
    primary_keys = {
        page.key
        for page in mobile_primary_destinations(
            startup_mode,
            show_experimental=show_experimental,
            show_dev=show_dev,
            show_founder_ops=show_founder_ops,
            show_founder_labs=show_founder_labs,
        )
    }
    return tuple(
        page
        for page in current_platform_destinations(
            startup_mode,
            show_experimental=show_experimental,
            show_dev=show_dev,
            show_founder_ops=show_founder_ops,
            show_founder_labs=show_founder_labs,
        )
        if page.key not in primary_keys and page.key not in ARCHIVED_DESTINATION_KEYS
    )


def domain_grouped_nav_destinations(
    destinations: Tuple[PageDefinition, ...],
) -> Tuple[Tuple[str, str, Tuple[PageDefinition, ...]], ...]:
    """Group already-visible destinations into the shared domain taxonomy.

    Single source of truth for the nav-facing grouping used by BOTH the
    desktop sidebar and the mobile-web destination sheet (structural
    web/mobile shell-parity pass, 2026-10-11) — before this, the two
    surfaces used two unrelated schemes (`group` captions on desktop,
    `category` tiers on mobile). Returns `(domain_key, domain_label,
    destinations_in_domain)` tuples in DOMAIN_ORDER, skipping empty domains.
    `LEGAL_CONSOLIDATED_SUBKEYS` destinations are always excluded — they
    stay independently routable (deep links), but the single "legal" entry
    is the one nav button for all four.
    """

    by_domain: dict[str, list] = {}
    for destination in destinations:
        if destination.key in LEGAL_CONSOLIDATED_SUBKEYS:
            continue
        by_domain.setdefault(destination.domain, []).append(destination)
    grouped = []
    for domain_key in DOMAIN_ORDER:
        items = by_domain.get(domain_key)
        if not items:
            continue
        grouped.append((domain_key, DOMAIN_LABELS.get(domain_key, domain_key.title()), tuple(items)))
    return tuple(grouped)
