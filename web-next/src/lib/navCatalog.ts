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
 * Deliberately NOT listed as menu rows (each is a tab or section of a page
 * below, found through the orb search as "Page > Tab"): Trade History (Trade
 * Hub > History), College Scouting (Players > Prospects), Live Draft (Draft >
 * Live room, only while a draft is live), Alerts (Today > Alerts, a section
 * with a count badge), League Recaps (News > My League), Portfolio (Home >
 * Standing, adapter-side), Playoff Odds (League Rankings > Playoff Odds),
 * Trade Finder / Trade Analyzer (Trade Hub tabs; coridian_, 2026-10-17).
 * Product-owner-approved nav consolidation, 2026-11-16: 18 pages -> 14. Every
 * retired route still opens (it redirects to its new tab/section). Header
 * chrome rows (Home, Pro, Account, Founder Analytics) are platform-specific
 * and stay in the adapters.
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
  { key: "dashboard", label: "Today", subtitle: "Personalized insights, recommendations, and alerts", group: "core", leagueScoped: true,
    tabs: [
      { label: "Alerts", subtitle: "Injuries, news, and important updates for your roster", keywords: ["injuries", "notifications", "updates", "unread", "bell"] },
    ] },
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
  { key: "players", label: "Players", subtitle: "Search, rankings, player insights, and college prospects", group: "core", leagueScoped: true,
    tabs: [
      { label: "Prospects", subtitle: "Grade incoming college prospects", keywords: ["college", "scouting", "college scouting", "rookies", "draft class"], pro: true },
    ] },

  { key: "trade-hub", label: "Trade Hub", subtitle: "Trade ideas, the finder, and a way to grade any deal", group: "tools", leagueScoped: true,
    tabs: [
      { label: "Ideas", subtitle: "Trade ideas built for your roster", keywords: ["hub", "trade hub", "trade ideas", "trade block", "offers"] },
      { label: "Finder", subtitle: "Shop a player or pick and see what partners pay", keywords: ["trade finder", "shop", "search", "partners"], pro: true },
      { label: "Grade a trade", subtitle: "Is this offer fair? Grade any deal against your lineup", keywords: ["analyzer", "trade analyzer", "calculator", "make a trade", "grade", "evaluate", "fair", "offer"] },
      { label: "History", subtitle: "Trades you have shared and confirmed", keywords: ["trade history", "past trades"] },
    ] },
  { key: "gm-plan", label: "GM Plan", subtitle: "Your roadmap, stance, and protected/watched players", group: "tools", leagueScoped: true,
    tabs: [
      { label: "Overview", subtitle: "Stance, roadmap, and plan snapshot", keywords: ["stance", "roadmap", "rebuild", "compete"] },
      { label: "Trades", subtitle: "Trade moves your plan calls for", keywords: ["trade window"] },
      { label: "Core", subtitle: "Players your plan is built around", keywords: ["protected", "keep"] },
      { label: "Watchlist", subtitle: "Players you are targeting", keywords: ["watching", "targets", "gm targets"] },
      { label: "Season Outlook", subtitle: "GM Plan forecast: playoff odds and projected finish", keywords: ["forecast", "playoff odds", "championship odds", "title odds", "projection", "projected record", "simulation", "fantasy sim", "rest of season"], pro: true },
    ] },
  { key: "draft-center", label: "Draft", subtitle: "Your picks, draft posture, and the live draft room", group: "tools", leagueScoped: true, pro: true,
    tabs: [
      { label: "Overview", subtitle: "Draft posture and pick decisions", keywords: ["posture", "capital", "draft center"] },
      { label: "Picks", subtitle: "Every pick you own", keywords: ["draft picks", "order"] },
      { label: "Live room", subtitle: "Real-time draft room (appears while a draft is live)", keywords: ["live draft", "draft room", "on the clock", "mock"] },
    ] },
  { key: "games", label: "Games", subtitle: "Season simulator and weekly pick'em", group: "tools", leagueScoped: true,
    tabs: [
      { label: "Season Outlook", subtitle: "Games: the what-if season simulator for your real league", keywords: ["simulator", "simulation", "playoff odds", "what if"] },
      { label: "Pick'em", subtitle: "Weekly pick'em in your league", keywords: ["pickem", "picks", "weekly"] },
    ] },
  { key: "commissioner", label: "Commissioner", subtitle: "League integrity: lineups, tanking signals, trades", group: "tools", leagueScoped: true, pro: true },

  { key: "gm-game", label: "Fantasy Sim", subtitle: "Draft a team and play a full season as GM", group: "general", leagueScoped: false },
  { key: "news", label: "News", subtitle: "NFL news and your league's weekly recap", group: "general", leagueScoped: false,
    tabs: [
      { label: "NFL", subtitle: "Latest NFL news and updates", keywords: ["nfl news", "injuries", "transactions"] },
      { label: "My League", subtitle: "Weekly league recap, stories, and your lineup roundup", keywords: ["league recaps", "recaps", "recap", "history", "storylines", "roundup", "bench", "optimal lineup", "weekly roundup", "bench regret", "missed swaps"] },
    ] },
  { key: "community", label: "Community", subtitle: "Craziest trades this week, anonymized", group: "general", leagueScoped: false },
];

/** Subtitle for the "Your leagues" row (was "Home"): it is the league switcher, not account settings
 * (that is Account), so the two no longer both claim "manage account". */
export const HOME_SUBTITLE = "Switch or add a league";

/** Subtitle of the Home "Standing" section (the old Portfolio page, now part of Home). */
export const HOME_STANDING_SUBTITLE = "Your standing across every saved league";

export function navPagesIn(group: NavGroup): readonly NavCatalogPage[] {
  return NAV_PAGES.filter((page) => page.group === group);
}

export function navPage(key: string): NavCatalogPage {
  const page = NAV_PAGES.find((candidate) => candidate.key === key);
  if (!page) throw new Error(`Unknown nav page: ${key}`);
  return page;
}
