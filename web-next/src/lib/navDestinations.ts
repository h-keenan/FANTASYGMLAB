import type { NavGlyphName } from "@/components/NavDestinationGlyph";

export interface NavDestination {
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
  /** Same page as another row, scrolled to a section (a `#hash` path): it
   * never takes the "current page" highlight from its parent row. */
  anchor?: boolean;
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

/**
 * Shared source for every league-scoped + general nav destination —
 * GmOrb.tsx and DesktopSidebar.tsx both render from this one list instead
 * of each keeping its own copy (GmOrb used to be the only consumer; this
 * is that same data, pulled out so a second surface doesn't duplicate it).
 */
export function useNavDestinations(leagueId: string | null, leagueName: string) {
  const query = leagueId ? `?name=${encodeURIComponent(leagueName)}` : "";
  const id = leagueId ? encodeURIComponent(leagueId) : "";
  // `?name=...&tab=x` — the tab param the page reads on load.
  const tabPath = (segment: string, tab: string) => `/${segment}/${id}${query}&tab=${tab}`;

  const coreLeagueDestinations: NavDestination[] = leagueId
    ? [
        { label: "Dashboard", path: `/dashboard/${encodeURIComponent(leagueId)}${query}`, subtitle: "Personalized insights and recommendations", glyph: "dashboard", color: "var(--color-accent)" },
        { label: "Alerts", path: `/alerts/${encodeURIComponent(leagueId)}${query}`, subtitle: "Injuries, news, and important updates", glyph: "alerts", color: "var(--color-warning)" },
        { label: "My Team", path: `/my-team/${encodeURIComponent(leagueId)}${query}`, subtitle: "Roster, lineup, and team analysis", glyph: "myTeam", color: "var(--color-success)" },
        { label: "Matchup", path: `/matchup/${encodeURIComponent(leagueId)}${query}`, subtitle: "This week's matchup and comparison", glyph: "matchup", color: "var(--color-danger)" },
        { label: "Waivers", path: `/waivers/${encodeURIComponent(leagueId)}${query}`, subtitle: "Top adds, trends, and free agents", glyph: "waivers", color: "var(--color-opportunity)",
          tabs: [
            { label: "Recommended", path: tabPath("waivers", "recommended"), subtitle: "Ranked pickups for your roster", keywords: ["adds", "faab", "pickups"] },
            { label: "Explore", path: tabPath("waivers", "explore"), subtitle: "Browse every free agent", keywords: ["free agents", "search"] },
            { label: "Watchlist", path: tabPath("waivers", "watchlist"), subtitle: "Free agents you are tracking", keywords: ["targets", "tracking"] },
          ] },
        { label: "Players", path: `/players/${encodeURIComponent(leagueId)}${query}`, subtitle: "Search, rankings, and player insights", glyph: "players", color: "var(--color-diagnostic)" },
        { label: "League Rankings", path: `/league-rankings/${encodeURIComponent(leagueId)}${query}`, subtitle: "Power rankings across the league", glyph: "leagueRankings", color: "var(--color-premium)",
          tabs: [
            { label: "Rankings", path: `/league-rankings/${id}${query}`, subtitle: "Power rankings across the league", keywords: ["power rankings", "teams"] },
            { label: "Playoff Odds", path: `/league-rankings/${id}${query}#playoff-odds`, subtitle: "Every team's chance at the playoffs", keywords: ["playoffs", "odds", "chance", "seeding"], pro: true },
          ] },
        // Web had no nav row for this (it lived behind a button inside
        // League Rankings); the app already did. Same page, scrolled to the
        // section, so no new route.
        { label: "Playoff Odds", path: `/league-rankings/${encodeURIComponent(leagueId)}${query}#playoff-odds`, subtitle: "Every team's chance at the playoffs", glyph: "playoffOdds", color: "var(--color-premium)", pro: true, anchor: true },
      ]
    : [];

  const gmToolsDestinations: NavDestination[] = leagueId
    ? [
        {
          // Trade Finder and Trade Analyzer deliberately NOT listed as
          // separate entries here — coridian_, 2026-10-17: "trade finder and
          // trade analyzer are redundant because of the tabs on trade hub so
          // we dont need those sidemenu/gm orb menus." Both are one tab-click
          // away from this destination via TradesTabBar; their routes still
          // exist, just without a dedicated nav entry.
          label: "Trade Hub",
          path: `/trade-hub/${encodeURIComponent(leagueId)}${query}`,
          subtitle: "Trade ideas, trade finder, and trade analyzer",
          glyph: "tradeHub",
          color: "var(--color-accent)",
          tabs: [
            { label: "Hub", path: `/trade-hub/${id}${query}`, subtitle: "Trade ideas built for your roster", keywords: ["trade ideas", "trade block", "offers"] },
            { label: "Finder", path: `/trade-finder/${id}${query}`, subtitle: "Shop a player or pick and see what partners pay", keywords: ["trade finder", "shop", "search", "partners"], pro: true },
            { label: "Analyzer", path: `/trade-analyzer/${id}${query}`, subtitle: "Grade any deal against your lineup", keywords: ["trade analyzer", "calculator", "make a trade", "grade", "evaluate"] },
            { label: "History", path: "/trade-history", subtitle: "Trades you have shared and confirmed", keywords: ["trade history", "past trades"] },
          ],
        },
        {
          // Revision 20 (2026-10-18, coridian_: "What do you think about
          // merging the team situation, GM targets and GM plan into one
          // page?" / "yes I like it... same reasoning as killing the
          // Explore grid today") — GM Targets and Team Situation no
          // longer have their own nav entries; both are now always-visible
          // sections on this same page. Their routes still exist as
          // redirects for stale bookmarks/links.
          label: "GM Plan",
          path: `/gm-plan/${encodeURIComponent(leagueId)}${query}`,
          subtitle: "Your roadmap, stance, and protected/watched players",
          glyph: "gmPlan",
          color: "var(--color-success)",
          tabs: [
            { label: "Overview", path: tabPath("gm-plan", "overview"), subtitle: "Stance, roadmap, and plan snapshot", keywords: ["stance", "roadmap", "rebuild", "compete"] },
            { label: "Trades", path: tabPath("gm-plan", "trades"), subtitle: "Trade moves your plan calls for", keywords: ["trade window"] },
            { label: "Core", path: tabPath("gm-plan", "core"), subtitle: "Players your plan is built around", keywords: ["protected", "keep"] },
            { label: "Watching", path: tabPath("gm-plan", "watching"), subtitle: "Players you are targeting", keywords: ["targets", "gm targets", "watchlist"] },
          ],
        },
        { label: "Draft Center", path: `/draft-center/${encodeURIComponent(leagueId)}${query}`, subtitle: "Picks, order, and draft tools", glyph: "draftCenter", color: "var(--color-danger)", pro: true,
          tabs: [
            { label: "Overview", path: tabPath("draft-center", "overview"), subtitle: "Draft posture and pick decisions", keywords: ["posture", "capital"] },
            { label: "Picks", path: tabPath("draft-center", "picks"), subtitle: "Every pick you own", keywords: ["draft picks", "order"] },
            { label: "Scouting", path: tabPath("draft-center", "scouting"), subtitle: "Grade incoming prospects", keywords: ["college", "prospects", "rookies"] },
          ] },
        { label: "Live Draft", path: `/live-draft/${encodeURIComponent(leagueId)}${query}`, subtitle: "Real-time draft room", glyph: "liveDraft", color: "var(--color-danger)", pro: true },
        { label: "League Recaps", path: `/league-recaps/${encodeURIComponent(leagueId)}${query}`, subtitle: "Weekly league recap and stories", glyph: "leagueRecaps", color: "var(--color-information)" },
        { label: "Games", path: `/games/${encodeURIComponent(leagueId)}${query}`, subtitle: "Season simulator and weekly pick'em", glyph: "games", color: "var(--color-opportunity)",
          tabs: [
            { label: "Season Sim", path: tabPath("games", "sim"), subtitle: "Season simulator", keywords: ["simulator", "simulation", "playoff odds", "what if"] },
            { label: "Pick'em", path: tabPath("games", "pickem"), subtitle: "Weekly pick'em in your league", keywords: ["pickem", "picks", "weekly"] },
          ] },
        { label: "Commissioner", path: `/commissioner/${encodeURIComponent(leagueId)}${query}`, subtitle: "League integrity: lineups, tanking signals, trades", glyph: "commissioner" as const, color: "var(--color-diagnostic)", pro: true },
      ]
    : [];

  const generalDestinations: NavDestination[] = [
    { label: "Home", path: "/", subtitle: "Switch leagues and manage account", glyph: "home", color: "var(--color-accent)" },
    { label: "Portfolio", path: "/portfolio", subtitle: "Your standing across every saved league", glyph: "portfolio", color: "var(--color-premium)", pro: true },
    { label: "News", path: "/news", subtitle: "Latest NFL news and updates", glyph: "news", color: "var(--color-information)" },
    { label: "Trade History", path: "/trade-history", subtitle: "Trades you've shared and confirmed", glyph: "tradeHistory", color: "var(--color-diagnostic)" },
    { label: "College Scouting", path: "/college-scouting", subtitle: "Grade incoming prospects", glyph: "collegeScouting", color: "var(--color-success)", pro: true },
    {
      // Social/community layer (docs/roadmap.md), coridian_ 2026-10-19 —
      // deliberately league-independent like Portfolio/Trade History/
      // College Scouting above: the whole point is trades from OTHER
      // users' leagues, never filtered to the one currently selected.
      label: "Community",
      path: "/community",
      subtitle: "Craziest trades this week, anonymized",
      glyph: "community",
      color: "var(--color-premium)",
    },
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
  // Anchor rows (the Playoff Odds menu row) are covered by their parent's tab.
  const pages = destinations.filter((d) => !d.anchor);
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
  dashboard: "Dashboard",
  alerts: "Alerts",
  "my-team": "My Team",
  matchup: "Matchup",
  waivers: "Waivers",
  players: "Players",
  "league-rankings": "League Rankings",
  "trade-hub": "Trade Hub",
  "gm-targets": "GM Targets",
  "team-situation": "Team Situation",
  "gm-plan": "GM Plan",
  "draft-center": "Draft Center",
  "live-draft": "Live Draft",
  "league-recaps": "League Recaps",
  games: "Games",
  commissioner: "Commissioner",
  portfolio: "Portfolio",
  news: "News",
  "trade-history": "Trade History",
  "college-scouting": "College Scouting",
  community: "Community",
  "trade-analyzer": "Trade Analyzer",
  "trade-finder": "Trade Finder",
  "trade-offer": "Build an Offer",
  "player-compare": "Player Compare",
  "founder-analytics": "Founder Analytics",
  premium: "Pro",
  features: "Features",
  account: "Account",
  legal: "Legal",
};
