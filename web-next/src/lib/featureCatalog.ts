import type { NavGlyphName } from "@/components/NavDestinationGlyph";
import { accentVar } from "@/lib/destinationAccent";

/**
 * "What FantasyDesk can do": the one grouped list of everything a user can
 * open, by what they want to do. Mobile twin: mobile/src/lib/featureCatalog.ts
 * (same ids, groups, names and copy; a test on each side pins them).
 *
 * Every item points at a route that exists (featureCatalog.test.ts checks the
 * app/ directory) and reuses the nav glyph and color token the same
 * destination already has in the sidebar / GM orb. `pro` mirrors a real
 * server gate (the whole feature returns premium_required to Free); `extra`
 * is a one-line note for features that are free but have a Pro part.
 */
export type FeatureGroupId = "trade" | "lineup" | "pickup" | "scout" | "league" | "keepup";

export const FEATURE_GROUPS: ReadonlyArray<{ id: FeatureGroupId; title: string }> = [
  { id: "trade", title: "Trade" },
  { id: "lineup", title: "Set your lineup" },
  { id: "pickup", title: "Pick up players" },
  { id: "scout", title: "Scout and research" },
  { id: "league", title: "Run your league" },
  { id: "keepup", title: "Keep up" },
];

export interface FeatureItem {
  id: string;
  group: FeatureGroupId;
  name: string;
  line: string;
  /** Whole feature is Pro (Free gets premium_required / a lock). */
  pro?: boolean;
  /** Free feature with a Pro part, said in words (no number). */
  extra?: string;
  /** First path segment under web-next/src/app. */
  segment: string;
  /** Route is /segment/[leagueId]; otherwise /segment. */
  leagueScoped: boolean;
  /** `#hash` on the same page. */
  hash?: string;
  glyph: NavGlyphName;
  color: string;
}

