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
}

/**
 * Shared source for every league-scoped + general nav destination —
 * GmOrb.tsx and DesktopSidebar.tsx both render from this one list instead
 * of each keeping its own copy (GmOrb used to be the only consumer; this
 * is that same data, pulled out so a second surface doesn't duplicate it).
 */
export function useNavDestinations(leagueId: string | null, leagueName: string) {
  const query = leagueId ? `?name=${encodeURIComponent(leagueName)}` : "";

  const coreLeagueDestinations: NavDestination[] = leagueId
    ? [
        { label: "Dashboard", path: `/dashboard/${encodeURIComponent(leagueId)}${query}`, subtitle: "Personalized insights and recommendations", glyph: "dashboard", color: "var(--color-accent)" },
        { label: "Alerts", path: `/alerts/${encodeURIComponent(leagueId)}${query}`, subtitle: "Injuries, news, and important updates", glyph: "alerts", color: "var(--color-warning)" },
        { label: "My Team", path: `/my-team/${encodeURIComponent(leagueId)}${query}`, subtitle: "Roster, lineup, and team analysis", glyph: "myTeam", color: "var(--color-success)" },
        { label: "Matchup", path: `/matchup/${encodeURIComponent(leagueId)}${query}`, subtitle: "This week's matchup and comparison", glyph: "matchup", color: "var(--color-danger)" },
        { label: "Waivers", path: `/waivers/${encodeURIComponent(leagueId)}${query}`, subtitle: "Top adds, trends, and free agents", glyph: "waivers", color: "var(--color-opportunity)" },
        { label: "Players", path: `/players/${encodeURIComponent(leagueId)}${query}`, subtitle: "Search, rankings, and player insights", glyph: "players", color: "var(--color-diagnostic)" },
        { label: "League Rankings", path: `/league-rankings/${encodeURIComponent(leagueId)}${query}`, subtitle: "Power rankings across the league", glyph: "leagueRankings", color: "var(--color-premium)" },
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
        },
        { label: "GM Targets", path: `/gm-targets/${encodeURIComponent(leagueId)}${query}`, subtitle: "Your saved watchlist", glyph: "gmTargets", color: "var(--color-premium)" },
        { label: "Team Situation", path: `/team-situation/${encodeURIComponent(leagueId)}${query}`, subtitle: "Declare your rebuild/compete stance", glyph: "teamSituation", color: "var(--color-warning)" },
        { label: "GM Plan", path: `/gm-plan/${encodeURIComponent(leagueId)}${query}`, subtitle: "Your season-long roadmap", glyph: "gmPlan", color: "var(--color-success)" },
        { label: "Draft Center", path: `/draft-center/${encodeURIComponent(leagueId)}${query}`, subtitle: "Picks, order, and draft tools", glyph: "draftCenter", color: "var(--color-danger)" },
        { label: "Live Draft", path: `/live-draft/${encodeURIComponent(leagueId)}${query}`, subtitle: "Real-time draft room", glyph: "liveDraft", color: "var(--color-danger)" },
        { label: "League Recaps", path: `/league-recaps/${encodeURIComponent(leagueId)}${query}`, subtitle: "Weekly league recap and stories", glyph: "leagueRecaps", color: "var(--color-information)" },
      ]
    : [];

  const generalDestinations: NavDestination[] = [
    { label: "Home", path: "/", subtitle: "Switch leagues and manage account", glyph: "home", color: "var(--color-accent)" },
    { label: "Portfolio", path: "/portfolio", subtitle: "Your standing across every saved league", glyph: "portfolio", color: "var(--color-premium)" },
    { label: "News", path: "/news", subtitle: "Latest NFL news and updates", glyph: "news", color: "var(--color-information)" },
    { label: "Trade History", path: "/trade-history", subtitle: "Trades you've shared and confirmed", glyph: "tradeHistory", color: "var(--color-diagnostic)" },
    { label: "College Scouting", path: "/college-scouting", subtitle: "Grade incoming prospects", glyph: "collegeScouting", color: "var(--color-success)" },
  ];

  return { coreLeagueDestinations, gmToolsDestinations, generalDestinations };
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
  portfolio: "Portfolio",
  news: "News",
  "trade-history": "Trade History",
  "college-scouting": "College Scouting",
  "trade-analyzer": "Trade Analyzer",
  "trade-finder": "Trade Finder",
  "player-compare": "Player Compare",
  premium: "Premium",
  legal: "Legal",
};
