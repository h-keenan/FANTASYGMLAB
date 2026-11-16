import type { NavGlyphName } from "@/components/NavDestinationGlyph";
import type { CollegeInterest } from "@/lib/displayPreferences";
import { ACCENT_BY_DESTINATION } from "@/lib/destinationAccents.generated";
import { accentVar as accent } from "@/lib/destinationAccent";
import { HOME_STANDING_SUBTITLE, HOME_SUBTITLE, NAV_PAGES, navPagesIn, type NavCatalogPage } from "@/lib/navCatalog";
import { HOME_PATH } from "@/lib/retiredRoutes";
import { TERMS } from "@/lib/terms";

export interface NavDestination {
  /** The nav-catalog page key (lib/navCatalog.ts), when the row is a catalog page. */
  key?: string;
  label: string;
  path: string;
  subtitle: string;
  glyph: NavGlyphName;
  // Per-destination accent, reusing existing semantic tokens (never a new
  // hex) — coridian_, 2026-10-17: "gm orb and soon to be desktop side menu
  // glyphs need colors." Picked by rough theme, not arbitrary: Waivers
  // uses --color-opportunity (that token's literal name already matches
  // the concept), Alerts/Team Situation use --color-warning, competitive/
  // head-to-head surfaces (Matchup, Draft Center, Live Draft) use
  // --color-danger, analytics-flavored surfaces use --color-diagnostic,
  // ranking/prestige surfaces use --color-premium.
  color: string;
  /** Paid destination: the nav shows a gold "Pro" marker to anyone not on
   * Pro, so the lock is visible before the tap (UX audit 2026-11-03, 4.2). */
  pro?: boolean;
  /** The page's own tabs/sections, each searchable in the GM orb as
   * "Page > Tab" (never rendered in the normal menu, which stays one row
   * per page). Each tab opens that exact tab. */
  tabs?: NavTab[];
}

export interface NavTab {
  label: string;
  /** Full path that opens this tab (`?tab=`, `#hash`, or its own route). */
  path: string;
  subtitle: string;
  /** Extra search terms beyond the label ('scouting', 'finder', ...). */
  keywords?: string[];
  /** Defaults to the page's own `pro` flag. */
  pro?: boolean;
}

const GLYPH_BY_PAGE: Record<string, NavGlyphName> = {
  dashboard: "dashboard",
  "my-team": "myTeam",
  matchup: "matchup",
  waivers: "waivers",
  "league-rankings": "leagueRankings",
  players: "players",
  "trade-hub": "tradeHub",
  "gm-plan": "gmPlan",
  "draft-center": "draftCenter",
  games: "games",
  commissioner: "commissioner",
  "gm-game": "fantasySim",
  news: "news",
  community: "community",
};

/** Where each tab opens on web: `?tab=` on the page, its own route, or a
 * `#section`. Tabs not listed open `?tab=<lowercased label>`. */
type TabPathContext = { id: string; query: string; tabPath: (segment: string, tab: string) => string };
const TAB_PATHS: Record<string, Record<string, (c: TabPathContext) => string>> = {
  "league-rankings": {
    Rankings: ({ id, query }) => `/league-rankings/${id}${query}`,
    "Playoff Odds": ({ id, query }) => `/league-rankings/${id}${query}#playoff-odds`,
  },
  dashboard: {
    Alerts: ({ id, query }) => `/dashboard/${id}${query}#alerts`,
  },
  players: {
    Prospects: ({ tabPath }) => tabPath("players", "prospects"),
  },
  "draft-center": {
    "Live room": ({ tabPath }) => tabPath("draft-center", "live"),
  },
  news: {
    NFL: () => "/news",
    // News is account-wide: the league rides along as `?league=` (the shell keeps the league context from it).
    "My League": ({ id, query }) => (id ? `/news?tab=league&league=${id}${query.replace("?", "&")}` : "/news?tab=league"),
  },
  "trade-hub": {
    Ideas: ({ id, query }) => `/trade-hub/${id}${query}`,
    Finder: ({ id, query }) => `/trade-finder/${id}${query}`,
    "Grade a trade": ({ id, query }) => `/trade-analyzer/${id}${query}`,
    History: ({ id, query }) => (id ? `/trade-history?league=${id}${query.replace("?", "&")}` : "/trade-history"),
  },
  "gm-plan": {
    // The tab's id stays `watching` (stable URLs); only the label is Watchlist.
    Watchlist: ({ tabPath }) => tabPath("gm-plan", "watching"),
    // Its own route (the sim page), reached from GM Plan; no top-level menu row.
    "Season Outlook": ({ id, query }) => `/fantasy-sim/${id}${query}`,
  },
  games: {
    "Season Outlook": ({ tabPath }) => tabPath("games", "sim"),
    "Pick'em": ({ tabPath }) => tabPath("games", "pickem"),
  },
};

