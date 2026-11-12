/**
 * The ONE list of FantasyDesk's navigable pages, shared by web (nav menu,
 * desktop sidebar, GM orb search, header page titles) and the app (GM orb).
 * Byte-identical twin: mobile/src/lib/navCatalog.ts (scripts/check_lib_twins.mjs
 * enforces it), so a page's label, subtitle, group, Pro flag and tabs are
 * edited once and can never drift between platforms.
 *
 * Only platform-neutral facts live here. Where a page lives (web path /
 * app route), its glyph and its accent stay in each platform's adapter
 * (web-next/src/lib/navDestinations.ts, mobile GmOrb.tsx + lib/orbTabs.ts),
 * keyed by `key`/tab label.
 *
 * Deliberately NOT listed as menu rows (each is a tab of a page below, found
 * through the orb search as "Page > Tab"): Trade History (Trade Hub > History),
 * College Scouting (Draft Center > Scouting), Playoff Odds (League Rankings >
 * Playoff Odds), Trade Finder / Trade Analyzer (Trade Hub tabs; coridian_,
 * 2026-10-17). Header chrome rows (Home, Pro, Account, Founder Analytics) are
 * platform-specific and stay in the adapters.
 *
 * Pure data, no imports, so it runs under node:test and vitest alike.
 */

export type NavGroup = "core" | "tools" | "general";

export interface NavCatalogTab {
  label: string;
  subtitle: string;
  /** Extra search terms beyond the label. */
  keywords?: readonly string[];
  /** Defaults to the page's own `pro` flag. */
  pro?: boolean;
}

export interface NavCatalogPage {
  /** Web route segment; also the stable id both adapters key on. */
  key: string;
  label: string;
  subtitle: string;
  /** core = league pages, tools = GM tools, general = account-wide pages. */
  group: NavGroup;
  /** Needs a selected league. */
  leagueScoped: boolean;
  /** Paid destination: the nav shows a gold "Pro" marker before the tap. */
  pro?: boolean;
  /** The page's own tabs, searchable in the GM orb as "Page > Tab" and never
   * rendered in the normal menu (one row per page). */
  tabs?: readonly NavCatalogTab[];
}

