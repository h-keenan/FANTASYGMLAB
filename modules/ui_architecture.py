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


PLATFORM_DESTINATIONS: Tuple[PageDefinition, ...] = (
    PageDefinition("dashboard", "Dashboard", "HOME", "Primary franchise landing page.", category="CORE", beta_visible=True),
    PageDefinition("my_team", "My Team", "ROSTER", "Hands-on roster management surface.", category="CORE", beta_visible=True),
    PageDefinition("players", "Players", "ROSTER", "Canonical player rankings and player tools.", category="EXPERIMENTAL"),
    PageDefinition(
        "gm_targets",
        "GM Targets",
        "ROSTER",
        "Keep an eye on players you're considering buying, selling, adding, or monitoring.",
        category="EXPERIMENTAL",
    ),
    PageDefinition("player_detail", "Player Detail", "ROSTER", "Player profile with fit, market, trade, and news context.", category="EXPERIMENTAL"),
    PageDefinition("rankings", "League Overview", "LEAGUE", "League-wide power, franchise value, pressure signals, and team context.", category="CORE", beta_visible=True),
    PageDefinition("teams", "Teams", "LEAGUE", "League team comparison pages and partner context. My Team owns daily roster decisions.", category="EXPERIMENTAL"),
    PageDefinition("weekly_report", "Weekly Report", "LEAGUE", "Weekly highlights, movement, and transaction recap.", category="EXPERIMENTAL"),
    PageDefinition("trade_hub", "Trade Hub", "TRANSACTIONS", "Find realistic trades for your roster — ranked by fit and fairness.", category="CORE", beta_visible=True),
    PageDefinition("trade_analyzer", "Trade Analyzer", "TRANSACTIONS", "Build and test an exact trade package once you know the assets.", category="EXPERIMENTAL"),
    PageDefinition("waivers", "Waivers", "TRANSACTIONS", "Find available upgrades, injury replacements, and FAAB guidance.", category="CORE", beta_visible=True),
    PageDefinition("startup_draft_center", "Startup Draft Center", "DRAFT", "Startup-only draft-first dashboard.", category="CORE", beta_visible=True),
    PageDefinition("draft_summary", "Draft Center", "DRAFT", "Primary rookie-draft, draft posture, and pick-strategy workspace.", category="CORE", beta_visible=True),
    PageDefinition("live_draft", "Live Draft", "DRAFT", "Read-only Sleeper live draft assistant for active draft rooms.", category="EXPERIMENTAL"),
    PageDefinition("news", "News", "INTELLIGENCE", "News monitoring for the current roster.", category="EXPERIMENTAL"),
    PageDefinition("archetypes", "Archetypes", "INTELLIGENCE", "Supporting franchise archetype context for League Overview and Teams.", category="EXPERIMENTAL"),
    PageDefinition("manager_tendencies", "Manager Tendencies", "INTELLIGENCE", "Supporting manager behavior context for League Overview and Teams.", category="EXPERIMENTAL"),
    PageDefinition("premium", "Premium", "SUPPORT", "Free and Premium plan preview for FantasyGM Lab.", category="SUPPORT", beta_visible=True),
    PageDefinition("about_disclaimer", "About / Disclaimer", "SUPPORT", "Product information, recommendation limits, and general disclaimer.", category="SUPPORT", beta_visible=True),
    PageDefinition("terms", "Terms of Use", "SUPPORT", "Plain-language terms for using FantasyGM Lab.", category="SUPPORT", beta_visible=True),
    PageDefinition("privacy", "Privacy Policy", "SUPPORT", "How FantasyGM Lab may handle usernames, league context, preferences, and feedback.", category="SUPPORT", beta_visible=True),
    PageDefinition("no_affiliation", "No-Affiliation Disclaimer", "SUPPORT", "Independent-product and third-party ownership notice.", category="SUPPORT", beta_visible=True),
    PageDefinition(
        "founder_ops",
        "Founder Ops",
        "OPS",
        "Founder-only operational health and read-only diagnostics.",
        category="FOUNDER_OPS",
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


def _destination_visible(
    page: PageDefinition,
    *,
    show_experimental: bool = False,
    show_dev: bool = False,
    show_founder_ops: bool = False,
    enabled_experimental: Tuple[str, ...] = (),
) -> bool:
    if page.category == "FOUNDER_OPS":
        return bool(show_founder_ops)
    if page.category == "DEV_ONLY":
        return bool(show_dev)
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


def mobile_primary_destinations(
    startup_mode: bool,
    *,
    show_experimental: bool = False,
    show_dev: bool = False,
    show_founder_ops: bool = False,
) -> Tuple[PageDefinition, ...]:
    destination_map = {
        page.key: page
        for page in current_platform_destinations(
            startup_mode,
            show_experimental=show_experimental,
            show_dev=show_dev,
            show_founder_ops=show_founder_ops,
        )
    }
    keys = MOBILE_PRIMARY_DESTINATION_KEYS
    if startup_mode:
        keys = (
            "dashboard",
            "startup_draft_center",
            "players",
            "news",
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
) -> Tuple[PageDefinition, ...]:
    primary_keys = {
        page.key
        for page in mobile_primary_destinations(
            startup_mode,
            show_experimental=show_experimental,
            show_dev=show_dev,
            show_founder_ops=show_founder_ops,
        )
    }
    return tuple(
        page
        for page in current_platform_destinations(
            startup_mode,
            show_experimental=show_experimental,
            show_dev=show_dev,
            show_founder_ops=show_founder_ops,
        )
        if page.key not in primary_keys and page.key != "player_detail"
    )