/**
 * Every league-scoped + general nav destination, built from the one catalog
 * shared with the app (lib/navCatalog.ts) plus this platform's paths, glyphs
 * and accents. GmOrb.tsx and DesktopSidebar.tsx both render from this list.
 */
export function useNavDestinations(
  leagueId: string | null,
  leagueName: string,
  // "off" (Account > College football) hides the College Scouting tab from
  // the menu search; the page itself still works by URL. Matches the app,
  // which only surfaces College Scouting once the user opts in. Callers pass
  // the preference in, so this stays callable outside a React tree.
  collegeInterest: CollegeInterest = "on",
) {
  const query = leagueId ? `?name=${encodeURIComponent(leagueName)}` : "";
  const id = leagueId ? encodeURIComponent(leagueId) : "";
  // `?name=...&tab=x` — the tab param the page reads on load.
  const tabPath = (segment: string, tab: string) => `/${segment}/${id}${query}&tab=${tab}`;
  const context: TabPathContext = { id, query, tabPath };

  const build = (page: NavCatalogPage): NavDestination => ({
    key: page.key,
    label: page.label,
    path: page.leagueScoped ? `/${page.key}/${id}${query}` : `/${page.key}`,
    subtitle: page.subtitle,
    glyph: GLYPH_BY_PAGE[page.key],
    // The shared accent map is keyed by catalog id; a page whose label was renamed (Draft Center -> Draft) keeps its id.
    color: accent(ACCENT_BY_DESTINATION[page.key] ? page.key : page.label),
    pro: page.pro,
    tabs: page.tabs
      ?.filter((tab) => !(collegeInterest === "off" && page.key === "players" && tab.label === "Prospects"))
      .map((tab) => ({
        label: tab.label,
        path: (TAB_PATHS[page.key]?.[tab.label] ?? (() => tabPath(page.key, tab.label.toLowerCase())))(context),
        subtitle: tab.subtitle,
        keywords: tab.keywords ? [...tab.keywords] : undefined,
        pro: tab.pro,
      })),
  });

  const coreLeagueDestinations: NavDestination[] = leagueId ? navPagesIn("core").map(build) : [];
  const gmToolsDestinations: NavDestination[] = leagueId ? navPagesIn("tools").map(build) : [];

  const generalDestinations: NavDestination[] = [
    // The league switcher; Account (below) owns settings.
    {
      label: TERMS.yourLeagues,
      path: HOME_PATH,
      subtitle: HOME_SUBTITLE,
      glyph: "home",
      color: "var(--color-accent)",
      // Portfolio became a section of Home (2026-11-16 nav consolidation): your standing across every league.
      tabs: [{ label: "Standing", path: `${HOME_PATH}#standing`, subtitle: HOME_STANDING_SUBTITLE, keywords: ["portfolio", "every league", "all leagues", "exposure"], pro: true }],
    },
    ...navPagesIn("general").map(build),
  ];

  // Account-wide chrome that used to be reachable only through the header
  // MENU (Account) or from inside an upsell card (Pro). Not league-scoped.
  const accountDestinations: NavDestination[] = [
    { label: "Pro", path: "/premium", subtitle: "Plans, trial, and billing", glyph: "pro", color: "var(--color-premium)" },
    { label: "Account", path: "/account", subtitle: "Sign-in, preferences, and settings", glyph: "account", color: "var(--color-text-secondary)" },
  ];

  return { coreLeagueDestinations, gmToolsDestinations, generalDestinations, accountDestinations };
}

