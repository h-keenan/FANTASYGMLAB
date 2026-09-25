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


# Category meanings (PR #226 graduation):
# CORE / SUPPORT — launch surfaces
# CONDITIONAL — launch-ready, visible only when enabled_experimental (or SHOW_EXPERIMENTAL for Ops)
# EXPERIMENTAL — kill-switch / SHOW_EXPERIMENTAL only; not launch-critical
# ARCHIVED — never in nav (superseded / duplicate); handlers may remain for safety
# FOUNDER_OPS / FOUNDER_LABS / DEV_ONLY — ops tooling

PLATFORM_DESTINATIONS: Tuple[PageDefinition, ...] = (
    PageDefinition("dashboard", "Dashboard", "HOME", "Primary franchise landing page.", category="CORE", beta_visible=True),
    PageDefinition(
        "alerts",
        "Alerts",
        "HOME",
        "Priority signals and activity timeline for the current league.",
        category="CORE",
        beta_visible=True,
    ),
    PageDefinition("my_team", "My Team", "ROSTER", "Hands-on roster management surface.", category="CORE", beta_visible=True),
    PageDefinition(
        "players",
        "Players",
        "ROSTER",
        "Discover and filter players across the league pool into Player Quick View.",
        category="CORE",
        beta_visible=True,
    ),
    PageDefinition(
        "gm_targets",
        "GM Targets",
        "ROSTER",
        "Keep an eye on players you're considering buying, selling, adding, or monitoring.",
        category="CONDITIONAL",
    ),
    PageDefinition(
        "team_stance",
        "Team Situation",
        "SUPPORT",
        "Declare your team's stance (Rebuilding/Competing/Balanced) and manage protected players — biases trade-idea language only, never valuation.",
        category="CONDITIONAL",
    ),
    PageDefinition(
        "player_detail",
        "Player Detail",
        "ROSTER",
        "Archived full-page profile — Player Quick View is canonical.",
        category="ARCHIVED",
    ),
    PageDefinition("rankings", "League Overview", "LEAGUE", "League-wide power, franchise value, pressure signals, and team context.", category="CORE", beta_visible=True),
    # GM Orb visible sections are page.category (Core / Active now / Support), not group.
    # Recaps stays CORE so it sits with League Overview; group=LEAGUE is sidebar only.
    PageDefinition(
        "league_recaps",
        "League Recaps / History",
        "LEAGUE",
        "Weekly recap, transaction history, and season storylines — what mattered and what happened.",
        category="CORE",
        beta_visible=True,
    ),
    PageDefinition(
        "teams",
        "Teams",
        "LEAGUE",
        "Archived — League Overview owns the Teams section.",
        category="ARCHIVED",
    ),
    PageDefinition(
        "weekly_report",
        "Weekly Report",
        "LEAGUE",
        "Archived — Dashboard owns daily briefing; week semantics unfinished.",
        category="ARCHIVED",
    ),
    PageDefinition("trade_hub", "Trade Hub", "TRANSACTIONS", "Find realistic trades for your roster — ranked by fit and fairness.", category="CORE", beta_visible=True),
    PageDefinition(
        "trade_analyzer",
        "Trade Analyzer",
        "TRANSACTIONS",
        "Evaluate an incoming dynasty offer — accept, decline, or counter.",
        category="CORE",
        beta_visible=True,
    ),
    PageDefinition("waivers", "Waivers", "TRANSACTIONS", "Find available upgrades, injury replacements, and FAAB guidance.", category="CORE", beta_visible=True),
    PageDefinition("startup_draft_center", "Startup Draft Center", "DRAFT", "Startup-only draft-first dashboard.", category="CORE", beta_visible=True),
    PageDefinition("draft_summary", "Draft Center", "DRAFT", "Primary rookie-draft, draft posture, and pick-strategy workspace.", category="CORE", beta_visible=True),
    PageDefinition(
        "live_draft",
        "Live Draft",
        "DRAFT",
        "Read-only Sleeper live draft assistant for active draft rooms.",
        category="CONDITIONAL",
    ),
    PageDefinition(
        "news",
        "News",
        "INTELLIGENCE",
        "Archived roster news route — Dashboard / League Intelligence owns the feed.",
        category="ARCHIVED",
    ),
    PageDefinition(
        "archetypes",
        "Archetypes",
        "INTELLIGENCE",
        "Archived standalone archetypes route — League Overview owns franchise context.",
        category="ARCHIVED",
    ),
    PageDefinition(
        "manager_tendencies",
        "Manager Tendencies",
        "INTELLIGENCE",
        "Archived standalone route — Trade Hub and League Overview own tendencies context.",
        category="ARCHIVED",
    ),
    PageDefinition("premium", "Premium", "SUPPORT", "Free and Premium plan preview for FantasyGM Lab.", category="SUPPORT", beta_visible=True),
    PageDefinition("methodology", "How We Evaluate", "SUPPORT", "How FantasyGM Lab evaluates players in league context, and how rankings differ from trade recommendations.", category="SUPPORT", beta_visible=True),
    PageDefinition("about_disclaimer", "About / Disclaimer", "SUPPORT", "Product information, recommendation limits, and general disclaimer.", category="SUPPORT", beta_visible=True),
    PageDefinition("terms", "Terms of Use", "SUPPORT", "Plain-language terms for using FantasyGM Lab.", category="SUPPORT", beta_visible=True),
    PageDefinition("privacy", "Privacy Policy", "SUPPORT", "How FantasyGM Lab may handle usernames, league context, preferences, and feedback.", category="SUPPORT", beta_visible=True),
    PageDefinition("subscription_terms", "Subscription Terms", "SUPPORT", "Auto-renewal, billing, and cancellation terms for FantasyGM Lab Premium.", category="SUPPORT", beta_visible=True),
    PageDefinition("no_affiliation", "No-Affiliation Disclaimer", "SUPPORT", "Independent-product and third-party ownership notice.", category="SUPPORT", beta_visible=True),
    PageDefinition(
        "founder_ops",
        "Founder Ops",
        "OPS",
        "Founder-only operational health and read-only diagnostics.",
        category="FOUNDER_OPS",
        beta_visible=False,
    ),
    PageDefinition(
        "founder_labs",
        "Founder Labs",
        "OPS",
        "Trusted founder/dev inventory of dormant and hidden product surfaces.",
        category="FOUNDER_LABS",
        beta_visible=False,
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