/* prettier-ignore */
export const NAV_PAGES: readonly NavCatalogPage[] = [
  { key: "dashboard", label: "Dashboard", subtitle: "Personalized insights and recommendations", group: "core", leagueScoped: true },
  { key: "alerts", label: "Alerts", subtitle: "Injuries, news, and important updates", group: "core", leagueScoped: true },
  { key: "my-team", label: "My Team", subtitle: "Roster, lineup, and team analysis", group: "core", leagueScoped: true },
  { key: "matchup", label: "Matchup", subtitle: "This week's matchup and comparison", group: "core", leagueScoped: true },
  { key: "waivers", label: "Waivers", subtitle: "Top adds, trends, and free agents", group: "core", leagueScoped: true,
    tabs: [
      { label: "Recommended", subtitle: "Ranked pickups for your roster", keywords: ["adds", "faab", "pickups"] },
      { label: "Explore", subtitle: "Browse every free agent", keywords: ["free agents", "search"] },
      { label: "Watchlist", subtitle: "Free agents you are tracking", keywords: ["targets", "tracking"] },
    ] },
  { key: "league-rankings", label: "League Rankings", subtitle: "Power rankings and playoff odds", group: "core", leagueScoped: true,
    tabs: [
      { label: "Rankings", subtitle: "Power rankings across the league", keywords: ["power rankings", "teams"] },
      { label: "Playoff Odds", subtitle: "Every team's chance at the playoffs", keywords: ["playoffs", "odds", "chance", "seeding"], pro: true },
    ] },
  { key: "players", label: "Players", subtitle: "Search, rankings, and player insights", group: "core", leagueScoped: true },

  { key: "trade-hub", label: "Trade Hub", subtitle: "Trade ideas, trade finder, and trade analyzer", group: "tools", leagueScoped: true,
    tabs: [
      { label: "Hub", subtitle: "Trade ideas built for your roster", keywords: ["trade ideas", "trade block", "offers"] },
      { label: "Finder", subtitle: "Shop a player or pick and see what partners pay", keywords: ["trade finder", "shop", "search", "partners"], pro: true },
      { label: "Analyzer", subtitle: "Grade any deal against your lineup", keywords: ["trade analyzer", "calculator", "make a trade", "grade", "evaluate"] },
      { label: "History", subtitle: "Trades you have shared and confirmed", keywords: ["trade history", "past trades"] },
    ] },
  { key: "gm-plan", label: "GM Plan", subtitle: "Your roadmap, stance, and protected/watched players", group: "tools", leagueScoped: true,
    tabs: [
      { label: "Overview", subtitle: "Stance, roadmap, and plan snapshot", keywords: ["stance", "roadmap", "rebuild", "compete"] },
      { label: "Trades", subtitle: "Trade moves your plan calls for", keywords: ["trade window"] },
      { label: "Core", subtitle: "Players your plan is built around", keywords: ["protected", "keep"] },
      { label: "Watching", subtitle: "Players you are targeting", keywords: ["targets", "gm targets", "watchlist"] },
      { label: "Season Outlook", subtitle: "Simulate the rest of your season", keywords: ["simulation", "simulate", "season sim", "fantasy sim", "what if", "strategy", "grade", "rest of season"], pro: true },
    ] },
  { key: "draft-center", label: "Draft Center", subtitle: "Picks, order, and draft tools", group: "tools", leagueScoped: true, pro: true,
    tabs: [
      { label: "Overview", subtitle: "Draft posture and pick decisions", keywords: ["posture", "capital"] },
      { label: "Picks", subtitle: "Every pick you own", keywords: ["draft picks", "order"] },
      { label: "Scouting", subtitle: "Grade incoming prospects", keywords: ["college", "prospects", "rookies"] },
    ] },
  { key: "live-draft", label: "Live Draft", subtitle: "Real-time draft room", group: "tools", leagueScoped: true, pro: true },
  { key: "league-recaps", label: "League Recaps", subtitle: "Weekly league recap, stories, and your lineup roundup", group: "tools", leagueScoped: true,
    tabs: [
      { label: "Roundup", subtitle: "Your lineup vs the best possible one, and what you left on the bench", keywords: ["bench", "optimal lineup", "weekly roundup", "bench regret", "missed swaps"] },
    ] },
  { key: "games", label: "Games", subtitle: "Season simulator and weekly pick'em", group: "tools", leagueScoped: true,
    tabs: [
      { label: "Season Sim", subtitle: "Season simulator", keywords: ["simulator", "simulation", "playoff odds", "what if"] },
      { label: "Pick'em", subtitle: "Weekly pick'em in your league", keywords: ["pickem", "picks", "weekly"] },
    ] },
  { key: "commissioner", label: "Commissioner", subtitle: "League integrity: lineups, tanking signals, trades", group: "tools", leagueScoped: true, pro: true },

  { key: "portfolio", label: "Portfolio", subtitle: "Your standing across every saved league", group: "general", leagueScoped: false, pro: true },
  { key: "gm-game", label: "Fantasy Sim", subtitle: "Draft a team and play a full season as GM", group: "general", leagueScoped: false },
  { key: "news", label: "News", subtitle: "Latest NFL news and updates", group: "general", leagueScoped: false },
  { key: "community", label: "Community", subtitle: "Craziest trades this week, anonymized", group: "general", leagueScoped: false },
];

/** Subtitle for the Home row: it is the league switcher, not account settings
 * (that is Account), so the two no longer both claim "manage account". */
export const HOME_SUBTITLE = "Your leagues";

export function navPagesIn(group: NavGroup): readonly NavCatalogPage[] {
  return NAV_PAGES.filter((page) => page.group === group);
}

export function navPage(key: string): NavCatalogPage {
  const page = NAV_PAGES.find((candidate) => candidate.key === key);
  if (!page) throw new Error(`Unknown nav page: ${key}`);
  return page;
}
