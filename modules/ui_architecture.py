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


@dataclass(frozen=True)
class FutureNavGroup:
    key: str
    label: str
    destinations: Tuple[str, ...]
    description: str


@dataclass(frozen=True)
class SectionDefinition:
    key: str
    label: str
    current_helpers: Tuple[str, ...]
    target_surfaces: Tuple[str, ...]
    purpose: str
    merge_target: str
    notes: str = ""


@dataclass(frozen=True)
class DuplicateSectionAudit:
    key: str
    duplicate_surfaces: Tuple[str, ...]
    reason: str
    target_merge: str


@dataclass(frozen=True)
class MigrationPhase:
    phase: str
    title: str
    goals: Tuple[str, ...]
    affected_surfaces: Tuple[str, ...]
    notes: str = ""


CURRENT_PAGE_REGISTRY: Tuple[PageDefinition, ...] = (
    PageDefinition("home_dashboard", "Home Dashboard", "HOME", "Primary executive landing page for the current franchise."),
    PageDefinition("players", "All Players", "ROSTER", "Canonical player rankings and scanning view."),
    PageDefinition("free_agents", "Waivers & FAAB", "TRANSACTIONS", "Waivers, best adds, and FAAB helper."),
    PageDefinition("my_team", "My Team", "ROSTER", "Hands-on roster management surface."),
    PageDefinition("startup_draft_center", "Startup Draft Center", "DRAFT", "Startup-only draft-first dashboard."),
    PageDefinition("league_overview", "League Overview", "LEAGUE", "League standings, rankings, team pages, and draft capital."),
    PageDefinition("weekly_report", "Weekly League Report", "LEAGUE", "Weekly highlights, movement, trends, and transaction recap."),
    PageDefinition("news", "My Players' News", "INTELLIGENCE", "News monitoring for the current roster."),
    PageDefinition("trade_ideas", "Trade Ideas", "TRANSACTIONS", "Team-wide trade generation."),
    PageDefinition("player_trade_hub", "Player Trade Hub", "TRANSACTIONS", "Player-centric trade discovery."),
    PageDefinition("trade_analyzer", "Trade Analyzer", "TRANSACTIONS", "Manual package building and fit analysis."),
    PageDefinition("player_explainer", "Player Explainer", "ROSTER", "Narrative explanation of the current valuation pipeline."),
)


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
    PageDefinition("player_detail", "Player Detail", "ROSTER", "Premium player profile and team-fit view.", category="EXPERIMENTAL"),
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


FUTURE_NAV_GROUPS: Tuple[FutureNavGroup, ...] = (
    FutureNavGroup("home", "HOME", ("team_dashboard",), "Primary franchise dashboard and landing experience."),
    FutureNavGroup("roster", "ROSTER", ("my_team", "players"), "Roster management, player browsing, and evaluation."),
    FutureNavGroup("league", "LEAGUE", ("league_overview", "weekly_report", "team_pages"), "League-wide context, trends, and roster comparisons."),
    FutureNavGroup("transactions", "TRANSACTIONS", ("trade_hub", "trade_ideas", "trade_analyzer", "waivers"), "Trades, waivers, and transaction decision tools."),
    FutureNavGroup("draft", "DRAFT", ("startup_draft_center", "draft_summary", "rookie_fit_scores"), "Startup and rookie-draft workflow surfaces, including draft posture and partner discovery."),
    FutureNavGroup("intelligence", "INTELLIGENCE", ("archetypes", "manager_tendencies", "news", "future_analytics"), "Scouting, behavior patterns, and advanced league context."),
)