/** One search hit: a `NavDestination`-shaped row, so the orb renders page
 * rows and tab rows with the same component. Tab rows read "Page > Tab". */
export function searchNavDestinations(destinations: NavDestination[], rawQuery: string): NavDestination[] {
  const tokens = rawQuery.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return [];
  const matches = (text: string) => {
    const hay = text.toLowerCase();
    return tokens.every((token) => hay.includes(token));
  };
  const pages = destinations;
  const pagePaths = new Set(pages.filter((d) => matches(`${d.label} ${d.subtitle}`)).map((d) => d.path));
  const out: NavDestination[] = [];
  const seen = new Set<string>();
  for (const page of pages) {
    if (pagePaths.has(page.path) && !seen.has(page.path)) {
      seen.add(page.path);
      out.push({ ...page, tabs: undefined });
    }
    for (const tab of page.tabs ?? []) {
      if (seen.has(tab.path) || pagePaths.has(tab.path)) continue;
      if (!matches(`${page.label} ${tab.label} ${(tab.keywords ?? []).join(" ")}`)) continue;
      seen.add(tab.path);
      out.push({ ...page, label: `${page.label} > ${tab.label}`, subtitle: tab.subtitle, path: tab.path, pro: tab.pro ?? page.pro, tabs: undefined });
    }
  }
  return out;
}

/**
 * Founder-only nav entry, shared by GmOrb (phone width) and DesktopSidebar
 * so neither can drift. Callers must gate on `isFounderSession`.
 */
export const FOUNDER_DESTINATION: NavDestination = {
  label: "Founder Analytics",
  path: "/founder-analytics",
  subtitle: "Internal product analytics",
  glyph: "founderAnalytics",
  color: "var(--color-diagnostic)",
};

/** Same server-issued app_metadata claim GET /v1/founder/analytics enforces
 * (UX gate only; the backend 403 is the real boundary). */
export function isFounderSession(
  session: { user?: { app_metadata?: Record<string, unknown> } | null } | null | undefined,
): boolean {
  return session?.user?.app_metadata?.founder_ops === true;
}

/** First path segment -> page label, for Header's persistent page title
 * (coridian_, 2026-10-18: "where it says dashboard... should go up into
 * the header... so you can always see what page you're on"). Derived from
 * the same destinations above rather than a second hand-maintained list,
 * plus the handful of real routes that aren't in the GM orb/sidebar nav
 * (Trade Finder/Trade Analyzer/Player Compare — reachable via Trade Hub's
 * own tabs, not a dedicated nav entry; Premium; Legal). */
export const PAGE_TITLE_BY_SEGMENT: Record<string, string> = {
  ...Object.fromEntries(NAV_PAGES.map((page) => [page.key, page.label])),
  // Routes that are real pages but not menu rows (reached as tabs of a menu
  // page, or from a link): see navCatalog.ts for the tab homes.
  "fantasy-sim": "Season Outlook",
  "trade-history": "Trade History",
  // Retired nav rows that now redirect into a tab/section of another page (2026-11-16 consolidation).
  alerts: "Today",
  leagues: "Your leagues",
  "live-draft": "Draft",
  portfolio: "Your leagues",
  "league-recaps": "News",
  "college-scouting": "Players",
  "trade-analyzer": "Trade Analyzer",
  "trade-finder": "Trade Finder",
  "trade-offer": "Build an Offer",
  "player-compare": "Player Compare",
  "founder-analytics": "Founder Analytics",
  premium: "Pro",
  features: "Features",
  account: "Account",
  legal: "Legal",
  // Retired pages that only redirect to GM Plan (old bookmarks/links).
  "gm-targets": "GM Plan",
  "team-situation": "GM Plan",
};