export const FEATURE_ITEMS: readonly FeatureItem[] = [
  { id: "trade-analyzer", group: "trade", name: "Trade Analyzer", line: "Grade any deal against your lineup before you send it.", segment: "trade-analyzer", leagueScoped: true, glyph: "tradeAnalyzer", color: accentVar("trade-analyzer") },
  { id: "trade-hub", group: "trade", name: "Trade ideas", line: "Offers built for your roster and what each manager needs.", extra: "Free shows a few ideas; Pro shows them all.", segment: "trade-hub", leagueScoped: true, glyph: "tradeHub", color: accentVar("trade-hub") },
  { id: "trade-finder", group: "trade", name: "Trade Finder", line: "Shop your players and picks and see what partners could pay.", pro: true, segment: "trade-finder", leagueScoped: true, glyph: "tradeFinder", color: accentVar("trade-finder") },
  { id: "trade-history", group: "trade", name: "Trade History", line: "Trades you confirmed, and how they worked out.", segment: "trade-history", leagueScoped: false, glyph: "tradeHistory", color: accentVar("trade-history") },
  { id: "community", group: "trade", name: "Community", line: "Trades other users chose to share, anonymized.", segment: "community", leagueScoped: false, glyph: "community", color: accentVar("community") },

  { id: "my-team", group: "lineup", name: "My Team", line: "Your roster, lineup, strengths and needs.", segment: "my-team", leagueScoped: true, glyph: "myTeam", color: accentVar("my-team") },
  { id: "matchup", group: "lineup", name: "Matchup", line: "This week's win odds and any swap worth making.", segment: "matchup", leagueScoped: true, glyph: "matchup", color: accentVar("matchup") },
  { id: "gm-plan", group: "lineup", name: "GM Plan", line: "Set rebuilding, competing or balanced and get a roadmap.", extra: "Pro adds focus areas.", segment: "gm-plan", leagueScoped: true, glyph: "gmPlan", color: accentVar("gm-plan") },

  { id: "waivers", group: "pickup", name: "Waivers", line: "Ranked pickups for your roster, with FAAB bid guidance.", extra: "Pro adds the FAAB shortlist and usage stats.", segment: "waivers", leagueScoped: true, glyph: "waivers", color: accentVar("waivers") },
  { id: "draft-center", group: "pickup", name: "Draft Center", line: "Your picks, draft posture and college scouting in one place.", pro: true, segment: "draft-center", leagueScoped: true, glyph: "draftCenter", color: accentVar("draft-center") },
  { id: "live-draft", group: "pickup", name: "Live Draft", line: "Pick recommendations while your Sleeper draft is running.", pro: true, segment: "live-draft", leagueScoped: true, glyph: "liveDraft", color: accentVar("live-draft") },

  { id: "players", group: "scout", name: "Players", line: "Search any player for value, stats, trends and news.", segment: "players", leagueScoped: true, glyph: "players", color: accentVar("players") },
  { id: "college-scouting", group: "scout", name: "College Scouting", line: "Grade incoming prospects and keep a watchlist.", pro: true, segment: "college-scouting", leagueScoped: false, glyph: "collegeScouting", color: accentVar("college-scouting") },
  { id: "league-rankings", group: "scout", name: "League Rankings", line: "Power rankings for every team in your league.", segment: "league-rankings", leagueScoped: true, glyph: "leagueRankings", color: accentVar("league-rankings") },

  { id: "commissioner", group: "league", name: "Commissioner", line: "League integrity, plus a trade veto calculator.", pro: true, segment: "commissioner", leagueScoped: true, glyph: "commissioner", color: accentVar("commissioner") },
  { id: "playoff-odds", group: "league", name: "Playoff Odds", line: "Every team's chance at the playoffs.", pro: true, segment: "league-rankings", leagueScoped: true, hash: "playoff-odds", glyph: "playoffOdds", color: accentVar("playoff-odds") },
  { id: "fantasy-sim", group: "league", name: "Season Outlook", line: "Your playoff odds, projected finish and title odds, from your GM Plan.", pro: true, segment: "fantasy-sim", leagueScoped: true, glyph: "games", color: accentVar("fantasy-sim") },
  { id: "games", group: "league", name: "Games", line: "Season simulator and weekly pick'em.", segment: "games", leagueScoped: true, glyph: "games", color: accentVar("games") },
  { id: "league-recaps", group: "league", name: "League Recaps", line: "Your league's weekly recap, stories, and your lineup roundup.", segment: "league-recaps", leagueScoped: true, glyph: "leagueRecaps", color: accentVar("league-recaps") },

  { id: "dashboard", group: "keepup", name: "Today", line: "Your game plan and top moves for this week.", segment: "dashboard", leagueScoped: true, glyph: "dashboard", color: accentVar("dashboard") },
  { id: "alerts", group: "keepup", name: "Alerts", line: "Injuries, news and updates on your players.", segment: "alerts", leagueScoped: true, glyph: "alerts", color: accentVar("alerts") },
  { id: "news", group: "keepup", name: "News", line: "The latest NFL news.", segment: "news", leagueScoped: false, glyph: "news", color: accentVar("news") },
  { id: "portfolio", group: "keepup", name: "Portfolio", line: "Your standing across every saved league.", pro: true, segment: "portfolio", leagueScoped: false, glyph: "portfolio", color: accentVar("portfolio") },
];

export interface FeatureLeague {
  id: string;
  name: string;
}

/** Where an item opens. League-scoped items without a league fall back to
 * Home, where a league is picked. */
export function featureHref(item: FeatureItem, league: FeatureLeague | null): string {
  if (!item.leagueScoped) return `/${item.segment}`;
  if (!league) return "/";
  const base = `/${item.segment}/${encodeURIComponent(league.id)}?name=${encodeURIComponent(league.name)}`;
  return item.hash ? `${base}#${item.hash}` : base;
}

/** The link used by Account and the first-run card. */
export function featuresPageHref(league?: FeatureLeague | null): string {
  return league ? `/features?league=${encodeURIComponent(league.id)}&name=${encodeURIComponent(league.name)}` : "/features";
}