REUSABLE_SECTION_DEFINITIONS: Tuple[SectionDefinition, ...] = (
    SectionDefinition(
        "hero_header",
        "Hero Header",
        ("app hero markup", "render_section_header"),
        ("home", "league", "transactions", "draft", "intelligence"),
        "Top-of-surface framing with title, kicker, and one-line context.",
        "single_header_system",
    ),
    SectionDefinition(
        "franchise_card",
        "Franchise Card",
        ("render_team_identity_card", "render_league_team_page_header"),
        ("home", "league_team_pages"),
        "Owner, team, identity, strategy, and core franchise framing.",
        "franchise_identity_component",
    ),
    SectionDefinition(
        "team_snapshot",
        "Team Snapshot",
        ("render_summary_tiles",),
        ("home", "league_team_pages"),
        "Power rank, franchise rank, strategy, age, starters, bench, and draft capital overview.",
        "snapshot_tile_system",
    ),
    SectionDefinition(
        "metric_tiles",
        "Metric Tiles",
        ("render_summary_tiles", "st.metric"),
        ("home", "league", "weekly_report", "draft"),
        "Compact metric clusters used across dashboards.",
        "summary_tile_system",
    ),
    SectionDefinition(
        "intelligence_cards",
        "Intelligence Cards",
        ("render_analysis_cards",),
        ("home", "league", "weekly_report", "intelligence"),
        "Strengths, weaknesses, risks, notes, and contextual diagnostics.",
        "intelligence_card_system",
    ),
    SectionDefinition(
        "trade_cards",
        "Trade Cards",
        ("render_trade_idea_card", "render_player_trade_hub_card"),
        ("transactions",),
        "Standardized transaction idea presentation with package context and rationale.",
        "trade_card_system",
    ),
    SectionDefinition(
        "player_cards",
        "Player Cards",
        ("render_free_agent_cards",),
        ("roster", "transactions", "draft"),
        "Portable player presentation with tier, injury, and opportunity context.",
        "player_card_system",
        notes="Most roster surfaces still rely on tables rather than cards.",
    ),
    SectionDefinition(
        "draft_cards",
        "Draft Cards",
        ("render_draft_capital_dashboard", "render_startup_draft_center"),
        ("draft", "league"),
        "Draft capital, startup board, and future-pick ownership framing.",
        "draft_surface_system",
    ),
)


DUPLICATE_SECTION_AUDIT: Tuple[DuplicateSectionAudit, ...] = (
    DuplicateSectionAudit(
        "team_identity",
        ("My Team", "League Team Pages"),
        "Both surfaces render a top-level franchise identity summary with overlapping strategy framing.",
        "franchise_card",
    ),
    DuplicateSectionAudit(
        "snapshot_metrics",
        ("My Team", "League Overview", "Weekly League Report"),
        "Power, franchise, draft, and health context are presented in multiple slightly different metric clusters.",
        "team_snapshot",
    ),
    DuplicateSectionAudit(
        "draft_context",
        ("League Overview Draft Capital", "Startup Draft Center"),
        "Draft-specific summary framing exists in more than one place with different card composition.",
        "draft_cards",
    ),
    DuplicateSectionAudit(
        "trade_recommendation_cards",
        ("Trade Ideas", "Player Trade Hub"),
        "Both use near-identical asset and rationale rendering with only small mode-specific differences.",
        "trade_cards",
    ),
    DuplicateSectionAudit(
        "intelligence_notes",
        ("My Team", "Weekly League Report", "League Overview"),
        "Strength, weakness, risk, and logic-note cards are repeated with separate assembly logic.",
        "intelligence_cards",
    ),
)


MIGRATION_PHASES: Tuple[MigrationPhase, ...] = (
    MigrationPhase(
        "Phase 1",
        "Navigation Registry",
        (
            "Centralize current page inventory.",
            "Define future nav groups without changing live IA.",
            "Stop hard-coding top-level tab labels in app.py.",
        ),
        ("All top-level tabs",),
    ),
    MigrationPhase(
        "Phase 2",
        "Section System",
        (
            "Unify duplicated snapshot and intelligence sections.",
            "Standardize hero/header, metric tiles, and trade card composition.",
        ),
        ("My Team", "League Overview", "Trade Ideas", "Player Trade Hub", "Weekly League Report"),
    ),
    MigrationPhase(
        "Phase 3",
        "Destination Consolidation",
        (
            "Group current tabs into future nav families.",
            "Promote Team Dashboard as the persistent home surface.",
            "Split League Overview internals into clearer league/team/draft destinations.",
        ),
        ("Home", "Roster", "League", "Transactions", "Draft", "Intelligence"),
    ),
    MigrationPhase(
        "Phase 4",
        "Visual Overhaul",
        (
            "Replace current tabs with a 2K-style hub and sub-navigation.",
            "Move tables into richer card/board shells where appropriate.",
            "Keep football logic unchanged while reskinning the UI shell.",
        ),
        ("Entire app shell",),
        notes="No football or valuation changes required in this phase.",
    ),
)


def current_primary_tabs(startup_mode: bool) -> Tuple[PageDefinition, ...]:
    labels = {
        "my_team": "Startup Draft Center" if startup_mode else "My Team",
    }
    tab_order = (
        "home_dashboard",
        "players",
        "free_agents",
        "my_team",
        "league_overview",
        "weekly_report",
        "news",
        "trade_ideas",
        "player_trade_hub",
        "trade_analyzer",
        "player_explainer",
    )
    registry = {page.key: page for page in CURRENT_PAGE_REGISTRY}
    tabs = []
    for key in tab_order:
        page = registry[key]
        tabs.append(
            PageDefinition(
                key=page.key,
                label=labels.get(page.key, page.label),
                group=page.group,
                purpose=page.purpose,
                notes=page.notes,
            )
        )
    return tuple(tabs)


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
